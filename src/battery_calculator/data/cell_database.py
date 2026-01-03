"""
Cell Database
=============

Comprehensive database of battery cells with specifications sourced from:
- Manufacturer datasheets (Molicel, Samsung SDI, LG, Sony/Murata)
- Battery Mooch independent testing (https://www.e-cigarette-forum.com)
- Lygte-info.dk reviews

All DC IR values are verified against Battery Mooch testing where available.
Values at 25°C, 50% SOC unless otherwise noted.

Data Sources Key:
- "mooch": Battery Mooch bench test
- "datasheet": Manufacturer datasheet
- "estimate": Estimated from similar cells
"""

from typing import Dict, List, Optional
from ..models.cell import CellSpec, CellChemistry, FormFactor


# =============================================================================
# 21700 Cells (High Priority for Drone Applications)
# =============================================================================

CELLS_21700: Dict[str, CellSpec] = {
    # Molicel P45B - Verified against Battery Mooch testing
    # https://endless-sphere.com/sphere/threads/bench-test-results-molicel-p45b-50a-4500mah-21700-an-extraordinary-cell.116190/
    "Molicel P45B": CellSpec(
        name="P45B",
        manufacturer="Molicel",
        chemistry=CellChemistry.NMC,
        form_factor=FormFactor.CYLINDRICAL_21700,
        capacity_mah=4500,
        nominal_voltage=3.6,
        max_voltage=4.2,
        min_voltage=2.5,
        max_continuous_discharge_a=45,  # Mooch: 45A continuous
        peak_discharge_a=50,
        dc_ir_mohm=12,  # Mooch: ~11-13mΩ at 50% SOC
        ac_ir_mohm=7,   # Datasheet: 7mΩ at 30% SOC
        mass_g=70,
        diameter_mm=21.7,
        length_mm=70.15,
        data_source="mooch",
        verified=True,
    ),

    # Molicel P50B - High capacity + high drain
    # https://www.e-cigarette-forum.com/threads/bench-test-results-molicel-p50b-40a-5000mah-21700.974089/
    # Mooch: 40A continuous, can handle 45A with temp monitoring
    "Molicel P50B": CellSpec(
        name="P50B",
        manufacturer="Molicel",
        chemistry=CellChemistry.NMC,
        form_factor=FormFactor.CYLINDRICAL_21700,
        capacity_mah=5000,
        nominal_voltage=3.6,
        max_voltage=4.2,
        min_voltage=2.5,
        max_continuous_discharge_a=40,  # Mooch: 40A continuous
        peak_discharge_a=50,
        dc_ir_mohm=13,  # Mooch: ~12-14mΩ at 50% SOC
        ac_ir_mohm=7,
        mass_g=70,
        diameter_mm=21.7,
        length_mm=70.15,
        data_source="mooch",
        verified=True,
    ),

    # Samsung 40T - Verified against Battery Mooch
    # https://www.e-cigarette-forum.com/threads/bench-re-retest-results-samsung-40t-35a-4000mah-21700-amazing-performer-but-25a-35a.873677/
    "Samsung 40T": CellSpec(
        name="40T",
        manufacturer="Samsung",
        chemistry=CellChemistry.NMC,
        form_factor=FormFactor.CYLINDRICAL_21700,
        capacity_mah=4000,
        nominal_voltage=3.6,
        max_voltage=4.2,
        min_voltage=2.5,
        max_continuous_discharge_a=25,  # Mooch: 25A, 35A if kept cool
        peak_discharge_a=35,
        dc_ir_mohm=14,  # Mooch: 13.5-14.1mΩ
        ac_ir_mohm=7,
        mass_g=67,
        diameter_mm=21.7,
        length_mm=70.15,
        data_source="mooch",
        verified=True,
    ),

    # Samsung 50S - High capacity
    "Samsung 50S": CellSpec(
        name="50S",
        manufacturer="Samsung",
        chemistry=CellChemistry.NMC,
        form_factor=FormFactor.CYLINDRICAL_21700,
        capacity_mah=5000,
        nominal_voltage=3.6,
        max_voltage=4.2,
        min_voltage=2.5,
        max_continuous_discharge_a=25,
        peak_discharge_a=35,
        dc_ir_mohm=14,
        ac_ir_mohm=7,
        mass_g=68.5,
        diameter_mm=21.7,
        length_mm=70.15,
        data_source="mooch",
        verified=True,
    ),

    # Samsung 50E - Energy optimized
    "Samsung 50E": CellSpec(
        name="50E",
        manufacturer="Samsung",
        chemistry=CellChemistry.NMC,
        form_factor=FormFactor.CYLINDRICAL_21700,
        capacity_mah=5000,
        nominal_voltage=3.6,
        max_voltage=4.2,
        min_voltage=2.5,
        max_continuous_discharge_a=10,
        peak_discharge_a=15,
        dc_ir_mohm=20,
        ac_ir_mohm=10,
        mass_g=68.9,
        diameter_mm=21.7,
        length_mm=70.15,
        data_source="datasheet",
        verified=False,
    ),

    # LG M50LT - High capacity, low drain
    "LG M50LT": CellSpec(
        name="M50LT",
        manufacturer="LG",
        chemistry=CellChemistry.NMC,
        form_factor=FormFactor.CYLINDRICAL_21700,
        capacity_mah=5000,
        nominal_voltage=3.6,
        max_voltage=4.2,
        min_voltage=2.5,
        max_continuous_discharge_a=7,
        peak_discharge_a=15,
        dc_ir_mohm=22,
        ac_ir_mohm=11,
        mass_g=69,
        diameter_mm=21.7,
        length_mm=70.15,
        data_source="datasheet",
        verified=False,
    ),

    # Vapcell RS50 - High drain alternative
    "Vapcell RS50": CellSpec(
        name="RS50",
        manufacturer="Vapcell",
        chemistry=CellChemistry.NMC,
        form_factor=FormFactor.CYLINDRICAL_21700,
        capacity_mah=5000,
        nominal_voltage=3.6,
        max_voltage=4.2,
        min_voltage=2.5,
        max_continuous_discharge_a=30,
        peak_discharge_a=40,
        dc_ir_mohm=13,
        ac_ir_mohm=7,
        mass_g=70,
        diameter_mm=21.7,
        length_mm=70.15,
        data_source="mooch",
        verified=True,
    ),
}


