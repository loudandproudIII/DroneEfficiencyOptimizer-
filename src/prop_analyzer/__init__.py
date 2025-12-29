"""
Propeller Analyzer Module
=========================

This module provides tools for analyzing APC propeller performance data.

The module enables:
- Lookup of thrust and power from RPM and airspeed
- Calculation of required power for a given thrust requirement
- Visualization of propeller performance curves
- Access to the APC propeller database

Key Functions:
--------------
- get_thrust_from_rpm_speed(): Get thrust (N) from RPM and airspeed
- get_power_from_rpm_speed(): Get power (W) from RPM and airspeed
- get_power_from_thrust_speed(): Get required power for a thrust target
- plot_prop_thrust(): Plot thrust curves for a propeller
- plot_prop_power(): Plot power curves for a propeller
- plot_prop_max_thrust(): Plot maximum thrust envelope

Example Usage:
-------------
    from src.prop_analyzer import PropAnalyzer

    analyzer = PropAnalyzer()
    thrust = analyzer.get_thrust_from_rpm_speed("7x7E", v_ms=30, rpm=22500)
    print(f"Thrust: {thrust:.2f} N")

Data Sources:
-------------
Performance data is sourced from APC Propellers (https://www.apcprop.com)

Units Convention:
----------------
- Speed: meters per second (m/s)
- RPM: revolutions per minute (1/min)
- Thrust: Newtons (N)
- Power: Watts (W)
"""

from .config import PropAnalyzerConfig
from .core import PropAnalyzer
from .plotting import PropPlotter

__all__ = [
    "PropAnalyzerConfig",
    "PropAnalyzer",
    "PropPlotter",
]
