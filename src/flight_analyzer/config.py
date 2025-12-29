"""
Flight Analyzer Configuration Module
====================================

This module contains configuration settings and physical constants
for flight performance analysis including atmospheric properties
and default aircraft parameters.

Physical Constants:
------------------
- AIR_DENSITY_SEA_LEVEL: Standard air density at sea level (1.225 kg/m³)
- GRAVITY: Gravitational acceleration (9.81 m/s²)
- ISA_TEMPERATURE_LAPSE: Temperature lapse rate (-0.0065 K/m)

Usage:
------
    from src.flight_analyzer.config import FlightAnalyzerConfig

    config = FlightAnalyzerConfig()
    density = config.get_air_density(altitude=1000)  # At 1000m
"""

import math
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path


# =============================================================================
# Physical Constants
# =============================================================================

# Standard air density at sea level (kg/m³)
# ISA conditions: 15°C, 101325 Pa
AIR_DENSITY_SEA_LEVEL = 1.225

# Gravitational acceleration (m/s²)
GRAVITY = 9.81

# ISA temperature lapse rate (K/m) - temperature decreases with altitude
ISA_TEMPERATURE_LAPSE = -0.0065

# ISA sea level temperature (K)
ISA_TEMPERATURE_SEA_LEVEL = 288.15

# ISA sea level pressure (Pa)
ISA_PRESSURE_SEA_LEVEL = 101325.0

# Gas constant for dry air (J/(kg·K))
GAS_CONSTANT_AIR = 287.05


@dataclass
class FlightAnalyzerConfig:
    """
    Configuration settings for the Flight Analyzer module.

    Attributes:
    ----------
    default_altitude : float
        Default altitude for calculations (m). Default 0 (sea level).

    default_temperature_offset : float
        Temperature offset from ISA standard (°C). Default 0.

    solver_max_iterations : int
        Maximum iterations for equilibrium solver.

    solver_tolerance : float
        Convergence tolerance for solver (relative).

    default_oswald_efficiency : float
        Default Oswald efficiency factor for induced drag.
        Typical values: 0.7-0.9 for most aircraft.

    default_cd0 : float
        Default zero-lift drag coefficient.
        Typical values: 0.02-0.05 for clean aircraft.
    """

    # -------------------------------------------------------------------------
    # Atmospheric Defaults
    # -------------------------------------------------------------------------

    # Default altitude (m)
    default_altitude: float = 0.0

    # Temperature offset from ISA (°C)
    # Positive = hotter than standard, negative = colder
    default_temperature_offset: float = 0.0

    # -------------------------------------------------------------------------
    # Solver Configuration
    # -------------------------------------------------------------------------

    # Maximum iterations for equilibrium solver
    solver_max_iterations: int = 50

    # Convergence tolerance (relative)
    solver_tolerance: float = 0.001

    # Damping factor for iterative solver
    solver_damping: float = 0.5

    # -------------------------------------------------------------------------
    # Default Aircraft Parameters
    # -------------------------------------------------------------------------

    # Default Oswald efficiency factor (for induced drag)
    # Typical: 0.7-0.85 for most wings
    default_oswald_efficiency: float = 0.8

    # Default zero-lift drag coefficient
    # Clean aircraft: 0.02-0.03
    # Multirotor: 0.5-1.5 (based on frontal area)
    default_cd0: float = 0.03

    # Default propeller count
    default_prop_count: int = 1

    # -------------------------------------------------------------------------
    # Atmospheric Calculations
    # -------------------------------------------------------------------------

    def get_air_density(
        self,
        altitude: float = 0.0,
        temperature_offset: float = 0.0
    ) -> float:
        """
        Calculate air density at a given altitude using ISA model.

        Uses the International Standard Atmosphere (ISA) model with
        optional temperature offset for non-standard conditions.

        The ISA model for the troposphere (< 11km):
            T = T0 + L × h
            p = p0 × (T/T0)^(g/(R×L))
            ρ = p / (R × T)

        Parameters:
        ----------
        altitude : float
            Altitude above sea level (m). Default 0.

        temperature_offset : float
            Deviation from ISA temperature (°C). Default 0.
            Positive = warmer than standard.

        Returns:
        -------
        float
            Air density (kg/m³)

        Example:
        -------
            config = FlightAnalyzerConfig()

            # Sea level, standard day
            rho = config.get_air_density(0)  # 1.225 kg/m³

            # At 2000m altitude
            rho = config.get_air_density(2000)  # ~1.007 kg/m³

            # Hot day at sea level (+15°C above standard)
            rho = config.get_air_density(0, 15)  # ~1.167 kg/m³
        """
        # ISA temperature at altitude
        T_isa = ISA_TEMPERATURE_SEA_LEVEL + ISA_TEMPERATURE_LAPSE * altitude

        # Actual temperature with offset
        T = T_isa + temperature_offset

        # Pressure at altitude (troposphere formula)
        if abs(ISA_TEMPERATURE_LAPSE) > 1e-10:
            # Standard lapse rate
            exponent = GRAVITY / (GAS_CONSTANT_AIR * (-ISA_TEMPERATURE_LAPSE))
            pressure_ratio = (T_isa / ISA_TEMPERATURE_SEA_LEVEL) ** exponent
        else:
            # Isothermal (unlikely but handle edge case)
            pressure_ratio = math.exp(
                -GRAVITY * altitude / (GAS_CONSTANT_AIR * ISA_TEMPERATURE_SEA_LEVEL)
            )

        p = ISA_PRESSURE_SEA_LEVEL * pressure_ratio

        # Density from ideal gas law: ρ = p / (R × T)
        density = p / (GAS_CONSTANT_AIR * T)

        return density

    def get_speed_of_sound(
        self,
        altitude: float = 0.0,
        temperature_offset: float = 0.0
    ) -> float:
        """
        Calculate speed of sound at given altitude.

        a = sqrt(γ × R × T)

        Where γ = 1.4 for air (ratio of specific heats)

        Parameters:
        ----------
        altitude : float
            Altitude above sea level (m).

        temperature_offset : float
            Temperature deviation from ISA (°C).

        Returns:
        -------
        float
            Speed of sound (m/s)
        """
        # Temperature at altitude
        T_isa = ISA_TEMPERATURE_SEA_LEVEL + ISA_TEMPERATURE_LAPSE * altitude
        T = T_isa + temperature_offset

        # Speed of sound
        gamma = 1.4  # Ratio of specific heats for air
        return math.sqrt(gamma * GAS_CONSTANT_AIR * T)

    def get_dynamic_pressure(
        self,
        velocity: float,
        altitude: float = 0.0,
        temperature_offset: float = 0.0
    ) -> float:
        """
        Calculate dynamic pressure (q).

        q = 0.5 × ρ × V²

        Parameters:
        ----------
        velocity : float
            Airspeed (m/s)

        altitude : float
            Altitude (m)

        temperature_offset : float
            Temperature deviation from ISA (°C)

        Returns:
        -------
        float
            Dynamic pressure (Pa or N/m²)
        """
        rho = self.get_air_density(altitude, temperature_offset)
        return 0.5 * rho * velocity ** 2


# =============================================================================
# Default Configuration Instance
# =============================================================================

DEFAULT_CONFIG = FlightAnalyzerConfig()