# =============================================================================
# 18650 Cells
# =============================================================================

CELLS_18650: Dict[str, CellSpec] = {
    # Molicel P28B - High drain 18650
    "Molicel P28B": CellSpec(
        name="P28B",
        manufacturer="Molicel",
        chemistry=CellChemistry.NMC,
        form_factor=FormFactor.CYLINDRICAL_18650,
        capacity_mah=2800,
        nominal_voltage=3.6,
        max_voltage=4.2,
        min_voltage=2.5,
        max_continuous_discharge_a=28,
        peak_discharge_a=35,
        dc_ir_mohm=12,
        ac_ir_mohm=6,
        mass_g=48,
        diameter_mm=18.5,
        length_mm=65.2,
        data_source="mooch",
        verified=True,
    ),

    # Samsung 30Q - Very popular, verified
    # https://www.tasteyourjuice.com/wordpress/archives/16748
    "Samsung 30Q": CellSpec(
        name="30Q",
        manufacturer="Samsung",
        chemistry=CellChemistry.NMC,
        form_factor=FormFactor.CYLINDRICAL_18650,
        capacity_mah=3000,
        nominal_voltage=3.6,
        max_voltage=4.2,
        min_voltage=2.5,
        max_continuous_discharge_a=15,  # Samsung spec, Mooch says 20A
        peak_discharge_a=20,
        dc_ir_mohm=18,  # Mooch testing
        ac_ir_mohm=9,
        mass_g=48,
        diameter_mm=18.5,
        length_mm=65.2,
        data_source="mooch",
        verified=True,
    ),

    # LG HG2 - Popular high capacity
    "LG HG2": CellSpec(
        name="HG2",
        manufacturer="LG",
        chemistry=CellChemistry.NMC,
        form_factor=FormFactor.CYLINDRICAL_18650,
        capacity_mah=3000,
        nominal_voltage=3.6,
        max_voltage=4.2,
        min_voltage=2.5,
        max_continuous_discharge_a=20,
        peak_discharge_a=25,
        dc_ir_mohm=15,
        ac_ir_mohm=8,
        mass_g=47,
        diameter_mm=18.5,
        length_mm=65.2,
        data_source="mooch",
        verified=True,
    ),

    # Sony VTC6 - Premium cell
    "Sony VTC6": CellSpec(
        name="VTC6",
        manufacturer="Sony/Murata",
        chemistry=CellChemistry.NMC,
        form_factor=FormFactor.CYLINDRICAL_18650,
        capacity_mah=3000,
        nominal_voltage=3.6,
        max_voltage=4.2,
        min_voltage=2.5,
        max_continuous_discharge_a=15,
        peak_discharge_a=30,
        dc_ir_mohm=13,  # Lower IR than 30Q
        ac_ir_mohm=7,
        mass_g=46.5,
        diameter_mm=18.5,
        length_mm=65.2,
        data_source="mooch",
        verified=True,
    ),

    # Samsung 25R - Older but reliable
    "Samsung 25R": CellSpec(
        name="25R",
        manufacturer="Samsung",
        chemistry=CellChemistry.NMC,
        form_factor=FormFactor.CYLINDRICAL_18650,
        capacity_mah=2500,
        nominal_voltage=3.6,
        max_voltage=4.2,
        min_voltage=2.5,
        max_continuous_discharge_a=20,
        peak_discharge_a=25,
        dc_ir_mohm=14,
        ac_ir_mohm=7,
        mass_g=45,
        diameter_mm=18.5,
        length_mm=65.2,
        data_source="mooch",
        verified=True,
    ),

    # Molicel P30B - Balanced performance
    "Molicel P30B": CellSpec(
        name="P30B",
        manufacturer="Molicel",
        chemistry=CellChemistry.NMC,
        form_factor=FormFactor.CYLINDRICAL_18650,
        capacity_mah=3000,
        nominal_voltage=3.6,
        max_voltage=4.2,
        min_voltage=2.5,
        max_continuous_discharge_a=18,
        peak_discharge_a=25,
        dc_ir_mohm=15,
        ac_ir_mohm=8,
        mass_g=47,
        diameter_mm=18.5,
        length_mm=65.2,
        data_source="datasheet",
        verified=False,
    ),
}


