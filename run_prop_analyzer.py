#!/usr/bin/env python3
"""
Propeller Analyzer Launcher
===========================

This script launches the Propeller Analyzer graphical user interface.

Usage:
------
    # From the project root directory:
    python run_prop_analyzer.py

    # Or if using a virtual environment:
    source venv/bin/activate  # Linux/Mac
    python run_prop_analyzer.py

Requirements:
------------
- Python 3.8+
- tkinter (usually included with Python)
- numpy
- pandas
- scipy
- matplotlib

The script automatically adds the src directory to the Python path
for proper module imports.
"""

import sys
from pathlib import Path

# -------------------------------------------------------------------------
# Path Configuration
# -------------------------------------------------------------------------

# Add the project root to the Python path
# This ensures imports work correctly regardless of where the script is run from
project_root = Path(__file__).parent.resolve()
sys.path.insert(0, str(project_root))

# -------------------------------------------------------------------------
# Main Entry Point
# -------------------------------------------------------------------------

def main():
    """
    Main function to launch the Propeller Analyzer UI.

    This function:
    1. Validates that required dependencies are available
    2. Creates and launches the PropAnalyzerUI application
    3. Handles any startup errors gracefully
    """
    print("=" * 60)
    print("  Drone Efficiency Optimizer - Propeller Analyzer")
    print("=" * 60)
    print()
    print("Initializing...")

    # Check for required dependencies
    try:
        import numpy
        import pandas
        import scipy
        import matplotlib
        print(f"  [OK] numpy {numpy.__version__}")
        print(f"  [OK] pandas {pandas.__version__}")
        print(f"  [OK] scipy {scipy.__version__}")
        print(f"  [OK] matplotlib {matplotlib.__version__}")
    except ImportError as e:
        print(f"\n[ERROR] Missing required dependency: {e}")
        print("\nPlease install dependencies using:")
        print("    pip install -r requirements.txt")
        sys.exit(1)

    # Check for tkinter
    try:
        import tkinter
        print(f"  [OK] tkinter (Tcl/Tk {tkinter.TclVersion})")
    except ImportError:
        print("\n[ERROR] tkinter is not available")
        print("\nPlease install tkinter:")
        print("  Ubuntu/Debian: sudo apt-get install python3-tk")
        print("  Fedora: sudo dnf install python3-tkinter")
        print("  macOS: brew install python-tk")
        sys.exit(1)

    print()
    print("Launching Propeller Analyzer UI...")
    print("-" * 60)

    # Import and launch the UI
    try:
        from src.ui.prop_analyzer_ui import PropAnalyzerUI

        app = PropAnalyzerUI()
        app.run()

    except FileNotFoundError as e:
        print(f"\n[ERROR] Data files not found: {e}")
        print("\nPlease ensure the 'Prop analysis Tool' directory contains:")
        print("  - 20_APC_interpolator_files/ (interpolator pickle files)")
        print("  - APC-Prop-DB.pkl (propeller database)")
        sys.exit(1)

    except Exception as e:
        print(f"\n[ERROR] Failed to start UI: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
