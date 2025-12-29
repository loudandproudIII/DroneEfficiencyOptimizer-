"""
DroneEfficiencyOptimizer UI Module
==================================

This module contains user interface components for the DroneEfficiencyOptimizer
tools. Currently includes:

- PropAnalyzerUI: Graphical interface for propeller analysis
- MotorAnalyzerUI: Graphical interface for motor performance analysis
- PowertrainUI: Combined motor + propeller analysis with bidirectional solving

Future additions:
- XFL5AnalyzerUI: Interface for XFL5 airfoil analysis
- BatteryBuilderUI: Interface for battery pack design

Usage:
------
    from src.ui import PropAnalyzerUI, MotorAnalyzerUI, PowertrainUI

    # Launch individual tools
    PropAnalyzerUI().run()
    MotorAnalyzerUI().run()

    # Launch combined powertrain analyzer
    PowertrainUI().run()
"""

from .prop_analyzer_ui import PropAnalyzerUI
from .motor_analyzer_ui import MotorAnalyzerUI
from .powertrain_ui import PowertrainUI

__all__ = [
    "PropAnalyzerUI",
    "MotorAnalyzerUI",
    "PowertrainUI",
]