# =============================================================================
# Combined Database
# =============================================================================

CELL_DATABASE: Dict[str, CellSpec] = {
    **CELLS_21700,
    **CELLS_18650,
}


# =============================================================================
# LiPo Cell Generator
# =============================================================================

def create_lipo_cell(
    capacity_mah: float,
    c_rating: float = 50.0,
    series_count: int = 1,
    name: Optional[str] = None
) -> CellSpec:
    """
    Create a LiPo cell specification based on capacity and C-rating.

    Uses empirical formulas based on typical LiPo characteristics:
    - IR estimated from capacity and C-rating
    - Mass estimated from capacity
    - Dimensions estimated from capacity

    Parameters:
    ----------
    capacity_mah : float
        Cell capacity (mAh)

    c_rating : float
        Continuous C-rating (e.g., 50C, 75C)

    series_count : int
        Number of cells in series (for multi-cell packs)
        This affects voltage but not individual cell properties.

    name : str, optional
        Custom name for the cell

    Returns:
    -------
    CellSpec
        Generated LiPo cell specification
    """
    # Generate name if not provided
    if name is None:
        name = f"LiPo {capacity_mah}mAh {int(c_rating)}C"

    # Estimate IR from capacity and C-rating
    # Formula: IR (mΩ) ≈ (1000 / capacity) × (100 / C_rating) × k
    # k ≈ 40 for typical quality cells
    k = 40.0
    ir_mohm = (1000.0 / capacity_mah) * (100.0 / c_rating) * k
    ir_mohm = max(0.3, min(10.0, ir_mohm))  # Clamp to reasonable range

    # Estimate mass from capacity
    # Approximately 6-7g per 100mAh for quality LiPos
    mass_per_100mah = 6.5
    mass_g = (capacity_mah / 100.0) * mass_per_100mah

    # Estimate dimensions from capacity (very approximate)
    # Based on typical LiPo aspect ratios
    if capacity_mah <= 500:
        width, height, thickness = 55, 30, 6
    elif capacity_mah <= 1000:
        width, height, thickness = 70, 35, 8
    elif capacity_mah <= 1500:
        width, height, thickness = 80, 38, 10
    elif capacity_mah <= 2200:
        width, height, thickness = 100, 34, 14
    elif capacity_mah <= 3000:
        width, height, thickness = 115, 38, 18
    elif capacity_mah <= 5000:
        width, height, thickness = 140, 45, 24
    else:
        width, height, thickness = 170, 52, 32

    # Scale dimensions based on actual capacity vs typical for that range
    scale_factor = (capacity_mah / 2000.0) ** 0.3  # Gentle scaling

    return CellSpec(
        name=name,
        manufacturer="Generic",
        chemistry=CellChemistry.LIPO,
        form_factor=FormFactor.POUCH,
        capacity_mah=capacity_mah,
        nominal_voltage=3.7,  # LiPo nominal is typically 3.7V
        max_voltage=4.2,
        min_voltage=3.0,  # LiPo cutoff typically higher
        max_continuous_discharge_a=capacity_mah * c_rating / 1000.0,
        peak_discharge_a=capacity_mah * c_rating * 1.5 / 1000.0,
        dc_ir_mohm=ir_mohm,
        ac_ir_mohm=ir_mohm * 0.5,
        mass_g=mass_g,
        width_mm=width,
        height_mm=height,
        thickness_mm=thickness,
        data_source="estimate",
        verified=False,
    )


