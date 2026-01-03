# Battery Pack Calculator Module - Claude Code Build Prompt

## Project Overview

Build a physics-accurate battery pack calculator for drone/UAV applications. This module will be standalone initially but designed for easy integration into a larger drone analysis engine that includes motor, prop, and airframe drag analyzers.

## Technical Requirements

### 1. Core Calculations

#### 1.1 Pack Configuration
- Support series configurations: 1S through 12S
- Support parallel configurations: 1P through 8P
- Calculate total nominal voltage, capacity (mAh/Wh), and energy (kWh)
- Calculate total pack mass including:
  - Cell mass
  - Interconnect mass estimate (nickel strip or wire, solder)
  - Shrink wrap/enclosure estimate (optional toggle)

#### 1.2 Physical Dimensions & Geometry

**Cylindrical Cells (18650, 21700):**
- Model cells as true cylinders with manufacturer dimensions
- Calculate pack bounding box for common arrangements:
  - Inline (all cells parallel to each other, side by side)
  - Staggered/nested (honeycomb pattern to minimize voids)
  - Stacked layers for parallel groups
- Account for cell spacing (default 0.5mm gap for thermal/assembly tolerance)
- Calculate void volume percentage
- Report overall L x W x H dimensions

**Pouch/Lipo Cells:**
- Model as rectangular prisms
- Stack directly for series (account for tabs)
- Side-by-side or stacked for parallel
- Include tab protrusion in bounding box (typical 10-15mm beyond cell body)
- Account for swelling margin (5-10% thickness increase recommended)

#### 1.3 Center of Gravity (COG)
- Calculate geometric COG of pack based on arrangement
- Assume uniform density within each cell
- Output COG as (x, y, z) from a defined corner origin
- Support user-defined cell arrangement patterns (future: custom layouts)

### 2. Cell Library

Create a comprehensive cell database with the following structure. All data must be sourced from manufacturer datasheets or reputable testing (e.g., Mooch, Battery Mooch 18650 tests).

#### 2.1 21700 Cells (High Priority)

| Cell | Manufacturer | Capacity (mAh) | Nominal V | Max Cont. Discharge (A) | DC IR (mΩ) | Mass (g) | Dimensions (mm) |
|------|--------------|----------------|-----------|-------------------------|------------|----------|-----------------|
| P50B | Molicel | 5000 | 3.6 | 9.8A (35A pulse) | ~18 | 70 | 21.7 x 70.15 |
| P45B | Molicel | 4500 | 3.6 | 45A | ~12 | 67 | 21.7 x 70.15 |
| M50LT | LG | 5000 | 3.6 | 7.3A | ~22 | 69 | 21.7 x 70.15 |
| 50S | Samsung | 5000 | 3.6 | 25A | ~14 | 68.5 | 21.7 x 70.15 |
| 50E | Samsung | 5000 | 3.6 | 9.8A | ~20 | 68.9 | 21.7 x 70.15 |
| 40T | Samsung | 4000 | 3.6 | 35A | ~10 | 67 | 21.7 x 70.15 |
| RS50 | Vapcell | 5000 | 3.6 | 30A | ~13 | 70 | 21.7 x 70.15 |
| 50PL | Vapcell | 5000 | 3.6 | 15A | ~16 | 69 | 21.7 x 70.15 |

#### 2.2 18650 Cells

| Cell | Manufacturer | Capacity (mAh) | Nominal V | Max Cont. Discharge (A) | DC IR (mΩ) | Mass (g) | Dimensions (mm) |
|------|--------------|----------------|-----------|-------------------------|------------|----------|-----------------|
| P28B | Molicel | 2800 | 3.6 | 28A | ~12 | 48 | 18.5 x 65.2 |
| P30B | Molicel | 3000 | 3.6 | 18A | ~15 | 47 | 18.5 x 65.2 |
| 30Q | Samsung | 3000 | 3.6 | 15A | ~18 | 48 | 18.5 x 65.2 |
| HG2 | LG | 3000 | 3.6 | 20A | ~15 | 47 | 18.5 x 65.2 |
| VTC6 | Sony/Murata | 3000 | 3.6 | 15A | ~13 | 46.5 | 18.5 x 65.2 |
| 25R | Samsung | 2500 | 3.6 | 20A | ~14 | 45 | 18.5 x 65.2 |

#### 2.3 LiPo Pouch Cells

Model a parametric LiPo system since there are hundreds of variants. Key parameters:

