"""
Fixed-Wing FPV Flight Analyzer User Interface
==============================================

This module provides a comprehensive graphical user interface (GUI) for
analyzing fixed-wing FPV aircraft performance, combining:
- Airframe drag modeling (parasitic + induced drag)
- Motor performance analysis with FPV motor preset library
- Propeller performance analysis
- Flight equilibrium solving

The UI solves for the complete flight condition: throttle, current, and
system efficiency required to maintain level cruise at a given airspeed.

Features:
---------
- Drag input: Raw drag value OR calculated from Cd × Area
- Motor preset selection for FPV fixed-wing motors (2807, 3315, etc.)
- Propeller selection from available database
- Speed sweep for performance envelope
- System efficiency visualization

Usage:
------
    from src.ui.flight_analyzer_ui import FlightAnalyzerUI

    app = FlightAnalyzerUI()
    app.run()

Theory:
-------
For level cruise flight:
    Thrust = Drag

Where:
    Parasitic Drag = 0.5 × ρ × V² × Cd × A
    Induced Drag = 0.5 × ρ × V² × CL² / (π × AR × e)  (for fixed-wing)
    Total Drag = Parasitic + Induced

System efficiency:
    η_system = (Thrust × Velocity) / Battery_Power
"""

import tkinter as tk
from tkinter import ttk, messagebox
import json
from typing import Optional, Dict, Any, List
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import matplotlib with TkAgg backend
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

# Import analyzer modules
from src.motor_analyzer.core import MotorAnalyzer
from src.motor_analyzer.config import MotorAnalyzerConfig
from src.prop_analyzer.core import PropAnalyzer
from src.prop_analyzer.config import PropAnalyzerConfig
from src.flight_analyzer.drag_model import DragModel
from src.flight_analyzer.flight_solver import FlightSolver, FlightResult
from src.flight_analyzer.config import FlightAnalyzerConfig, AIR_DENSITY_SEA_LEVEL


