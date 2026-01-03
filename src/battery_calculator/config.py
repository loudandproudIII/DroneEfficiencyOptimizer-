"""
Battery Calculator Configuration
=================================

Contains configuration settings, physical constants, and default values
for battery pack calculations.

All internal calculations use SI units:
- Voltage: V
- Current: A
- Resistance: Ohms (displayed as mΩ)
- Temperature: Celsius
- Mass: kg (displayed as g)
- Length: m (displayed as mm)
- Energy: J or Wh
- Power: W
"""

from dataclasses import dataclass, field
from typing import Optional


# =============================================================================
# Physical Constants
# =============================================================================

# Gravitational acceleration (m/s²)
GRAVITY = 9.81

# Standard temperature for specs (°C)
REFERENCE_TEMP_C = 25.0

# Li-ion cell specific heat capacity (J/g·K) - typical for all Li-ion
SPECIFIC_HEAT_LION = 1.0  # J/g·K or kJ/kg·K

# Copper thermal conductivity (W/m·K) - for interconnects
COPPER_THERMAL_CONDUCTIVITY = 400.0


# =============================================================================
# Default Cell Gaps and Tolerances
# =============================================================================

# Gap between cylindrical cells (mm) - for thermal expansion and assembly
DEFAULT_CELL_GAP_MM = 0.5

# LiPo swelling margin (percentage of thickness)
DEFAULT_LIPO_SWELL_MARGIN = 0.08  # 8%

# LiPo tab protrusion beyond cell body (mm)
DEFAULT_LIPO_TAB_PROTRUSION_MM = 12.0


# =============================================================================
# Electrical Defaults
# =============================================================================

# Default IR temperature coefficient (%/°C from 25°C reference)
# IR increases as temperature decreases, decreases as temp increases
DEFAULT_IR_TEMP_COEFF = 0.007  # 0.7% per °C

# Li-ion Peukert exponent (much less than lead-acid)
PEUKERT_EXPONENT_LION = 1.05  # 1.02-1.08 typical

# Minimum cell voltage cutoff (V) - to protect cells
DEFAULT_CUTOFF_VOLTAGE = 3.0

# Maximum cell voltage (V)
DEFAULT_MAX_VOLTAGE = 4.2

# Nominal cell voltage (V) for NMC/NCA
DEFAULT_NOMINAL_VOLTAGE = 3.6


# =============================================================================
# Thermal Resistance Estimates (°C/W PER CELL)
# =============================================================================
# Based on 21700 cell (~46 cm² surface area)
# R = 1/(h*A) where h is convection coefficient
# Natural convection: h ≈ 10-15 W/m²·K
# Forced convection: h ≈ 25-100 W/m²·K depending on airspeed

THERMAL_RESISTANCE = {
    "still_air": 18.0,            # Bare cell, no airflow (h≈12 W/m²·K)
    "light_airflow": 8.0,         # Bench with some airflow (h≈27 W/m²·K)
    "drone_in_flight": 4.0,       # Drone in flight, good airflow (h≈55 W/m²·K)
    "high_airflow": 2.5,          # Racing drone, high speed (h≈90 W/m²·K)
    "active_cooling": 1.5,        # Active fan directly on cells
}


# =============================================================================
# Interconnect Mass Estimates
# =============================================================================

# Nickel strip mass per connection (g) - for spot welding
NICKEL_STRIP_MASS_PER_CONNECTION_G = 0.8

# Wire mass per connection (g) - for soldering
WIRE_MASS_PER_CONNECTION_G = 1.5

# Solder mass per connection (g)
SOLDER_MASS_PER_CONNECTION_G = 0.3

# BMS mass estimate per series count (g/S)
BMS_MASS_PER_S_G = 3.0

# Shrink wrap/case mass estimate (g per cell)
ENCLOSURE_MASS_PER_CELL_G = 1.0


# =============================================================================
# SOC-OCV Lookup Table (NMC Chemistry)
# =============================================================================

