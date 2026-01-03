"""
Cell Specification Model
========================

Defines the CellSpec dataclass that represents a single battery cell
with all its electrical, thermal, and physical properties.

All specifications are based on manufacturer datasheets and independent
testing from sources like Battery Mooch.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class CellChemistry(Enum):
    """Battery cell chemistry types."""
    NMC = "NMC"      # Nickel Manganese Cobalt (most common Li-ion)
    NCA = "NCA"      # Nickel Cobalt Aluminum (Tesla cells)
    LFP = "LFP"      # Lithium Iron Phosphate (safer, lower energy density)
    LCO = "LCO"      # Lithium Cobalt Oxide (older chemistry)
    LIPO = "LiPo"    # Lithium Polymer (pouch cells)


class FormFactor(Enum):
    """Cell physical form factors."""
    CYLINDRICAL_21700 = "21700"
    CYLINDRICAL_18650 = "18650"
    CYLINDRICAL_26650 = "26650"
    POUCH = "pouch"


@dataclass
class CellSpec:
    """
    Complete specification for a battery cell.

    All values at 25°C, 50% SOC unless otherwise noted.
    Resistance values verified against Battery Mooch testing where available.

    Attributes:
    ----------
    name : str
        Cell model name (e.g., "P45B", "30Q")

    manufacturer : str
        Cell manufacturer (e.g., "Molicel", "Samsung")

    chemistry : CellChemistry
        Cell chemistry type

    form_factor : FormFactor
        Physical form factor

    # Electrical Specifications
    capacity_mah : float
        Rated capacity (mAh) at 0.2C discharge

    nominal_voltage : float
        Nominal voltage (V) - typically 3.6-3.7V for Li-ion

    max_voltage : float
        Maximum charge voltage (V) - typically 4.2V

    min_voltage : float
        Minimum safe discharge voltage (V)

    max_continuous_discharge_a : float
        Maximum continuous discharge current (A)
        Based on manufacturer spec or Mooch testing

    peak_discharge_a : float
        Peak/pulse discharge current (A), typically 2-10 seconds

    dc_ir_mohm : float
        DC internal resistance (mΩ) at 25°C, 50% SOC
        This is the key value for voltage sag calculations

    ac_ir_mohm : float
        AC impedance (mΩ) at 1kHz - typically lower than DC IR

    # Physical Specifications
    mass_g : float
        Cell mass (g)

    # Cylindrical cell dimensions
    diameter_mm : float | None
        Outer diameter (mm) for cylindrical cells

    length_mm : float | None
        Length (mm) for cylindrical cells

    # Pouch cell dimensions
    width_mm : float | None
        Width (mm) for pouch cells

    height_mm : float | None
        Height (mm) for pouch cells

    thickness_mm : float | None
        Thickness (mm) for pouch cells

    # Thermal Properties
    thermal_resistance_c_per_w : float
        Cell-to-surface thermal resistance (°C/W)
        Default is estimated based on form factor

    specific_heat_j_per_g_c : float
        Specific heat capacity (J/g·°C)
        ~1.0 for most Li-ion cells

    max_temp_c : float
        Maximum operating temperature (°C)

    # Data source
    data_source : str
        Source of specifications (datasheet, Mooch test, etc.)

    verified : bool
        Whether specs have been verified against third-party testing
    """
    # Identification
    name: str
    manufacturer: str
    chemistry: CellChemistry
    form_factor: FormFactor

    # Electrical
    capacity_mah: float
    nominal_voltage: float = 3.6
    max_voltage: float = 4.2
    min_voltage: float = 2.5
    max_continuous_discharge_a: float = 10.0
    peak_discharge_a: float = 20.0
    dc_ir_mohm: float = 20.0  # mΩ
    ac_ir_mohm: Optional[float] = None  # mΩ

    # Physical - Cylindrical
    mass_g: float = 70.0
    diameter_mm: Optional[float] = None
    length_mm: Optional[float] = None

    # Physical - Pouch
    width_mm: Optional[float] = None
    height_mm: Optional[float] = None
    thickness_mm: Optional[float] = None

    # Thermal
    thermal_resistance_c_per_w: float = 3.0  # °C/W cell to surface
    specific_heat_j_per_g_c: float = 1.0     # J/g·°C
    max_temp_c: float = 60.0

    # Metadata
    data_source: str = "manufacturer"
    verified: bool = False

    def __post_init__(self):
        """Validate and set defaults based on form factor."""
        # Set default AC IR if not provided (typically ~50% of DC IR)
        if self.ac_ir_mohm is None:
            self.ac_ir_mohm = self.dc_ir_mohm * 0.5

        # Validate dimensions for cylindrical cells
        if self.form_factor in (FormFactor.CYLINDRICAL_21700,
                                 FormFactor.CYLINDRICAL_18650,
                                 FormFactor.CYLINDRICAL_26650):
            if self.diameter_mm is None or self.length_mm is None:
                raise ValueError(
                    f"Cylindrical cell {self.name} requires diameter_mm and length_mm"
                )

        # Validate dimensions for pouch cells
        if self.form_factor == FormFactor.POUCH:
            if self.width_mm is None or self.height_mm is None or self.thickness_mm is None:
                raise ValueError(
                    f"Pouch cell {self.name} requires width_mm, height_mm, and thickness_mm"
                )

    @property
    def dc_ir_ohm(self) -> float:
        """DC internal resistance in Ohms (for calculations)."""
        return self.dc_ir_mohm / 1000.0

    @property
    def energy_wh(self) -> float:
        """Nominal energy per cell (Wh)."""
        return (self.capacity_mah / 1000.0) * self.nominal_voltage

    @property
    def energy_density_wh_per_kg(self) -> float:
        """Gravimetric energy density (Wh/kg)."""
        return self.energy_wh / (self.mass_g / 1000.0)

    @property
    def volume_ml(self) -> float:
        """Cell volume in mL (cm³)."""
        import math
        if self.form_factor == FormFactor.POUCH:
            return (self.width_mm * self.height_mm * self.thickness_mm) / 1000.0
        else:
            # Cylindrical: V = π × r² × h
            radius_cm = (self.diameter_mm / 2.0) / 10.0
            height_cm = self.length_mm / 10.0
            return math.pi * radius_cm ** 2 * height_cm

    @property
    def energy_density_wh_per_l(self) -> float:
        """Volumetric energy density (Wh/L)."""
        return self.energy_wh / (self.volume_ml / 1000.0)

    @property
    def max_continuous_power_w(self) -> float:
        """Maximum continuous power per cell (W) at nominal voltage."""
        return self.max_continuous_discharge_a * self.nominal_voltage

    @property
    def c_rate_continuous(self) -> float:
        """Continuous discharge C-rate."""
        return self.max_continuous_discharge_a / (self.capacity_mah / 1000.0)

    def get_ir_at_temp(self, temp_c: float, temp_coeff: float = 0.007) -> float:
        """
        Get internal resistance adjusted for temperature.

        IR increases at low temps, decreases at high temps.
        Typical coefficient: 0.7% per °C from 25°C reference.

        Parameters:
        ----------
        temp_c : float
            Cell temperature (°C)

        temp_coeff : float
            Temperature coefficient (fraction per °C)

        Returns:
        -------
        float
            Temperature-adjusted DC IR (mΩ)
        """
        # IR increases as temp decreases from 25°C
        temp_factor = 1.0 + temp_coeff * (25.0 - temp_c)
        return self.dc_ir_mohm * max(0.5, temp_factor)  # Cap at 50% reduction

    def get_ir_at_soc(self, soc_percent: float) -> float:
        """
        Get internal resistance adjusted for state of charge.

        IR is lowest around 50% SOC, higher at extremes.

        Parameters:
        ----------
        soc_percent : float
            State of charge (0-100%)

        Returns:
        -------
        float
            SOC-adjusted DC IR (mΩ)
        """
        # U-shaped curve: lowest at 50%, higher at 0% and 100%
        soc_factor = 1.0 + 0.3 * ((soc_percent - 50.0) / 50.0) ** 2
        return self.dc_ir_mohm * soc_factor

    def get_ir_adjusted(
        self,
        soc_percent: float = 50.0,
        temp_c: float = 25.0,
        temp_coeff: float = 0.007
    ) -> float:
        """
        Get internal resistance adjusted for both SOC and temperature.

        Parameters:
        ----------
        soc_percent : float
            State of charge (0-100%)

        temp_c : float
            Cell temperature (°C)

        temp_coeff : float
            Temperature coefficient (fraction per °C)

        Returns:
        -------
        float
            Fully adjusted DC IR (mΩ)
        """
        # Combine SOC and temperature factors
        soc_factor = 1.0 + 0.3 * ((soc_percent - 50.0) / 50.0) ** 2
        temp_factor = 1.0 + temp_coeff * (25.0 - temp_c)
        return self.dc_ir_mohm * soc_factor * max(0.5, temp_factor)

    def summary(self) -> str:
        """Return a formatted summary string."""
        return (
            f"{self.manufacturer} {self.name}\n"
            f"  Chemistry: {self.chemistry.value}, Form: {self.form_factor.value}\n"
            f"  Capacity: {self.capacity_mah}mAh ({self.energy_wh:.1f}Wh)\n"
            f"  Max Discharge: {self.max_continuous_discharge_a}A continuous, "
            f"{self.peak_discharge_a}A peak\n"
            f"  DC IR: {self.dc_ir_mohm}mΩ\n"
            f"  Mass: {self.mass_g}g\n"
            f"  Energy Density: {self.energy_density_wh_per_kg:.0f} Wh/kg\n"
            f"  Data Source: {self.data_source}, Verified: {self.verified}"
        )