class FlightAnalyzerUI:
    """
    Fixed-wing FPV flight analyzer GUI combining drag, motor, and prop analysis.

    This interface allows users to:
    1. Configure airframe drag (raw value OR from coefficients)
    2. Select motor from FPV fixed-wing preset library
    3. Select propeller
    4. Set flight conditions (voltage, airspeed, altitude)
    5. Solve for equilibrium (throttle, current, efficiency)
    6. Visualize performance across speed range
    """

    # =========================================================================
    # UI Constants
    # =========================================================================

    WINDOW_TITLE = "Fixed-Wing FPV Flight Analyzer"
    WINDOW_MIN_WIDTH = 1300
    WINDOW_MIN_HEIGHT = 900

    FRAME_PADDING = 10
    WIDGET_PADDING = 3
    SECTION_PADDING = 5

    # Common battery configurations for FPV fixed-wing (cells × nominal voltage)
    BATTERY_OPTIONS = {
        "3S (11.1V)": 11.1,
        "4S (14.8V)": 14.8,
        "5S (18.5V)": 18.5,
        "6S (22.2V)": 22.2,
    }

    def __init__(self):
        """Initialize the Flight Analyzer UI."""
        # =====================================================================
        # Initialize Backend Analyzers
        # =====================================================================

        self.motor_config = MotorAnalyzerConfig()
        self.prop_config = PropAnalyzerConfig()
        self.flight_config = FlightAnalyzerConfig()

        self.motor_analyzer = MotorAnalyzer(self.motor_config)
        self.prop_analyzer = PropAnalyzer(self.prop_config)
        self.flight_solver = FlightSolver(self.flight_config)

        # Load motor presets
        self.presets = self._load_motor_presets()
        self.motor_categories = list(self.presets.get("categories", {}).keys())
        self.motors = self.presets.get("motors", {})

        # Load available propellers
        self.available_props = self._get_available_props()

        # Store current result for plotting
        self.current_result: Optional[FlightResult] = None
        self.speed_sweep_results: List[FlightResult] = []

        # =====================================================================
        # Create Main Window
        # =====================================================================

        self.root = tk.Tk()
        self.root.title(self.WINDOW_TITLE)
        self.root.minsize(self.WINDOW_MIN_WIDTH, self.WINDOW_MIN_HEIGHT)

        # Configure grid weights for resizing
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # Main container frame
        self.main_frame = ttk.Frame(self.root, padding=self.FRAME_PADDING)
        self.main_frame.grid(row=0, column=0, sticky="nsew")

        # Configure main frame grid
        self.main_frame.columnconfigure(0, weight=0)  # Left panel (inputs)
        self.main_frame.columnconfigure(1, weight=1)  # Right panel (results/plots)
        self.main_frame.rowconfigure(1, weight=1)     # Main content row

        # Build UI sections
        self._create_header()
        self._create_left_panel()
        self._create_right_panel()
        self._create_status_bar()

        # Set defaults
        self._set_defaults()

    # =========================================================================
    # Data Loading Methods
    # =========================================================================

    def _load_motor_presets(self) -> Dict[str, Any]:
        """
        Load motor presets from JSON file.

        Returns:
        -------
        dict
            Motor preset data with categories and motor parameters
        """
        preset_path = self.motor_config.data_root / "motor_presets.json"

        if preset_path.exists():
            try:
                with open(preset_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Could not load motor presets: {e}")

        # Fall back to motor_database.json
        db_path = self.motor_config.database_path
        if db_path.exists():
            try:
                with open(db_path, 'r') as f:
                    data = json.load(f)
                    return {
                        "categories": {"All Motors": list(data.get("motors", {}).keys())},
                        "motors": data.get("motors", {})
                    }
            except Exception as e:
                print(f"Warning: Could not load motor database: {e}")

        return {"categories": {}, "motors": {}}

    def _get_available_props(self) -> List[str]:
        """
        Get list of available propeller identifiers.

        Returns:
        -------
        list
            List of prop ID strings (e.g., "10x5", "11x7")
        """
        try:
            return self.prop_analyzer.list_available_props()
        except Exception:
            # Return common sizes as fallback
            return [
                "8x4", "9x4.5", "9x6", "10x4.5", "10x5", "10x7",
                "11x4.5", "11x5.5", "11x7", "12x4", "12x6",
                "13x4.5", "13x6.5", "14x4.8", "14x7", "15x5", "15x8"
            ]

    # =========================================================================
    # UI Construction Methods
    # =========================================================================

    def _create_header(self):
        """Create the header section with title and description."""
        header_frame = ttk.Frame(self.main_frame)
        header_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        # Title
        title_label = ttk.Label(
            header_frame,
            text="Fixed-Wing FPV Flight Analyzer",
            font=("Helvetica", 18, "bold")
        )
        title_label.pack(anchor="w")

        # Description
        desc_label = ttk.Label(
            header_frame,
            text="Analyze cruise performance: Throttle, Current, Power, and System Efficiency",
            font=("Helvetica", 10)
        )
        desc_label.pack(anchor="w")

    def _create_left_panel(self):
        """Create the left panel containing all input sections."""
        # Scrollable left panel
        left_canvas = tk.Canvas(self.main_frame, width=450)
        left_scrollbar = ttk.Scrollbar(self.main_frame, orient="vertical", command=left_canvas.yview)
        left_frame = ttk.Frame(left_canvas)

        left_frame.bind(
            "<Configure>",
            lambda e: left_canvas.configure(scrollregion=left_canvas.bbox("all"))
        )

        left_canvas.create_window((0, 0), window=left_frame, anchor="nw")
        left_canvas.configure(yscrollcommand=left_scrollbar.set)

        left_canvas.grid(row=1, column=0, sticky="nsew", padx=(0, 5))
        left_scrollbar.grid(row=1, column=0, sticky="nse", padx=(0, 5))

        # Build input sections
        self._create_drag_section(left_frame)
        self._create_motor_section(left_frame)
        self._create_prop_section(left_frame)
        self._create_flight_conditions_section(left_frame)
        self._create_action_buttons(left_frame)

    def _create_drag_section(self, parent):
        """
        Create the drag configuration section.

        Allows user to input drag as:
        - Raw value (Newtons)
        - OR calculate from Cd × Reference Area
        """
        frame = ttk.LabelFrame(parent, text="Airframe Drag Configuration", padding=self.SECTION_PADDING)
        frame.pack(fill="x", pady=self.WIDGET_PADDING, padx=self.WIDGET_PADDING)

        # Drag method selection
        method_frame = ttk.Frame(frame)
        method_frame.pack(fill="x", pady=2)

        ttk.Label(method_frame, text="Drag Method:").pack(side="left")

        self.drag_method_var = tk.StringVar(value="coefficient")
        method_combo = ttk.Combobox(
            method_frame,
            textvariable=self.drag_method_var,
            values=["coefficient", "raw", "flat_plate", "fixed_wing"],
            state="readonly",
            width=15
        )
        method_combo.pack(side="left", padx=5)
        method_combo.bind("<<ComboboxSelected>>", self._on_drag_method_change)

        # Create notebook for different drag input methods
        self.drag_notebook = ttk.Notebook(frame)
        self.drag_notebook.pack(fill="x", pady=5)

        # Tab 1: Coefficient Method (simple parasitic drag)
        coef_frame = ttk.Frame(self.drag_notebook, padding=5)
        self.drag_notebook.add(coef_frame, text="Cd × Area")

        # Drag coefficient
        row1 = ttk.Frame(coef_frame)
        row1.pack(fill="x", pady=2)
        ttk.Label(row1, text="Drag Coefficient (Cd):", width=22).pack(side="left")
        self.cd_var = tk.StringVar(value="0.04")
        ttk.Entry(row1, textvariable=self.cd_var, width=12).pack(side="left")
        ttk.Label(row1, text="(0.02-0.08 typical)").pack(side="left", padx=5)

        # Reference area (wing area for aircraft)
        row2 = ttk.Frame(coef_frame)
        row2.pack(fill="x", pady=2)
        ttk.Label(row2, text="Wing Area:", width=22).pack(side="left")
        self.ref_area_var = tk.StringVar(value="0.15")
        ttk.Entry(row2, textvariable=self.ref_area_var, width=12).pack(side="left")
        ttk.Label(row2, text="m²").pack(side="left", padx=5)

        # Tab 2: Raw Drag
        raw_frame = ttk.Frame(self.drag_notebook, padding=5)
        self.drag_notebook.add(raw_frame, text="Raw Value")

        row_raw = ttk.Frame(raw_frame)
        row_raw.pack(fill="x", pady=2)
        ttk.Label(row_raw, text="Drag Force:", width=22).pack(side="left")
        self.raw_drag_var = tk.StringVar(value="0.5")
        ttk.Entry(row_raw, textvariable=self.raw_drag_var, width=12).pack(side="left")
        ttk.Label(row_raw, text="N").pack(side="left", padx=5)

        # Tab 3: Flat Plate Equivalent
        flat_frame = ttk.Frame(self.drag_notebook, padding=5)
        self.drag_notebook.add(flat_frame, text="Flat Plate")

        row_flat = ttk.Frame(flat_frame)
        row_flat.pack(fill="x", pady=2)
        ttk.Label(row_flat, text="Flat Plate Area (f):", width=22).pack(side="left")
        self.flat_plate_var = tk.StringVar(value="0.006")
        ttk.Entry(row_flat, textvariable=self.flat_plate_var, width=12).pack(side="left")
        ttk.Label(row_flat, text="m² (Cd × A)").pack(side="left", padx=5)

        # Tab 4: Fixed-Wing with Induced Drag
        fw_frame = ttk.Frame(self.drag_notebook, padding=5)
        self.drag_notebook.add(fw_frame, text="Fixed-Wing")

        # Wing area
        row_wing = ttk.Frame(fw_frame)
        row_wing.pack(fill="x", pady=2)
        ttk.Label(row_wing, text="Wing Area:", width=22).pack(side="left")
        self.wing_area_var = tk.StringVar(value="0.15")
        ttk.Entry(row_wing, textvariable=self.wing_area_var, width=12).pack(side="left")
        ttk.Label(row_wing, text="m²").pack(side="left", padx=5)

        # Wingspan
        row_span = ttk.Frame(fw_frame)
        row_span.pack(fill="x", pady=2)
        ttk.Label(row_span, text="Wingspan:", width=22).pack(side="left")
        self.wingspan_var = tk.StringVar(value="1.0")
        ttk.Entry(row_span, textvariable=self.wingspan_var, width=12).pack(side="left")
        ttk.Label(row_span, text="m").pack(side="left", padx=5)

        # Aircraft weight (for induced drag calculation)
        row_weight = ttk.Frame(fw_frame)
        row_weight.pack(fill="x", pady=2)
        ttk.Label(row_weight, text="Aircraft Weight:", width=22).pack(side="left")
        self.weight_var = tk.StringVar(value="1.0")
        ttk.Entry(row_weight, textvariable=self.weight_var, width=12).pack(side="left")
        ttk.Label(row_weight, text="kg").pack(side="left", padx=5)

        # Parasitic drag coefficient (Cd0)
        row_cd0 = ttk.Frame(fw_frame)
        row_cd0.pack(fill="x", pady=2)
        ttk.Label(row_cd0, text="Cd0 (parasitic):", width=22).pack(side="left")
        self.cd0_var = tk.StringVar(value="0.025")
        ttk.Entry(row_cd0, textvariable=self.cd0_var, width=12).pack(side="left")
        ttk.Label(row_cd0, text="(0.02-0.04)").pack(side="left", padx=5)

        # Oswald efficiency
        row_oswald = ttk.Frame(fw_frame)
        row_oswald.pack(fill="x", pady=2)
        ttk.Label(row_oswald, text="Oswald Efficiency (e):", width=22).pack(side="left")
        self.oswald_var = tk.StringVar(value="0.8")
        ttk.Entry(row_oswald, textvariable=self.oswald_var, width=12).pack(side="left")
        ttk.Label(row_oswald, text="(0.7-0.85)").pack(side="left", padx=5)

        # Altitude (affects air density)
        alt_frame = ttk.Frame(frame)
        alt_frame.pack(fill="x", pady=2)
        ttk.Label(alt_frame, text="Altitude:", width=22).pack(side="left")
        self.altitude_var = tk.StringVar(value="0")
        ttk.Entry(alt_frame, textvariable=self.altitude_var, width=12).pack(side="left")
        ttk.Label(alt_frame, text="m ASL").pack(side="left", padx=5)

    def _create_motor_section(self, parent):
        """Create the motor configuration section with preset selection."""
        frame = ttk.LabelFrame(parent, text="Motor Configuration", padding=self.SECTION_PADDING)
        frame.pack(fill="x", pady=self.WIDGET_PADDING, padx=self.WIDGET_PADDING)

        # Category selection
        cat_frame = ttk.Frame(frame)
        cat_frame.pack(fill="x", pady=2)
        ttk.Label(cat_frame, text="Category:", width=18).pack(side="left")
        self.motor_category_var = tk.StringVar()
        cat_combo = ttk.Combobox(
            cat_frame,
            textvariable=self.motor_category_var,
            values=self.motor_categories,
            state="readonly",
            width=28
        )
        cat_combo.pack(side="left", padx=5)
        cat_combo.bind("<<ComboboxSelected>>", self._on_motor_category_change)

        # Motor preset selection
        preset_frame = ttk.Frame(frame)
        preset_frame.pack(fill="x", pady=2)
        ttk.Label(preset_frame, text="Motor Preset:", width=18).pack(side="left")
        self.motor_preset_var = tk.StringVar()
        self.motor_preset_combo = ttk.Combobox(
            preset_frame,
            textvariable=self.motor_preset_var,
            state="readonly",
            width=28
        )
        self.motor_preset_combo.pack(side="left", padx=5)
        self.motor_preset_combo.bind("<<ComboboxSelected>>", self._on_motor_preset_change)

        # Separator
        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=5)

        # Motor parameters (auto-filled from preset, editable)
        params_label = ttk.Label(frame, text="Motor Parameters (editable):", font=("Helvetica", 9, "italic"))
        params_label.pack(anchor="w")

        # KV
        kv_frame = ttk.Frame(frame)
        kv_frame.pack(fill="x", pady=2)
        ttk.Label(kv_frame, text="KV:", width=18).pack(side="left")
        self.motor_kv_var = tk.StringVar(value="900")
        ttk.Entry(kv_frame, textvariable=self.motor_kv_var, width=12).pack(side="left")
        ttk.Label(kv_frame, text="RPM/V").pack(side="left", padx=5)

        # Resistance
        rm_frame = ttk.Frame(frame)
        rm_frame.pack(fill="x", pady=2)
        ttk.Label(rm_frame, text="Rm (cold):", width=18).pack(side="left")
        self.motor_rm_var = tk.StringVar(value="0.030")
        ttk.Entry(rm_frame, textvariable=self.motor_rm_var, width=12).pack(side="left")
        ttk.Label(rm_frame, text="Ω").pack(side="left", padx=5)

        # No-load current
        i0_frame = ttk.Frame(frame)
        i0_frame.pack(fill="x", pady=2)
        ttk.Label(i0_frame, text="I0 (no-load):", width=18).pack(side="left")
        self.motor_i0_var = tk.StringVar(value="1.5")
        ttk.Entry(i0_frame, textvariable=self.motor_i0_var, width=12).pack(side="left")
        ttk.Label(i0_frame, text="A").pack(side="left", padx=5)

        # I0 reference RPM
        i0rpm_frame = ttk.Frame(frame)
        i0rpm_frame.pack(fill="x", pady=2)
        ttk.Label(i0rpm_frame, text="I0 ref RPM:", width=18).pack(side="left")
        self.motor_i0rpm_var = tk.StringVar(value="9000")
        ttk.Entry(i0rpm_frame, textvariable=self.motor_i0rpm_var, width=12).pack(side="left")
        ttk.Label(i0rpm_frame, text="RPM").pack(side="left", padx=5)

        # Max current
        imax_frame = ttk.Frame(frame)
        imax_frame.pack(fill="x", pady=2)
        ttk.Label(imax_frame, text="I max:", width=18).pack(side="left")
        self.motor_imax_var = tk.StringVar(value="40")
        ttk.Entry(imax_frame, textvariable=self.motor_imax_var, width=12).pack(side="left")
        ttk.Label(imax_frame, text="A").pack(side="left", padx=5)

        # Winding temperature
        temp_frame = ttk.Frame(frame)
        temp_frame.pack(fill="x", pady=2)
        ttk.Label(temp_frame, text="Winding Temp:", width=18).pack(side="left")
        self.winding_temp_var = tk.StringVar(value="80")
        ttk.Entry(temp_frame, textvariable=self.winding_temp_var, width=12).pack(side="left")
        ttk.Label(temp_frame, text="°C").pack(side="left", padx=5)

    def _create_prop_section(self, parent):
        """Create the propeller selection section."""
        frame = ttk.LabelFrame(parent, text="Propeller Configuration", padding=self.SECTION_PADDING)
        frame.pack(fill="x", pady=self.WIDGET_PADDING, padx=self.WIDGET_PADDING)

        # Prop selection
        prop_frame = ttk.Frame(frame)
        prop_frame.pack(fill="x", pady=2)
        ttk.Label(prop_frame, text="Propeller:", width=18).pack(side="left")
        self.prop_var = tk.StringVar()
        prop_combo = ttk.Combobox(
            prop_frame,
            textvariable=self.prop_var,
            values=self.available_props,
            state="readonly",
            width=15
        )
        prop_combo.pack(side="left", padx=5)
        ttk.Label(prop_frame, text="(diameter × pitch)").pack(side="left")

    def _create_flight_conditions_section(self, parent):
        """Create the flight conditions section."""
        frame = ttk.LabelFrame(parent, text="Flight Conditions", padding=self.SECTION_PADDING)
        frame.pack(fill="x", pady=self.WIDGET_PADDING, padx=self.WIDGET_PADDING)

        # Battery selection
        batt_frame = ttk.Frame(frame)
        batt_frame.pack(fill="x", pady=2)
        ttk.Label(batt_frame, text="Battery Config:", width=18).pack(side="left")
        self.battery_var = tk.StringVar()
        batt_combo = ttk.Combobox(
            batt_frame,
            textvariable=self.battery_var,
            values=list(self.BATTERY_OPTIONS.keys()),
            state="readonly",
            width=15
        )
        batt_combo.pack(side="left", padx=5)
        batt_combo.bind("<<ComboboxSelected>>", self._on_battery_change)

        # Custom voltage
        volt_frame = ttk.Frame(frame)
        volt_frame.pack(fill="x", pady=2)
        ttk.Label(volt_frame, text="Voltage:", width=18).pack(side="left")
        self.voltage_var = tk.StringVar(value="14.8")
        ttk.Entry(volt_frame, textvariable=self.voltage_var, width=12).pack(side="left")
        ttk.Label(volt_frame, text="V").pack(side="left", padx=5)

        # Target airspeed
        speed_frame = ttk.Frame(frame)
        speed_frame.pack(fill="x", pady=2)
        ttk.Label(speed_frame, text="Target Airspeed:", width=18).pack(side="left")
        self.airspeed_var = tk.StringVar(value="15.0")
        ttk.Entry(speed_frame, textvariable=self.airspeed_var, width=12).pack(side="left")
        ttk.Label(speed_frame, text="m/s").pack(side="left", padx=5)

        # Speed conversion helper
        conv_frame = ttk.Frame(frame)
        conv_frame.pack(fill="x", pady=2)
        ttk.Label(conv_frame, text="", width=18).pack(side="left")
        self.speed_mph_label = ttk.Label(conv_frame, text="(33.6 mph / 54.0 km/h)", font=("Helvetica", 8))
        self.speed_mph_label.pack(side="left")

        # Bind speed entry to update conversion
        self.airspeed_var.trace_add("write", self._update_speed_conversion)

    def _create_action_buttons(self, parent):
        """Create action buttons for calculations."""
        frame = ttk.Frame(parent)
        frame.pack(fill="x", pady=10, padx=self.WIDGET_PADDING)

        # Main solve button
        self.solve_btn = ttk.Button(
            frame,
            text="⚡ Solve Equilibrium",
            command=self._solve_equilibrium,
            width=20
        )
        self.solve_btn.pack(side="left", padx=5)

        # Speed sweep button
        self.sweep_btn = ttk.Button(
            frame,
            text="📊 Speed Sweep",
            command=self._run_speed_sweep,
            width=15
        )
        self.sweep_btn.pack(side="left", padx=5)

        # Find max speed button
        self.max_speed_btn = ttk.Button(
            frame,
            text="🚀 Max Speed",
            command=self._find_max_speed,
            width=12
        )
        self.max_speed_btn.pack(side="left", padx=5)

    def _create_right_panel(self):
        """Create the right panel with results and plots."""
        right_frame = ttk.Frame(self.main_frame)
        right_frame.grid(row=1, column=1, sticky="nsew", padx=(5, 0))

        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(1, weight=1)

        # Results section
        self._create_results_section(right_frame)

        # Plot section
        self._create_plot_section(right_frame)

    def _create_results_section(self, parent):
        """Create the results display section."""
        frame = ttk.LabelFrame(parent, text="Results", padding=self.SECTION_PADDING)
        frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))

        # Results in two columns
        results_frame = ttk.Frame(frame)
        results_frame.pack(fill="x")

        # Left column - Primary results
        left_col = ttk.Frame(results_frame)
        left_col.pack(side="left", fill="x", expand=True, padx=5)

        # Throttle
        row1 = ttk.Frame(left_col)
        row1.pack(fill="x", pady=1)
        ttk.Label(row1, text="Throttle:", width=14, font=("Helvetica", 10, "bold")).pack(side="left")
        self.result_throttle_var = tk.StringVar(value="--")
        ttk.Label(row1, textvariable=self.result_throttle_var, font=("Helvetica", 12, "bold"), foreground="blue").pack(side="left")

        # Current (total)
        row2 = ttk.Frame(left_col)
        row2.pack(fill="x", pady=1)
        ttk.Label(row2, text="Total Current:", width=14).pack(side="left")
        self.result_current_var = tk.StringVar(value="--")
        ttk.Label(row2, textvariable=self.result_current_var, font=("Helvetica", 10)).pack(side="left")

        # Power
        row3 = ttk.Frame(left_col)
        row3.pack(fill="x", pady=1)
        ttk.Label(row3, text="Battery Power:", width=14).pack(side="left")
        self.result_power_var = tk.StringVar(value="--")
        ttk.Label(row3, textvariable=self.result_power_var, font=("Helvetica", 10)).pack(side="left")

        # System efficiency
        row4 = ttk.Frame(left_col)
        row4.pack(fill="x", pady=1)
        ttk.Label(row4, text="System Eff:", width=14, font=("Helvetica", 10, "bold")).pack(side="left")
        self.result_sys_eff_var = tk.StringVar(value="--")
        ttk.Label(row4, textvariable=self.result_sys_eff_var, font=("Helvetica", 12, "bold"), foreground="green").pack(side="left")

        # Right column - Component results
        right_col = ttk.Frame(results_frame)
        right_col.pack(side="left", fill="x", expand=True, padx=5)

        # Drag
        row5 = ttk.Frame(right_col)
        row5.pack(fill="x", pady=1)
        ttk.Label(row5, text="Drag/Thrust:", width=14).pack(side="left")
        self.result_drag_var = tk.StringVar(value="--")
        ttk.Label(row5, textvariable=self.result_drag_var).pack(side="left")

        # RPM
        row6 = ttk.Frame(right_col)
        row6.pack(fill="x", pady=1)
        ttk.Label(row6, text="Prop RPM:", width=14).pack(side="left")
        self.result_rpm_var = tk.StringVar(value="--")
        ttk.Label(row6, textvariable=self.result_rpm_var).pack(side="left")

        # Motor efficiency
        row7 = ttk.Frame(right_col)
        row7.pack(fill="x", pady=1)
        ttk.Label(row7, text="Motor Eff:", width=14).pack(side="left")
        self.result_motor_eff_var = tk.StringVar(value="--")
        ttk.Label(row7, textvariable=self.result_motor_eff_var).pack(side="left")

        # Prop efficiency
        row8 = ttk.Frame(right_col)
        row8.pack(fill="x", pady=1)
        ttk.Label(row8, text="Prop Eff:", width=14).pack(side="left")
        self.result_prop_eff_var = tk.StringVar(value="--")
        ttk.Label(row8, textvariable=self.result_prop_eff_var).pack(side="left")

        # Status/warning message
        self.result_status_var = tk.StringVar(value="")
        status_label = ttk.Label(frame, textvariable=self.result_status_var, foreground="red")
        status_label.pack(anchor="w", pady=(5, 0))

    def _create_plot_section(self, parent):
        """Create the plot visualization section."""
        frame = ttk.LabelFrame(parent, text="Performance Visualization", padding=self.SECTION_PADDING)
        frame.grid(row=1, column=0, sticky="nsew")

        # Create matplotlib figure
        self.figure = Figure(figsize=(8, 5), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.figure, frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        # Add toolbar
        toolbar_frame = ttk.Frame(frame)
        toolbar_frame.pack(fill="x")
        toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
        toolbar.update()

        # Initialize with empty plot
        self._init_plot()

    def _init_plot(self):
        """Initialize the plot with default empty axes."""
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.set_xlabel("Airspeed (m/s)")
        ax.set_ylabel("Value")
        ax.set_title("Speed Sweep Results")
        ax.grid(True, alpha=0.3)
        ax.text(0.5, 0.5, "Run 'Speed Sweep' to see results",
                ha='center', va='center', transform=ax.transAxes,
                fontsize=12, color='gray')
        self.canvas.draw()

    def _create_status_bar(self):
        """Create the status bar at the bottom of the window."""
        status_frame = ttk.Frame(self.main_frame)
        status_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(5, 0))

        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(status_frame, textvariable=self.status_var, anchor="w")
        status_label.pack(side="left", fill="x", expand=True)

    # =========================================================================
    # Event Handlers
    # =========================================================================

    def _on_drag_method_change(self, event=None):
        """Handle drag method selection change."""
        method = self.drag_method_var.get()
        method_to_tab = {
            "coefficient": 0,
            "raw": 1,
            "flat_plate": 2,
            "fixed_wing": 3
        }
        tab_idx = method_to_tab.get(method, 0)
        self.drag_notebook.select(tab_idx)

    def _on_motor_category_change(self, event=None):
        """Handle motor category selection change."""
        category = self.motor_category_var.get()
        motors_in_category = self.presets.get("categories", {}).get(category, [])
        self.motor_preset_combo['values'] = motors_in_category

        if motors_in_category:
            self.motor_preset_combo.current(0)
            self._on_motor_preset_change()

    def _on_motor_preset_change(self, event=None):
        """Handle motor preset selection - auto-populate parameters."""
        motor_name = self.motor_preset_var.get()
        motor_data = self.motors.get(motor_name, {})

        if motor_data:
            self.motor_kv_var.set(str(motor_data.get("kv", 900)))
            self.motor_rm_var.set(str(motor_data.get("rm_cold", 0.030)))
            self.motor_i0_var.set(str(motor_data.get("i0_ref", 1.5)))
            self.motor_i0rpm_var.set(str(motor_data.get("i0_rpm_ref", 9000)))
            self.motor_imax_var.set(str(motor_data.get("i_max", 40)))

            self._update_status(f"Loaded motor preset: {motor_name}")

    def _on_battery_change(self, event=None):
        """Handle battery selection change."""
        battery = self.battery_var.get()
        voltage = self.BATTERY_OPTIONS.get(battery, 22.2)
        self.voltage_var.set(str(voltage))

    def _update_speed_conversion(self, *args):
        """Update speed conversion display (m/s to mph and km/h)."""
        try:
            speed_ms = float(self.airspeed_var.get())
            speed_mph = speed_ms * 2.23694
            speed_kmh = speed_ms * 3.6
            self.speed_mph_label.config(text=f"({speed_mph:.1f} mph / {speed_kmh:.1f} km/h)")
        except ValueError:
            self.speed_mph_label.config(text="")

    # =========================================================================
    # Calculation Methods
    # =========================================================================

    def _get_drag_model(self) -> DragModel:
        """
        Build a DragModel from current UI settings.

        Returns:
        -------
        DragModel
            Configured drag model instance
        """
        method = self.drag_method_var.get()

        if method == "raw":
            return DragModel(
                method="raw",
                raw_drag=float(self.raw_drag_var.get())
            )
        elif method == "coefficient":
            return DragModel(
                method="coefficient",
                cd=float(self.cd_var.get()),
                reference_area=float(self.ref_area_var.get())
            )
        elif method == "flat_plate":
            return DragModel(
                method="flat_plate",
                flat_plate_area=float(self.flat_plate_var.get())
            )
        elif method == "fixed_wing":
            # Fixed-wing with induced drag calculation
            weight_kg = float(self.weight_var.get())
            weight_n = weight_kg * 9.81  # Convert kg to N
            return DragModel(
                method="fixed_wing",
                cd0=float(self.cd0_var.get()),
                wing_area=float(self.wing_area_var.get()),
                wingspan=float(self.wingspan_var.get()),
                weight=weight_n,
                oswald_efficiency=float(self.oswald_var.get())
            )
        else:
            return DragModel(method="coefficient", cd=0.04, reference_area=0.15)

    def _register_motor(self) -> str:
        """
        Register the current motor parameters with the analyzer.

        Returns:
        -------
        str
            Motor ID for reference
        """
        motor_id = "UI_Motor"

        self.motor_analyzer.add_motor(motor_id, {
            "kv": float(self.motor_kv_var.get()),
            "rm_cold": float(self.motor_rm_var.get()),
            "i0_ref": float(self.motor_i0_var.get()),
            "i0_rpm_ref": float(self.motor_i0rpm_var.get()),
            "i_max": float(self.motor_imax_var.get()),
            "p_max": 2000  # Default high value
        })

        return motor_id

    def _solve_equilibrium(self):
        """Solve for cruise flight equilibrium."""
        try:
            self._update_status("Solving equilibrium...")

            # Build drag model
            drag_model = self._get_drag_model()

            # Register motor
            motor_id = self._register_motor()

            # Get prop
            prop_id = self.prop_var.get()
            if not prop_id:
                messagebox.showerror("Error", "Please select a propeller")
                return

            # Get flight conditions
            v_battery = float(self.voltage_var.get())
            airspeed = float(self.airspeed_var.get())
            altitude = float(self.altitude_var.get())
            winding_temp = float(self.winding_temp_var.get())

            # Solve (fixed-wing = single motor)
            result = self.flight_solver.solve_cruise(
                motor_id=motor_id,
                prop_id=prop_id,
                drag_model=drag_model,
                v_battery=v_battery,
                airspeed=airspeed,
                altitude=altitude,
                winding_temp=winding_temp,
                num_motors=1
            )

            self.current_result = result
            self._display_result(result)

        except Exception as e:
            self._update_status(f"Error: {str(e)}")
            messagebox.showerror("Calculation Error", str(e))

    def _display_result(self, result: FlightResult):
        """Display calculation result in the UI."""
        if result.valid:
            self.result_throttle_var.set(f"{result.throttle:.1f} %")
            self.result_current_var.set(f"{result.battery_current:.1f} A")
            self.result_power_var.set(f"{result.battery_power:.0f} W")
            self.result_sys_eff_var.set(f"{result.system_efficiency*100:.1f} %")
            self.result_drag_var.set(f"{result.drag:.2f} N")
            self.result_rpm_var.set(f"{result.prop_rpm:.0f}")
            self.result_motor_eff_var.set(f"{result.motor_efficiency*100:.1f} %")
            self.result_prop_eff_var.set(f"{result.prop_efficiency*100:.1f} %")

            # Check for warnings
            if result.throttle > 100:
                self.result_status_var.set("⚠ Throttle exceeds 100% - need more voltage or different setup")
            elif result.motor_current > float(self.motor_imax_var.get()):
                self.result_status_var.set(f"⚠ Current ({result.motor_current:.1f}A) exceeds motor limit")
            else:
                self.result_status_var.set("")

            self._update_status("Equilibrium solved successfully")
        else:
            self.result_throttle_var.set("--")
            self.result_current_var.set("--")
            self.result_power_var.set("--")
            self.result_sys_eff_var.set("--")
            self.result_drag_var.set("--")
            self.result_rpm_var.set("--")
            self.result_motor_eff_var.set("--")
            self.result_prop_eff_var.set("--")
            self.result_status_var.set(f"⚠ {result.error_message}")
            self._update_status(f"Could not solve: {result.error_message}")

    def _run_speed_sweep(self):
        """Run a sweep across airspeed range and plot results."""
        try:
            self._update_status("Running speed sweep...")

            # Build drag model
            drag_model = self._get_drag_model()

            # Register motor
            motor_id = self._register_motor()

            # Get prop
            prop_id = self.prop_var.get()
            if not prop_id:
                messagebox.showerror("Error", "Please select a propeller")
                return

            # Get flight conditions
            v_battery = float(self.voltage_var.get())
            altitude = float(self.altitude_var.get())
            winding_temp = float(self.winding_temp_var.get())

            # Run sweep (fixed-wing = single motor)
            results = self.flight_solver.solve_speed_sweep(
                motor_id=motor_id,
                prop_id=prop_id,
                drag_model=drag_model,
                v_battery=v_battery,
                speed_range=(5, 50),
                altitude=altitude,
                winding_temp=winding_temp,
                num_motors=1,
                num_points=25
            )

            self.speed_sweep_results = results
            self._plot_speed_sweep(results)
            self._update_status(f"Speed sweep complete - {len(results)} points")

        except Exception as e:
            self._update_status(f"Error: {str(e)}")
            messagebox.showerror("Calculation Error", str(e))

    def _plot_speed_sweep(self, results: List[FlightResult]):
        """Plot speed sweep results."""
        self.figure.clear()

        # Filter valid results
        valid_results = [r for r in results if r.valid and r.throttle <= 100]

        if not valid_results:
            ax = self.figure.add_subplot(111)
            ax.text(0.5, 0.5, "No valid operating points found",
                    ha='center', va='center', transform=ax.transAxes,
                    fontsize=12, color='red')
            self.canvas.draw()
            return

        # Extract data
        speeds = [r.airspeed for r in valid_results]
        throttles = [r.throttle for r in valid_results]
        currents = [r.battery_current for r in valid_results]
        powers = [r.battery_power for r in valid_results]
        efficiencies = [r.system_efficiency * 100 for r in valid_results]

        # Create 2x2 subplot grid
        ax1 = self.figure.add_subplot(221)
        ax2 = self.figure.add_subplot(222)
        ax3 = self.figure.add_subplot(223)
        ax4 = self.figure.add_subplot(224)

        # Throttle vs Speed
        ax1.plot(speeds, throttles, 'b-o', markersize=3)
        ax1.set_xlabel("Airspeed (m/s)")
        ax1.set_ylabel("Throttle (%)")
        ax1.set_title("Throttle Required")
        ax1.grid(True, alpha=0.3)
        ax1.axhline(y=100, color='r', linestyle='--', alpha=0.5)

        # Current vs Speed
        ax2.plot(speeds, currents, 'r-o', markersize=3)
        ax2.set_xlabel("Airspeed (m/s)")
        ax2.set_ylabel("Current (A)")
        ax2.set_title("Battery Current")
        ax2.grid(True, alpha=0.3)

        # Power vs Speed
        ax3.plot(speeds, powers, 'g-o', markersize=3)
        ax3.set_xlabel("Airspeed (m/s)")
        ax3.set_ylabel("Power (W)")
        ax3.set_title("Battery Power")
        ax3.grid(True, alpha=0.3)

        # Efficiency vs Speed
        ax4.plot(speeds, efficiencies, 'm-o', markersize=3)
        ax4.set_xlabel("Airspeed (m/s)")
        ax4.set_ylabel("Efficiency (%)")
        ax4.set_title("System Efficiency")
        ax4.grid(True, alpha=0.3)

        # Find and mark best efficiency
        if efficiencies:
            best_idx = efficiencies.index(max(efficiencies))
            ax4.axvline(x=speeds[best_idx], color='r', linestyle='--', alpha=0.5)
            ax4.annotate(f"Best: {speeds[best_idx]:.1f} m/s",
                        xy=(speeds[best_idx], efficiencies[best_idx]),
                        xytext=(10, -10), textcoords='offset points',
                        fontsize=8)

        self.figure.tight_layout()
        self.canvas.draw()

    def _find_max_speed(self):
        """Find the maximum achievable airspeed."""
        try:
            self._update_status("Finding max speed...")

            # Build drag model
            drag_model = self._get_drag_model()

            # Register motor
            motor_id = self._register_motor()

            # Get prop
            prop_id = self.prop_var.get()
            if not prop_id:
                messagebox.showerror("Error", "Please select a propeller")
                return

            # Get flight conditions
            v_battery = float(self.voltage_var.get())
            altitude = float(self.altitude_var.get())
            winding_temp = float(self.winding_temp_var.get())

            # Find max speed (fixed-wing = single motor)
            result = self.flight_solver.find_max_speed(
                motor_id=motor_id,
                prop_id=prop_id,
                drag_model=drag_model,
                v_battery=v_battery,
                altitude=altitude,
                winding_temp=winding_temp,
                num_motors=1
            )

            if result.valid:
                self.current_result = result
                self._display_result(result)

                # Update airspeed field to max speed
                self.airspeed_var.set(f"{result.airspeed:.1f}")

                messagebox.showinfo(
                    "Max Speed Found",
                    f"Maximum airspeed: {result.airspeed:.1f} m/s\n"
                    f"({result.airspeed * 2.237:.1f} mph)\n\n"
                    f"At 100% throttle:\n"
                    f"Current: {result.battery_current:.1f} A\n"
                    f"Power: {result.battery_power:.0f} W"
                )
            else:
                messagebox.showwarning("Max Speed", f"Could not find max speed: {result.error_message}")

        except Exception as e:
            self._update_status(f"Error: {str(e)}")
            messagebox.showerror("Calculation Error", str(e))

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def _set_defaults(self):
        """Set default values for UI elements."""
        # Battery
        # Default to 4S for typical FPV fixed-wing
        if self.BATTERY_OPTIONS:
            first_battery = "4S (14.8V)"
            if first_battery in self.BATTERY_OPTIONS:
                self.battery_var.set(first_battery)
                self.voltage_var.set(str(self.BATTERY_OPTIONS[first_battery]))

        # Motor category - default to first category
        if self.motor_categories:
            self.motor_category_var.set(self.motor_categories[0])
            self._on_motor_category_change()

        # Propeller - common FPV fixed-wing props
        if self.available_props:
            default_props = ["7x4", "8x4", "9x6", "10x5"]
            for dp in default_props:
                if dp in self.available_props:
                    self.prop_var.set(dp)
                    break
            else:
                self.prop_var.set(self.available_props[0])

        # Initial speed conversion
        self._update_speed_conversion()

    def _update_status(self, message: str):
        """Update status bar message."""
        self.status_var.set(message)
        self.root.update_idletasks()

    def run(self):
        """Start the UI main loop."""
        self.root.mainloop()


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    """Launch the Flight Analyzer UI."""
    app = FlightAnalyzerUI()
    app.run()


if __name__ == "__main__":
    main()
