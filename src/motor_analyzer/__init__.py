"""
Motor Analyzer Module
=====================

This module provides tools for analyzing brushless DC motor performance
using an equivalent circuit model with temperature and RPM corrections.

The module enables:
- Motor performance calculation from operating conditions
- Efficiency mapping across the operating envelope
- Integration with the Prop Analyzer for powertrain modeling
- Visualization of motor performance characteristics

Key Classes:
------------
- MotorAnalyzer: Core calculation engine for motor performance
- MotorPlotter: Visualization tools for motor characteristics

Key Functions:
--------------
- solve_operating_point(): Find equilibrium state for given load
- get_state_at_rpm(): Calculate motor state at known RPM
- get_torque_from_current(): Convert current to torque
- generate_efficiency_map(): Create 2D efficiency surface

Example Usage:
-------------
    from src.motor_analyzer import MotorAnalyzer

    analyzer = MotorAnalyzer()

    # Add a custom motor
    analyzer.add_motor("MyMotor", {
        "kv": 1000,
        "rm_cold": 0.020,
        "i0_ref": 2.0,
        "i0_rpm_ref": 10000,
        "i_max": 50,
        "p_max": 800
    })

    # Solve operating point
    state = analyzer.solve_operating_point(
        motor_id="MyMotor",
        v_supply=14.8,
        torque_load=0.3
    )
    print(f"RPM: {state['rpm']:.0f}, Efficiency: {state['efficiency']:.1%}")

Units Convention:
----------------
- Voltage: Volts (V)
- Current: Amperes (A)
- Power: Watts (W)
- Torque: Newton-meters (Nm)
- RPM: revolutions per minute
- Resistance: Ohms (Ω)
- Temperature: Celsius (°C)
"""

from .config import MotorAnalyzerConfig
from .core import MotorAnalyzer
from .plotting import MotorPlotter

__all__ = [
    "MotorAnalyzerConfig",
    "MotorAnalyzer",
    "MotorPlotter",
]
