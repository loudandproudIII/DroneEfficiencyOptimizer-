#!/usr/bin/env python3
"""
Fixed-Wing FPV Flight Analyzer Launcher
========================================

Launch script for the Fixed-Wing FPV Flight Performance Analyzer GUI.

This application analyzes fixed-wing FPV aircraft performance by combining:
- Airframe drag modeling (parasitic + induced drag)
- FPV motor performance analysis with preset library (2807, 3315, etc.)
- Propeller performance analysis
- Flight equilibrium solving

Usage:
------
    python run_flight_analyzer.py

Requirements:
------------
    - Python 3.8+
    - tkinter (usually included with Python)
    - matplotlib
    - numpy
    - scipy
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Check for required dependencies
def check_dependencies():
    """Check that all required packages are installed."""
    missing = []

    try:
        import tkinter
    except ImportError:
        missing.append("tkinter")

    try:
        import matplotlib
    except ImportError:
        missing.append("matplotlib")

    try:
        import numpy
    except ImportError:
        missing.append("numpy")

    try:
        import scipy
    except ImportError:
        missing.append("scipy")

    if missing:
        print("Missing required packages:")
        for pkg in missing:
            print(f"  - {pkg}")
        print("\nInstall with: pip install -r requirements.txt")
        sys.exit(1)


def main():
    """Launch the Flight Analyzer UI."""
    print("=" * 60)
    print("  Fixed-Wing FPV Flight Analyzer")
    print("=" * 60)
    print()
    print("Checking dependencies...")
    check_dependencies()
    print("All dependencies OK.")
    print()
    print("Starting Flight Analyzer UI...")
    print("(Close the window to exit)")
    print()

    # Import and launch
    from src.ui.flight_analyzer_ui import FlightAnalyzerUI

    app = FlightAnalyzerUI()
    app.run()


if __name__ == "__main__":
    main()
