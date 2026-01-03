#!/usr/bin/env python3
"""
Battery Pack Calculator Launcher
================================

Launch script for the Battery Pack Calculator GUI.

This tool calculates electrical, thermal, and physical properties
of battery packs built from 18650, 21700, or LiPo cells.

Features:
- Cell library with verified specifications from Battery Mooch
- Pack configuration (1S-12S, 1P-8P)
- Voltage sag and internal resistance calculations
- Thermal analysis (heat generation, temperature rise)
- Optional physical layout (dimensions, center of gravity)
- Energy and runtime estimates

Usage:
    python run_battery_calculator.py

Requirements:
    - Python 3.8+
    - tkinter (usually included with Python)
    - matplotlib
    - numpy
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.ui.battery_calculator_ui import BatteryCalculatorUI


def main():
    """Launch the Battery Pack Calculator UI."""
    print("=" * 60)
    print("Battery Pack Calculator")
    print("=" * 60)
    print()
    print("Loading GUI...")
    print()

    app = BatteryCalculatorUI()
    app.run()


if __name__ == "__main__":
    main()


