"""
Flight Analyzer Module
======================

This module provides complete flight performance analysis by integrating:
- Airframe drag modeling
- Propeller performance (from prop_analyzer)
- Motor performance (from motor_analyzer)

The module solves for equilibrium flight conditions and calculates
system efficiency, power requirements, and flight endurance.

Key Classes:
------------
- DragModel: Airframe drag calculation methods
- FlightSolver: Equilibrium solver for complete powertrain
- FlightAnalyzer: High-level analysis interface

Drag Calculation Methods:
------------------------
1. Raw drag input (direct N value)
2. Parasitic drag: D = 0.5 × ρ × V² × Cd × A
3. Fixed-wing total drag with induced drag component

Example Usage:
-------------
    from src.flight_analyzer import FlightAnalyzer

    analyzer = FlightAnalyzer()

    # Configure aircraft
    analyzer.set_drag_model(
        method="coefficient",
        cd=0.035,
        reference_area=0.5,  # m²
    )

    # Solve flight condition
    result = analyzer.solve_cruise(
        motor_id="Scorpion SII-3014-830",
        prop_id="10x5",
        v_battery=22.2,
        airspeed=25.0,  # m/s
        altitude=0
    )

    print(f"Throttle: {result['throttle']:.1f}%")
    print(f"Current: {result['current']:.1f} A")
    print(f"System Efficiency: {result['system_efficiency']:.1%}")

Units Convention:
----------------
- Velocity: m/s
- Drag/Thrust: Newtons (N)
- Area: m² (square meters)
- Density: kg/m³
- Altitude: meters
- Power: Watts
"""

from .config import FlightAnalyzerConfig, AIR_DENSITY_SEA_LEVEL
from .drag_model import DragModel
from .flight_solver import FlightSolver, FlightResult

__all__ = [
    "DragModel",
    "FlightSolver",
    "FlightResult",
    "FlightAnalyzerConfig",
    "AIR_DENSITY_SEA_LEVEL",
]