| Capacity (mAh) | C-Rating | Typical Mass (g) | Typical Dimensions (mm) | IR Estimate (mΩ) |
|----------------|----------|------------------|-------------------------|------------------|
| 450 | 75-95C | 12-14 | 55 x 30 x 6 | ~3.5 |
| 650 | 75-95C | 17-20 | 60 x 32 x 7 | ~2.8 |
| 850 | 75-95C | 22-26 | 68 x 34 x 8 | ~2.2 |
| 1000 | 75-95C | 26-30 | 72 x 35 x 8.5 | ~2.0 |
| 1300 | 45-75C | 35-42 | 78 x 36 x 10 | ~2.5 |
| 1500 | 45-75C | 42-50 | 82 x 38 x 11 | ~2.2 |
| 1800 | 30-65C | 50-60 | 90 x 40 x 12 | ~2.0 |
| 2200 | 30-50C | 60-75 | 105 x 34 x 15 | ~1.8 |
| 3000 | 30-50C | 85-100 | 115 x 38 x 18 | ~1.5 |
| 4000 | 25-45C | 110-130 | 130 x 42 x 22 | ~1.2 |
| 5000 | 25-45C | 135-160 | 145 x 45 x 25 | ~1.0 |
| 6000 | 20-35C | 165-195 | 155 x 48 x 28 | ~0.9 |
| 8000 | 20-35C | 220-260 | 170 x 52 x 32 | ~0.7 |
| 10000 | 15-30C | 280-330 | 185 x 58 x 38 | ~0.6 |

**LiPo IR Estimation Formula:**
```
IR_cell (mΩ) ≈ (1000 / capacity_mAh) * (100 / C_rating) * k
where k ≈ 35-50 depending on cell quality
```

#### 2.4 Cell Data Structure

```python
@dataclass
class CellSpec:
    name: str
    manufacturer: str
    chemistry: str  # "NMC", "LFP", "LiPo", "NCA"
    form_factor: str  # "21700", "18650", "pouch"
    capacity_mah: float
    nominal_voltage: float  # typically 3.6-3.7V for Li-ion
    max_voltage: float  # 4.2V typical
    min_voltage: float  # 2.5-3.0V typical
    max_continuous_discharge_a: float
    peak_discharge_a: float  # pulse rating
    dc_ir_mohm: float  # at 25°C, 50% SOC
    mass_g: float
    diameter_mm: float | None  # for cylindrical
    length_mm: float | None  # for cylindrical
    width_mm: float | None  # for pouch
    height_mm: float | None  # for pouch
    thickness_mm: float | None  # for pouch
    temp_coefficient_ir: float  # IR multiplier per °C deviation from 25°C
    thermal_resistance_c_per_w: float  # cell to ambient
    specific_heat_j_per_g_c: float  # ~1.0 J/g°C for Li-ion
```

### 3. Electrical Modeling

#### 3.1 Voltage Sag Calculation

**Simple Model (Ohmic):**
```
V_loaded = V_oc - (I_total / P) * IR_cell
```
Where:
- V_oc = Open circuit voltage (function of SOC)
- I_total = Total current draw
- P = Parallel count
- IR_cell = Cell internal resistance

**SOC to OCV Relationship (typical Li-ion NMC):**
```python
def soc_to_ocv(soc_percent: float) -> float:
    """
    Approximate SOC to OCV for NMC chemistry.
    soc_percent: 0-100
    returns: voltage (V)
    """
    # Polynomial fit or lookup table
    # Typical values:
    # 100% -> 4.20V
    # 90%  -> 4.10V
    # 80%  -> 4.00V
    # 70%  -> 3.92V
    # 60%  -> 3.85V
    # 50%  -> 3.80V
    # 40%  -> 3.75V
    # 30%  -> 3.70V
    # 20%  -> 3.60V
    # 10%  -> 3.45V
    # 0%   -> 3.00V (cutoff)
```

#### 3.2 Internal Resistance vs Temperature

IR increases at low temps, decreases at high temps (up to a point):
```python
def ir_at_temp(ir_25c: float, temp_c: float) -> float:
    """
    IR temperature compensation.
    Typical coefficient: ~0.5-1% per °C from reference.
    """
    temp_coeff = 0.007  # 0.7% per °C
    return ir_25c * (1 + temp_coeff * (25 - temp_c))
```

#### 3.3 Internal Resistance vs SOC

