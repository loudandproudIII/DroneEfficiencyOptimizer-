"""
Battery Calculator Data Module
==============================

Contains cell database and lookup functions.
"""

from .cell_database import (
    CELL_DATABASE,
    get_cell,
    list_cells,
    list_cells_by_form_factor,
    list_cells_by_manufacturer,
    create_lipo_cell,
)

__all__ = [
    "CELL_DATABASE",
    "get_cell",
    "list_cells",
    "list_cells_by_form_factor",
    "list_cells_by_manufacturer",
    "create_lipo_cell",
]
