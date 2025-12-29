# Motor Analyzer - Technical Specification

## Overview

The Motor Analyzer module provides performance calculations for brushless DC motors using an equivalent circuit model with temperature and RPM-dependent corrections. Designed to operate standalone or integrate with the Propeller Analyzer module for complete powertrain modeling.

**Target Accuracy:** ±5% on efficiency across operating range, tighter at full load.

---

## Table of Contents

1. [Units Convention](#units-convention)
2. [Variable Naming](#variable-naming)
3. [Motor Model Theory](#motor-model-theory)
4. [Data Sources & Formats](#data-sources--formats)
5. [Calculation Methods](#calculation-methods)
6. [API Reference](#api-reference)
7. [Integration with Prop Analyzer](#integration-with-prop-analyzer)
8. [Examples](#examples)

---

## Units Convention

All calculations use SI units, consistent with Prop Analyzer:

| Parameter | Unit | Symbol | Description |
|-----------|------|--------|-------------|
| Voltage | Volts | V | Supply voltage to motor |
| Current | Amperes | A | Motor current draw |
| Power (electrical) | Watts | W | Input power (V × I) |
| Power (mechanical) | Watts | W | Shaft output power |
| Torque | Newton-meters | Nm | Shaft torque |
| RPM | revolutions/minute | RPM | Rotational speed |
| Resistance | Ohms | Ω | Winding resistance |
| Temperature | Celsius | °C | Winding temperature |
| Efficiency | dimensionless | η | Ratio (0-1) |

---

## Variable Naming

### Motor Parameters (from datasheet or measurement)

| Variable | Type | Unit | Description |
|----------|------|------|-------------|
| `kv` | float | RPM/V | Motor velocity constant |
| `rm_cold` | float | Ω | Phase-to-phase resistance at reference temp |
| `i0_ref` | float | A | No-load current at reference RPM |
| `i0_rpm_ref` | float | RPM | RPM where I0 was measured |
| `temp_ref` | float | °C | Temperature where Rm was measured (default 25) |
| `i_max` | float | A | Maximum continuous current rating |
| `p_max` | float | W | Maximum continuous power rating |

### Operating Inputs

| Variable | Type | Unit | Description |
|----------|------|------|-------------|
| `v_supply` | float | V | Battery/ESC supply voltage |
| `rpm` | float | RPM | Operating RPM (from load or specified) |
| `torque_load` | float | Nm | Load torque requirement |
| `winding_temp` | float | °C | Estimated winding temperature |
| `throttle` | float | 0-1 | Throttle position (fraction of v_supply) |

### Outputs

| Variable | Type | Unit | Description |
|----------|------|------|-------------|
| `current` | float | A | Total motor current |
| `p_elec` | float | W | Electrical input power |
| `p_mech` | float | W | Mechanical output power |
| `torque` | float | Nm | Output torque |
| `efficiency` | float | 0-1 | Motor efficiency |
| `p_loss_copper` | float | W | I²R losses |
| `p_loss_iron` | float | W | Core losses (estimated) |

---

## Motor Model Theory

### Equivalent Circuit

The brushless motor is modeled as:

```
V_supply ──┬── Rm ──┬── V_bemf
           │        │
         I_total   Load
```

Where:
- `V_bemf = RPM / Kv` (back-EMF)
- `I_total = (V_supply - V_bemf) / Rm`
- `I_torque = I_total - I0` (current producing torque)
- `Torque = I_torque × Kt` where `Kt = 30 / (π × Kv)` [Nm/A]

### Temperature Correction

Copper winding resistance increases with temperature:

```
Rm(T) = Rm_cold × (1 + 0.00393 × (T - T_ref))
```

Coefficient 0.00393 /°C is standard for copper. At typical operating temps (80-100°C), resistance increases 20-30% from cold measurements.

### RPM-Dependent No-Load Current

Iron losses (hysteresis + eddy currents) scale with frequency:

```
I0(RPM) = I0_ref × (RPM / RPM_ref)^α
```

Where α typically ranges 0.3-0.7 depending on lamination quality. Default α = 0.5 provides reasonable accuracy for most outrunners.

### Saturation Correction (Optional)

At high currents, magnetic saturation reduces effective Kt:

```
Kt_eff = Kt × (1 - k_sat × (I / I_rated)²)
```

Where k_sat ≈ 0.03-0.08 for typical motors. Only significant above rated current.

---

## Data Sources & Formats

### Motor Database File (motor_database.json)

```json
{
  "motors": {
    "Scorpion SII-3014-830": {
      "kv": 830,
      "rm_cold": 0.028,
      "i0_ref": 1.8,
      "i0_rpm_ref": 8300,
      "temp_ref": 25,
      "i_max": 65,
      "p_max": 1400,
      "mass_g": 152,
      "poles": 14,
      "source": "manufacturer"
    }
  }
}
```

### Measured Motor File (Optional)

For motors with dyno data, store measured points:

```json
{
  "motor_id": "Scorpion SII-3014-830",
  "test_date": "2024-01-15",
  "test_points": [
    {"rpm": 5000, "torque_Nm": 0.5, "current_A": 12.3, "efficiency": 0.82},
    {"rpm": 8000, "torque_Nm": 0.8, "current_A": 25.1, "efficiency": 0.79}
  ]
}
```

Measured data enables model calibration and validation.

---

## Calculation Methods

### 1. Operating Point from Voltage and Load Torque

**Method:** Iterative solve (RPM and I0 are coupled)

**Function:** `solve_operating_point(v_supply, torque_load, winding_temp)`

**Algorithm:**
```
1. Initial guess: RPM = Kv × V_supply × 0.8
2. Iterate until convergence (max 20 iterations):
   a. Calculate Rm at winding_temp
   b. Calculate V_bemf = RPM / Kv
   c. Calculate I_total = (V_supply - V_bemf) / Rm
   d. Calculate I0 at current RPM
   e. Calculate I_torque = I_total - I0
   f. Calculate torque_motor = I_torque × Kt
   g. Update RPM from torque balance with load
   h. Check convergence: |RPM_new - RPM| < 1
3. Calculate efficiency = P_mech / P_elec
4. Return operating state dict
```

**Convergence:** Typically 5-10 iterations for 0.1% accuracy.

---

### 2. Current and Power from RPM (Known Speed)

**Method:** Direct calculation when RPM is fixed by load

**Function:** `get_current_at_rpm(v_supply, rpm, winding_temp)`

**Algorithm:**
```
1. Rm = Rm_cold × (1 + 0.00393 × (winding_temp - temp_ref))
2. V_bemf = rpm / Kv
3. I_total = (V_supply - V_bemf) / Rm
4. Return I_total
```

**Use case:** When prop analyzer has already determined required RPM.

---

### 3. Torque from Current

**Method:** Direct calculation

**Function:** `get_torque_from_current(current, rpm)`

**Algorithm:**
```
1. I0 = I0_ref × (rpm / i0_rpm_ref)^0.5
2. I_torque = current - I0
3. Torque = I_torque × Kt
4. Return torque in Nm
```

---

### 4. Maximum Torque at RPM

**Method:** Calculate torque at maximum current

**Function:** `get_max_torque_at_rpm(rpm, winding_temp)`

**Algorithm:**
```
1. I0 = I0_ref × (rpm / i0_rpm_ref)^0.5
2. I_torque_max = I_max - I0
3. Torque_max = I_torque_max × Kt
4. Return torque_max
```

---

### 5. Efficiency Map Generation

**Method:** Sweep RPM and torque, calculate efficiency at each point

**Function:** `generate_efficiency_map(rpm_range, torque_range, v_supply, winding_temp)`

**Output:** 2D array of efficiency values for contour plotting

---

### 6. Thermal Estimate (Simplified)

**Method:** Steady-state thermal resistance model

**Function:** `estimate_winding_temp(p_loss, ambient_temp, thermal_resistance)`

**Algorithm:**
```
1. P_loss = I²R + (I0 × V_bemf)  # Copper + Iron
2. T_winding = T_ambient + P_loss × R_thermal
3. Return T_winding
```

Note: Thermal resistance (°C/W) is motor and mounting dependent. Typical range 0.5-2.0 °C/W for well-cooled outrunners.

---

## API Reference

### MotorAnalyzer Class

```python
from src.motor_analyzer import MotorAnalyzer

analyzer = MotorAnalyzer(config=None)
```

#### Motor Management Methods

##### `load_motor(motor_id)`
Load motor parameters from database.

##### `add_motor(motor_id, params_dict)`
Add custom motor to runtime database.

##### `list_available_motors()`
Returns list of motor IDs in database.

---

#### Core Calculation Methods

##### `solve_operating_point(motor_id, v_supply, torque_load, winding_temp=80)`

Find equilibrium operating point for given load.

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `motor_id` | str | Motor identifier |
| `v_supply` | float | Supply voltage (V) |
| `torque_load` | float | Load torque (Nm) |
| `winding_temp` | float | Winding temperature (°C) |

**Returns:** `dict` with keys:
- `rpm`: Equilibrium RPM
- `current`: Motor current (A)
- `torque`: Output torque (Nm)
- `p_elec`: Electrical power (W)
- `p_mech`: Mechanical power (W)
- `efficiency`: Motor efficiency
- `p_loss_copper`: Copper losses (W)
- `p_loss_iron`: Iron losses (W)

---

##### `get_state_at_rpm(motor_id, v_supply, rpm, winding_temp=80)`

Calculate motor state when RPM is known (e.g., from prop load curve).

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `motor_id` | str | Motor identifier |
| `v_supply` | float | Supply voltage (V) |
| `rpm` | float | Operating RPM |
| `winding_temp` | float | Winding temperature (°C) |

**Returns:** `dict` with same keys as `solve_operating_point`

---

##### `get_torque_from_current(motor_id, current, rpm)`

Calculate torque for given current draw.

**Returns:** `float` - Torque in Nm

---

##### `get_max_torque_at_rpm(motor_id, rpm, winding_temp=80)`

Calculate maximum available torque at given RPM.

**Returns:** `float` - Maximum torque in Nm

---

##### `get_efficiency(motor_id, rpm, torque, winding_temp=80)`

Calculate efficiency at specific operating point.

**Returns:** `float` - Efficiency (0-1)

---

#### Analysis Methods

##### `generate_efficiency_map(motor_id, v_supply, rpm_range, torque_range, winding_temp=80)`

Generate 2D efficiency map for visualization.

**Returns:** `dict` with:
- `rpm_values`: 1D array
- `torque_values`: 1D array
- `efficiency_map`: 2D array
- `valid_mask`: 2D boolean array (within motor limits)

---

##### `get_motor_limits(motor_id, v_supply)`

Get operating envelope for motor at given voltage.

**Returns:** `dict` with:
- `rpm_no_load`: No-load RPM
- `torque_stall`: Stall torque (theoretical)
- `i_max`: Maximum current
- `p_max`: Maximum power

---

### MotorPlotter Class

```python
from src.motor_analyzer import MotorPlotter

plotter = MotorPlotter(config=None)
```

#### Methods

| Method | Description |
|--------|-------------|
| `plot_efficiency_map(motor_id, v_supply)` | Contour plot of efficiency vs RPM/torque |
| `plot_torque_speed_curve(motor_id, v_supply)` | Torque vs RPM at max current |
| `plot_power_curve(motor_id, v_supply)` | Power vs RPM |
| `plot_current_vs_torque(motor_id, rpm)` | Current draw vs output torque |
| `compare_motors(motor_ids, v_supply)` | Overlay multiple motors |

---

## Integration with Prop Analyzer

### Upstream: Motor Drives Prop Analysis

Given motor and throttle, find prop operating point:

```python
from src.motor_analyzer import MotorAnalyzer
from src.prop_analyzer import PropAnalyzer

motor = MotorAnalyzer()
prop = PropAnalyzer()

# Motor parameters
motor_id = "Scorpion SII-3014-830"
v_supply = 22.2  # 6S
throttle = 0.8
v_motor = v_supply * throttle

# Iterate to find equilibrium (motor torque = prop torque)
prop_id = "10x5E"
v_ms = 25.0  # cruise speed

rpm_guess = 830 * v_motor * 0.85
for _ in range(20):
    # Prop torque at this RPM
    power_prop = prop.get_power_from_rpm_speed(prop_id, v_ms, rpm_guess)
    torque_prop = power_prop / (rpm_guess * 3.14159 / 30)
    
    # Motor state at this torque
    state = motor.solve_operating_point(motor_id, v_motor, torque_prop)
    
    if abs(state['rpm'] - rpm_guess) < 1:
        break
    rpm_guess = state['rpm']

print(f"Equilibrium: {state['rpm']:.0f} RPM, {state['current']:.1f} A")
```

### Downstream: Prop Requirement Drives Motor Analysis

Given thrust requirement, find motor operating state:

```python
# Prop determines required power and RPM
thrust_required = 15.0  # N
v_ms = 30.0  # m/s

power_req, rpm_req = prop.get_power_from_thrust_speed(
    prop_id, thrust_required, v_ms, return_rpm=True
)

# Motor state at that operating point
state = motor.get_state_at_rpm(motor_id, v_supply, rpm_req)

print(f"For {thrust_required} N thrust at {v_ms} m/s:")
print(f"  Motor: {state['current']:.1f} A, {state['efficiency']:.1%} efficient")
print(f"  System power: {state['p_elec']:.0f} W electrical")
```

### Combined Powertrain Class (Optional)

```python
from src.powertrain import Powertrain

pt = Powertrain(motor_id="Scorpion SII-3014-830", prop_id="10x5E")

# Solve complete system
result = pt.solve_cruise(v_supply=22.2, v_ms=30.0, thrust_required=15.0)

print(f"Throttle: {result['throttle']:.1%}")
print(f"Current: {result['current']:.1f} A")
print(f"Motor efficiency: {result['motor_eta']:.1%}")
print(f"Prop efficiency: {result['prop_eta']:.1%}")
print(f"System efficiency: {result['system_eta']:.1%}")
```

---

## Examples

### Basic Motor Calculation

```python
from src.motor_analyzer import MotorAnalyzer

motor = MotorAnalyzer()

# Define motor (or load from database)
motor.add_motor("Test Motor", {
    "kv": 1000,
    "rm_cold": 0.020,
    "i0_ref": 2.0,
    "i0_rpm_ref": 10000,
    "i_max": 50,
    "p_max": 800
})

# Operating conditions
v_supply = 14.8  # 4S
torque_load = 0.3  # Nm

state = motor.solve_operating_point("Test Motor", v_supply, torque_load)

print(f"RPM: {state['rpm']:.0f}")
print(f"Current: {state['current']:.1f} A")
print(f"Efficiency: {state['efficiency']:.1%}")
print(f"Mech Power: {state['p_mech']:.0f} W")
```

---

### Efficiency Map Generation

```python
from src.motor_analyzer import MotorAnalyzer, MotorPlotter
import numpy as np

motor = MotorAnalyzer()
plotter = MotorPlotter()

motor_id = "Scorpion SII-3014-830"
v_supply = 22.2

# Generate and plot efficiency map
plotter.plot_efficiency_map(motor_id, v_supply)
plt.savefig("motor_efficiency_map.png")
```

---

## Parameter Measurement Guide

### Measuring Rm (Winding Resistance)

1. Use 4-wire measurement to eliminate lead resistance
2. Measure phase-to-phase (any two motor wires)
3. Record ambient temperature at time of measurement
4. For delta-wound motors: Rm_phase = 1.5 × Rm_measured
5. For wye-wound motors: Rm_phase = 0.5 × Rm_measured

### Measuring I0 (No-Load Current)

1. Run motor with no load (prop removed)
2. Use known voltage, record current and RPM
3. Repeat at 2-3 voltage levels
4. I0 should scale with RPM^0.5 approximately
5. If not, fit your own exponent

### Measuring Kv

1. Spin motor with drill or as generator
2. Measure back-EMF voltage and RPM
3. Kv = RPM / V_bemf (phase-to-phase, peak-to-peak / 2)
4. Or trust manufacturer spec (usually within 5%)

---

## Error Handling

### Invalid Operating Points

```python
state = motor.solve_operating_point(motor_id, v_supply, torque_load)

if state is None:
    print("Operating point outside motor capability")
elif state['current'] > motor.get_motor_params(motor_id)['i_max']:
    print(f"Warning: Current {state['current']:.1f} A exceeds rating")
```

### Temperature Warnings

```python
if state['p_loss_copper'] + state['p_loss_iron'] > p_max * 0.3:
    print("Warning: High losses may cause thermal issues")
```

---

## Limitations

1. **Model Simplifications:** Assumes linear magnetics below saturation. High-current accuracy depends on saturation correction.

2. **Thermal Coupling:** Winding temperature must be estimated or measured. Model does not include transient thermal behavior.

3. **ESC Effects:** Assumes ideal voltage source. PWM losses and ESC resistance not modeled.

4. **Timing/Advance:** Fixed timing assumed. Motors with adjustable timing will vary from predictions.

5. **Manufacturing Variation:** Individual motors vary ±5-10% from nominal specs.

---

## References

- Hanselman, D. "Brushless Permanent Magnet Motor Design" (2nd ed.)
- Hughes, A. "Electric Motors and Drives" (4th ed.)
- Hendershot & Miller, "Design of Brushless Permanent-Magnet Machines"