# SOC (%) -> OCV (V) for typical NMC cells
# Based on Battery Mooch testing and manufacturer datasheets
SOC_TO_OCV_NMC = {
    100: 4.20,
    95: 4.15,
    90: 4.10,
    85: 4.05,
    80: 4.00,
    75: 3.95,
    70: 3.92,
    65: 3.88,
    60: 3.85,
    55: 3.82,
    50: 3.80,
    45: 3.78,
    40: 3.75,
    35: 3.72,
    30: 3.70,
    25: 3.65,
    20: 3.60,
    15: 3.52,
    10: 3.45,
    5: 3.30,
    0: 3.00,
}

# SOC-OCV for LiFePO4 (LFP) - flatter curve
SOC_TO_OCV_LFP = {
    100: 3.60,
    90: 3.35,
    80: 3.32,
    70: 3.30,
    60: 3.28,
    50: 3.26,
    40: 3.25,
    30: 3.22,
    20: 3.18,
    10: 3.10,
    0: 2.50,
}


# =============================================================================
# Configuration Dataclass
# =============================================================================

@dataclass
class BatteryCalculatorConfig:
    """
    Configuration for battery pack calculations.

    Attributes:
    ----------
    cell_gap_mm : float
        Gap between cylindrical cells (mm)

    include_interconnect_mass : bool
        Include estimated interconnect mass in total

    include_enclosure_mass : bool
        Include shrink wrap/case mass estimate

    include_bms_mass : bool
        Include BMS mass estimate

    lipo_swell_margin : float
        LiPo swelling margin as fraction of thickness

    ir_temp_coefficient : float
        IR temperature coefficient (fraction per °C from 25°C)

    cutoff_voltage : float
        Minimum cell voltage (V)

    thermal_environment : str
        One of: bare_still_air, shrinkwrap_still_air, light_airflow,
        active_cooling, liquid_cooling

    ambient_temp_c : float
        Ambient temperature (°C)

    max_cell_temp_c : float
        Maximum allowed cell temperature (°C)

    enable_geometry : bool
        Enable physical layout calculations (dimensions, COG)
    """
    # Mass calculation options
    cell_gap_mm: float = DEFAULT_CELL_GAP_MM
    include_interconnect_mass: bool = True
    include_enclosure_mass: bool = True
    include_bms_mass: bool = False

    # LiPo options
    lipo_swell_margin: float = DEFAULT_LIPO_SWELL_MARGIN
    lipo_tab_protrusion_mm: float = DEFAULT_LIPO_TAB_PROTRUSION_MM

    # Electrical
    ir_temp_coefficient: float = DEFAULT_IR_TEMP_COEFF
    cutoff_voltage: float = DEFAULT_CUTOFF_VOLTAGE

    # Thermal (default to drone_in_flight for drone applications)
    thermal_environment: str = "drone_in_flight"
    ambient_temp_c: float = 25.0
    max_cell_temp_c: float = 60.0

    # Geometry (optional feature)
    enable_geometry: bool = False

    @property
    def thermal_resistance(self) -> float:
        """Get thermal resistance for current environment (°C/W per cell)."""
        return THERMAL_RESISTANCE.get(
            self.thermal_environment,
            THERMAL_RESISTANCE["drone_in_flight"]
        )

    def validate(self) -> tuple[bool, str]:
        """Validate configuration values."""
        errors = []

        if self.cell_gap_mm < 0:
            errors.append("Cell gap cannot be negative")
        if self.cutoff_voltage < 2.0 or self.cutoff_voltage > 3.5:
            errors.append("Cutoff voltage should be between 2.0-3.5V")
        if self.ambient_temp_c < -40 or self.ambient_temp_c > 60:
            errors.append("Ambient temperature should be -40 to 60°C")
        if self.max_cell_temp_c < 40 or self.max_cell_temp_c > 80:
            errors.append("Max cell temperature should be 40-80°C")
        if self.thermal_environment not in THERMAL_RESISTANCE:
            errors.append(f"Unknown thermal environment: {self.thermal_environment}")

        if errors:
            return False, "; ".join(errors)
        return True, ""
