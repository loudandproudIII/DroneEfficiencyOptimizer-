"""
Battery Calculator Calculations Module
=======================================

Pure functions for battery pack calculations.
All calculations use SI units internally.
"""

from .electrical import (
    soc_to_ocv,
    calculate_pack_voltage,
    calculate_voltage_sag,
    calculate_loaded_voltage,
    calculate_pack_ir,
)

from .geometry import (
    calculate_pack_dimensions,
    calculate_pack_cog,
    calculate_void_fraction,
)

from .energy import (
    calculate_pack_capacity,
    calculate_pack_energy,
    calculate_runtime,
    calculate_effective_capacity,
)

from .limits import (
    calculate_max_current_thermal,
    calculate_max_current_rating,
    calculate_max_current_voltage,
    calculate_max_continuous_current,
    calculate_max_continuous_power,
)

__all__ = [
    # Electrical
    "soc_to_ocv",
    "calculate_pack_voltage",
    "calculate_voltage_sag",
    "calculate_loaded_voltage",
    "calculate_pack_ir",
    # Geometry
    "calculate_pack_dimensions",
    "calculate_pack_cog",
    "calculate_void_fraction",
    # Energy
    "calculate_pack_capacity",
    "calculate_pack_energy",
    "calculate_runtime",
    "calculate_effective_capacity",
    # Limits
    "calculate_max_current_thermal",
    "calculate_max_current_rating",
    "calculate_max_current_voltage",
    "calculate_max_continuous_current",
    "calculate_max_continuous_power",
]
