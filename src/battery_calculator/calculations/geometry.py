"""
Geometry Calculations
=====================

Physical layout calculations for battery packs:
- Bounding box dimensions
- Center of gravity
- Void fraction
- Cell arrangement patterns

These calculations are OPTIONAL and only used when enable_geometry=True.
"""

import math
from enum import Enum
from typing import Tuple, List, Optional
from dataclasses import dataclass
from ..models.cell import CellSpec, FormFactor


class CylindricalArrangement(Enum):
    """Arrangement patterns for cylindrical cells."""
    INLINE = "inline"           # Side-by-side in rows
    STAGGERED = "staggered"     # Honeycomb pattern (more compact)
    STACKED = "stacked"         # Cells stacked on top of each other


@dataclass
class PackDimensions:
    """
    Physical dimensions of a battery pack.

    All dimensions in mm.
    Origin is at corner closest to (0,0,0).
    """
    length_mm: float      # X dimension
    width_mm: float       # Y dimension
    height_mm: float      # Z dimension
    cell_gap_mm: float    # Gap between cells

    # Cell arrangement info
    cells_x: int = 1      # Number of cells in X direction
    cells_y: int = 1      # Number of cells in Y direction
    cells_z: int = 1      # Number of cells in Z direction (layers)

    @property
    def volume_mm3(self) -> float:
        """Total bounding box volume (mm³)."""
        return self.length_mm * self.width_mm * self.height_mm

    @property
    def volume_ml(self) -> float:
        """Total bounding box volume (mL)."""
        return self.volume_mm3 / 1000.0

    def summary(self) -> str:
        """Formatted summary string."""
        return (
            f"Pack Dimensions: {self.length_mm:.1f} × "
            f"{self.width_mm:.1f} × {self.height_mm:.1f} mm "
            f"({self.volume_ml:.0f} mL)\n"
            f"  Arrangement: {self.cells_x} × {self.cells_y} × {self.cells_z}"
        )


@dataclass
class CenterOfGravity:
    """
    Center of gravity position.

    Origin is at corner of bounding box (0,0,0).
    Assumes uniform density within each cell.
    """
    x_mm: float
    y_mm: float
    z_mm: float

    def as_tuple(self) -> Tuple[float, float, float]:
        """Return as (x, y, z) tuple."""
        return (self.x_mm, self.y_mm, self.z_mm)

    def summary(self) -> str:
        """Formatted summary string."""
        return f"COG: ({self.x_mm:.1f}, {self.y_mm:.1f}, {self.z_mm:.1f}) mm"


def calculate_pack_dimensions(
    cell: CellSpec,
    series: int,
    parallel: int,
    arrangement: CylindricalArrangement = CylindricalArrangement.INLINE,
    cell_gap_mm: float = 0.5,
    lipo_swell_margin: float = 0.08,
    lipo_tab_protrusion_mm: float = 12.0
) -> PackDimensions:
    """
    Calculate battery pack bounding box dimensions.

    Parameters:
    ----------
    cell : CellSpec
        Cell specification

    series : int
        Number of cells in series

    parallel : int
        Number of cells in parallel

    arrangement : CylindricalArrangement
        Cell arrangement pattern (for cylindrical cells)

    cell_gap_mm : float
        Gap between cells (mm)

    lipo_swell_margin : float
        Swelling margin for LiPo cells (fraction of thickness)

    lipo_tab_protrusion_mm : float
        Tab protrusion beyond LiPo cell body (mm)

    Returns:
    -------
    PackDimensions
        Pack bounding box dimensions
    """
    total_cells = series * parallel

    if cell.form_factor == FormFactor.POUCH:
        return _calculate_pouch_dimensions(
            cell, series, parallel, cell_gap_mm,
            lipo_swell_margin, lipo_tab_protrusion_mm
        )
    else:
        return _calculate_cylindrical_dimensions(
            cell, series, parallel, arrangement, cell_gap_mm
        )


