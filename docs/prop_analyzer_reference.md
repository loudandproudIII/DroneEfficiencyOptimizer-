# Propeller Analyzer - Technical Reference

## Overview

The Propeller Analyzer module provides performance calculations for APC propellers using interpolated data from manufacturer-published performance tests. This document details the calculation methods, data formats, variable naming conventions, and API specifications.

---

## Table of Contents

1. [Units Convention](#units-convention)
2. [Variable Naming](#variable-naming)
3. [Data Sources & Formats](#data-sources--formats)
4. [Calculation Methods](#calculation-methods)
5. [API Reference](#api-reference)
6. [Examples](#examples)

---

## Units Convention

All calculations use SI units consistently:

| Parameter | Unit | Symbol | Description |
|-----------|------|--------|-------------|
| Airspeed | meters/second | m/s | Forward velocity of aircraft |
| RPM | revolutions/minute | RPM | Propeller rotational speed |
| Thrust | Newtons | N | Force produced by propeller |
| Power | Watts | W | Mechanical shaft power required |
| Efficiency | dimensionless | η | Ratio (0-1 typical range) |

---

## Variable Naming

### Input Variables

| Variable | Type | Description | Valid Range |
|----------|------|-------------|-------------|
| `prop` | string | Propeller identifier (e.g., "7x7E", "10x5") | See available props |
| `v_ms` | float | Airspeed in meters per second | 0 to ~80 m/s (prop dependent) |
| `rpm` | float | Rotational speed | ~1000 to ~30000 (prop dependent) |
| `thrust_required` | float | Target thrust in Newtons | Must be within prop capability |

### Output Variables

| Variable | Type | Description |
|----------|------|-------------|
| `thrust` | float | Calculated thrust in Newtons |
| `power` | float | Calculated power in Watts |
| `efficiency` | float | Propulsive efficiency (η = T·V / P) |

### Propeller Naming Convention

Propeller identifiers follow APC's naming format:

```
[Diameter]x[Pitch][Suffix]

Examples:
  7x7E    → 7" diameter, 7" pitch, Electric
  10x5    → 10" diameter, 5" pitch, Standard
  12x6E   → 12" diameter, 6" pitch, Electric
  10x45MR → 10" diameter, 4.5" pitch, Multi-Rotor
```

Common suffixes:
- `E` - Electric
- `MR` - Multi-Rotor
- `SF` - Slow Flyer
- `WE` - Wide blade Electric
- `F` - Folding

---

## Data Sources & Formats

### Source Data

Performance data originates from APC Propellers:
- Website: https://www.apcprop.com/technical-information/performance-data/
- Format: DAT files containing wind tunnel test results
- Conditions: Standard atmospheric conditions (sea level, ~15°C)

### Database File (APC-Prop-DB.pkl)

Pandas DataFrame with columns:

| Column | Type | Description |
|--------|------|-------------|
| `PROP` | string | Propeller identifier |
| `RPM` | int | Test RPM value |
| `V_ms` | float | Airspeed in m/s |
| `Thrust_N` | float | Measured thrust in Newtons |
| `PWR_W` | float | Measured power in Watts |
| `Torque_Nm` | float | Measured torque in Newton-meters |
| `Ct` | float | Thrust coefficient |
| `Cp` | float | Power coefficient |
| `eta` | float | Measured efficiency |

### Interpolator Files

Each propeller has two scipy `LinearNDInterpolator` objects stored as pickle files:

```
{prop}_thrust_interpolator.pkl  → f(V_ms, RPM) → Thrust_N
{prop}_power_interpolator.pkl   → f(V_ms, RPM) → Power_W
```

The interpolators enable continuous queries within the tested envelope.

---

## Calculation Methods

### 1. Thrust from RPM and Airspeed

**Method:** Bilinear interpolation on (V, RPM) grid

**Function:** `get_thrust_from_rpm_speed(prop, v_ms, rpm)`

**Algorithm:**
```
1. Load thrust interpolator for specified prop
2. Query: Thrust = interpolator(v_ms, rpm)
3. Return thrust in Newtons (or -99 if out of bounds)
```

**Physical basis:** Thrust decreases with increasing airspeed at constant RPM due to reduced angle of attack on blade elements.

---

### 2. Power from RPM and Airspeed

**Method:** Bilinear interpolation on (V, RPM) grid

**Function:** `get_power_from_rpm_speed(prop, v_ms, rpm)`

**Algorithm:**
```
1. Load power interpolator for specified prop
2. Query: Power = interpolator(v_ms, rpm)
3. Return power in Watts (or -99 if out of bounds)
```

**Physical basis:** Power is primarily a function of RPM (approximately P ∝ RPM³) with minor airspeed dependence.

---

### 3. Power from Thrust Requirement

**Method:** Root-finding with Brent's method

**Function:** `get_power_from_thrust_speed(prop, thrust_required, v_ms)`

**Algorithm:**
```
1. Load thrust interpolator
2. Get RPM bounds [RPM_min, RPM_max] from interpolator
3. Check if thrust_required ≤ max achievable thrust
4. Define objective: f(RPM) = Thrust(v_ms, RPM) - thrust_required
5. Solve f(RPM) = 0 using scipy.optimize.root_scalar
   - Method: Brent's method (bracketed)
   - Tolerance: 0.1% relative
6. Calculate power at solution RPM
7. Return (power, rpm) tuple
```

**Convergence:** Brent's method guarantees convergence for continuous functions with a valid bracket.

---

### 4. Propeller Efficiency

**Method:** Direct calculation from thrust and power

**Function:** `get_efficiency(prop, v_ms, rpm)`

**Formula:**
```
η = (Thrust × Velocity) / Power
η = (T × V) / P
```

**Where:**
- η = propeller efficiency (dimensionless)
- T = thrust (N)
- V = airspeed (m/s)
- P = shaft power (W)

**Notes:**
- At V = 0 (hover/static), efficiency = 0 by definition
- Maximum efficiency typically 0.7-0.85 for well-matched props
- Efficiency varies with advance ratio J = V / (n × D)

---

## API Reference

### PropAnalyzer Class

```python
from src.prop_analyzer import PropAnalyzer

analyzer = PropAnalyzer(config=None)
```

#### Methods

##### `get_thrust_from_rpm_speed(prop, v_ms, rpm, verbose=False)`

Calculate thrust for given operating conditions.

| Parameter | Type | Description |
|-----------|------|-------------|
| `prop` | str | Propeller identifier |
| `v_ms` | float | Airspeed (m/s) |
| `rpm` | float | Rotational speed (RPM) |
| `verbose` | bool | Print warnings if out of bounds |

**Returns:** `float` - Thrust in Newtons (-99 if out of bounds)

---

##### `get_power_from_rpm_speed(prop, v_ms, rpm, verbose=False)`

Calculate power for given operating conditions.

| Parameter | Type | Description |
|-----------|------|-------------|
| `prop` | str | Propeller identifier |
| `v_ms` | float | Airspeed (m/s) |
| `rpm` | float | Rotational speed (RPM) |
| `verbose` | bool | Print warnings if out of bounds |

**Returns:** `float` - Power in Watts (-99 if out of bounds)

---

##### `get_power_from_thrust_speed(prop, thrust_required, v_ms, return_rpm=False)`

Find power needed to achieve target thrust.

| Parameter | Type | Description |
|-----------|------|-------------|
| `prop` | str | Propeller identifier |
| `thrust_required` | float | Target thrust (N) |
| `v_ms` | float | Airspeed (m/s) |
| `return_rpm` | bool | Also return calculated RPM |

**Returns:**
- If `return_rpm=False`: `float` - Power in Watts
- If `return_rpm=True`: `tuple(float, int)` - (Power, RPM)
- Returns `None` if thrust exceeds propeller capability

---

##### `get_efficiency(prop, v_ms, rpm)`

Calculate propeller efficiency.

| Parameter | Type | Description |
|-----------|------|-------------|
| `prop` | str | Propeller identifier |
| `v_ms` | float | Airspeed (m/s) |
| `rpm` | float | Rotational speed (RPM) |

**Returns:** `float` - Efficiency (0-1 range typical)

---

##### `get_prop_operating_envelope(prop)`

Get valid operating range for a propeller.

**Returns:** `dict` with keys:
- `min_speed`: Minimum tested airspeed (m/s)
- `max_speed`: Maximum tested airspeed (m/s)
- `min_rpm`: Minimum tested RPM
- `max_rpm`: Maximum tested RPM

---

##### `list_available_propellers()`

Get list of all available propeller models.

**Returns:** `list[str]` - Sorted list of propeller identifiers

---

### PropPlotter Class

```python
from src.prop_analyzer import PropPlotter

plotter = PropPlotter(config=None)
```

#### Methods

| Method | Description |
|--------|-------------|
| `plot_thrust_curves(prop)` | Plot thrust vs airspeed for all RPM values |
| `plot_power_curves(prop)` | Plot power vs airspeed for all RPM values |
| `plot_max_thrust(prop)` | Plot maximum thrust envelope |
| `plot_efficiency_map(prop)` | Plot efficiency vs airspeed |
| `compare_props_max_thrust(props)` | Compare multiple propellers |

---

## Examples

### Basic Thrust/Power Calculation

```python
from src.prop_analyzer import PropAnalyzer

analyzer = PropAnalyzer()

# Operating conditions
prop = "7x7E"
airspeed = 30.0  # m/s
rpm = 22500

# Calculate performance
thrust = analyzer.get_thrust_from_rpm_speed(prop, airspeed, rpm)
power = analyzer.get_power_from_rpm_speed(prop, airspeed, rpm)
efficiency = analyzer.get_efficiency(prop, airspeed, rpm)

print(f"Thrust: {thrust:.2f} N")
print(f"Power: {power:.0f} W")
print(f"Efficiency: {efficiency:.3f}")
```

**Output:**
```
Thrust: 24.30 N
Power: 1229 W
Efficiency: 0.593
```

---

### Finding Power for Thrust Requirement

```python
from src.prop_analyzer import PropAnalyzer

analyzer = PropAnalyzer()

# Design requirement
prop = "7x7E"
required_thrust = 25.0  # N
cruise_speed = 30.0     # m/s

# Find required power and RPM
result = analyzer.get_power_from_thrust_speed(
    prop,
    required_thrust,
    cruise_speed,
    return_rpm=True
)

if result:
    power, rpm = result
    print(f"To achieve {required_thrust} N at {cruise_speed} m/s:")
    print(f"  Required RPM: {rpm}")
    print(f"  Required Power: {power:.0f} W")
else:
    print("Thrust requirement exceeds propeller capability")
```

**Output:**
```
To achieve 25.0 N at 30.0 m/s:
  Required RPM: 22847
  Required Power: 1274 W
```

---

### Plotting Performance Curves

```python
from src.prop_analyzer import PropPlotter
import matplotlib.pyplot as plt

plotter = PropPlotter()

# Generate plots
plotter.plot_thrust_curves("7x7E")
plt.savefig("thrust_curves.png")

plotter.plot_max_thrust("7x7E")
plt.savefig("max_thrust.png")

plt.show()
```

---

## Error Handling

### Out-of-Bounds Queries

When querying outside the tested envelope:
- Interpolators return `-99.0`
- Set `verbose=True` to see warnings

```python
# Query outside envelope
thrust = analyzer.get_thrust_from_rpm_speed("7x7E", 100, 50000, verbose=True)
# Warning: Parameters are outside the propeller's tested envelope.
# Returns: -99.0
```

### Exceeding Propeller Limits

When thrust requirement exceeds capability:

```python
result = analyzer.get_power_from_thrust_speed("7x7E", 100, 30)
# Prints: Thrust request (100.0 N) exceeds propeller limits!
# Returns: None
```

---

## Limitations

1. **Atmospheric Conditions:** Data assumes standard sea-level conditions. Altitude correction not included.

2. **Interpolation Accuracy:** Results between test points are interpolated; accuracy depends on data density.

3. **Dynamic Effects:** Static/steady-state data only. Does not account for transient behavior.

4. **Installation Effects:** Data is for isolated propeller. Fuselage/wing interference not modeled.

5. **Blade Damage:** Assumes undamaged propeller in specified configuration.

---

## References

- APC Propellers Technical Data: https://www.apcprop.com/technical-information/
- Propeller Theory: McCormick, B.W. "Aerodynamics, Aeronautics, and Flight Mechanics"
- SciPy Interpolation: https://docs.scipy.org/doc/scipy/reference/interpolate.html
