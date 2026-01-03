"""
Battery Pack Model
==================

Main BatteryPack class that integrates all calculations.
This is the primary user-facing API for battery pack analysis.

Designed for integration with motor/prop/airframe analyzers.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple, Dict, Any
import sys
from pathlib import Path

# Ensure imports work
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from .cell import CellSpec, FormFactor
from .thermal import ThermalModel, ThermalState, ThermalEnvironment
from ..config import (
    BatteryCalculatorConfig,
    NICKEL_STRIP_MASS_PER_CONNECTION_G,
    WIRE_MASS_PER_CONNECTION_G,
    SOLDER_MASS_PER_CONNECTION_G,
    BMS_MASS_PER_S_G,
    ENCLOSURE_MASS_PER_CELL_G,
    THERMAL_RESISTANCE,
)


class PackArrangement(Enum):
    """Physical arrangement of cells in pack."""
    INLINE = "inline"       # Side-by-side grid
    STAGGERED = "staggered" # Honeycomb (cylindrical only)
    STACKED = "stacked"     # Cells stacked vertically


@dataclass
class BatteryPack:
    """
    Complete battery pack model.

    Integrates electrical, thermal, and optional geometric calculations.

    Designed for integration with drone analysis engine:
    - get_voltage_at_current() for motor voltage calculations
    - get_max_continuous_current() for power budget
    - get_mass_kg() for weight calculations
    - get_heat_generation_w() for thermal analysis

    Attributes:
    ----------
    cell : CellSpec
        Cell specification

    series : int
        Number of cells in series (determines voltage)

    parallel : int
        Number of cells in parallel (determines capacity/current)

    config : BatteryCalculatorConfig
        Configuration settings

    Example:
    -------
        from src.battery_calculator import BatteryPack, CELL_DATABASE

        cell = CELL_DATABASE["Molicel P45B"]
        pack = BatteryPack(cell, series=6, parallel=2)

        # Get loaded voltage at 30A
        voltage = pack.get_voltage_at_current(30.0, soc=80.0)

        # Get max continuous current
        max_i, limit = pack.get_max_continuous_current()

        # Get pack mass
        mass_kg = pack.get_mass_kg()
    """
    cell: CellSpec
    series: int
    parallel: int
    config: BatteryCalculatorConfig = field(default_factory=BatteryCalculatorConfig)

    # Internal state
    _thermal_model: Optional[ThermalModel] = field(default=None, repr=False)
    _thermal_state: Optional[ThermalState] = field(default=None, repr=False)
    _cached_dimensions: Optional[Any] = field(default=None, repr=False)

    def __post_init__(self):
        """Validate and initialize internal state."""
        if self.series < 1 or self.series > 12:
            raise ValueError(f"Series must be 1-12, got {self.series}")
        if self.parallel < 1 or self.parallel > 8:
            raise ValueError(f"Parallel must be 1-8, got {self.parallel}")

        # Initialize thermal model
        # Convert per-cell thermal resistance to pack-level thermal resistance
        # Cells act as parallel thermal paths: R_th_pack = R_th_cell / num_cells
        # This ensures consistency: pack heat × pack R_th = correct temperature rise
        total_mass_g = self.get_total_mass_g()
        pack_thermal_resistance = self.config.thermal_resistance / self.total_cells
        self._thermal_model = ThermalModel(
            total_mass_g=total_mass_g,
            specific_heat_j_per_g_c=self.cell.specific_heat_j_per_g_c,
            thermal_resistance_c_per_w=pack_thermal_resistance,
        )
        self._thermal_state = ThermalState(
            cell_temp_c=self.config.ambient_temp_c,
            ambient_temp_c=self.config.ambient_temp_c,
        )

    # =========================================================================
    # Basic Properties
    # =========================================================================

    @property
    def total_cells(self) -> int:
        """Total number of cells in pack."""
        return self.series * self.parallel

    @property
    def configuration_string(self) -> str:
        """Configuration string (e.g., '6S2P')."""
        return f"{self.series}S{self.parallel}P"

    @property
    def nominal_voltage(self) -> float:
        """Nominal pack voltage (V)."""
        return self.cell.nominal_voltage * self.series

    @property
    def max_voltage(self) -> float:
        """Maximum pack voltage (V)."""
        return self.cell.max_voltage * self.series

    @property
    def min_voltage(self) -> float:
        """Minimum safe pack voltage (V)."""
        return self.cell.min_voltage * self.series

    @property
    def capacity_mah(self) -> float:
        """Total pack capacity (mAh)."""
        return self.cell.capacity_mah * self.parallel

    @property
    def capacity_ah(self) -> float:
        """Total pack capacity (Ah)."""
        return self.capacity_mah / 1000.0

    @property
    def energy_wh(self) -> float:
        """Nominal pack energy (Wh)."""
        return self.capacity_ah * self.nominal_voltage

    @property
    def energy_kwh(self) -> float:
        """Nominal pack energy (kWh)."""
        return self.energy_wh / 1000.0

    # =========================================================================
    # Mass Calculations
    # =========================================================================

    def get_cell_mass_g(self) -> float:
        """Get total cell mass (g)."""
        return self.cell.mass_g * self.total_cells

    def get_interconnect_mass_g(self) -> float:
        """Get estimated interconnect mass (g)."""
        if not self.config.include_interconnect_mass:
            return 0.0

        # Each cell needs 2 connections (+ and -)
        num_connections = self.total_cells * 2

        # Use nickel strip for cylindrical, wire for pouch
        if self.cell.form_factor == FormFactor.POUCH:
            return num_connections * WIRE_MASS_PER_CONNECTION_G
        else:
            return num_connections * NICKEL_STRIP_MASS_PER_CONNECTION_G

    def get_enclosure_mass_g(self) -> float:
        """Get estimated enclosure/shrinkwrap mass (g)."""
        if not self.config.include_enclosure_mass:
            return 0.0
        return self.total_cells * ENCLOSURE_MASS_PER_CELL_G

    def get_bms_mass_g(self) -> float:
        """Get estimated BMS mass (g)."""
        if not self.config.include_bms_mass:
            return 0.0
        return self.series * BMS_MASS_PER_S_G

    def get_total_mass_g(self) -> float:
        """Get total pack mass (g)."""
        return (
            self.get_cell_mass_g() +
            self.get_interconnect_mass_g() +
            self.get_enclosure_mass_g() +
            self.get_bms_mass_g()
        )

    def get_mass_kg(self) -> float:
        """Get total pack mass (kg). For integration API."""
        return self.get_total_mass_g() / 1000.0

    def get_mass_breakdown(self) -> Dict[str, float]:
        """Get detailed mass breakdown (g)."""
        return {
            "cells": self.get_cell_mass_g(),
            "interconnects": self.get_interconnect_mass_g(),
            "enclosure": self.get_enclosure_mass_g(),
            "bms": self.get_bms_mass_g(),
            "total": self.get_total_mass_g(),
        }

    # =========================================================================
    # Electrical Calculations - Integration API
    # =========================================================================

    def get_pack_ir_mohm(
        self,
        soc_percent: float = 50.0,
        temp_c: Optional[float] = None
    ) -> float:
        """
        Get pack internal resistance (mΩ).

        Parameters:
        ----------
        soc_percent : float
            State of charge (0-100%)

        temp_c : float, optional
            Cell temperature (defaults to config ambient)

        Returns:
        -------
        float
            Pack internal resistance (mΩ)
        """
        from ..calculations.electrical import calculate_pack_ir

        if temp_c is None:
            temp_c = self.config.ambient_temp_c

        return calculate_pack_ir(
            self.cell, self.series, self.parallel, soc_percent, temp_c
        )

    def get_voltage_at_current(
        self,
        current_a: float,
        soc: float = 50.0,
        temp_c: Optional[float] = None
    ) -> float:
        """
        Get loaded pack voltage. For integration API.

        Parameters:
        ----------
        current_a : float
            Total pack current (A)

        soc : float
            State of charge (0-100%)

        temp_c : float, optional
            Cell temperature (defaults to config ambient)

        Returns:
        -------
        float
            Loaded pack voltage (V)
        """
        from ..calculations.electrical import calculate_loaded_voltage

        if temp_c is None:
            temp_c = self.config.ambient_temp_c

        return calculate_loaded_voltage(
            self.cell, self.series, self.parallel, current_a, soc, temp_c
        )

    def get_open_circuit_voltage(self, soc: float = 100.0) -> float:
        """
        Get open circuit voltage at given SOC.

        Parameters:
        ----------
        soc : float
            State of charge (0-100%)

        Returns:
        -------
        float
            Open circuit voltage (V)
        """
        from ..calculations.electrical import calculate_pack_voltage
        return calculate_pack_voltage(self.cell, self.series, soc)

    def get_voltage_sag(
        self,
        current_a: float,
        soc: float = 50.0,
        temp_c: Optional[float] = None
    ) -> float:
        """
        Get voltage sag at given current.

        Parameters:
        ----------
        current_a : float
            Total pack current (A)

        soc : float
            State of charge (0-100%)

        temp_c : float, optional
            Cell temperature (defaults to config ambient)

        Returns:
        -------
        float
            Voltage sag (V)
        """
        from ..calculations.electrical import calculate_voltage_sag

        if temp_c is None:
            temp_c = self.config.ambient_temp_c

        return calculate_voltage_sag(
            self.cell, self.series, self.parallel, current_a, soc, temp_c
        )

    # =========================================================================
    # Current/Power Limits - Integration API
    # =========================================================================

    def get_max_continuous_current(
        self,
        soc: float = 50.0,
        temp_c: Optional[float] = None
    ) -> Tuple[float, str]:
        """
        Get maximum continuous current. For integration API.

        Parameters:
        ----------
        soc : float
            State of charge (0-100%)

        temp_c : float, optional
            Cell temperature (defaults to config ambient)

        Returns:
        -------
        Tuple[float, str]
            (max_current_a, limiting_factor)
            limiting_factor: "thermal", "rating", or "voltage"
        """
        from ..calculations.limits import calculate_max_continuous_current

        if temp_c is None:
            temp_c = self.config.ambient_temp_c

        return calculate_max_continuous_current(
            self.cell, self.series, self.parallel,
            ambient_temp_c=self.config.ambient_temp_c,
            max_temp_c=self.config.max_cell_temp_c,
            thermal_resistance_c_per_w=self.config.thermal_resistance,
            min_voltage_per_cell=self.config.cutoff_voltage,
            soc_percent=soc,
        )

    def get_max_continuous_power(
        self,
        soc: float = 50.0,
        temp_c: Optional[float] = None
    ) -> Tuple[float, str]:
        """
        Get maximum continuous power.

        Parameters:
        ----------
        soc : float
            State of charge (0-100%)

        temp_c : float, optional
            Cell temperature (defaults to config ambient)

        Returns:
        -------
        Tuple[float, str]
            (max_power_w, limiting_factor)
        """
        from ..calculations.limits import calculate_max_continuous_power

        if temp_c is None:
            temp_c = self.config.ambient_temp_c

        return calculate_max_continuous_power(
            self.cell, self.series, self.parallel,
            ambient_temp_c=self.config.ambient_temp_c,
            max_temp_c=self.config.max_cell_temp_c,
            thermal_resistance_c_per_w=self.config.thermal_resistance,
            min_voltage_per_cell=self.config.cutoff_voltage,
            soc_percent=soc,
        )

    # =========================================================================
    # Energy/Runtime - Integration API
    # =========================================================================

    def get_energy_wh(
        self,
        start_soc: float = 100.0,
        end_soc: float = 0.0,
        avg_current: float = 10.0
    ) -> float:
        """
        Get usable energy between SOC points. For integration API.

        Parameters:
        ----------
        start_soc : float
            Starting SOC (0-100%)

        end_soc : float
            Ending SOC (0-100%)

        avg_current : float
            Average discharge current (A)

        Returns:
        -------
        float
            Usable energy (Wh)
        """
        from ..calculations.energy import calculate_usable_energy

        return calculate_usable_energy(
            self.cell, self.series, self.parallel, avg_current,
            start_soc=start_soc,
            cutoff_voltage_per_cell=self.config.cutoff_voltage,
            temp_c=self.config.ambient_temp_c,
        )

    def get_runtime_minutes(
        self,
        current_a: float,
        start_soc: float = 100.0
    ) -> float:
        """
        Get estimated runtime at constant current.

        Parameters:
        ----------
        current_a : float
            Discharge current (A)

        start_soc : float
            Starting SOC (0-100%)

        Returns:
        -------
        float
            Runtime (minutes)
        """
        from ..calculations.energy import calculate_runtime

        return calculate_runtime(
            self.cell, self.series, self.parallel, current_a,
            start_soc=start_soc,
            cutoff_voltage_per_cell=self.config.cutoff_voltage,
            temp_c=self.config.ambient_temp_c,
        )

    def get_energy_density_wh_kg(self) -> float:
        """Get pack energy density (Wh/kg)."""
        return self.energy_wh / self.get_mass_kg()

    # =========================================================================
    # Thermal - Integration API
    # =========================================================================

    def get_heat_generation_w(
        self,
        current_a: float,
        soc: float = 50.0,
        temp_c: Optional[float] = None
    ) -> float:
        """
        Get heat generation rate. For integration API.

        Parameters:
        ----------
        current_a : float
            Total pack current (A)

        soc : float
            State of charge (0-100%)

        temp_c : float, optional
            Cell temperature (defaults to config ambient)

        Returns:
        -------
        float
            Heat generation rate (W)
        """
        from ..calculations.electrical import calculate_heat_generation

        if temp_c is None:
            temp_c = self.config.ambient_temp_c

        return calculate_heat_generation(
            self.cell, self.series, self.parallel, current_a, soc, temp_c
        )

    def get_steady_state_temp(
        self,
        current_a: float,
        soc: float = 50.0
    ) -> float:
        """
        Get steady-state cell temperature at given current.

        Uses iterative solution to find self-consistent temperature where:
        T_steady = T_ambient + P(T_steady) × R_thermal

        This accounts for the temperature-dependence of internal resistance.

        Parameters:
        ----------
        current_a : float
            Total pack current (A)

        soc : float
            State of charge (0-100%)

        Returns:
        -------
        float
            Steady-state temperature (°C)
        """
        # Iterative solution for self-consistent steady-state temperature
        # IR decreases with temperature, so heat generation changes with T
        temp_estimate = self.config.ambient_temp_c

        for _ in range(10):  # Usually converges in 2-3 iterations
            heat_w = self.get_heat_generation_w(current_a, soc, temp_estimate)
            new_temp = self._thermal_model.calculate_steady_state_temp(
                heat_w, self.config.ambient_temp_c
            )
            # Check convergence (within 0.1°C)
            if abs(new_temp - temp_estimate) < 0.1:
                return new_temp
            temp_estimate = new_temp

        return temp_estimate

    def step_thermal(
        self,
        current_a: float,
        dt_s: float,
        t_ambient: Optional[float] = None
    ) -> float:
        """
        Update internal temperature state. For integration API.

        Parameters:
        ----------
        current_a : float
            Total pack current (A)

        dt_s : float
            Time step (seconds)

        t_ambient : float, optional
            Ambient temperature (defaults to config)

        Returns:
        -------
        float
            New cell temperature (°C)
        """
        if t_ambient is not None:
            self._thermal_state.ambient_temp_c = t_ambient

        heat_w = self.get_heat_generation_w(
            current_a, 50.0, self._thermal_state.cell_temp_c
        )

        self._thermal_state = self._thermal_model.step_temperature(
            self._thermal_state, heat_w, dt_s
        )

        return self._thermal_state.cell_temp_c

    def reset_thermal(self, temp_c: Optional[float] = None):
        """Reset thermal state to ambient temperature."""
        if temp_c is None:
            temp_c = self.config.ambient_temp_c
        self._thermal_state = ThermalState(
            cell_temp_c=temp_c,
            ambient_temp_c=self.config.ambient_temp_c,
        )

    # =========================================================================
    # Geometry (Optional) - Integration API
    # =========================================================================

    def get_dimensions_mm(
        self,
        arrangement: PackArrangement = PackArrangement.INLINE
    ) -> Tuple[float, float, float]:
        """
        Get pack bounding box dimensions. For integration API.

        Only available if config.enable_geometry is True.

        Parameters:
        ----------
        arrangement : PackArrangement
            Cell arrangement pattern

        Returns:
        -------
        Tuple[float, float, float]
            (length, width, height) in mm
        """
        if not self.config.enable_geometry:
            raise RuntimeError(
                "Geometry calculations disabled. "
                "Set config.enable_geometry = True to enable."
            )

        from ..calculations.geometry import (
            calculate_pack_dimensions,
            CylindricalArrangement,
        )

        # Map enum
        arr_map = {
            PackArrangement.INLINE: CylindricalArrangement.INLINE,
            PackArrangement.STAGGERED: CylindricalArrangement.STAGGERED,
            PackArrangement.STACKED: CylindricalArrangement.STACKED,
        }

        dims = calculate_pack_dimensions(
            self.cell, self.series, self.parallel,
            arr_map.get(arrangement, CylindricalArrangement.INLINE),
            self.config.cell_gap_mm,
            self.config.lipo_swell_margin,
            self.config.lipo_tab_protrusion_mm,
        )

        self._cached_dimensions = dims
        return (dims.length_mm, dims.width_mm, dims.height_mm)

    def get_cog_mm(
        self,
        arrangement: PackArrangement = PackArrangement.INLINE
    ) -> Tuple[float, float, float]:
        """
        Get center of gravity position. For integration API.

        Only available if config.enable_geometry is True.

        Parameters:
        ----------
        arrangement : PackArrangement
            Cell arrangement pattern

        Returns:
        -------
        Tuple[float, float, float]
            (x, y, z) position in mm from corner origin
        """
        if not self.config.enable_geometry:
            raise RuntimeError(
                "Geometry calculations disabled. "
                "Set config.enable_geometry = True to enable."
            )

        from ..calculations.geometry import calculate_pack_cog

        # Ensure dimensions are calculated
        if self._cached_dimensions is None:
            self.get_dimensions_mm(arrangement)

        cog = calculate_pack_cog(self.cell, self._cached_dimensions)
        return cog.as_tuple()

    # =========================================================================
    # Summary and Export
    # =========================================================================

    def summary(self) -> str:
        """Generate formatted summary string."""
        max_i, limit = self.get_max_continuous_current()
        max_p, _ = self.get_max_continuous_power()

        lines = [
            f"Battery Pack: {self.configuration_string}",
            f"Cell: {self.cell.manufacturer} {self.cell.name}",
            f"=" * 50,
            f"",
            f"Electrical:",
            f"  Nominal Voltage: {self.nominal_voltage:.1f}V",
            f"  Voltage Range: {self.min_voltage:.1f}V - {self.max_voltage:.1f}V",
            f"  Capacity: {self.capacity_mah:.0f}mAh ({self.capacity_ah:.2f}Ah)",
            f"  Energy: {self.energy_wh:.1f}Wh",
            f"  Pack IR: {self.get_pack_ir_mohm():.1f}mΩ (at 50% SOC, 25°C)",
            f"",
            f"Limits:",
            f"  Max Continuous Current: {max_i:.1f}A ({limit} limited)",
            f"  Max Continuous Power: {max_p:.0f}W",
            f"  Cell Rating: {self.cell.max_continuous_discharge_a}A × {self.parallel}P = "
            f"{self.cell.max_continuous_discharge_a * self.parallel}A",
            f"",
            f"Mass:",
        ]

        mass_bd = self.get_mass_breakdown()
        lines.append(f"  Cells: {mass_bd['cells']:.0f}g")
        if mass_bd['interconnects'] > 0:
            lines.append(f"  Interconnects: {mass_bd['interconnects']:.0f}g")
        if mass_bd['enclosure'] > 0:
            lines.append(f"  Enclosure: {mass_bd['enclosure']:.0f}g")
        if mass_bd['bms'] > 0:
            lines.append(f"  BMS: {mass_bd['bms']:.0f}g")
        lines.append(f"  Total: {mass_bd['total']:.0f}g ({self.get_mass_kg():.3f}kg)")
        lines.append(f"  Energy Density: {self.get_energy_density_wh_kg():.0f} Wh/kg")

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Export pack data as dictionary."""
        max_i, limit = self.get_max_continuous_current()
        max_p, _ = self.get_max_continuous_power()

        return {
            "configuration": self.configuration_string,
            "cell_name": f"{self.cell.manufacturer} {self.cell.name}",
            "series": self.series,
            "parallel": self.parallel,
            "total_cells": self.total_cells,
            "nominal_voltage_v": self.nominal_voltage,
            "max_voltage_v": self.max_voltage,
            "min_voltage_v": self.min_voltage,
            "capacity_mah": self.capacity_mah,
            "energy_wh": self.energy_wh,
            "pack_ir_mohm": self.get_pack_ir_mohm(),
            "max_continuous_current_a": max_i,
            "max_continuous_power_w": max_p,
            "limiting_factor": limit,
            "total_mass_g": self.get_total_mass_g(),
            "energy_density_wh_kg": self.get_energy_density_wh_kg(),
        }
