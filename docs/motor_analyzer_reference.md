# Motor Analyzer - Technical Reference

## Overview

The Motor Analyzer module provides performance calculations for brushless DC (BLDC) motors using an equivalent circuit model with temperature and RPM-dependent corrections.

---

## Table of Contents

1. [Units Convention](#units-convention)
2. [Motor Model Theory](#motor-model-theory)
3. [Variable Naming](#variable-naming)
4. [API Reference](#api-reference)
5. [Calculation Methods](#calculation-methods)
6. [Integration with Prop Analyzer](#integration-with-prop-analyzer)
7. [Examples](#examples)

---

## Units Convention

All calculations use SI units:

| Parameter | Unit | Symbol | Description |
|-----------|------|--------|-------------|
| Voltage | Volts | V | Supply voltage |
| Current | Amperes | A | Motor current draw |
| Power | Watts | W | Electrical or mechanical power |
| Torque | Newton-meters | Nm | Shaft torque |
| RPM | rev/minute | RPM | Rotational speed |
| Resistance | Ohms | Ω | Winding resistance |
| Temperature | Celsius | °C | Winding temperature |
| Efficiency | dimensionless | η | Ratio (0-1) |

---

## Motor Model Theory

### Equivalent Circuit

The BLDC motor is modeled as:

```
V_supply ──┬── Rm ──┬── V_bemf
           │        │
         I_total   Load
```

### Key Equations

**Back-EMF:**
```
V_bemf = RPM / Kv
```

**Current:**
```
I_total = (V_supply - V_bemf) / Rm
```

**Torque-producing current:**
```
I_torque = I_total - I0
```

**Torque:**
```
Torque = I_torque × Kt

where: Kt = 30 / (π × Kv)  [Nm/A]
```

### Temperature Correction

Copper winding resistance increases with temperature:

```
Rm(T) = Rm_cold × (1 + 0.00393 × (T - T_ref))
```

At 80°C operating temperature, resistance is ~21.7% higher than at 25°C.

### RPM-Dependent No-Load Current

Iron losses scale with rotational speed:

```
I0(RPM) = I0_ref × (RPM / RPM_ref)^α

where α = 0.5 (default)
```

---

## Variable Naming

### Motor Parameters

| Variable | Type | Unit | Description |
|----------|------|------|-------------|
| `kv` | float | RPM/V | Motor velocity constant |
| `rm_cold` | float | Ω | Phase-to-phase resistance at 25°C |
| `i0_ref` | float | A | No-load current at reference RPM |
| `i0_rpm_ref` | float | RPM | Reference RPM for I0 measurement |
| `i_max` | float | A | Maximum continuous current |
| `p_max` | float | W | Maximum continuous power |

### Operating Inputs

| Variable | Type | Unit | Description |
|----------|------|------|-------------|
| `v_supply` | float | V | Battery/ESC voltage |
| `rpm` | float | RPM | Operating speed |
| `torque_load` | float | Nm | Load torque requirement |
| `winding_temp` | float | °C | Winding temperature |

### Outputs

| Variable | Type | Unit | Description |
|----------|------|------|-------------|
| `current` | float | A | Motor current |
| `p_elec` | float | W | Electrical input power |
| `p_mech` | float | W | Mechanical output power |
| `torque` | float | Nm | Output torque |
| `efficiency` | float | 0-1 | Motor efficiency |
| `p_loss_copper` | float | W | I²R copper losses |
| `p_loss_iron` | float | W | Iron/core losses |

---

## API Reference

### MotorAnalyzer Class

```python
from src.motor_analyzer import MotorAnalyzer

analyzer = MotorAnalyzer()
```

#### Motor Management

| Method | Description |
|--------|-------------|
| `add_motor(motor_id, params)` | Add motor to database |
| `get_motor(motor_id)` | Get motor parameters |
| `list_available_motors()` | List all motor IDs |

#### Core Calculations

##### `get_state_at_rpm(motor_id, v_supply, rpm, winding_temp=80)`

Calculate motor state when RPM is known.

**Returns:** `dict` with keys:
- `rpm`, `current`, `torque`, `p_elec`, `p_mech`
- `efficiency`, `p_loss_copper`, `p_loss_iron`
- `v_bemf`, `i_torque`, `valid`

##### `solve_operating_point(motor_id, v_supply, torque_load, winding_temp=80)`

Find equilibrium RPM for given load torque (iterative solver).

**Returns:** Same dict as `get_state_at_rpm`, or `None` if no solution.

##### `get_torque_from_current(motor_id, current, rpm)`

Calculate torque for given current and RPM.

**Returns:** `float` - Torque in Nm

##### `get_max_torque_at_rpm(motor_id, rpm, winding_temp=80)`

Get maximum torque at given RPM (at I_max).

**Returns:** `float` - Max torque in Nm

##### `generate_efficiency_map(motor_id, v_supply, ...)`

Generate 2D efficiency map for visualization.

**Returns:** `dict` with `rpm_values`, `torque_values`, `efficiency_map`

---

## Calculation Methods

### 1. State at Known RPM

**Method:** Direct calculation

```
1. Calculate Rm at temperature
2. V_bemf = RPM / Kv
3. I_total = (V_supply - V_bemf) / Rm
4. I0 = I0_ref × (RPM / RPM_ref)^0.5
5. I_torque = I_total - I0
6. Torque = I_torque × Kt
7. P_mech = Torque × ω
8. Efficiency = P_mech / P_elec
```

### 2. Solve Operating Point

**Method:** Iterative Newton-Raphson style solver

```
1. Initial guess: RPM = Kv × V × 0.8
2. Loop until convergence:
   a. Calculate motor torque at current RPM
   b. Compare with load torque
   c. Adjust RPM based on torque error
   d. Apply damping for stability
3. Return final state
```

Typical convergence: 5-15 iterations for 0.1% accuracy.

---

## Integration with Prop Analyzer

### Motor → Prop (Find Equilibrium)

Given motor voltage and throttle, find where motor torque equals prop torque:

```python
from src.motor_analyzer import MotorAnalyzer
from src.prop_analyzer import PropAnalyzer

motor = MotorAnalyzer()
prop = PropAnalyzer()

v_motor = 22.2 * 0.7  # 70% throttle on 6S

# Iterate to find equilibrium
rpm = 8000  # initial guess
for _ in range(20):
    # Prop torque at this RPM
    power = prop.get_power_from_rpm_speed("10x5", 15.0, rpm)
    torque_prop = power / (rpm * 3.14159 / 30)

    # Motor state at this torque
    state = motor.solve_operating_point("MyMotor", v_motor, torque_prop)

    if abs(state['rpm'] - rpm) < 1:
        break
    rpm = state['rpm']

thrust = prop.get_thrust_from_rpm_speed("10x5", 15.0, rpm)
```

### Prop → Motor (Thrust Requirement)

Given thrust requirement, find motor operating state:

```python
# Get prop requirements
power, rpm = prop.get_power_from_thrust_speed("10x5", 15.0, 25.0, return_rpm=True)

# Find motor state at that RPM
state = motor.get_state_at_rpm("MyMotor", 22.2, rpm)

print(f"Motor current: {state['current']:.1f} A")
print(f"Motor efficiency: {state['efficiency']:.1%}")
```

---

## Examples

### Basic Motor Calculation

```python
from src.motor_analyzer import MotorAnalyzer

analyzer = MotorAnalyzer()

# Use built-in motor or add custom
state = analyzer.get_state_at_rpm(
    "Scorpion SII-3014-830",
    v_supply=22.2,
    rpm=8000,
    winding_temp=80
)

print(f"Current: {state['current']:.1f} A")
print(f"Torque: {state['torque']*1000:.1f} mNm")
print(f"Power: {state['p_mech']:.0f} W")
print(f"Efficiency: {state['efficiency']:.1%}")
```

### Add Custom Motor

```python
analyzer.add_motor("My Custom Motor", {
    "kv": 1000,
    "rm_cold": 0.025,
    "i0_ref": 1.5,
    "i0_rpm_ref": 10000,
    "i_max": 40,
    "p_max": 800
})

state = analyzer.solve_operating_point(
    "My Custom Motor",
    v_supply=14.8,
    torque_load=0.3
)
```

### Generate Efficiency Map

```python
from src.motor_analyzer import MotorPlotter

plotter = MotorPlotter()
plotter.plot_efficiency_map("Scorpion SII-3014-830", v_supply=22.2)
plt.savefig("motor_efficiency.png")
```

---

## Motor Database Format

Motors are stored in `motor_database.json`:

```json
{
  "motors": {
    "Motor Name": {
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

---

## Error Handling

### Operating Point Not Found

```python
state = analyzer.solve_operating_point(motor_id, v_supply, torque_load)
if state is None:
    print("No valid operating point - torque exceeds capability")
```

### Current Limit Warning

```python
motor = analyzer.get_motor(motor_id)
if state['current'] > motor.i_max:
    print(f"Warning: Current {state['current']:.1f}A exceeds rating")
```

---

## Limitations

1. **Linear Magnetics:** Assumes no saturation below rated current
2. **Thermal:** Winding temp must be estimated; no transient thermal model
3. **ESC Effects:** Assumes ideal voltage source; PWM losses not modeled
4. **Timing:** Fixed motor timing assumed
5. **Manufacturing Variation:** ±5-10% from nominal specs typical

---

## References

- Hanselman, D. "Brushless Permanent Magnet Motor Design"
- Hughes, A. "Electric Motors and Drives"
- Motor manufacturer datasheets
