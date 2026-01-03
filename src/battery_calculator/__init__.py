"""
Battery Pack Calculator Module
==============================

Physics-accurate battery pack calculator for drone/UAV applications.
Calculates electrical, thermal, and geometric properties of battery packs
built from cylindrical (18650, 21700) or pouch (LiPo) cells.

Features:
---------
- Pack configuration (1S-12S, 1P-8P)
- Voltage sag calculation with SOC and temperature compensation
- Thermal modeling (heat generation, temperature rise)
- Optional physical layout (dimensions, COG)
- Energy/runtime calculations
- Max current/power limit calculations

Usage:
------
    from src.battery_calculator import BatteryPack, CellSpec, CELL_DATABASE

    # Get a cell from the database
    cell = CELL_DATABASE["Molicel P45B"]

    # Create a 6S2P pack
    pack = BatteryPack(cell, series=6, parallel=2)

    # Get voltage under load
    voltage = pack.get_voltage_at_current(current_a=30.0, soc=80.0)

    # Get max continuous current
    max_current = pack.get_max_continuous_current()

Data Sources:
-------------
Cell specifications sourced from:
- Manufacturer datasheets (Molicel, Samsung SDI, LG, Sony/Murata)
- Battery Mooch independent testing (https://www.e-cigarette-forum.com)
- Lygte-info.dk cell reviews
"""

from .models.cell import CellSpec, CellChemistry, FormFactor
from .models.pack import BatteryPack, PackArrangement
from .models.thermal import ThermalEnvironment
from .data.cell_database import CELL_DATABASE, get_cell, list_cells, list_cells_by_form_factor
from .config import BatteryCalculatorConfig, THERMAL_RESISTANCE
from .debugger import CalculationDebugger, get_debugger, set_debugger, debug_step
from .debug_trace import trace_all_calculations

__all__ = [
    # Core classes
    "CellSpec",
    "BatteryPack",
    "PackArrangement",
    "ThermalEnvironment",
    # Enums
    "CellChemistry",
    "FormFactor",
    # Database access
    "CELL_DATABASE",
    "get_cell",
    "list_cells",
    "list_cells_by_form_factor",
    # Config
    "BatteryCalculatorConfig",
    "THERMAL_RESISTANCE",
    # Debugger
    "CalculationDebugger",
    "get_debugger",
    "set_debugger",
    "debug_step",
    "trace_all_calculations",
]
