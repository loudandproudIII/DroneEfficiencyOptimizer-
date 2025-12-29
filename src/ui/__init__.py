"""
DroneEfficiencyOptimizer UI Module
==================================

This module contains user interface components for the DroneEfficiencyOptimizer
tools. Currently includes:

- PropAnalyzerUI: Simple graphical interface for propeller analysis

Future additions:
- XFL5AnalyzerUI: Interface for XFL5 airfoil analysis
- MotorAnalyzerUI: Interface for motor performance analysis
- BatteryBuilderUI: Interface for battery pack design

Usage:
------
    from src.ui import PropAnalyzerUI

    # Launch the propeller analyzer UI
    app = PropAnalyzerUI()
    app.run()
"""

from .prop_analyzer_ui import PropAnalyzerUI

__all__ = ["PropAnalyzerUI"]