# =============================================================================
# Database Access Functions
# =============================================================================

def get_cell(name: str) -> Optional[CellSpec]:
    """
    Get a cell by name.

    Parameters:
    ----------
    name : str
        Cell name (e.g., "Samsung 30Q", "Molicel P45B")

    Returns:
    -------
    CellSpec or None
        Cell specification if found
    """
    return CELL_DATABASE.get(name)


def list_cells() -> List[str]:
    """
    List all available cell names.

    Returns:
    -------
    List[str]
        Sorted list of cell names
    """
    return sorted(CELL_DATABASE.keys())


def list_cells_by_form_factor(form_factor: FormFactor) -> List[str]:
    """
    List cells filtered by form factor.

    Parameters:
    ----------
    form_factor : FormFactor
        Form factor to filter by

    Returns:
    -------
    List[str]
        Cell names matching the form factor
    """
    return sorted([
        name for name, cell in CELL_DATABASE.items()
        if cell.form_factor == form_factor
    ])


def list_cells_by_manufacturer(manufacturer: str) -> List[str]:
    """
    List cells filtered by manufacturer.

    Parameters:
    ----------
    manufacturer : str
        Manufacturer name (case-insensitive partial match)

    Returns:
    -------
    List[str]
        Cell names from the manufacturer
    """
    manufacturer_lower = manufacturer.lower()
    return sorted([
        name for name, cell in CELL_DATABASE.items()
        if manufacturer_lower in cell.manufacturer.lower()
    ])