IR increases at very low and very high SOC:
```python
def ir_at_soc(ir_nominal: float, soc_percent: float) -> float:
    """
    IR varies with SOC. Lowest around 50%, higher at extremes.
    """
    # Approximate U-shaped curve
    soc_factor = 1 + 0.3 * ((soc_percent - 50) / 50) ** 2
    return ir_nominal * soc_factor
```

### 4. Thermal Modeling

#### 4.1 Heat Generation

**Joule Heating:**
```
P_heat = I² * R_internal (per cell)
P_heat_total = (I_total / P)² * IR_cell * S * P
```

**Entropic Heating (secondary, can simplify or omit):**
Generally smaller contribution, can be approximated as 5-15% of Joule heating at moderate currents.

#### 4.2 Temperature Rise Model

**Lumped Thermal Model:**
```
dT/dt = (P_heat - Q_dissipated) / (m * Cp)
Q_dissipated = (T_cell - T_ambient) / R_thermal
```

**Steady State:**
```
T_steady = T_ambient + P_heat * R_thermal
```

Where:
- R_thermal = thermal resistance to ambient (°C/W)
- m = cell mass
- Cp = specific heat (~1.0 J/g°C for Li-ion cells)

#### 4.3 Thermal Resistance Estimates

| Condition | R_thermal (°C/W) |
|-----------|------------------|
| Bare cell, still air | 15-25 |
| Pack with shrink wrap, still air | 20-35 |
| Pack with light airflow | 8-15 |
| Pack with active cooling | 3-8 |

### 5. Energy & Runtime Calculations

#### 5.1 Available Energy to Cutoff

```python
def available_kwh(
    cell: CellSpec,
    series: int,
    parallel: int,
    start_soc_percent: float,
    cutoff_voltage_per_cell: float,
    avg_current_a: float
) -> float:
    """
    Calculate usable kWh considering voltage sag.
    Must integrate over discharge curve or use Peukert-like model.
    """
```

**Key considerations:**
- Higher current = more voltage sag = hits cutoff voltage sooner
- Less usable capacity at high discharge rates
- Temperature affects this significantly

#### 5.2 Peukert Effect (simplified for Li-ion)

Li-ion has much less Peukert effect than lead-acid, but some capacity reduction at high rates:
```
Effective_capacity = Rated_capacity * (Rated_current / Actual_current)^(k-1)
where k ≈ 1.02-1.08 for Li-ion (vs 1.1-1.3 for lead acid)
```

### 6. Max Continuous Power Calculation

#### 6.1 Thermal Limited

Find max current where steady-state temp stays below limit:
```python
def max_current_thermal(
    cell: CellSpec,
    parallel: int,
    t_ambient: float,
    t_max: float,
    r_thermal: float
) -> float:
    """
    Solve: T_max = T_ambient + (I/P)² * IR * R_thermal
    I_max = P * sqrt((T_max - T_ambient) / (IR * R_thermal))
    """
```

#### 6.2 Cell Rating Limited

```
I_max_rating = cell.max_continuous_discharge_a * parallel
```

#### 6.3 Voltage Sag Limited (maintain minimum voltage)

```python
def max_current_voltage(
    cell: CellSpec,
    series: int,
    parallel: int,
    soc_percent: float,
    min_pack_voltage: float
) -> float:
    """
    Find I where V_loaded = min_pack_voltage
    """
```

**Final max current = min(thermal_limit, rating_limit, voltage_limit)**

### 7. User Interface Requirements

Build a standalone test UI (web-based, React or plain HTML/JS) with:

#### 7.1 Input Section

**Cell Selection:**
- Dropdown for cell type (grouped by form factor)
- Or custom cell entry with all parameters

**Configuration:**
- Series count (1-12, slider or input)
- Parallel count (1-8, slider or input)
- Arrangement style (inline, staggered) for cylindrical

**Operating Conditions:**
- Ambient temperature (°C)
- Starting SOC (%) or starting voltage
- Load current (A) or power (W) with toggle
- Cutoff voltage per cell
- Thermal environment (dropdown: still air, light airflow, active cooling)

#### 7.2 Output Section

**Pack Specifications:**
- Total nominal voltage (V)
- Total capacity (mAh, Wh)
- Total mass (g, with breakdown)
- Bounding box dimensions (L x W x H mm)
- COG location (x, y, z mm)

**Electrical Performance:**
- Open circuit voltage at input SOC
- Loaded voltage at input current
- Voltage sag (V and %)
- Total pack IR (mΩ)

