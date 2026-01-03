#!/usr/bin/env python3
"""
Integrated Motor/Prop/Battery Analyzer Launcher
=================================================

Entry point for the integrated batch analyzer that combines motor/prop
optimization with battery thermal modeling.

Usage:
------
    python run_integrated_analyzer.py

Features:
---------
- Batch analysis across motor, propeller, and battery configurations
- Thermal limit evaluation at cruise and max speed
- Multi-tab UI with comparison matrix and drill-down
- Export to CSV and JSON

Requirements:
-------------
- Python 3.8+
- tkinter (usually included with Python)
- matplotlib
- numpy
"""

import sys
import multiprocessing
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.ui.integrated_analyzer_ui import IntegratedAnalyzerUI


def main():
    """Launch the Integrated Analyzer UI."""
    print("=" * 60)
    print("Integrated Motor/Prop/Battery Analyzer")
    print("=" * 60)
    print()
    print(f"Using {multiprocessing.cpu_count()} CPU cores for batch processing")
    print()
    print("Starting GUI...")
    print()

    app = IntegratedAnalyzerUI()
    app.run()


if __name__ == "__main__":
    # Required for Windows multiprocessing support
    multiprocessing.freeze_support()
    main()
