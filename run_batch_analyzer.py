#!/usr/bin/env python3
"""
Batch Motor/Prop Optimizer Launcher
====================================

Launches the batch analyzer UI for finding optimal motor and propeller
combinations for fixed-wing FPV aircraft.

This tool allows you to:
- Configure your airframe (wing area, weight, drag coefficient)
- Select motor categories and size ranges to test
- Filter propellers by diameter and pitch
- Define speed range and resolution
- Run batch analysis with live progress
- View and export optimized results

Usage:
------
    python run_batch_analyzer.py

Requirements:
-------------
- Python 3.8+
- tkinter (usually included with Python)
- numpy
- scipy
- matplotlib
"""

import sys
from pathlib import Path

# Ensure the src directory is in the path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.ui.batch_analyzer_ui import main

if __name__ == "__main__":
    print("=" * 60)
    print("Batch Motor/Prop Optimizer")
    print("Fixed-Wing FPV Aircraft Analysis Tool")
    print("=" * 60)
    print()
    print("Starting batch analyzer UI...")
    print()
    main()