def _calculate_cylindrical_dimensions(
    cell: CellSpec,
    series: int,
    parallel: int,
    arrangement: CylindricalArrangement,
    cell_gap_mm: float
) -> PackDimensions:
    """Calculate dimensions for cylindrical cell packs."""
    total_cells = series * parallel
    diameter = cell.diameter_mm
    length = cell.length_mm

    if arrangement == CylindricalArrangement.STACKED:
        # Cells stacked vertically
        # All cells in one vertical column - unrealistic for large packs
        # but useful as a reference
        cells_x = 1
        cells_y = 1
        cells_z = total_cells

        width = diameter + cell_gap_mm
        height = diameter + cell_gap_mm
        depth = total_cells * length + (total_cells - 1) * cell_gap_mm

    elif arrangement == CylindricalArrangement.STAGGERED:
        # Honeycomb pattern - most compact
        # Try to make pack roughly square/cubic

        # For staggered arrangement, adjacent rows are offset by half a diameter
        # Row spacing = diameter × cos(30°) = diameter × 0.866

        # Determine best arrangement
        best_cells_x, best_cells_y, best_cells_z = _find_best_arrangement(
            total_cells, series, parallel
        )

        cells_x = best_cells_x
        cells_y = best_cells_y
        cells_z = best_cells_z

        # Width: cells_x cells, staggered
        width = cells_x * (diameter + cell_gap_mm)

        # Height: cells_y rows with staggered offset
        row_spacing = (diameter + cell_gap_mm) * 0.866
        height = diameter + (cells_y - 1) * row_spacing + cell_gap_mm

        # Depth: cells stacked along length
        depth = cells_z * length + (cells_z - 1) * cell_gap_mm

    else:  # INLINE
        # Simple grid arrangement
        best_cells_x, best_cells_y, best_cells_z = _find_best_arrangement(
            total_cells, series, parallel
        )

        cells_x = best_cells_x
        cells_y = best_cells_y
        cells_z = best_cells_z

        width = cells_x * (diameter + cell_gap_mm)
        height = cells_y * (diameter + cell_gap_mm)
        depth = cells_z * length + (cells_z - 1) * cell_gap_mm

    return PackDimensions(
        length_mm=depth,  # Along cell axis
        width_mm=width,
        height_mm=height,
        cell_gap_mm=cell_gap_mm,
        cells_x=cells_x,
        cells_y=cells_y,
        cells_z=cells_z,
    )


def _calculate_pouch_dimensions(
    cell: CellSpec,
    series: int,
    parallel: int,
    cell_gap_mm: float,
    swell_margin: float,
    tab_protrusion_mm: float
) -> PackDimensions:
    """Calculate dimensions for pouch/LiPo cell packs."""
    # For pouch cells, typically stacked for series, side-by-side for parallel
    thickness = cell.thickness_mm * (1 + swell_margin)

    # Series cells stacked (thickness adds up)
    # Parallel cells could be stacked or side-by-side
    # Assume stacked for simplicity

    total_cells = series * parallel
    cells_stacked = total_cells  # All in one stack

    length = cell.height_mm + tab_protrusion_mm  # Include tabs
    width = cell.width_mm + cell_gap_mm
    height = cells_stacked * thickness + (cells_stacked - 1) * cell_gap_mm

    return PackDimensions(
        length_mm=length,
        width_mm=width,
        height_mm=height,
        cell_gap_mm=cell_gap_mm,
        cells_x=1,
        cells_y=1,
        cells_z=cells_stacked,
    )


def _find_best_arrangement(
    total_cells: int,
    series: int,
    parallel: int
) -> Tuple[int, int, int]:
    """
    Find best 3D arrangement for given cell count.

    Tries to minimize pack volume while respecting series/parallel constraints.

    Returns:
    -------
    Tuple[int, int, int]
        (cells_x, cells_y, cells_z) arrangement
    """
    # For drone packs, often want to keep height low
    # Try to arrange parallel groups side-by-side, series stacked

    if parallel == 1:
        # Simple series pack
        # Arrange in a line or 2D grid
        if series <= 4:
            return (series, 1, 1)
        elif series <= 8:
            return (series // 2, 2, 1)
        else:
            # 2 rows, multiple cells
            return (series // 2, 2, 1)

    else:
        # Parallel groups
        # Each parallel group is series cells
        # Arrange groups side-by-side

        # Option 1: All in one row
        cells_x = parallel
        cells_y = 1
        cells_z = series

        # Option 2: 2 rows of parallel groups
        if parallel >= 4:
            cells_x = parallel // 2
            cells_y = 2
            cells_z = series

        return (cells_x, cells_y, cells_z)


def calculate_pack_cog(
    cell: CellSpec,
    dimensions: PackDimensions
) -> CenterOfGravity:
    """
    Calculate center of gravity of battery pack.

    Assumes uniform density and symmetric arrangement.

    Parameters:
    ----------
    cell : CellSpec
        Cell specification

    dimensions : PackDimensions
        Pack dimensions

    Returns:
    -------
    CenterOfGravity
        Center of gravity position
    """
    # For symmetric arrangements, COG is at geometric center
    x = dimensions.length_mm / 2.0
    y = dimensions.width_mm / 2.0
    z = dimensions.height_mm / 2.0

    return CenterOfGravity(x_mm=x, y_mm=y, z_mm=z)


def calculate_void_fraction(
    cell: CellSpec,
    dimensions: PackDimensions,
    total_cells: int
) -> float:
    """
    Calculate void (empty space) fraction of pack.

    Void fraction = 1 - (cell volume / pack volume)

    Parameters:
    ----------
    cell : CellSpec
        Cell specification

    dimensions : PackDimensions
        Pack dimensions

    total_cells : int
        Total number of cells

    Returns:
    -------
    float
        Void fraction (0-1)
    """
    # Calculate total cell volume
    cell_volume_ml = cell.volume_ml
    total_cell_volume = cell_volume_ml * total_cells

    # Pack volume
    pack_volume = dimensions.volume_ml

    if pack_volume <= 0:
        return 0.0

    # Void fraction
    cell_fraction = total_cell_volume / pack_volume
    return 1.0 - min(1.0, cell_fraction)
