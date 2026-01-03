"""
DroneEfficiencyOptimizer UI Module
==================================

This module contains user interface components for the DroneEfficiencyOptimizer
tools. Currently includes:

- PropAnalyzerUI: Graphical interface for propeller analysis
- MotorAnalyzerUI: Graphical interface for motor performance analysis
- PowertrainUI: Combined motor + propeller analysis with bidirectional solving
- BatteryCalculatorUI: Interface for battery pack design and analysis

Usage:
------
    from src.ui import PropAnalyzerUI, MotorAnalyzerUI, PowertrainUI, BatteryCalculatorUI

    # Launch individual tools
    PropAnalyzerUI().run()
    MotorAnalyzerUI().run()
    BatteryCalculatorUI().run()

    # Launch combined powertrain analyzer
    PowertrainUI().run()
"""

from .prop_analyzer_ui import PropAnalyzerUI
from .motor_analyzer_ui import MotorAnalyzerUI
from .powertrain_ui import PowertrainUI
from .battery_calculator_ui import BatteryCalculatorUI

__all__ = [
    "PropAnalyzerUI",
    "MotorAnalyzerUI",
    "PowertrainUI",
    "BatteryCalculatorUI",
]
