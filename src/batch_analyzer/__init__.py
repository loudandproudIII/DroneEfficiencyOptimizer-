"""
Batch Analyzer Module
=====================

This module provides batch processing capabilities for finding optimal
motor and propeller combinations for fixed-wing FPV aircraft.

Classes:
--------
- BatchConfig: Configuration for batch analysis
- BatchResult: Single result from batch calculation
- BatchSolver: Main batch processing engine

Usage:
------
    from src.batch_analyzer import BatchSolver, BatchConfig

    config = BatchConfig(
        wing_area=0.15,
        wingspan=1.0,
        weight=1.0,
        cd0=0.025,
        voltage=14.8,
        speed_range=(10, 30),
        speed_step=2.0
    )

    solver = BatchSolver(config)
    print(f"Testing {solver.get_permutation_count()} combinations")

    results = solver.run_batch(progress_callback=my_callback)
    best = solver.find_best_combinations(results, top_n=10)
"""

from .config import BatchConfig, BatchResult, DEFAULT_LIMITS
from .batch_solver import BatchSolver

__all__ = [
    "BatchConfig",
    "BatchResult",
    "BatchSolver",
    "DEFAULT_LIMITS",
]
