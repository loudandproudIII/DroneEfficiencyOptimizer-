#!/usr/bin/env python3
"""
Motor Analyzer Launcher
=======================

This script launches the Motor Analyzer graphical user interface.

Usage:
------
    python run_motor_analyzer.py

Requirements:
------------
- Python 3.8+
- tkinter (usually included with Python)
- numpy, scipy, matplotlib
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.resolve()
sys.path.insert(0, str(project_root))


def main():
    """Launch the Motor Analyzer UI."""
    print("=" * 60)
    print("  Drone Efficiency Optimizer - Motor Analyzer")
    print("=" * 60)
    print()
    print("Initializing...")

    # Check dependencies
    try:
        import numpy
        import scipy
        import matplotlib
        print(f"  [OK] numpy {numpy.__version__}")
        print(f"  [OK] scipy {scipy.__version__}")
        print(f"  [OK] matplotlib {matplotlib.__version__}")
    except ImportError as e:
        print(f"\n[ERROR] Missing dependency: {e}")
        print("\nInstall with: pip install -r requirements.txt")
        sys.exit(1)

    try:
        import tkinter
        print(f"  [OK] tkinter (Tcl/Tk {tkinter.TclVersion})")
    except ImportError:
        print("\n[ERROR] tkinter not available")
        sys.exit(1)

    print()
    print("Launching Motor Analyzer UI...")
    print("-" * 60)

    try:
        from src.ui.motor_analyzer_ui import MotorAnalyzerUI
        app = MotorAnalyzerUI()
        app.run()
    except Exception as e:
        print(f"\n[ERROR] Failed to start UI: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
