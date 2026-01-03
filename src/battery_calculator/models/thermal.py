"""
Thermal Model
=============

Models thermal behavior of battery packs including:
- Heat generation from I²R losses
- Temperature rise calculations
- Steady-state and transient thermal analysis
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ThermalEnvironment(Enum):
    """Thermal environment categories with typical thermal resistances."""
    BARE_STILL_AIR = "bare_still_air"
    SHRINKWRAP_STILL_AIR = "shrinkwrap_still_air"
    LIGHT_AIRFLOW = "light_airflow"
    ACTIVE_COOLING = "active_cooling"
    LIQUID_COOLING = "liquid_cooling"

    @property
    def thermal_resistance(self) -> float:
        """Get typical thermal resistance (°C/W) for this environment."""
        values = {
            self.BARE_STILL_AIR: 20.0,
            self.SHRINKWRAP_STILL_AIR: 28.0,
            self.LIGHT_AIRFLOW: 12.0,
            self.ACTIVE_COOLING: 5.0,
            self.LIQUID_COOLING: 2.0,
        }
        return values.get(self, 20.0)

    @property
    def description(self) -> str:
        """Human-readable description."""
        descriptions = {
            self.BARE_STILL_AIR: "Bare cells, no airflow",
            self.SHRINKWRAP_STILL_AIR: "Pack with shrink wrap, still air",
            self.LIGHT_AIRFLOW: "Natural convection or light forced air",
            self.ACTIVE_COOLING: "Active fan cooling",
            self.LIQUID_COOLING: "Liquid cooled pack",
        }
        return descriptions.get(self, "Unknown environment")


@dataclass
class ThermalState:
    """
    Current thermal state of a battery pack.

    Used for transient thermal simulations.

    Attributes:
    ----------
    cell_temp_c : float
        Current cell temperature (°C)

    ambient_temp_c : float
        Ambient temperature (°C)

    heat_generation_w : float
        Current heat generation rate (W)

    heat_dissipation_w : float
        Current heat dissipation rate (W)

    time_s : float
        Elapsed simulation time (s)
    """
    cell_temp_c: float = 25.0
    ambient_temp_c: float = 25.0
    heat_generation_w: float = 0.0
    heat_dissipation_w: float = 0.0
    time_s: float = 0.0

    @property
    def temp_rise_c(self) -> float:
        """Temperature rise above ambient (°C)."""
        return self.cell_temp_c - self.ambient_temp_c

    @property
    def net_heat_w(self) -> float:
        """Net heat accumulation rate (W)."""
        return self.heat_generation_w - self.heat_dissipation_w


@dataclass
class ThermalModel:
    """
    Thermal model for battery pack calculations.

    Implements lumped thermal mass model:
    dT/dt = (P_heat - Q_dissipated) / (m × Cp)
    Q_dissipated = (T_cell - T_ambient) / R_thermal

    Attributes:
    ----------
    total_mass_g : float
        Total thermal mass of the pack (g)

    specific_heat_j_per_g_c : float
        Specific heat capacity (J/g·°C)

    thermal_resistance_c_per_w : float
        Pack-to-ambient thermal resistance (°C/W)

    environment : ThermalEnvironment
        Current thermal environment
    """
    total_mass_g: float
    specific_heat_j_per_g_c: float = 1.0
    thermal_resistance_c_per_w: float = 20.0
    environment: ThermalEnvironment = ThermalEnvironment.SHRINKWRAP_STILL_AIR

    def __post_init__(self):
        """Set thermal resistance from environment if not overridden."""
        if self.thermal_resistance_c_per_w == 20.0:
            self.thermal_resistance_c_per_w = self.environment.thermal_resistance

    @property
    def thermal_mass_j_per_c(self) -> float:
        """Thermal mass (J/°C)."""
        return self.total_mass_g * self.specific_heat_j_per_g_c

    @property
    def thermal_time_constant_s(self) -> float:
        """
        Thermal time constant (seconds).

        τ = m × Cp × R_thermal

        Time to reach 63.2% of steady-state temperature.
        """
        return self.thermal_mass_j_per_c * self.thermal_resistance_c_per_w

    def calculate_heat_generation(
        self,
        current_a: float,
        total_ir_ohm: float,
        entropic_factor: float = 1.1
    ) -> float:
        """
        Calculate heat generation from current flow.

        P_heat = I² × R × entropic_factor

        Parameters:
        ----------
        current_a : float
            Total pack current (A)

        total_ir_ohm : float
            Total pack internal resistance (Ω)

        entropic_factor : float
            Multiplier for entropic heating (typically 1.05-1.15)

        Returns:
        -------
        float
            Heat generation rate (W)
        """
        joule_heating = current_a ** 2 * total_ir_ohm
        return joule_heating * entropic_factor

    def calculate_steady_state_temp(
        self,
        heat_generation_w: float,
        ambient_temp_c: float
    ) -> float:
        """
        Calculate steady-state cell temperature.

        T_steady = T_ambient + P_heat × R_thermal

        Parameters:
        ----------
        heat_generation_w : float
            Heat generation rate (W)

        ambient_temp_c : float
            Ambient temperature (°C)

        Returns:
        -------
        float
            Steady-state cell temperature (°C)
        """
        temp_rise = heat_generation_w * self.thermal_resistance_c_per_w
        return ambient_temp_c + temp_rise

    def calculate_temp_rise_rate(
        self,
        heat_generation_w: float,
        current_temp_c: float,
        ambient_temp_c: float
    ) -> float:
        """
        Calculate instantaneous temperature rise rate.

        dT/dt = (P_heat - Q_dissipated) / (m × Cp)

        Parameters:
        ----------
        heat_generation_w : float
            Heat generation rate (W)

        current_temp_c : float
            Current cell temperature (°C)

        ambient_temp_c : float
            Ambient temperature (°C)

        Returns:
        -------
        float
            Temperature rise rate (°C/s)
        """
        # Heat dissipation
        q_dissipated = (current_temp_c - ambient_temp_c) / self.thermal_resistance_c_per_w

        # Net heat
        net_heat = heat_generation_w - q_dissipated

        # Temperature rise rate
        return net_heat / self.thermal_mass_j_per_c

    def step_temperature(
        self,
        state: ThermalState,
        heat_generation_w: float,
        dt_s: float
    ) -> ThermalState:
        """
        Step thermal simulation forward in time.

        Uses simple Euler integration.

        Parameters:
        ----------
        state : ThermalState
            Current thermal state

        heat_generation_w : float
            Heat generation rate (W)

        dt_s : float
            Time step (seconds)

        Returns:
        -------
        ThermalState
            Updated thermal state
        """
        # Heat dissipation
        q_dissipated = (
            (state.cell_temp_c - state.ambient_temp_c) /
            self.thermal_resistance_c_per_w
        )

        # Temperature change
        dt_per_dt = self.calculate_temp_rise_rate(
            heat_generation_w,
            state.cell_temp_c,
            state.ambient_temp_c
        )

        new_temp = state.cell_temp_c + dt_per_dt * dt_s

        return ThermalState(
            cell_temp_c=new_temp,
            ambient_temp_c=state.ambient_temp_c,
            heat_generation_w=heat_generation_w,
            heat_dissipation_w=q_dissipated,
            time_s=state.time_s + dt_s
        )

    def time_to_temperature(
        self,
        target_temp_c: float,
        heat_generation_w: float,
        ambient_temp_c: float,
        start_temp_c: Optional[float] = None
    ) -> float:
        """
        Estimate time to reach target temperature.

        Uses exponential approach model.

        Parameters:
        ----------
        target_temp_c : float
            Target temperature (°C)

        heat_generation_w : float
            Constant heat generation rate (W)

        ambient_temp_c : float
            Ambient temperature (°C)

        start_temp_c : float, optional
            Starting temperature (defaults to ambient)

        Returns:
        -------
        float
            Time to reach target (seconds), or inf if unreachable
        """
        import math

        if start_temp_c is None:
            start_temp_c = ambient_temp_c

        # Calculate steady-state temp
        steady_temp = self.calculate_steady_state_temp(
            heat_generation_w, ambient_temp_c
        )

        # If target is above steady-state, it's unreachable
        if target_temp_c >= steady_temp:
            return float('inf')

        # If already at or above target
        if start_temp_c >= target_temp_c:
            return 0.0

        # Exponential approach: T(t) = T_steady - (T_steady - T_start) × e^(-t/τ)
        # Solve for t: t = -τ × ln((T_steady - T_target) / (T_steady - T_start))
        tau = self.thermal_time_constant_s
        numerator = steady_temp - target_temp_c
        denominator = steady_temp - start_temp_c

        if denominator <= 0:
            return 0.0

        return -tau * math.log(numerator / denominator)

    def max_current_thermal(
        self,
        max_temp_c: float,
        ambient_temp_c: float,
        total_ir_ohm: float,
        entropic_factor: float = 1.1
    ) -> float:
        """
        Calculate maximum current for thermal limit.

        Solves: T_max = T_ambient + I² × R × entropic × R_thermal

        Parameters:
        ----------
        max_temp_c : float
            Maximum allowed temperature (°C)

        ambient_temp_c : float
            Ambient temperature (°C)

        total_ir_ohm : float
            Total pack internal resistance (Ω)

        entropic_factor : float
            Entropic heating multiplier

        Returns:
        -------
        float
            Maximum sustainable current (A)
        """
        import math

        max_temp_rise = max_temp_c - ambient_temp_c
        if max_temp_rise <= 0:
            return 0.0

        # P_max = ΔT / R_thermal
        max_heat = max_temp_rise / self.thermal_resistance_c_per_w

        # I² × R × entropic = P_max
        # I = sqrt(P_max / (R × entropic))
        denominator = total_ir_ohm * entropic_factor
        if denominator <= 0:
            return float('inf')

        return math.sqrt(max_heat / denominator)
