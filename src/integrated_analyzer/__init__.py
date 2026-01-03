"""
Integrated Analyzer Module
===========================

Batch analyzer that combines motor/prop optimization with battery
thermal modeling for fixed-wing FPV aircraft.

This module iterates across:
- Motor options (from motor_presets.json)
- Propeller options (from APC database)
- Battery configurations (cell type, series, parallel)
- Thermal environments

And evaluates:
- Cruise performance and efficiency
- Maximum achievable speed
- Thermal limits and margins
- Runtime estimates

Classes:
--------
- IntegratedConfig: Complete analysis configuration
- BatteryIterationConfig: Battery iteration parameters
- IntegratedResult: Single combination result
- IntegratedBatchResult: Complete batch results
- IntegratedSolver: Main solver class
- ThermalEvaluator: Thermal limit evaluator
- ResultAnalyzer: Result processing and export

Usage:
------
    from src.integrated_analyzer import (
        IntegratedSolver,
        IntegratedConfig,
        BatteryIterationConfig,
    )

    # Configure analysis
    battery_config = BatteryIterationConfig(
        cell_types=["Molicel P45B", "Samsung 40T"],
        series_range=(4, 6),
        parallel_range=(1, 3),
        thermal_environments=["drone_in_flight"],
    )

    config = IntegratedConfig(
        wing_area=0.15,
        wingspan=1.0,
        weight=1.2,
        cruise_speed=25.0,
        battery_config=battery_config,
    )

    # Run analysis
    solver = IntegratedSolver(config)
    results = solver.run_batch(progress_callback=on_progress)

    # Analyze results
    print(results.best_by_efficiency.get_summary_string())
"""

from .config import (
    BatchLimits,
    DEFAULT_LIMITS,
    BatteryIterationConfig,
    IntegratedConfig,
    ThermalEvaluation,
    SpeedPointResult,
    IntegratedResult,
    IntegratedProgress,
    IntegratedBatchResult,
)

from .thermal_evaluator import ThermalEvaluator
from .integrated_solver import IntegratedSolver
from .result_analyzer import ResultAnalyzer

__all__ = [
    # Configuration
    'BatchLimits',
    'DEFAULT_LIMITS',
    'BatteryIterationConfig',
    'IntegratedConfig',
    # Results
    'ThermalEvaluation',
    'SpeedPointResult',
    'IntegratedResult',
    'IntegratedProgress',
    'IntegratedBatchResult',
    # Classes
    'ThermalEvaluator',
    'IntegratedSolver',
    'ResultAnalyzer',
]
