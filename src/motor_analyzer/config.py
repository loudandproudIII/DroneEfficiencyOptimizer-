"""
Motor Analyzer Configuration Module
===================================

This module contains configuration settings and physical constants
for the Motor Analyzer. All paths, default values, and model parameters
are centralized here for easy modification.

Configuration Classes:
---------------------
- MotorAnalyzerConfig: Main configuration class with all settings

Physical Constants:
------------------
- COPPER_TEMP_COEFF: Temperature coefficient of copper (0.00393 /°C)
- KT_FROM_KV_FACTOR: Conversion factor Kt = 30/(π × Kv)

Usage:
------
    from src.motor_analyzer.config import MotorAnalyzerConfig

    config = MotorAnalyzerConfig()
    print(config.database_path)
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import math


# =============================================================================
# Physical Constants
# =============================================================================

# Temperature coefficient of copper resistance (per °C)
# Standard value for pure copper at 20°C reference
COPPER_TEMP_COEFF = 0.00393

# Conversion factor from Kv to Kt
# Kt [Nm/A] = 30 / (π × Kv [RPM/V])
# Derived from the relationship between back-EMF and torque constants
KT_FROM_KV_FACTOR = 30.0 / math.pi

# Default exponent for RPM-dependent no-load current
# I0(RPM) = I0_ref × (RPM / RPM_ref)^α
# α = 0.5 is typical for iron losses (hysteresis + eddy)
DEFAULT_I0_RPM_EXPONENT = 0.5

# Default saturation coefficient
# Kt_eff = Kt × (1 - k_sat × (I / I_rated)²)
# Only significant at currents above rated
DEFAULT_SATURATION_COEFF = 0.05


@dataclass
class MotorAnalyzerConfig:
    """
    Configuration settings for the Motor Analyzer module.

    This class centralizes all configuration parameters including file paths,
    physical constants, and solver settings used throughout the motor analyzer.

    Attributes:
    ----------
    data_root : Path
        Root directory containing motor data files.
        Default: "data/motor_analyzer" relative to project root.

    database_filename : str
        Filename of the motor database (JSON format).

    default_winding_temp : float
        Default winding temperature for calculations (°C).
        80°C is typical for a warm but not overheated motor.

    default_ambient_temp : float
        Default ambient temperature (°C).

    copper_temp_coeff : float
        Temperature coefficient for copper resistance (/°C).

    i0_rpm_exponent : float
        Exponent for RPM-dependent no-load current scaling.

    saturation_coeff : float
        Magnetic saturation coefficient for high-current correction.

    solver_max_iterations : int
        Maximum iterations for operating point solver.

    solver_tolerance : float
        Convergence tolerance for RPM in solver (RPM units).

    Example:
    -------
        config = MotorAnalyzerConfig()
        print(config.database_path)
        print(config.kt_from_kv(1000))  # Kt for 1000 Kv motor
    """

    # -------------------------------------------------------------------------
    # Path Configuration
    # -------------------------------------------------------------------------

    # Root directory for motor data
    data_root: Optional[Path] = None

    # Database filename
    database_filename: str = "motor_database.json"

    # -------------------------------------------------------------------------
    # Default Operating Conditions
    # -------------------------------------------------------------------------

    # Default winding temperature (°C)
    # 80°C is reasonable for continuous operation
    default_winding_temp: float = 80.0

    # Default ambient temperature (°C)
    default_ambient_temp: float = 25.0

    # Reference temperature for resistance measurements (°C)
    reference_temp: float = 25.0

    # -------------------------------------------------------------------------
    # Physical Model Parameters
    # -------------------------------------------------------------------------

    # Temperature coefficient for copper (/°C)
    copper_temp_coeff: float = COPPER_TEMP_COEFF

    # Exponent for I0 vs RPM relationship
    i0_rpm_exponent: float = DEFAULT_I0_RPM_EXPONENT

    # Saturation coefficient for Kt reduction at high current
    saturation_coeff: float = DEFAULT_SATURATION_COEFF

    # Enable/disable saturation correction
    enable_saturation_correction: bool = False

    # -------------------------------------------------------------------------
    # Solver Configuration
    # -------------------------------------------------------------------------

    # Maximum iterations for operating point solver
    solver_max_iterations: int = 50

    # Convergence tolerance for RPM (absolute, in RPM)
    solver_rpm_tolerance: float = 1.0

    # Damping factor for solver (0-1, lower = more stable but slower)
    solver_damping: float = 0.7

    # -------------------------------------------------------------------------
    # Thermal Model Parameters
    # -------------------------------------------------------------------------

    # Default thermal resistance (°C/W)
    # Typical range: 0.5-2.0 for well-cooled outrunners
    default_thermal_resistance: float = 1.0

    # -------------------------------------------------------------------------
    # Computed Properties
    # -------------------------------------------------------------------------

    def __post_init__(self):
        """
        Initialize computed paths after dataclass initialization.
        """
        # Determine project root (three levels up from this file)
        # File location: src/motor_analyzer/config.py
        # Path: config.py -> motor_analyzer/ -> src/ -> PROJECT_ROOT/
        self._project_root = Path(__file__).parent.parent.parent

        # Set default data_root if not provided
        if self.data_root is None:
            self.data_root = self._project_root / "src" / "motor_analyzer" / "database"
        elif isinstance(self.data_root, str):
            self.data_root = Path(self.data_root)

    @property
    def project_root(self) -> Path:
        """Get the project root directory."""
        return self._project_root

    @property
    def database_path(self) -> Path:
        """
        Get the full path to the motor database file.

        Returns:
        -------
        Path
            Absolute path to the JSON database file.
        """
        return self.data_root / self.database_filename

    # -------------------------------------------------------------------------
    # Calculation Helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def kt_from_kv(kv: float) -> float:
        """
        Calculate torque constant (Kt) from velocity constant (Kv).

        The relationship between Kt and Kv is:
            Kt [Nm/A] = 30 / (π × Kv [RPM/V])

        This assumes a sinusoidal back-EMF waveform and phase-to-phase
        measurements for both constants.

        Parameters:
        ----------
        kv : float
            Motor velocity constant in RPM/V.

        Returns:
        -------
        float
            Torque constant in Nm/A.

        Example:
        -------
            kt = MotorAnalyzerConfig.kt_from_kv(1000)
            # kt ≈ 0.00955 Nm/A
        """
        return KT_FROM_KV_FACTOR / kv

    def resistance_at_temp(self, rm_cold: float, temp: float) -> float:
        """
        Calculate winding resistance at a given temperature.

        Uses the standard copper temperature coefficient:
            R(T) = R_ref × (1 + α × (T - T_ref))

        Where α = 0.00393 /°C for copper.

        Parameters:
        ----------
        rm_cold : float
            Resistance at reference temperature (Ω).

        temp : float
            Target temperature (°C).

        Returns:
        -------
        float
            Resistance at the specified temperature (Ω).

        Example:
        -------
            config = MotorAnalyzerConfig()
            rm_hot = config.resistance_at_temp(0.020, 80)
            # rm_hot ≈ 0.0243 Ω (21.7% increase)
        """
        delta_t = temp - self.reference_temp
        return rm_cold * (1.0 + self.copper_temp_coeff * delta_t)

    def i0_at_rpm(self, i0_ref: float, rpm_ref: float, rpm: float) -> float:
        """
        Calculate no-load current at a given RPM.

        Iron losses (hysteresis + eddy currents) cause the no-load current
        to vary with rotational speed:
            I0(RPM) = I0_ref × (RPM / RPM_ref)^α

        Where α typically ranges 0.3-0.7 (default 0.5).

        Parameters:
        ----------
        i0_ref : float
            No-load current at reference RPM (A).

        rpm_ref : float
            Reference RPM where I0 was measured.

        rpm : float
            Target RPM.

        Returns:
        -------
        float
            No-load current at the specified RPM (A).

        Example:
        -------
            config = MotorAnalyzerConfig()
            i0 = config.i0_at_rpm(2.0, 10000, 15000)
            # i0 ≈ 2.45 A
        """
        if rpm_ref <= 0 or rpm <= 0:
            return i0_ref
        return i0_ref * (rpm / rpm_ref) ** self.i0_rpm_exponent

    def validate_paths(self) -> dict:
        """
        Validate that all required paths exist.

        Returns:
        -------
        dict
            Dictionary with path names as keys and existence status as values.
        """
        return {
            "data_root": self.data_root.exists(),
            "database_file": self.database_path.exists(),
        }


# =============================================================================
# Default Configuration Instance
# =============================================================================

DEFAULT_CONFIG = MotorAnalyzerConfig()