**Thermal Performance:**
- Heat generation at input current (W)
- Steady state temperature rise (°C)
- Max continuous current (thermal limited)
- Max continuous current (rating limited)
- Max continuous power (W)

**Energy/Runtime:**
- Usable energy to cutoff (Wh, kWh)
- Estimated runtime at input current (minutes)
- Energy density (Wh/kg)

#### 7.3 Visualization (Optional but valuable)

- Pack layout diagram (2D top view showing cell arrangement)
- Discharge curve preview (V vs capacity consumed)
- Temperature rise curve vs time at given current

### 8. Code Architecture

```
battery_calculator/
├── src/
│   ├── __init__.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── cell.py          # CellSpec dataclass, cell library
│   │   ├── pack.py          # BatteryPack class
│   │   └── thermal.py       # Thermal model
│   ├── calculations/
│   │   ├── __init__.py
│   │   ├── electrical.py    # Voltage, current, IR calculations
│   │   ├── geometry.py      # Dimensions, COG, bounding box
│   │   ├── energy.py        # kWh, runtime calculations
│   │   └── limits.py        # Max current/power calculations
│   ├── data/
│   │   ├── __init__.py
│   │   ├── cells_21700.py   # 21700 cell database
│   │   ├── cells_18650.py   # 18650 cell database
│   │   └── cells_lipo.py    # LiPo cell database/generator
│   └── ui/
│       ├── index.html       # Standalone UI
│       ├── app.js           # UI logic
│       └── styles.css       # Styling
├── tests/
│   ├── test_electrical.py
│   ├── test_geometry.py
│   ├── test_thermal.py
│   └── test_integration.py
├── requirements.txt
└── README.md
```

### 9. Integration Interface

Design for future integration with motor/prop/drag analyzer:

```python
class BatteryPack:
    def __init__(self, cell: CellSpec, series: int, parallel: int, ...):
        ...
    
    # Methods needed by parent system:
    def get_voltage_at_current(self, current_a: float, soc: float, temp_c: float) -> float:
        """Return loaded pack voltage."""
    
    def get_max_continuous_current(self, soc: float, temp_c: float) -> float:
        """Return max sustainable current."""
    
    def get_mass_kg(self) -> float:
        """Return total pack mass."""
    
    def get_dimensions_mm(self) -> tuple[float, float, float]:
        """Return (length, width, height) bounding box."""
    
    def get_cog_mm(self) -> tuple[float, float, float]:
        """Return center of gravity position."""
    
    def get_energy_wh(self, start_soc: float, end_soc: float, avg_current: float) -> float:
        """Return usable energy between SOC points at given current."""
    
    def get_heat_generation_w(self, current_a: float, soc: float, temp_c: float) -> float:
        """Return heat generation rate."""
    
    def step_thermal(self, current_a: float, dt_s: float, t_ambient: float) -> float:
        """Update internal temp state, return new temperature."""
```

### 10. Validation & Testing

Include test cases for:

1. **Known pack configurations** - Compare calculated specs against commercial pack datasheets
2. **Voltage sag** - Validate against published discharge curves
3. **Thermal** - Sanity check temperature rise against rule-of-thumb expectations
4. **Geometry** - Verify bounding box calculations against manual layout
5. **Edge cases** - 1S1P, 12S8P, very high currents, low temperatures

### 11. Data Sources for Cell Library

Prioritize these sources for cell data:
1. Manufacturer datasheets (Samsung SDI, LG Energy, Molicel, Murata)
2. Battery Mooch test data (especially for vape/high-drain cells)
3. Lygte-info.dk reviews
4. Published academic papers with cell characterization

For LiPo cells, use aggregate data from manufacturers like:
- Turnigy/Hobbyking
- Tattu/Gens Ace
- CNHL
- Bonka

### 12. Build Order

1. **Phase 1:** Cell data structures and library
2. **Phase 2:** Basic electrical calculations (voltage, IR, sag)
3. **Phase 3:** Geometry calculations (dimensions, COG)
4. **Phase 4:** Thermal model
5. **Phase 5:** Energy/runtime calculations
6. **Phase 6:** Max power/current limits
7. **Phase 7:** UI implementation
8. **Phase 8:** Testing and validation
9. **Phase 9:** Integration interface finalization

---

## Notes

- Use SI units internally, convert for display
- All calculations should be pure functions where possible for testability
- Include uncertainty/tolerance in outputs where data quality varies
- Document assumptions clearly in code comments
- Target Python 3.10+ for type hints
- Use dataclasses extensively for clean data structures
