"""
Integrated Analyzer User Interface
===================================

Multi-tab GUI for the integrated motor/prop/battery batch analyzer.

Features:
---------
- Airframe configuration (drag, weight, wing geometry)
- Motor/prop selection filters
- Battery iteration configuration (cell types, S/P range, thermal environments)
- Batch execution with progress tracking
- Six result tabs: Summary, Motor, Prop, Battery, Speed Curves, Thermal
- Comparison matrix with drill-down selection
- CSV/JSON export

Usage:
------
    from src.ui.integrated_analyzer_ui import IntegratedAnalyzerUI

    app = IntegratedAnalyzerUI()
    app.run()
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import json
import tempfile
import atexit
import os
import csv
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
import numpy as np

# Import integrated analyzer
from src.integrated_analyzer import (
    IntegratedSolver,
    IntegratedConfig,
    BatteryIterationConfig,
    IntegratedResult,
    IntegratedBatchResult,
    ResultAnalyzer,
    DEFAULT_LIMITS,
)

# Import battery calculator for cell database
from src.battery_calculator import CELL_DATABASE, THERMAL_RESISTANCE

# Import motor and prop config
from src.motor_analyzer.config import MotorAnalyzerConfig
from src.prop_analyzer.core import PropAnalyzer
from src.prop_analyzer.config import PropAnalyzerConfig
from src.batch_analyzer.batch_solver import parse_prop_dimensions


class IntegratedAnalyzerUI:
    """
    Integrated analyzer GUI for motor/prop/battery optimization.

    Provides comprehensive UI for configuring and running batch analysis
    across motor, propeller, and battery configurations.
    """

    # =========================================================================
    # UI Constants
    # =========================================================================

    WINDOW_TITLE = "Integrated Motor/Prop/Battery Analyzer - Fixed-Wing FPV"
    WINDOW_MIN_WIDTH = 1600
    WINDOW_MIN_HEIGHT = 1000

    FRAME_PADDING = 10
    WIDGET_PADDING = 3
    SECTION_PADDING = 5

    # Warning thresholds
    WARNING_PERMUTATIONS = 10_000
    LARGE_BATCH_PERMUTATIONS = 50_000  # Show extra warning above this

    def __init__(self):
        """Initialize the Integrated Analyzer UI."""
        # Initialize backend
        self._motor_config = MotorAnalyzerConfig()
        self._prop_config = PropAnalyzerConfig()
        self._prop_analyzer = PropAnalyzer(self._prop_config)

        # Load motor presets
        self._motor_presets = self._load_motor_presets()
        self._motor_categories = list(self._motor_presets.get("categories", {}).keys())
        self._motors = self._motor_presets.get("motors", {})

        # Load available props
        self._all_props = self._prop_analyzer.list_available_propellers()

        # Solver and results
        self._solver: Optional[IntegratedSolver] = None
        self._batch_result: Optional[IntegratedBatchResult] = None
        self._results: List[IntegratedResult] = []
        self._batch_thread: Optional[threading.Thread] = None
        self._selected_result: Optional[IntegratedResult] = None

        # Temp file for batch results (auto-cleanup on exit)
        self._temp_results_file: Optional[str] = None
        self._init_temp_file()

        # Create main window
        self.root = tk.Tk()
        self.root.title(self.WINDOW_TITLE)
        self.root.minsize(self.WINDOW_MIN_WIDTH, self.WINDOW_MIN_HEIGHT)

        # Configure grid
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # Main container
        self.main_frame = ttk.Frame(self.root, padding=self.FRAME_PADDING)
        self.main_frame.grid(row=0, column=0, sticky="nsew")

        self.main_frame.columnconfigure(0, weight=0)  # Left panel
        self.main_frame.columnconfigure(1, weight=1)  # Right panel
        self.main_frame.rowconfigure(1, weight=1)

        # Build UI
        self._create_header()
        self._create_left_panel()
        self._create_right_panel()
        self._create_status_bar()

        # Set defaults and update permutation count
        self._set_defaults()
        self._schedule_permutation_update()

    # =========================================================================
    # Data Loading
    # =========================================================================

    def _load_motor_presets(self) -> Dict[str, Any]:
        """Load motor presets from JSON file."""
        preset_path = self._motor_config.data_root / "motor_presets.json"
        if preset_path.exists():
            try:
                with open(preset_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Could not load motor presets: {e}")
        return {"categories": {}, "motors": {}}

    # =========================================================================
    # UI Construction
    # =========================================================================

    def _create_header(self):
        """Create header section."""
        header_frame = ttk.Frame(self.main_frame)
        header_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        ttk.Label(
            header_frame,
            text="Integrated Motor/Prop/Battery Analyzer",
            font=("Helvetica", 18, "bold")
        ).pack(anchor="w")

        ttk.Label(
            header_frame,
            text="Optimize motor, propeller, and battery combinations for fixed-wing FPV aircraft with thermal modeling",
            font=("Helvetica", 10)
        ).pack(anchor="w")

    def _create_left_panel(self):
        """Create left panel with all input sections."""
        # Scrollable left panel
        left_canvas = tk.Canvas(self.main_frame, width=520)
        left_scrollbar = ttk.Scrollbar(
            self.main_frame, orient="vertical", command=left_canvas.yview
        )
        left_frame = ttk.Frame(left_canvas)

        left_frame.bind(
            "<Configure>",
            lambda e: left_canvas.configure(scrollregion=left_canvas.bbox("all"))
        )

        left_canvas.create_window((0, 0), window=left_frame, anchor="nw")
        left_canvas.configure(yscrollcommand=left_scrollbar.set)

        left_canvas.grid(row=1, column=0, sticky="nsew", padx=(0, 5))
        left_scrollbar.grid(row=1, column=0, sticky="nse", padx=(0, 5))

        # Bind mouse wheel
        def _on_mousewheel(event):
            left_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        left_canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Build sections
        self._create_airframe_section(left_frame)
        self._create_motor_section(left_frame)
        self._create_prop_section(left_frame)
        self._create_battery_section(left_frame)
        self._create_thermal_section(left_frame)
        self._create_speed_section(left_frame)
        self._create_permutation_section(left_frame)
        self._create_action_section(left_frame)

    def _create_airframe_section(self, parent):
        """Create airframe configuration section."""
        frame = ttk.LabelFrame(
            parent, text="Airframe Configuration", padding=self.SECTION_PADDING
        )
        frame.pack(fill="x", pady=self.WIDGET_PADDING, padx=self.WIDGET_PADDING)

        # Wing area
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Wing Area:", width=22).pack(side="left")
        self.wing_area_var = tk.StringVar(value="0.15")
        ttk.Entry(row, textvariable=self.wing_area_var, width=10).pack(side="left")
        ttk.Label(row, text="m^2").pack(side="left", padx=5)

        # Wingspan
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Wingspan:", width=22).pack(side="left")
        self.wingspan_var = tk.StringVar(value="1.0")
        ttk.Entry(row, textvariable=self.wingspan_var, width=10).pack(side="left")
        ttk.Label(row, text="m").pack(side="left", padx=5)

        # Weight (without battery)
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Dry Weight (no batt):", width=22).pack(side="left")
        self.weight_var = tk.StringVar(value="0.8")
        ttk.Entry(row, textvariable=self.weight_var, width=10).pack(side="left")
        ttk.Label(row, text="kg").pack(side="left", padx=5)

        # Cd0
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Cd0 (parasitic drag):", width=22).pack(side="left")
        self.cd0_var = tk.StringVar(value="0.025")
        ttk.Entry(row, textvariable=self.cd0_var, width=10).pack(side="left")
        ttk.Label(row, text="(0.02-0.04)").pack(side="left", padx=5)

        # Oswald efficiency
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Oswald Efficiency:", width=22).pack(side="left")
        self.oswald_var = tk.StringVar(value="0.8")
        ttk.Entry(row, textvariable=self.oswald_var, width=10).pack(side="left")
        ttk.Label(row, text="(0.7-0.85)").pack(side="left", padx=5)

    def _create_motor_section(self, parent):
        """Create motor filter section."""
        frame = ttk.LabelFrame(
            parent, text="Motor Selection", padding=self.SECTION_PADDING
        )
        frame.pack(fill="x", pady=self.WIDGET_PADDING, padx=self.WIDGET_PADDING)

        # Category checkboxes
        ttk.Label(frame, text="Select motor categories to include:").pack(anchor="w")

        self.motor_category_vars = {}
        cat_frame = ttk.Frame(frame)
        cat_frame.pack(fill="x", pady=5)

        for i, category in enumerate(self._motor_categories):
            var = tk.BooleanVar(value=True)
            self.motor_category_vars[category] = var
            cb = ttk.Checkbutton(
                cat_frame,
                text=category,
                variable=var,
                command=self._schedule_permutation_update
            )
            cb.grid(row=i // 2, column=i % 2, sticky="w", padx=5)

        # Select all / none buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x", pady=2)
        ttk.Button(
            btn_frame, text="Select All", width=12,
            command=self._select_all_motors
        ).pack(side="left", padx=2)
        ttk.Button(
            btn_frame, text="Select None", width=12,
            command=self._select_no_motors
        ).pack(side="left", padx=2)

        # Motor count display
        self.motor_count_var = tk.StringVar(value="0 motors selected")
        ttk.Label(
            frame, textvariable=self.motor_count_var,
            font=("Helvetica", 9, "italic")
        ).pack(anchor="w", pady=(5, 0))

    def _create_prop_section(self, parent):
        """Create propeller filter section."""
        frame = ttk.LabelFrame(
            parent, text="Propeller Selection", padding=self.SECTION_PADDING
        )
        frame.pack(fill="x", pady=self.WIDGET_PADDING, padx=self.WIDGET_PADDING)

        ttk.Label(
            frame, text="Filter propellers by diameter and pitch (inches):"
        ).pack(anchor="w")

        # Diameter range
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Diameter Range:", width=20).pack(side="left")
        self.prop_dia_min_var = tk.StringVar(value="7")
        self.prop_dia_max_var = tk.StringVar(value="11")
        ttk.Entry(row, textvariable=self.prop_dia_min_var, width=6).pack(side="left")
        ttk.Label(row, text=" to ").pack(side="left")
        ttk.Entry(row, textvariable=self.prop_dia_max_var, width=6).pack(side="left")
        ttk.Label(row, text=" inches").pack(side="left", padx=5)

        # Pitch range
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Pitch Range:", width=20).pack(side="left")
        self.prop_pitch_min_var = tk.StringVar(value="4")
        self.prop_pitch_max_var = tk.StringVar(value="7")
        ttk.Entry(row, textvariable=self.prop_pitch_min_var, width=6).pack(side="left")
        ttk.Label(row, text=" to ").pack(side="left")
        ttk.Entry(row, textvariable=self.prop_pitch_max_var, width=6).pack(side="left")
        ttk.Label(row, text=" inches").pack(side="left", padx=5)

        # Bind updates
        for var in [self.prop_dia_min_var, self.prop_dia_max_var,
                    self.prop_pitch_min_var, self.prop_pitch_max_var]:
            var.trace_add("write", lambda *a: self._schedule_permutation_update())

        # Prop count display
        self.prop_count_var = tk.StringVar(value="0 props selected")
        ttk.Label(
            frame, textvariable=self.prop_count_var,
            font=("Helvetica", 9, "italic")
        ).pack(anchor="w", pady=(5, 0))

    def _create_battery_section(self, parent):
        """Create battery iteration configuration section."""
        frame = ttk.LabelFrame(
            parent, text="Battery Configuration", padding=self.SECTION_PADDING
        )
        frame.pack(fill="x", pady=self.WIDGET_PADDING, padx=self.WIDGET_PADDING)

        # Cell type selection
        ttk.Label(frame, text="Select cell types to evaluate:").pack(anchor="w")

        # Get high-drain cells only
        high_drain_cells = [
            name for name, cell in CELL_DATABASE.items()
            if cell.max_continuous_discharge_a >= 20
        ]

        self.cell_type_vars = {}
        cell_frame = ttk.Frame(frame)
        cell_frame.pack(fill="x", pady=5)

        for i, cell_name in enumerate(high_drain_cells[:8]):  # Limit to 8 for UI
            var = tk.BooleanVar(value=(cell_name in ["Molicel P45B", "Samsung 40T"]))
            self.cell_type_vars[cell_name] = var
            cb = ttk.Checkbutton(
                cell_frame,
                text=cell_name,
                variable=var,
                command=self._schedule_permutation_update
            )
            cb.grid(row=i // 2, column=i % 2, sticky="w", padx=5)

        # Series selection - individual checkboxes
        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=8)
        ttk.Label(frame, text="Series Count (S):").pack(anchor="w")

        series_frame = ttk.Frame(frame)
        series_frame.pack(fill="x", pady=2)

        self.series_values = [1, 2, 3, 4, 5, 6, 8, 10, 12]
        self.series_vars = {}
        for i, s in enumerate(self.series_values):
            var = tk.BooleanVar(value=(s in [4, 5, 6]))  # Default: 4S, 5S, 6S
            self.series_vars[s] = var
            cb = ttk.Checkbutton(
                series_frame,
                text=f"{s}S",
                variable=var,
                command=self._on_series_selection_change
            )
            cb.grid(row=0, column=i, sticky="w", padx=3)

        # Series quick select buttons
        series_btn_frame = ttk.Frame(frame)
        series_btn_frame.pack(fill="x", pady=2)
        ttk.Button(series_btn_frame, text="All", width=6,
                   command=lambda: self._select_all_series(True)).pack(side="left", padx=2)
        ttk.Button(series_btn_frame, text="None", width=6,
                   command=lambda: self._select_all_series(False)).pack(side="left", padx=2)
        ttk.Button(series_btn_frame, text="4-6S", width=6,
                   command=lambda: self._select_series_range([4, 5, 6])).pack(side="left", padx=2)

        # Parallel mode selection
        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=8)
        ttk.Label(frame, text="Parallel Count (P):").pack(anchor="w")

        self.parallel_mode_var = tk.StringVar(value="all_combinations")
        mode_frame = ttk.Frame(frame)
        mode_frame.pack(fill="x", pady=2)

        ttk.Radiobutton(
            mode_frame, text="Same P for all S (all combinations)",
            variable=self.parallel_mode_var, value="all_combinations",
            command=self._on_parallel_mode_change
        ).pack(anchor="w")
        ttk.Radiobutton(
            mode_frame, text="Different P per S (custom per series)",
            variable=self.parallel_mode_var, value="per_series",
            command=self._on_parallel_mode_change
        ).pack(anchor="w")

        # All combinations parallel frame
        self.all_parallel_frame = ttk.Frame(frame)
        self.all_parallel_frame.pack(fill="x", pady=5)

        self.parallel_values = [1, 2, 3, 4, 5, 6, 8, 12]
        self.parallel_vars = {}
        for i, p in enumerate(self.parallel_values):
            var = tk.BooleanVar(value=(p in [1, 2, 3]))  # Default: 1P, 2P, 3P
            self.parallel_vars[p] = var
            cb = ttk.Checkbutton(
                self.all_parallel_frame,
                text=f"{p}P",
                variable=var,
                command=self._schedule_permutation_update
            )
            cb.grid(row=0, column=i, sticky="w", padx=3)

        # All parallel quick select buttons
        all_p_btn_frame = ttk.Frame(self.all_parallel_frame)
        all_p_btn_frame.grid(row=1, column=0, columnspan=len(self.parallel_values), sticky="w", pady=2)
        ttk.Button(all_p_btn_frame, text="All", width=6,
                   command=lambda: self._select_all_parallel(True)).pack(side="left", padx=2)
        ttk.Button(all_p_btn_frame, text="None", width=6,
                   command=lambda: self._select_all_parallel(False)).pack(side="left", padx=2)
        ttk.Button(all_p_btn_frame, text="1-3P", width=6,
                   command=lambda: self._select_parallel_range([1, 2, 3])).pack(side="left", padx=2)

        # Per-series parallel frame (hidden by default)
        self.per_series_frame = ttk.Frame(frame)
        self.per_series_parallel_vars = {}  # {series: {parallel: BooleanVar}}
        self._rebuild_per_series_frame()

        # Battery config count
        self.battery_count_var = tk.StringVar(value="0 battery configs")
        ttk.Label(
            frame, textvariable=self.battery_count_var,
            font=("Helvetica", 9, "italic")
        ).pack(anchor="w", pady=(5, 0))

    def _select_all_series(self, select: bool):
        """Select or deselect all series checkboxes."""
        for var in self.series_vars.values():
            var.set(select)
        self._on_series_selection_change()

    def _select_series_range(self, series_list: list):
        """Select specific series values."""
        for s, var in self.series_vars.items():
            var.set(s in series_list)
        self._on_series_selection_change()

    def _select_all_parallel(self, select: bool):
        """Select or deselect all parallel checkboxes."""
        for var in self.parallel_vars.values():
            var.set(select)
        self._schedule_permutation_update()

    def _select_parallel_range(self, parallel_list: list):
        """Select specific parallel values."""
        for p, var in self.parallel_vars.items():
            var.set(p in parallel_list)
        self._schedule_permutation_update()

    def _on_series_selection_change(self):
        """Handle series selection change - rebuild per-series frame if needed."""
        if self.parallel_mode_var.get() == "per_series":
            self._rebuild_per_series_frame()
        self._schedule_permutation_update()

    def _on_parallel_mode_change(self):
        """Toggle between all-combinations and per-series parallel modes."""
        if self.parallel_mode_var.get() == "all_combinations":
            self.per_series_frame.pack_forget()
            self.all_parallel_frame.pack(fill="x", pady=5)
        else:
            self.all_parallel_frame.pack_forget()
            self._rebuild_per_series_frame()
            self.per_series_frame.pack(fill="x", pady=5)
        self._schedule_permutation_update()

    def _rebuild_per_series_frame(self):
        """Rebuild the per-series parallel selection frame."""
        # Clear existing widgets
        for widget in self.per_series_frame.winfo_children():
            widget.destroy()

        # Get selected series
        selected_series = [s for s, var in self.series_vars.items() if var.get()]
        selected_series.sort()

        if not selected_series:
            ttk.Label(self.per_series_frame, text="(Select series first)").pack(anchor="w")
            return

        # Create header row
        header_frame = ttk.Frame(self.per_series_frame)
        header_frame.pack(fill="x", pady=2)
        ttk.Label(header_frame, text="Series", width=8).grid(row=0, column=0, sticky="w")
        for i, p in enumerate(self.parallel_values):
            ttk.Label(header_frame, text=f"{p}P", width=4).grid(row=0, column=i+1)

        # Create row for each selected series
        for row_idx, s in enumerate(selected_series):
            row_frame = ttk.Frame(self.per_series_frame)
            row_frame.pack(fill="x", pady=1)

            ttk.Label(row_frame, text=f"{s}S:", width=8).grid(row=0, column=0, sticky="w")

            if s not in self.per_series_parallel_vars:
                self.per_series_parallel_vars[s] = {}

            for col_idx, p in enumerate(self.parallel_values):
                if p not in self.per_series_parallel_vars[s]:
                    # Default: enable 1P, 2P, 3P for each series
                    self.per_series_parallel_vars[s][p] = tk.BooleanVar(value=(p <= 3))

                cb = ttk.Checkbutton(
                    row_frame,
                    variable=self.per_series_parallel_vars[s][p],
                    command=self._schedule_permutation_update
                )
                cb.grid(row=0, column=col_idx+1, padx=2)

        # Quick buttons for per-series
        btn_frame = ttk.Frame(self.per_series_frame)
        btn_frame.pack(fill="x", pady=5)
        ttk.Button(btn_frame, text="All P for All S", width=14,
                   command=self._select_all_per_series).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="1-3P for All S", width=14,
                   command=lambda: self._select_per_series_range([1, 2, 3])).pack(side="left", padx=2)

    def _select_all_per_series(self):
        """Select all parallel values for all series."""
        for s_vars in self.per_series_parallel_vars.values():
            for var in s_vars.values():
                var.set(True)
        self._schedule_permutation_update()

    def _select_per_series_range(self, parallel_list: list):
        """Select specific parallel values for all series."""
        for s_vars in self.per_series_parallel_vars.values():
            for p, var in s_vars.items():
                var.set(p in parallel_list)
        self._schedule_permutation_update()

    def _create_thermal_section(self, parent):
        """Create thermal environment section."""
        frame = ttk.LabelFrame(
            parent, text="Thermal Configuration", padding=self.SECTION_PADDING
        )
        frame.pack(fill="x", pady=self.WIDGET_PADDING, padx=self.WIDGET_PADDING)

        # Thermal environments
        ttk.Label(frame, text="Thermal environments to evaluate:").pack(anchor="w")

        self.thermal_env_vars = {}
        thermal_frame = ttk.Frame(frame)
        thermal_frame.pack(fill="x", pady=5)

        env_labels = {
            "still_air": "Still Air (18 C/W)",
            "light_airflow": "Light Airflow (8 C/W)",
            "drone_in_flight": "Drone in Flight (4 C/W)",
            "high_airflow": "High Airflow (2.5 C/W)",
            "active_cooling": "Active Cooling (1.5 C/W)",
        }

        for i, (env_key, env_label) in enumerate(env_labels.items()):
            var = tk.BooleanVar(value=(env_key == "drone_in_flight"))
            self.thermal_env_vars[env_key] = var
            cb = ttk.Checkbutton(
                thermal_frame,
                text=env_label,
                variable=var,
                command=self._schedule_permutation_update
            )
            cb.pack(anchor="w", padx=5)

        # Ambient temperature
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Ambient Temperature:", width=20).pack(side="left")
        self.ambient_temp_var = tk.StringVar(value="25")
        ttk.Entry(row, textvariable=self.ambient_temp_var, width=8).pack(side="left")
        ttk.Label(row, text="C").pack(side="left", padx=5)

        # Max cell temperature
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Max Cell Temperature:", width=20).pack(side="left")
        self.max_cell_temp_var = tk.StringVar(value="60")
        ttk.Entry(row, textvariable=self.max_cell_temp_var, width=8).pack(side="left")
        ttk.Label(row, text="C").pack(side="left", padx=5)

        # SOC for analysis
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Analysis SOC:", width=20).pack(side="left")
        self.analysis_soc_var = tk.StringVar(value="80")
        ttk.Entry(row, textvariable=self.analysis_soc_var, width=8).pack(side="left")
        ttk.Label(row, text="%").pack(side="left", padx=5)

    def _create_speed_section(self, parent):
        """Create speed configuration section."""
        frame = ttk.LabelFrame(
            parent, text="Speed Configuration", padding=self.SECTION_PADDING
        )
        frame.pack(fill="x", pady=self.WIDGET_PADDING, padx=self.WIDGET_PADDING)

        # Batch cruise speed range checkbox
        self.batch_cruise_var = tk.BooleanVar(value=False)
        self.batch_cruise_checkbox = ttk.Checkbutton(
            frame,
            text="Batch cruise speed range",
            variable=self.batch_cruise_var,
            command=self._toggle_cruise_range
        )
        self.batch_cruise_checkbox.pack(anchor="w", pady=2)

        # Single cruise speed (shown when not batching)
        self.single_cruise_frame = ttk.Frame(frame)
        self.single_cruise_frame.pack(fill="x", pady=2)
        ttk.Label(self.single_cruise_frame, text="Cruise Speed:", width=20).pack(side="left")
        self.cruise_speed_var = tk.StringVar(value="22")
        ttk.Entry(self.single_cruise_frame, textvariable=self.cruise_speed_var, width=8).pack(side="left")
        ttk.Label(self.single_cruise_frame, text="m/s").pack(side="left", padx=5)
        self.cruise_mph_label = ttk.Label(self.single_cruise_frame, text="(49.2 mph)")
        self.cruise_mph_label.pack(side="left")

        # Cruise speed range (hidden by default)
        self.cruise_range_frame = ttk.Frame(frame)

        row1 = ttk.Frame(self.cruise_range_frame)
        row1.pack(fill="x", pady=2)
        ttk.Label(row1, text="Min Cruise Speed:", width=20).pack(side="left")
        self.cruise_min_var = tk.StringVar(value="15")
        ttk.Entry(row1, textvariable=self.cruise_min_var, width=8).pack(side="left")
        ttk.Label(row1, text="m/s").pack(side="left", padx=5)
        self.cruise_min_mph_label = ttk.Label(row1, text="(33.6 mph)")
        self.cruise_min_mph_label.pack(side="left")

        row2 = ttk.Frame(self.cruise_range_frame)
        row2.pack(fill="x", pady=2)
        ttk.Label(row2, text="Max Cruise Speed:", width=20).pack(side="left")
        self.cruise_max_var = tk.StringVar(value="30")
        ttk.Entry(row2, textvariable=self.cruise_max_var, width=8).pack(side="left")
        ttk.Label(row2, text="m/s").pack(side="left", padx=5)
        self.cruise_max_mph_label = ttk.Label(row2, text="(67.1 mph)")
        self.cruise_max_mph_label.pack(side="left")

        row3 = ttk.Frame(self.cruise_range_frame)
        row3.pack(fill="x", pady=2)
        ttk.Label(row3, text="Speed Step:", width=20).pack(side="left")
        self.cruise_step_var = tk.StringVar(value="2")
        ttk.Entry(row3, textvariable=self.cruise_step_var, width=8).pack(side="left")
        ttk.Label(row3, text="m/s").pack(side="left", padx=5)

        # Speed points info
        row4 = ttk.Frame(self.cruise_range_frame)
        row4.pack(fill="x", pady=2)
        ttk.Label(row4, text="Speed Points:", width=20).pack(side="left")
        self.speed_points_label = ttk.Label(row4, text="8 points (15, 17, 19, ... 29 m/s)")
        self.speed_points_label.pack(side="left")

        # Bind speed update
        self.cruise_speed_var.trace_add("write", lambda *a: self._update_speed_display())
        for var in [self.cruise_min_var, self.cruise_max_var, self.cruise_step_var]:
            var.trace_add("write", lambda *a: self._update_speed_range_display())
            var.trace_add("write", lambda *a: self._schedule_permutation_update())

        # Evaluate max speed checkbox
        self.eval_max_speed_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            frame,
            text="Evaluate maximum achievable speed",
            variable=self.eval_max_speed_var
        ).pack(anchor="w", pady=5)

    def _toggle_cruise_range(self):
        """Toggle between single cruise speed and range mode."""
        if self.batch_cruise_var.get():
            # Hide single speed, show range inputs
            self.single_cruise_frame.pack_forget()
            self.cruise_range_frame.pack(fill="x", pady=2, after=self.batch_cruise_checkbox)
        else:
            # Hide range inputs, show single speed
            self.cruise_range_frame.pack_forget()
            self.single_cruise_frame.pack(fill="x", pady=2, after=self.batch_cruise_checkbox)
        self._schedule_permutation_update()

    def _create_permutation_section(self, parent):
        """Create permutation counter section."""
        frame = ttk.LabelFrame(
            parent, text="Batch Summary", padding=self.SECTION_PADDING
        )
        frame.pack(fill="x", pady=self.WIDGET_PADDING, padx=self.WIDGET_PADDING)

        # Permutation count
        self.perm_count_var = tk.StringVar(value="0")
        count_frame = ttk.Frame(frame)
        count_frame.pack(fill="x", pady=5)

        ttk.Label(count_frame, text="Total Combinations:").pack(side="left")
        self.perm_count_label = ttk.Label(
            count_frame,
            textvariable=self.perm_count_var,
            font=("Helvetica", 14, "bold"),
            foreground="black"
        )
        self.perm_count_label.pack(side="left", padx=10)

        # Warning label
        self.perm_warning_var = tk.StringVar(value="")
        self.perm_warning_label = ttk.Label(
            frame,
            textvariable=self.perm_warning_var,
            foreground="orange",
            font=("Helvetica", 9)
        )
        self.perm_warning_label.pack(anchor="w")

        # Breakdown
        self.perm_breakdown_var = tk.StringVar(value="")
        ttk.Label(
            frame,
            textvariable=self.perm_breakdown_var,
            font=("Helvetica", 9)
        ).pack(anchor="w")

    def _create_action_section(self, parent):
        """Create action buttons section."""
        frame = ttk.Frame(parent)
        frame.pack(fill="x", pady=10, padx=self.WIDGET_PADDING)

        self.run_btn = ttk.Button(
            frame, text="Run Batch Analysis", width=20,
            command=self._start_batch
        )
        self.run_btn.pack(side="left", padx=5)

        self.cancel_btn = ttk.Button(
            frame, text="Cancel", width=12,
            command=self._cancel_batch, state="disabled"
        )
        self.cancel_btn.pack(side="left", padx=5)

    def _create_right_panel(self):
        """Create right panel with progress and results."""
        right_frame = ttk.Frame(self.main_frame)
        right_frame.grid(row=1, column=1, sticky="nsew", padx=(5, 0))
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(2, weight=1)

        self._create_progress_section(right_frame)
        self._create_summary_bar(right_frame)
        self._create_results_notebook(right_frame)

    def _create_progress_section(self, parent):
        """Create progress display section."""
        frame = ttk.LabelFrame(
            parent, text="Progress", padding=self.SECTION_PADDING
        )
        frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))

        # Progress bar
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            frame, variable=self.progress_var, maximum=100
        )
        self.progress_bar.pack(fill="x", pady=5)

        # Status text
        status_frame = ttk.Frame(frame)
        status_frame.pack(fill="x")

        # Left side: current operation
        left_status = ttk.Frame(status_frame)
        left_status.pack(side="left", fill="x", expand=True)

        self.progress_status_var = tk.StringVar(value="Ready")
        ttk.Label(
            left_status, textvariable=self.progress_status_var,
            font=("Helvetica", 10, "bold")
        ).pack(anchor="w")

        self.progress_detail_var = tk.StringVar(value="")
        ttk.Label(
            left_status, textvariable=self.progress_detail_var,
            font=("Helvetica", 9)
        ).pack(anchor="w")

        # Right side: stats
        right_status = ttk.Frame(status_frame)
        right_status.pack(side="right")

        self.progress_stats_var = tk.StringVar(value="")
        ttk.Label(
            right_status, textvariable=self.progress_stats_var,
            font=("Helvetica", 9)
        ).pack(anchor="e")

        self.progress_time_var = tk.StringVar(value="")
        ttk.Label(
            right_status, textvariable=self.progress_time_var,
            font=("Helvetica", 9)
        ).pack(anchor="e")

    def _create_summary_bar(self, parent):
        """Create results summary bar."""
        frame = ttk.Frame(parent)
        frame.grid(row=1, column=0, sticky="ew", pady=5)

        self.summary_var = tk.StringVar(value="No results yet")
        self.summary_label = ttk.Label(
            frame,
            textvariable=self.summary_var,
            font=("Helvetica", 10, "bold"),
            foreground="green"
        )
        self.summary_label.pack(anchor="w")

    def _create_results_notebook(self, parent):
        """Create results notebook with multiple tabs."""
        notebook_frame = ttk.Frame(parent)
        notebook_frame.grid(row=2, column=0, sticky="nsew")
        notebook_frame.columnconfigure(0, weight=1)
        notebook_frame.rowconfigure(0, weight=1)

        self.results_notebook = ttk.Notebook(notebook_frame)
        self.results_notebook.grid(row=0, column=0, sticky="nsew")

        # Tab 1: Summary (comparison matrix)
        self._create_summary_tab()

        # Tab 2: Motor Details
        self._create_motor_tab()

        # Tab 3: Prop Details
        self._create_prop_tab()

        # Tab 4: Battery Analysis
        self._create_battery_tab()

        # Tab 5: Speed Curves
        self._create_speed_tab()

        # Tab 6: Thermal Analysis
        self._create_thermal_tab()

        # Tab 7: Motor Efficiency
        self._create_motor_efficiency_tab()

        # Tab 8: Prop Efficiency
        self._create_prop_efficiency_tab()

        # Tab 9: Verbose Calculations
        self._create_verbose_calcs_tab()

    def _create_summary_tab(self):
        """Create summary/comparison matrix tab."""
        frame = ttk.Frame(self.results_notebook, padding=5)
        self.results_notebook.add(frame, text="Summary")

        # Toolbar
        toolbar = ttk.Frame(frame)
        toolbar.pack(fill="x", pady=(0, 5))

        ttk.Label(toolbar, text="Sort by:").pack(side="left")
        self.sort_var = tk.StringVar(value="efficiency")
        sort_combo = ttk.Combobox(
            toolbar,
            textvariable=self.sort_var,
            values=["efficiency", "runtime", "max_speed", "power_density"],
            state="readonly",
            width=15
        )
        sort_combo.pack(side="left", padx=5)
        sort_combo.bind("<<ComboboxSelected>>", self._on_sort_change)

        ttk.Label(toolbar, text="Show:").pack(side="left", padx=(10, 0))
        self.top_n_var = tk.StringVar(value="50")
        top_combo = ttk.Combobox(
            toolbar,
            textvariable=self.top_n_var,
            values=["10", "25", "50", "100", "All"],
            state="readonly",
            width=8
        )
        top_combo.pack(side="left", padx=5)
        top_combo.bind("<<ComboboxSelected>>", self._on_sort_change)

        ttk.Button(
            toolbar, text="Export CSV", width=10,
            command=self._export_csv
        ).pack(side="right", padx=5)

        ttk.Button(
            toolbar, text="Verbose CSV", width=12,
            command=self._export_verbose_csv
        ).pack(side="right", padx=5)

        ttk.Button(
            toolbar, text="Export JSON", width=10,
            command=self._export_json
        ).pack(side="right", padx=5)

        self.result_count_var = tk.StringVar(value="")
        ttk.Label(
            toolbar, textvariable=self.result_count_var,
            font=("Helvetica", 9)
        ).pack(side="right", padx=10)

        # Results treeview
        tree_frame = ttk.Frame(frame)
        tree_frame.pack(fill="both", expand=True)
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        columns = (
            "rank", "motor", "prop", "cell", "config",
            "cruise_eff", "cruise_power", "runtime",
            "max_speed", "thermal_limit", "valid"
        )
        self.summary_tree = ttk.Treeview(
            tree_frame, columns=columns, show="headings", height=20
        )

        # Configure columns
        col_config = {
            "rank": ("Rank", 50),
            "motor": ("Motor", 150),
            "prop": ("Prop", 70),
            "cell": ("Cell", 100),
            "config": ("Config", 60),
            "cruise_eff": ("Cruise Eff %", 85),
            "cruise_power": ("Cruise W", 75),
            "runtime": ("Runtime min", 85),
            "max_speed": ("Max m/s", 75),
            "thermal_limit": ("Thermal Limit", 90),
            "valid": ("Valid", 50),
        }

        for col, (heading, width) in col_config.items():
            self.summary_tree.heading(col, text=heading)
            self.summary_tree.column(col, width=width, anchor="center")

        # Scrollbars
        y_scroll = ttk.Scrollbar(
            tree_frame, orient="vertical", command=self.summary_tree.yview
        )
        x_scroll = ttk.Scrollbar(
            tree_frame, orient="horizontal", command=self.summary_tree.xview
        )
        self.summary_tree.configure(
            yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set
        )

        self.summary_tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")

        # Bind selection
        self.summary_tree.bind("<<TreeviewSelect>>", self._on_result_selected)

    def _create_motor_tab(self):
        """Create motor details tab."""
        frame = ttk.Frame(self.results_notebook, padding=5)
        self.results_notebook.add(frame, text="Motor Details")

        self.motor_detail_text = tk.Text(
            frame, height=25, width=80, state="disabled", font=("Courier", 10)
        )
        self.motor_detail_text.pack(fill="both", expand=True)

    def _create_prop_tab(self):
        """Create propeller details tab."""
        frame = ttk.Frame(self.results_notebook, padding=5)
        self.results_notebook.add(frame, text="Prop Details")

        self.prop_detail_text = tk.Text(
            frame, height=25, width=80, state="disabled", font=("Courier", 10)
        )
        self.prop_detail_text.pack(fill="both", expand=True)

    def _create_battery_tab(self):
        """Create battery analysis tab."""
        frame = ttk.Frame(self.results_notebook, padding=5)
        self.results_notebook.add(frame, text="Battery Analysis")

        self.battery_detail_text = tk.Text(
            frame, height=25, width=80, state="disabled", font=("Courier", 10)
        )
        self.battery_detail_text.pack(fill="both", expand=True)

    def _create_speed_tab(self):
        """Create speed curves tab."""
        frame = ttk.Frame(self.results_notebook, padding=5)
        self.results_notebook.add(frame, text="Speed Curves")

        # Create matplotlib figure
        self.speed_fig = Figure(figsize=(8, 5), dpi=100)
        self.speed_ax = self.speed_fig.add_subplot(111)

        self.speed_canvas = FigureCanvasTkAgg(self.speed_fig, master=frame)
        self.speed_canvas.draw()
        self.speed_canvas.get_tk_widget().pack(fill="both", expand=True)

        # Toolbar
        toolbar_frame = ttk.Frame(frame)
        toolbar_frame.pack(fill="x")
        toolbar = NavigationToolbar2Tk(self.speed_canvas, toolbar_frame)
        toolbar.update()

    def _create_thermal_tab(self):
        """Create thermal analysis tab."""
        frame = ttk.Frame(self.results_notebook, padding=5)
        self.results_notebook.add(frame, text="Thermal Analysis")

        # Create matplotlib figure
        self.thermal_fig = Figure(figsize=(8, 5), dpi=100)
        self.thermal_ax = self.thermal_fig.add_subplot(111)

        self.thermal_canvas = FigureCanvasTkAgg(self.thermal_fig, master=frame)
        self.thermal_canvas.draw()
        self.thermal_canvas.get_tk_widget().pack(fill="both", expand=True)

        # Toolbar
        toolbar_frame = ttk.Frame(frame)
        toolbar_frame.pack(fill="x")
        toolbar = NavigationToolbar2Tk(self.thermal_canvas, toolbar_frame)
        toolbar.update()

    def _create_motor_efficiency_tab(self):
        """Create motor efficiency analysis tab."""
        frame = ttk.Frame(self.results_notebook, padding=5)
        self.results_notebook.add(frame, text="Motor Efficiency")

        # Create matplotlib figure
        self.motor_eff_fig = Figure(figsize=(8, 5), dpi=100)
        self.motor_eff_ax = self.motor_eff_fig.add_subplot(111)

        self.motor_eff_canvas = FigureCanvasTkAgg(self.motor_eff_fig, master=frame)
        self.motor_eff_canvas.draw()
        self.motor_eff_canvas.get_tk_widget().pack(fill="both", expand=True)

        # Toolbar
        toolbar_frame = ttk.Frame(frame)
        toolbar_frame.pack(fill="x")
        toolbar = NavigationToolbar2Tk(self.motor_eff_canvas, toolbar_frame)
        toolbar.update()

    def _create_prop_efficiency_tab(self):
        """Create propeller efficiency analysis tab."""
        frame = ttk.Frame(self.results_notebook, padding=5)
        self.results_notebook.add(frame, text="Prop Efficiency")

        # Create matplotlib figure
        self.prop_eff_fig = Figure(figsize=(8, 5), dpi=100)
        self.prop_eff_ax = self.prop_eff_fig.add_subplot(111)

        self.prop_eff_canvas = FigureCanvasTkAgg(self.prop_eff_fig, master=frame)
        self.prop_eff_canvas.draw()
        self.prop_eff_canvas.get_tk_widget().pack(fill="both", expand=True)

        # Toolbar
        toolbar_frame = ttk.Frame(frame)
        toolbar_frame.pack(fill="x")
        toolbar = NavigationToolbar2Tk(self.prop_eff_canvas, toolbar_frame)
        toolbar.update()

    def _create_verbose_calcs_tab(self):
        """Create verbose calculations tab with step-by-step engineering output."""
        frame = ttk.Frame(self.results_notebook, padding=5)
        self.results_notebook.add(frame, text="Verbose Calcs")

        # Header
        header_frame = ttk.Frame(frame)
        header_frame.pack(fill="x", pady=5)
        ttk.Label(header_frame, text="Step-by-Step Calculation Details",
                  font=("TkDefaultFont", 11, "bold")).pack(side="left")

        # Copy button
        ttk.Button(header_frame, text="Copy to Clipboard",
                   command=self._copy_verbose_to_clipboard).pack(side="right", padx=5)

        # Scrollable text widget with monospace font
        text_frame = ttk.Frame(frame)
        text_frame.pack(fill="both", expand=True)

        self.verbose_text = tk.Text(text_frame, wrap="none", font=("Consolas", 9),
                                     bg="#1e1e1e", fg="#d4d4d4")
        v_scroll = ttk.Scrollbar(text_frame, orient="vertical", command=self.verbose_text.yview)
        h_scroll = ttk.Scrollbar(text_frame, orient="horizontal", command=self.verbose_text.xview)
        self.verbose_text.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.verbose_text.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")

        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)

        # Configure text tags for syntax highlighting
        self.verbose_text.tag_configure("header", foreground="#569cd6", font=("Consolas", 10, "bold"))
        self.verbose_text.tag_configure("subheader", foreground="#4ec9b0")
        self.verbose_text.tag_configure("param", foreground="#9cdcfe")
        self.verbose_text.tag_configure("value", foreground="#ce9178")
        self.verbose_text.tag_configure("unit", foreground="#608b4e")
        self.verbose_text.tag_configure("equation", foreground="#dcdcaa")
        self.verbose_text.tag_configure("result", foreground="#4fc1ff")
        self.verbose_text.tag_configure("warning", foreground="#f14c4c")

    def _copy_verbose_to_clipboard(self):
        """Copy verbose output to clipboard."""
        content = self.verbose_text.get(1.0, tk.END)
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        messagebox.showinfo("Copied", "Verbose output copied to clipboard")

    def _create_status_bar(self):
        """Create status bar."""
        status_frame = ttk.Frame(self.main_frame)
        status_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(5, 0))

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(
            status_frame, textvariable=self.status_var, anchor="w"
        ).pack(side="left", fill="x", expand=True)

    # =========================================================================
    # Event Handlers
    # =========================================================================

    def _select_all_motors(self):
        """Select all motor categories."""
        for var in self.motor_category_vars.values():
            var.set(True)
        self._schedule_permutation_update()

    def _select_no_motors(self):
        """Deselect all motor categories."""
        for var in self.motor_category_vars.values():
            var.set(False)
        self._schedule_permutation_update()

    def _on_sort_change(self, event=None):
        """Handle sort option change."""
        self._update_summary_display()

    def _on_result_selected(self, event=None):
        """Handle result selection in treeview."""
        selection = self.summary_tree.selection()
        if not selection:
            return

        # Get selected item index
        item = self.summary_tree.item(selection[0])
        values = item['values']
        if not values:
            return

        # Find matching result
        rank = int(values[0])
        if rank <= len(self._displayed_results):
            self._selected_result = self._displayed_results[rank - 1]
            self._update_detail_tabs()

    def _update_speed_display(self):
        """Update speed display in mph."""
        try:
            speed_ms = float(self.cruise_speed_var.get())
            mph = speed_ms * 2.237
            self.cruise_mph_label.config(text=f"({mph:.1f} mph)")
        except ValueError:
            pass

    def _update_speed_range_display(self):
        """Update speed range display with mph conversions and point count."""
        try:
            min_speed = float(self.cruise_min_var.get())
            max_speed = float(self.cruise_max_var.get())
            step = float(self.cruise_step_var.get())

            # Update mph labels
            self.cruise_min_mph_label.config(text=f"({min_speed * 2.237:.1f} mph)")
            self.cruise_max_mph_label.config(text=f"({max_speed * 2.237:.1f} mph)")

            # Calculate speed points
            if step > 0 and max_speed >= min_speed:
                speeds = []
                current = min_speed
                while current <= max_speed + 0.001:
                    speeds.append(round(current, 1))
                    current += step

                num_points = len(speeds)
                if num_points <= 5:
                    points_str = ", ".join(f"{s:.0f}" for s in speeds)
                    self.speed_points_label.config(text=f"{num_points} points ({points_str} m/s)")
                else:
                    self.speed_points_label.config(
                        text=f"{num_points} points ({speeds[0]:.0f}, {speeds[1]:.0f}, ... {speeds[-1]:.0f} m/s)"
                    )
            else:
                self.speed_points_label.config(text="Invalid range")
        except ValueError:
            self.speed_points_label.config(text="--")

    # =========================================================================
    # Permutation Counting
    # =========================================================================

    def _schedule_permutation_update(self):
        """Schedule a permutation count update (debounced)."""
        if hasattr(self, '_perm_update_id'):
            self.root.after_cancel(self._perm_update_id)
        self._perm_update_id = self.root.after(200, self._update_permutation_count)

    def _update_permutation_count(self):
        """Update the permutation count display."""
        try:
            # Count selected motors
            selected_categories = [
                cat for cat, var in self.motor_category_vars.items()
                if var.get()
            ]
            motor_set = set()
            for cat in selected_categories:
                motor_set.update(
                    self._motor_presets.get("categories", {}).get(cat, [])
                )
            motor_count = len(motor_set)
            self.motor_count_var.set(f"{motor_count} motors selected")

            # Count matching props
            try:
                dia_min = float(self.prop_dia_min_var.get())
                dia_max = float(self.prop_dia_max_var.get())
                pitch_min = float(self.prop_pitch_min_var.get())
                pitch_max = float(self.prop_pitch_max_var.get())

                matching_props = []
                for prop_id in self._all_props:
                    d, p = parse_prop_dimensions(prop_id)
                    if d and p:
                        if dia_min <= d <= dia_max and pitch_min <= p <= pitch_max:
                            matching_props.append(prop_id)
                prop_count = len(matching_props)
            except ValueError:
                prop_count = 0
            self.prop_count_var.set(f"{prop_count} props matched")

            # Count selected cell types
            cell_count = sum(1 for v in self.cell_type_vars.values() if v.get())

            # Count series/parallel based on mode
            selected_series = [s for s, v in self.series_vars.items() if v.get()]
            series_count = len(selected_series)

            if self.parallel_mode_var.get() == "all_combinations":
                # All selected series × all selected parallel
                selected_parallel = [p for p, v in self.parallel_vars.items() if v.get()]
                parallel_count = len(selected_parallel)
                sp_combinations = series_count * parallel_count
            else:
                # Per-series mode: count actual selected combinations
                sp_combinations = 0
                for s in selected_series:
                    if s in self.per_series_parallel_vars:
                        sp_combinations += sum(1 for v in self.per_series_parallel_vars[s].values() if v.get())
                parallel_count = sp_combinations // max(1, series_count) if series_count > 0 else 0

            # Count thermal environments
            thermal_count = sum(1 for v in self.thermal_env_vars.values() if v.get())

            # Battery configurations
            battery_configs = cell_count * sp_combinations * thermal_count
            self.battery_count_var.set(f"{battery_configs} battery configs")

            # Total permutations
            total = motor_count * prop_count * battery_configs
            self.perm_count_var.set(f"{total:,}")

            # Breakdown
            if self.parallel_mode_var.get() == "all_combinations":
                self.perm_breakdown_var.set(
                    f"({motor_count} motors x {prop_count} props x "
                    f"{cell_count} cells x {series_count}S x {parallel_count}P x {thermal_count} thermal)"
                )
            else:
                self.perm_breakdown_var.set(
                    f"({motor_count} motors x {prop_count} props x "
                    f"{cell_count} cells x {sp_combinations} S/P combos x {thermal_count} thermal)"
                )

            # Warning/color (no max limit - just warnings)
            if total > self.LARGE_BATCH_PERMUTATIONS:
                self.perm_count_label.config(foreground="orange")
                self.perm_warning_var.set(
                    f"Very large batch - may take a long time"
                )
                self.run_btn.config(state="normal")
            elif total > self.WARNING_PERMUTATIONS:
                self.perm_count_label.config(foreground="orange")
                self.perm_warning_var.set(
                    "Large batch - may take several minutes"
                )
                self.run_btn.config(state="normal")
            elif total == 0:
                self.perm_count_label.config(foreground="gray")
                self.perm_warning_var.set("No combinations to test")
                self.run_btn.config(state="disabled")
            else:
                self.perm_count_label.config(foreground="green")
                self.perm_warning_var.set("")
                self.run_btn.config(state="normal")

        except Exception as e:
            self.perm_count_var.set("Error")
            self.perm_warning_var.set(str(e))

    # =========================================================================
    # Batch Execution
    # =========================================================================

    def _build_config(self) -> IntegratedConfig:
        """Build IntegratedConfig from UI values."""
        # Get selected motor categories
        selected_categories = [
            cat for cat, var in self.motor_category_vars.items()
            if var.get()
        ]

        # Get selected cell types
        selected_cells = [
            cell for cell, var in self.cell_type_vars.items()
            if var.get()
        ]

        # Get selected thermal environments
        selected_thermal = [
            env for env, var in self.thermal_env_vars.items()
            if var.get()
        ]

        # Get selected series values
        selected_series = [s for s, var in self.series_vars.items() if var.get()]

        # Get parallel config based on mode
        if self.parallel_mode_var.get() == "all_combinations":
            # All selected series × all selected parallel
            selected_parallel = [p for p, var in self.parallel_vars.items() if var.get()]
            series_parallel_map = None
        else:
            # Per-series mode: build map of series -> parallel values
            selected_parallel = None
            series_parallel_map = {}
            for s in selected_series:
                if s in self.per_series_parallel_vars:
                    parallel_for_s = [p for p, var in self.per_series_parallel_vars[s].items() if var.get()]
                    if parallel_for_s:
                        series_parallel_map[s] = parallel_for_s

        # Build battery config
        battery_config = BatteryIterationConfig(
            cell_types=selected_cells,
            series_values=selected_series,
            parallel_values=selected_parallel,
            series_parallel_map=series_parallel_map,
            thermal_environments=selected_thermal,
            ambient_temp_c=float(self.ambient_temp_var.get()),
            max_cell_temp_c=float(self.max_cell_temp_var.get()),
            soc_for_analysis=float(self.analysis_soc_var.get()),
        )

        # Build cruise speed config
        if self.batch_cruise_var.get():
            cruise_speed_range = (
                float(self.cruise_min_var.get()),
                float(self.cruise_max_var.get())
            )
            cruise_speed_step = float(self.cruise_step_var.get())
            cruise_speed = float(self.cruise_min_var.get())  # Default to min
        else:
            cruise_speed_range = None
            cruise_speed_step = 2.0
            cruise_speed = float(self.cruise_speed_var.get())

        return IntegratedConfig(
            wing_area=float(self.wing_area_var.get()),
            wingspan=float(self.wingspan_var.get()),
            weight=float(self.weight_var.get()),
            cd0=float(self.cd0_var.get()),
            oswald_efficiency=float(self.oswald_var.get()),
            motor_categories=selected_categories,
            prop_diameter_range=(float(self.prop_dia_min_var.get()), float(self.prop_dia_max_var.get())),
            prop_pitch_range=(float(self.prop_pitch_min_var.get()), float(self.prop_pitch_max_var.get())),
            cruise_speed=cruise_speed,
            cruise_speed_range=cruise_speed_range,
            cruise_speed_step=cruise_speed_step,
            evaluate_max_speed=self.eval_max_speed_var.get(),
            battery_config=battery_config,
        )

    def _start_batch(self):
        """Start batch analysis."""
        try:
            # Build config
            config = self._build_config()

            # Validate
            is_valid, error = config.validate()
            if not is_valid:
                messagebox.showerror("Configuration Error", error)
                return

            # Create solver
            self._solver = IntegratedSolver(config)

            # Check permutation count - warn but don't block
            total = self._solver.get_permutation_count()
            if total > self.LARGE_BATCH_PERMUTATIONS:
                if not messagebox.askyesno(
                    "Very Large Batch",
                    f"This will test {total:,} combinations and may take "
                    "a long time.\n\nAre you sure you want to continue?"
                ):
                    return
            elif total > self.WARNING_PERMUTATIONS:
                if not messagebox.askyesno(
                    "Large Batch",
                    f"This will test {total:,} combinations and may take "
                    "several minutes.\n\nContinue?"
                ):
                    return

            # Update UI state
            self.run_btn.config(state="disabled")
            self.cancel_btn.config(state="normal")
            self._results = []
            self._batch_result = None
            self._batch_error = None  # Reset error state
            self._clear_results_display()

            # Reset progress
            self.progress_var.set(0)
            self.progress_status_var.set("Starting batch analysis...")
            self.progress_detail_var.set("")
            self.progress_stats_var.set("")
            self.progress_time_var.set("")
            self.summary_var.set("Analysis in progress...")

            # Start batch in thread
            self._batch_thread = threading.Thread(
                target=self._run_batch_thread, daemon=True
            )
            self._batch_thread.start()

            # Start progress polling
            self._poll_progress()

        except ValueError as e:
            messagebox.showerror("Input Error", str(e))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _run_batch_thread(self):
        """Run batch analysis in background thread."""
        try:
            self._batch_result = self._solver.run_batch(
                progress_callback=self._on_progress_update
            )
            self._results = self._batch_result.results
        except Exception as e:
            self._batch_error = str(e)

    def _on_progress_update(self, progress):
        """Handle progress update from solver."""
        pass  # Progress is polled from main thread

    def _format_time(self, seconds: float) -> str:
        """Format seconds into human-readable time string."""
        if seconds == float('inf') or seconds < 0:
            return "calculating..."
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            mins = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{mins}m {secs}s"
        else:
            hours = int(seconds // 3600)
            mins = int((seconds % 3600) // 60)
            return f"{hours}h {mins}m"

    def _poll_progress(self):
        """Poll progress and update UI."""
        if self._solver is None:
            return

        progress = self._solver.progress

        # Update progress bar
        self.progress_var.set(progress.percent_complete)

        # Update status
        if progress.is_running:
            # Main status with ETA
            if progress.total > 0 and progress.current > 0:
                remaining = progress.estimated_remaining_seconds
                eta_str = self._format_time(remaining)
                self.progress_status_var.set(
                    f"Processing {progress.current:,} / {progress.total:,} "
                    f"({progress.percent_complete:.1f}%) - ETA: {eta_str}"
                )
            elif progress.total > 0:
                self.progress_status_var.set(
                    f"Starting... {progress.total:,} combinations to process"
                )
            else:
                self.progress_status_var.set("Generating work items...")

            # Current item detail
            if progress.current_motor and progress.current_prop:
                self.progress_detail_var.set(
                    f"Current: {progress.current_motor} + {progress.current_prop}"
                )

            # Stats
            self.progress_stats_var.set(
                f"Valid: {progress.results_valid:,} | "
                f"Invalid: {progress.results_invalid:,}"
            )

            # Time info
            if progress.elapsed_seconds > 0 and progress.current > 0:
                rate = progress.rate_per_second
                elapsed_str = self._format_time(progress.elapsed_seconds)
                self.progress_time_var.set(
                    f"Rate: {rate:.0f}/sec | Elapsed: {elapsed_str}"
                )

            # Continue polling
            self.root.after(100, self._poll_progress)

        else:
            # Batch complete
            self._on_batch_complete()

    def _on_batch_complete(self):
        """Handle batch completion."""
        self.run_btn.config(state="normal")
        self.cancel_btn.config(state="disabled")

        # Check for errors from batch thread
        if hasattr(self, '_batch_error') and self._batch_error:
            self.progress_status_var.set("Error!")
            self.status_var.set(f"Batch failed: {self._batch_error}")
            self.summary_var.set("Analysis failed - see error above")
            messagebox.showerror("Batch Error", self._batch_error)
            return

        if self._solver.progress.is_cancelled:
            self.progress_status_var.set("Cancelled")
            self.status_var.set("Batch analysis cancelled")
            self.summary_var.set("Analysis cancelled")
        else:
            self.progress_status_var.set("Complete!")
            valid_count = len([r for r in self._results if r.valid])
            self.status_var.set(
                f"Batch complete: {valid_count:,} valid results "
                f"from {len(self._results):,} combinations"
            )

            # Update summary
            if self._batch_result and self._batch_result.best_by_efficiency:
                best = self._batch_result.best_by_efficiency
                self.summary_var.set(
                    f"Best: {best.motor_id} + {best.prop_id} + "
                    f"{best.cell_type} {best.pack_config} | "
                    f"Eff: {best.cruise_result.system_efficiency*100:.1f}% | "
                    f"Runtime: {best.cruise_runtime_minutes:.1f}min"
                )

        # Update results display
        self._update_summary_display()

        # Write results to temp file for recovery
        self._write_results_to_temp()

    def _cancel_batch(self):
        """Cancel running batch."""
        if self._solver:
            self._solver.cancel()
        self.progress_status_var.set("Cancelling...")

    # =========================================================================
    # Results Display
    # =========================================================================

    def _clear_results_display(self):
        """Clear all results displays."""
        for item in self.summary_tree.get_children():
            self.summary_tree.delete(item)
        self.result_count_var.set("")
        self._displayed_results = []

    def _update_summary_display(self):
        """Update summary results table."""
        self._clear_results_display()

        if not self._results:
            return

        # Get sort metric
        metric = self.sort_var.get()

        # Get top N
        top_n_str = self.top_n_var.get()
        if top_n_str == "All":
            top_n = len(self._results)
        else:
            top_n = int(top_n_str)

        # Filter and sort
        valid_results = [r for r in self._results if r.valid]

        if metric == "efficiency":
            valid_results.sort(key=lambda r: r.cruise_result.system_efficiency, reverse=True)
        elif metric == "runtime":
            valid_results.sort(key=lambda r: r.cruise_runtime_minutes, reverse=True)
        elif metric == "max_speed":
            valid_results.sort(key=lambda r: r.max_achievable_speed, reverse=True)
        elif metric == "power_density":
            valid_results.sort(key=lambda r: r.power_density_w_kg, reverse=True)

        # Display top N
        display_results = valid_results[:top_n]
        self._displayed_results = display_results

        for i, r in enumerate(display_results, 1):
            thermal_status = "OK"
            if r.thermal_throttle_limit is not None:
                thermal_status = f"{r.thermal_throttle_limit:.0f}%"

            self.summary_tree.insert("", "end", values=(
                i,
                r.motor_id,
                r.prop_id,
                r.cell_type,
                r.pack_config,
                f"{r.cruise_result.system_efficiency*100:.1f}",
                f"{r.cruise_result.battery_power:.0f}",
                f"{r.cruise_runtime_minutes:.1f}",
                f"{r.max_achievable_speed:.1f}" if r.max_achievable_speed > 0 else "N/A",
                thermal_status,
                "Yes" if r.valid else "No",
            ))

        self.result_count_var.set(
            f"Showing {len(display_results)} of {len(valid_results)} valid results"
        )

    def _update_detail_tabs(self):
        """Update detail tabs for selected result."""
        if not self._selected_result:
            return

        r = self._selected_result

        # Update motor tab
        motor_text = self._format_motor_details(r)
        self.motor_detail_text.config(state="normal")
        self.motor_detail_text.delete(1.0, tk.END)
        self.motor_detail_text.insert(tk.END, motor_text)
        self.motor_detail_text.config(state="disabled")

        # Update prop tab
        prop_text = self._format_prop_details(r)
        self.prop_detail_text.config(state="normal")
        self.prop_detail_text.delete(1.0, tk.END)
        self.prop_detail_text.insert(tk.END, prop_text)
        self.prop_detail_text.config(state="disabled")

        # Update battery tab
        battery_text = self._format_battery_details(r)
        self.battery_detail_text.config(state="normal")
        self.battery_detail_text.delete(1.0, tk.END)
        self.battery_detail_text.insert(tk.END, battery_text)
        self.battery_detail_text.config(state="disabled")

        # Update plots
        self._plot_speed_curves(r)
        self._plot_thermal_analysis(r)
        self._plot_motor_efficiency(r)
        self._plot_prop_efficiency(r)

        # Update verbose calculations tab
        self._update_verbose_calcs(r)

    def _format_motor_details(self, r: IntegratedResult) -> str:
        """Format motor details for display."""
        lines = [
            f"Motor: {r.motor_id}",
            "=" * 50,
            "",
            "CRUISE OPERATING POINT",
            "-" * 50,
            f"Airspeed:           {r.cruise_result.airspeed:.1f} m/s ({r.cruise_result.airspeed * 2.237:.1f} mph)",
            f"Throttle:           {r.cruise_result.throttle:.1f}%",
            f"Motor Current:      {r.cruise_result.motor_current:.2f} A",
            f"Motor Power:        {r.cruise_result.battery_power:.0f} W",
            f"Motor RPM:          {r.cruise_result.prop_rpm:.0f}",
            f"Motor Efficiency:   {r.cruise_result.motor_efficiency * 100:.1f}%",
            "",
        ]

        if r.max_speed_result:
            lines.extend([
                "MAX SPEED OPERATING POINT",
                "-" * 50,
                f"Airspeed:           {r.max_speed_result.airspeed:.1f} m/s ({r.max_speed_result.airspeed * 2.237:.1f} mph)",
                f"Throttle:           {r.max_speed_result.throttle:.1f}%",
                f"Motor Current:      {r.max_speed_result.motor_current:.2f} A",
                f"Motor Power:        {r.max_speed_result.battery_power:.0f} W",
                f"Motor RPM:          {r.max_speed_result.prop_rpm:.0f}",
                f"Motor Efficiency:   {r.max_speed_result.motor_efficiency * 100:.1f}%",
                "",
            ])

        return "\n".join(lines)

    def _format_prop_details(self, r: IntegratedResult) -> str:
        """Format propeller details for display."""
        lines = [
            f"Propeller: {r.prop_id}",
            "=" * 50,
            "",
            "CRUISE OPERATING POINT",
            "-" * 50,
            f"Airspeed:           {r.cruise_result.airspeed:.1f} m/s",
            f"RPM:                {r.cruise_result.prop_rpm:.0f}",
            f"Thrust Required:    (see flight solver for drag)",
            f"Prop Efficiency:    {r.cruise_result.prop_efficiency * 100:.1f}%",
            f"Advance Ratio J:    (calculated internally)",
            "",
        ]

        if r.max_speed_result:
            lines.extend([
                "MAX SPEED OPERATING POINT",
                "-" * 50,
                f"Airspeed:           {r.max_speed_result.airspeed:.1f} m/s",
                f"RPM:                {r.max_speed_result.prop_rpm:.0f}",
                f"Prop Efficiency:    {r.max_speed_result.prop_efficiency * 100:.1f}%",
                "",
            ])

        return "\n".join(lines)

    def _format_battery_details(self, r: IntegratedResult) -> str:
        """Format battery details for display."""
        lines = [
            f"Battery: {r.cell_type} {r.pack_config}",
            f"Thermal Environment: {r.thermal_environment}",
            "=" * 50,
            "",
            "PACK SPECIFICATIONS",
            "-" * 50,
            f"Configuration:      {r.series}S{r.parallel}P",
            f"Nominal Voltage:    {r.pack_voltage_nominal:.1f} V",
            f"Capacity:           {r.pack_capacity_mah:.0f} mAh",
            f"Energy:             {r.pack_energy_wh:.1f} Wh",
            f"Pack Mass:          {r.pack_mass_kg * 1000:.0f} g ({r.pack_mass_kg:.3f} kg)",
            f"Energy Density:     {r.energy_density_wh_kg:.0f} Wh/kg",
            f"Power Density:      {r.power_density_w_kg:.0f} W/kg",
            "",
            "CRUISE PERFORMANCE",
            "-" * 50,
            f"Battery Current:    {r.cruise_result.battery_current:.2f} A",
            f"Battery Power:      {r.cruise_result.battery_power:.0f} W",
            f"Loaded Voltage:     {r.cruise_result.loaded_voltage:.2f} V",
            f"Steady-State Temp:  {r.cruise_result.thermal_eval.steady_state_temp_c:.1f} C",
            f"Thermal Margin:     {r.cruise_result.thermal_eval.thermal_margin_c:.1f} C",
            f"Heat Generation:    {r.cruise_result.thermal_eval.heat_generation_w:.1f} W",
            f"Runtime:            {r.cruise_runtime_minutes:.1f} min",
            "",
        ]

        if r.max_speed_result:
            lines.extend([
                "MAX SPEED PERFORMANCE",
                "-" * 50,
                f"Battery Current:    {r.max_speed_result.battery_current:.2f} A",
                f"Battery Power:      {r.max_speed_result.battery_power:.0f} W",
                f"Loaded Voltage:     {r.max_speed_result.loaded_voltage:.2f} V",
                f"Steady-State Temp:  {r.max_speed_result.thermal_eval.steady_state_temp_c:.1f} C",
                f"Thermal Margin:     {r.max_speed_result.thermal_eval.thermal_margin_c:.1f} C",
                "",
            ])

        if r.thermal_throttle_limit is not None:
            lines.extend([
                "THERMAL LIMITS",
                "-" * 50,
                f"Max Safe Throttle:  {r.thermal_throttle_limit:.1f}%",
                "Note: Thermal limit reached before 100% throttle",
                "",
            ])

        return "\n".join(lines)

    def _plot_speed_curves(self, r: IntegratedResult):
        """Plot speed vs efficiency/power curves using actual cruise speed data."""
        self.speed_ax.clear()

        # Get cruise speed results
        valid_results = [res for res in r.cruise_speed_results if res.valid]

        if not valid_results:
            # Fallback to single points
            valid_results = [r.cruise_result]

        # Extract data for curves
        speeds = [res.airspeed for res in valid_results]
        efficiencies = [res.system_efficiency * 100 for res in valid_results]
        powers = [res.battery_power for res in valid_results]
        runtimes = [res.runtime_minutes for res in valid_results]

        # Sort by speed
        sorted_data = sorted(zip(speeds, efficiencies, powers, runtimes))
        speeds = [d[0] for d in sorted_data]
        efficiencies = [d[1] for d in sorted_data]
        powers = [d[2] for d in sorted_data]
        runtimes = [d[3] for d in sorted_data]

        # Create figure with better layout
        self.speed_ax.set_xlabel('Airspeed (m/s)', fontsize=10)

        # Plot efficiency as primary line
        color1 = 'tab:blue'
        line1, = self.speed_ax.plot(speeds, efficiencies, 'o-', color=color1,
                                     linewidth=2, markersize=6, label='Efficiency (%)')
        self.speed_ax.set_ylabel('System Efficiency (%)', color=color1, fontsize=10)
        self.speed_ax.tick_params(axis='y', labelcolor=color1)

        # Find peak efficiency
        if efficiencies:
            peak_idx = efficiencies.index(max(efficiencies))
            self.speed_ax.axvline(x=speeds[peak_idx], color=color1, linestyle=':',
                                  alpha=0.5, linewidth=1)
            self.speed_ax.annotate(f'Peak Eff: {max(efficiencies):.1f}%\n@ {speeds[peak_idx]:.1f} m/s',
                                   xy=(speeds[peak_idx], max(efficiencies)),
                                   xytext=(10, -20), textcoords='offset points',
                                   fontsize=8, color=color1)

        # Secondary axis for power
        ax2 = self.speed_ax.twinx()
        color2 = 'tab:red'
        line2, = ax2.plot(speeds, powers, 's--', color=color2,
                          linewidth=2, markersize=5, label='Power (W)')
        ax2.set_ylabel('Power (W)', color=color2, fontsize=10)
        ax2.tick_params(axis='y', labelcolor=color2)

        # Mark max speed point if available
        if r.max_speed_result and r.max_speed_result.valid:
            max_v = r.max_speed_result.airspeed
            max_eff = r.max_speed_result.system_efficiency * 100
            max_pwr = r.max_speed_result.battery_power
            self.speed_ax.axvline(x=max_v, color='darkred', linestyle='--',
                                  alpha=0.7, linewidth=1.5, label=f'Max Speed ({max_v:.1f} m/s)')
            self.speed_ax.scatter([max_v], [max_eff], color='darkred', s=100, marker='*', zorder=5)

        # Mark primary cruise speed
        cruise_v = r.cruise_result.airspeed
        self.speed_ax.axvline(x=cruise_v, color='green', linestyle='--',
                              alpha=0.7, linewidth=1.5, label=f'Primary Cruise ({cruise_v:.1f} m/s)')

        # Combined legend
        lines = [line1, line2]
        labels = [l.get_label() for l in lines]
        self.speed_ax.legend(lines, labels, loc='upper left', fontsize=8)

        self.speed_ax.set_title(f'{r.motor_id} + {r.prop_id} + {r.cell_type} {r.pack_config}',
                                fontsize=11, fontweight='bold')
        self.speed_ax.grid(True, alpha=0.3)
        self.speed_ax.set_xlim(left=0)

        self.speed_fig.tight_layout()
        self.speed_canvas.draw()

    def _plot_thermal_analysis(self, r: IntegratedResult):
        """Plot thermal analysis with physics-based extrapolation (T = T_amb + k*I²)."""
        self.thermal_ax.clear()

        # Get thermal data from cruise speed results
        valid_results = [res for res in r.cruise_speed_results if res.valid and res.thermal_eval]

        if not valid_results:
            valid_results = [r.cruise_result]

        # Extract current and temperature data
        currents = [res.battery_current for res in valid_results]
        temps = [res.thermal_eval.steady_state_temp_c for res in valid_results]

        # Sort by current
        sorted_data = sorted(zip(currents, temps))
        currents_sorted = np.array([d[0] for d in sorted_data])
        temps_sorted = np.array([d[1] for d in sorted_data])

        # Get max allowed temperature
        max_temp = r.cruise_result.thermal_eval.steady_state_temp_c + r.cruise_result.thermal_eval.thermal_margin_c

        # Determine max current for extrapolation (to max speed or beyond)
        max_current_data = max(currents_sorted) if len(currents_sorted) > 0 else 20
        if r.max_speed_result and r.max_speed_result.valid:
            max_current_extrap = max(max_current_data, r.max_speed_result.battery_current) * 1.1
        else:
            max_current_extrap = max_current_data * 1.3

        # Physics-based extrapolation: T = T_ambient + k * I²
        # Fit k coefficient from data points
        if len(currents_sorted) >= 2:
            # Assume ambient ~25°C (or estimate from lowest current point)
            T_ambient_est = temps_sorted[0] - 0.5 * (temps_sorted[1] - temps_sorted[0]) if len(temps_sorted) > 1 else 25

            # Fit T = T_amb + k * I² using least squares
            # T - T_amb = k * I² => solve for k
            delta_T = temps_sorted - T_ambient_est
            I_squared = currents_sorted ** 2
            k_fit = np.sum(delta_T * I_squared) / np.sum(I_squared ** 2) if np.sum(I_squared ** 2) > 0 else 0.01

            # Generate physics-based extrapolation curve
            I_extrap = np.linspace(0, max_current_extrap, 50)
            T_extrap = T_ambient_est + k_fit * I_extrap ** 2

            # Plot calculated data points as solid line
            self.thermal_ax.plot(currents_sorted, temps_sorted, 'b-', linewidth=2.5,
                                 label='Calculated Points', alpha=0.9)
            self.thermal_ax.scatter(currents_sorted, temps_sorted, c='blue', s=50,
                                    marker='o', zorder=3, edgecolors='white')

            # Plot physics-based extrapolation as dotted line
            # Only show extrapolation beyond data points
            mask_extrap = I_extrap > max_current_data
            if np.any(mask_extrap):
                self.thermal_ax.plot(I_extrap[mask_extrap], T_extrap[mask_extrap], 'b:',
                                     linewidth=2, alpha=0.7, label='Physics Extrapolation (I²R)')

            # Show thermal model equation
            self.thermal_ax.text(0.98, 0.02,
                                 f'Model: T = {T_ambient_est:.1f} + {k_fit:.4f}·I²',
                                 transform=self.thermal_ax.transAxes,
                                 fontsize=8, ha='right', va='bottom',
                                 bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.7))

        # Draw max temperature limit line
        self.thermal_ax.axhline(y=max_temp, color='red', linestyle='--', linewidth=2,
                                alpha=0.8, label=f'Max Temp Limit ({max_temp:.0f}°C)')

        # Fill danger zone
        self.thermal_ax.fill_between([0, max_current_extrap], [max_temp, max_temp],
                                      [max_temp + 25, max_temp + 25],
                                      color='red', alpha=0.1)

        # Mark cruise operating point
        cruise_i = r.cruise_result.battery_current
        cruise_t = r.cruise_result.thermal_eval.steady_state_temp_c
        self.thermal_ax.scatter([cruise_i], [cruise_t], c='green', s=180,
                                marker='*', zorder=5, edgecolors='black', linewidths=1.5)
        self.thermal_ax.annotate(f'Cruise\n{cruise_t:.1f}°C',
                                 xy=(cruise_i, cruise_t),
                                 xytext=(12, 12), textcoords='offset points',
                                 fontsize=9, color='green', fontweight='bold',
                                 bbox=dict(boxstyle='round', facecolor='white', alpha=0.7))

        # Mark max speed operating point and draw dotted line to it
        if r.max_speed_result and r.max_speed_result.valid:
            max_i = r.max_speed_result.battery_current
            max_t = r.max_speed_result.thermal_eval.steady_state_temp_c
            color = 'darkred' if max_t >= max_temp else 'orange'
            status = 'OVER LIMIT!' if max_t >= max_temp else 'OK'

            # Draw dotted connection line from last data point to max speed point
            if len(currents_sorted) > 0 and max_i > currents_sorted[-1]:
                self.thermal_ax.plot([currents_sorted[-1], max_i], [temps_sorted[-1], max_t],
                                     'b:', linewidth=2, alpha=0.5)

            self.thermal_ax.scatter([max_i], [max_t], c=color, s=180,
                                    marker='*', zorder=5, edgecolors='white', linewidths=1.5)
            self.thermal_ax.annotate(f'Max Speed\n{max_t:.1f}°C\n{status}',
                                     xy=(max_i, max_t),
                                     xytext=(12, -35), textcoords='offset points',
                                     fontsize=9, color=color, fontweight='bold',
                                     bbox=dict(boxstyle='round', facecolor='white', alpha=0.7))

        # Thermal margin indicator
        margin = r.cruise_result.thermal_eval.thermal_margin_c
        margin_color = 'green' if margin > 10 else ('orange' if margin > 5 else 'red')
        self.thermal_ax.text(0.02, 0.98, f'Thermal Margin: {margin:.1f}°C',
                             transform=self.thermal_ax.transAxes,
                             fontsize=10, fontweight='bold', color=margin_color,
                             verticalalignment='top',
                             bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

        self.thermal_ax.set_xlabel('Battery Current (A)', fontsize=10)
        self.thermal_ax.set_ylabel('Steady-State Temperature (°C)', fontsize=10)
        self.thermal_ax.set_title(f'Thermal Analysis - {r.cell_type} {r.pack_config} ({r.thermal_environment})',
                                  fontsize=11, fontweight='bold')
        self.thermal_ax.grid(True, alpha=0.3)
        self.thermal_ax.legend(loc='upper left', fontsize=8)
        self.thermal_ax.set_xlim(left=0)
        self.thermal_ax.set_ylim(bottom=20)

        self.thermal_fig.tight_layout()
        self.thermal_canvas.draw()

    def _plot_motor_efficiency(self, r: IntegratedResult):
        """Plot motor efficiency contour map (RPM vs Current) with operating points overlaid."""
        self.motor_eff_fig.clear()
        self.motor_eff_ax = self.motor_eff_fig.add_subplot(111)

        # Get motor data from presets
        motor_data = self._motors.get(r.motor_id)
        if not motor_data:
            self.motor_eff_ax.text(0.5, 0.5, f'Motor data not found for {r.motor_id}',
                                   transform=self.motor_eff_ax.transAxes,
                                   ha='center', va='center', fontsize=12)
            self.motor_eff_canvas.draw()
            return

        # Get motor parameters
        kv = motor_data.get('kv', 1000)
        rm = motor_data.get('rm_cold', 0.030)
        i0_ref = motor_data.get('i0_ref', 1.5)
        i0_rpm_ref = motor_data.get('i0_rpm_ref', 10000)
        i_max = motor_data.get('i_max', 50)
        v_supply = r.pack_voltage_nominal
        kt = 9.5493 / kv  # Torque constant Nm/A

        # Define grid for contour plot: X=RPM, Y=Current
        max_rpm = kv * v_supply  # No-load RPM
        rpm_values = np.linspace(2000, max_rpm * 0.95, 45)
        current_values = np.linspace(i0_ref * 1.2, i_max, 40)

        # Create 2D efficiency map
        efficiency_map = np.zeros((len(current_values), len(rpm_values)))

        for i, current in enumerate(current_values):
            for j, rpm in enumerate(rpm_values):
                # Calculate no-load current at this RPM
                i0 = i0_ref * np.sqrt(rpm / i0_rpm_ref) if i0_rpm_ref > 0 else i0_ref

                # Back-EMF at this RPM
                v_bemf = rpm / kv
                # Voltage needed = back-EMF + IR drop
                v_needed = v_bemf + current * rm

                if v_needed > v_supply or current < i0:
                    efficiency_map[i, j] = np.nan  # Invalid operating point
                else:
                    # Calculate efficiency: eta = P_mech / P_elec
                    i_torque = current - i0
                    torque = i_torque * kt if i_torque > 0 else 0
                    omega = rpm * 2 * np.pi / 60
                    p_mech = torque * omega
                    p_elec = v_needed * current

                    if p_elec > 0 and p_mech > 0:
                        eff = min(p_mech / p_elec * 100, 98)
                        efficiency_map[i, j] = eff
                    else:
                        efficiency_map[i, j] = np.nan

        # Create meshgrid
        RPM, CURRENT = np.meshgrid(rpm_values, current_values)

        # Plot contour map
        efficiency_masked = np.ma.masked_invalid(efficiency_map)
        levels = np.arange(40, 96, 4)

        contourf = self.motor_eff_ax.contourf(RPM, CURRENT, efficiency_masked,
                                               levels=levels, cmap='viridis', extend='both')
        contour_lines = self.motor_eff_ax.contour(RPM, CURRENT, efficiency_masked,
                                                   levels=levels, colors='white',
                                                   linewidths=0.5, alpha=0.6)
        self.motor_eff_ax.clabel(contour_lines, inline=True, fontsize=7, fmt='%.0f%%')

        # Add colorbar
        cbar = self.motor_eff_fig.colorbar(contourf, ax=self.motor_eff_ax, shrink=0.9)
        cbar.set_label('Motor Efficiency (%)', fontsize=9)

        # Plot max current limit line
        self.motor_eff_ax.axhline(y=i_max, color='red', linestyle='--', linewidth=2,
                                   alpha=0.8, label=f'Max Current ({i_max:.0f}A)')

        # Overlay operating points from cruise speed results
        valid_results = [res for res in r.cruise_speed_results if res.valid]
        if valid_results:
            op_rpms = [res.prop_rpm for res in valid_results]
            op_currents = [res.motor_current for res in valid_results]
            self.motor_eff_ax.plot(op_rpms, op_currents, 'w-', linewidth=2, alpha=0.6)
            self.motor_eff_ax.scatter(op_rpms, op_currents, c='lime', s=50,
                                       marker='o', zorder=5, edgecolors='black',
                                       linewidths=1, label='Operating Trajectory')

        # Mark primary cruise point with star
        cruise_rpm = r.cruise_result.prop_rpm
        cruise_i = r.cruise_result.motor_current
        cruise_eff = r.cruise_result.motor_efficiency * 100
        self.motor_eff_ax.scatter([cruise_rpm], [cruise_i], c='lime', s=250,
                                   marker='*', zorder=6, edgecolors='black', linewidths=2)
        self.motor_eff_ax.annotate(f'Cruise\n{cruise_eff:.1f}%',
                                   xy=(cruise_rpm, cruise_i),
                                   xytext=(15, 10), textcoords='offset points',
                                   fontsize=9, color='white', fontweight='bold',
                                   bbox=dict(boxstyle='round', facecolor='green', alpha=0.8))

        # Mark max speed point with star
        if r.max_speed_result and r.max_speed_result.valid:
            max_rpm = r.max_speed_result.prop_rpm
            max_i = r.max_speed_result.motor_current
            max_eff = r.max_speed_result.motor_efficiency * 100
            self.motor_eff_ax.scatter([max_rpm], [max_i], c='red', s=250,
                                       marker='*', zorder=6, edgecolors='white', linewidths=2)
            self.motor_eff_ax.annotate(f'Max Spd\n{max_eff:.1f}%',
                                       xy=(max_rpm, max_i),
                                       xytext=(15, -25), textcoords='offset points',
                                       fontsize=9, color='white', fontweight='bold',
                                       bbox=dict(boxstyle='round', facecolor='darkred', alpha=0.8))

        self.motor_eff_ax.set_xlabel('Motor RPM', fontsize=10)
        self.motor_eff_ax.set_ylabel('Motor Current (A)', fontsize=10)
        self.motor_eff_ax.set_title(f'Motor Efficiency Map - {r.motor_id} @ {v_supply:.1f}V',
                                    fontsize=11, fontweight='bold')
        self.motor_eff_ax.legend(loc='upper left', fontsize=8)

        self.motor_eff_fig.tight_layout()
        self.motor_eff_canvas.draw()

    def _plot_prop_efficiency(self, r: IntegratedResult):
        """Plot propeller efficiency contour map (Airspeed vs RPM) with operating points overlaid."""
        self.prop_eff_fig.clear()
        self.prop_eff_ax = self.prop_eff_fig.add_subplot(111)

        # Try to get prop data for contour map
        try:
            from src.prop_analyzer.core import PropAnalyzer
            from src.prop_analyzer.config import PropAnalyzerConfig
            prop_analyzer = PropAnalyzer(PropAnalyzerConfig())

            # Get prop operating envelope
            envelope = prop_analyzer.get_prop_operating_envelope(r.prop_id)
            min_speed = max(envelope.get('min_speed', 5), 5)
            max_speed = min(envelope.get('max_speed', 50), 60)
            min_rpm = max(envelope.get('min_rpm', 5000), 5000)
            max_rpm = min(envelope.get('max_rpm', 25000), 30000)

            # Define grid for contour plot: X=Airspeed, Y=RPM
            speed_values = np.linspace(min_speed, max_speed, 35)
            rpm_values = np.linspace(min_rpm, max_rpm, 30)

            # Create 2D efficiency map
            efficiency_map = np.zeros((len(rpm_values), len(speed_values)))

            for i, rpm in enumerate(rpm_values):
                for j, speed in enumerate(speed_values):
                    try:
                        eff = prop_analyzer.get_efficiency(r.prop_id, speed, rpm)
                        if eff is not None and 0 < eff < 1:
                            efficiency_map[i, j] = eff * 100
                        else:
                            efficiency_map[i, j] = np.nan
                    except:
                        efficiency_map[i, j] = np.nan

            # Create meshgrid
            SPEED, RPM = np.meshgrid(speed_values, rpm_values)

            # Plot contour map
            efficiency_masked = np.ma.masked_invalid(efficiency_map)
            levels = np.arange(30, 85, 5)

            contourf = self.prop_eff_ax.contourf(SPEED, RPM, efficiency_masked,
                                                  levels=levels, cmap='plasma', extend='both')
            contour_lines = self.prop_eff_ax.contour(SPEED, RPM, efficiency_masked,
                                                      levels=levels, colors='white',
                                                      linewidths=0.5, alpha=0.6)
            self.prop_eff_ax.clabel(contour_lines, inline=True, fontsize=7, fmt='%.0f%%')

            # Add colorbar
            cbar = self.prop_eff_fig.colorbar(contourf, ax=self.prop_eff_ax, shrink=0.9)
            cbar.set_label('Propeller Efficiency (%)', fontsize=9)

            contour_plotted = True
        except Exception as e:
            # Fallback to simple line plot if contour fails
            contour_plotted = False
            print(f"Could not create prop contour map: {e}")

        # Overlay operating points from cruise speed results
        valid_results = [res for res in r.cruise_speed_results if res.valid]
        if valid_results:
            op_speeds = [res.airspeed for res in valid_results]
            op_rpms = [res.prop_rpm for res in valid_results]

            # Plot operating trajectory line connecting points
            sorted_data = sorted(zip(op_speeds, op_rpms))
            op_speeds_sorted = [d[0] for d in sorted_data]
            op_rpms_sorted = [d[1] for d in sorted_data]

            self.prop_eff_ax.plot(op_speeds_sorted, op_rpms_sorted, 'w-', linewidth=2.5, alpha=0.7)
            self.prop_eff_ax.scatter(op_speeds, op_rpms, c='cyan', s=50,
                                      marker='o', zorder=5, edgecolors='black',
                                      linewidths=1, label='Operating Trajectory')

        # Mark primary cruise point with star
        cruise_v = r.cruise_result.airspeed
        cruise_rpm = r.cruise_result.prop_rpm
        cruise_eff = r.cruise_result.prop_efficiency * 100
        self.prop_eff_ax.scatter([cruise_v], [cruise_rpm], c='lime', s=250,
                                  marker='*', zorder=6, edgecolors='black', linewidths=2)
        self.prop_eff_ax.annotate(f'Cruise\n{cruise_eff:.1f}%',
                                  xy=(cruise_v, cruise_rpm),
                                  xytext=(15, 10), textcoords='offset points',
                                  fontsize=9, color='white', fontweight='bold',
                                  bbox=dict(boxstyle='round', facecolor='green', alpha=0.8))

        # Mark max speed point with star
        if r.max_speed_result and r.max_speed_result.valid:
            max_v = r.max_speed_result.airspeed
            max_rpm = r.max_speed_result.prop_rpm
            max_eff = r.max_speed_result.prop_efficiency * 100
            self.prop_eff_ax.scatter([max_v], [max_rpm], c='red', s=250,
                                      marker='*', zorder=6, edgecolors='white', linewidths=2)
            self.prop_eff_ax.annotate(f'Max Spd\n{max_eff:.1f}%',
                                      xy=(max_v, max_rpm),
                                      xytext=(15, -25), textcoords='offset points',
                                      fontsize=9, color='white', fontweight='bold',
                                      bbox=dict(boxstyle='round', facecolor='darkred', alpha=0.8))

        self.prop_eff_ax.set_xlabel('Airspeed (m/s)', fontsize=10)
        self.prop_eff_ax.set_ylabel('Propeller RPM', fontsize=10)
        self.prop_eff_ax.set_title(f'Propeller Efficiency Map - {r.prop_id}',
                                   fontsize=11, fontweight='bold')
        self.prop_eff_ax.legend(loc='upper left', fontsize=8)

        self.prop_eff_fig.tight_layout()
        self.prop_eff_canvas.draw()

    # =========================================================================
    # Verbose Calculations
    # =========================================================================

    def _update_verbose_calcs(self, r: IntegratedResult):
        """Generate step-by-step verbose calculation output."""
        self.verbose_text.config(state="normal")
        self.verbose_text.delete(1.0, tk.END)

        lines = []

        # Header
        lines.append("=" * 80)
        lines.append("INTEGRATED ANALYSIS - VERBOSE CALCULATION OUTPUT")
        lines.append("=" * 80)
        lines.append("")

        # =====================================================================
        # SECTION 1: INPUT PARAMETERS
        # =====================================================================
        lines.append("┌" + "─" * 78 + "┐")
        lines.append("│ SECTION 1: INPUT PARAMETERS" + " " * 49 + "│")
        lines.append("└" + "─" * 78 + "┘")
        lines.append("")

        # Airframe
        lines.append("  AIRFRAME PARAMETERS:")
        lines.append("  ─────────────────────")
        if self._batch_result:
            cfg = self._batch_result.config
            lines.append(f"    Wing Area (S)        = {cfg.wing_area:.4f} m²    [Planform area of main lifting surface]")
            lines.append(f"    Wingspan (b)         = {cfg.wingspan:.3f} m      [Tip-to-tip distance]")
            lines.append(f"    Weight (W)           = {cfg.weight:.3f} kg     [Total aircraft mass]")
            lines.append(f"    Aspect Ratio (AR)    = {cfg.wingspan**2/cfg.wing_area:.2f}       [AR = b²/S]")
            lines.append(f"    CD0 (parasitic)      = {cfg.cd0:.4f}        [Zero-lift drag coefficient]")
            lines.append(f"    Oswald Efficiency    = {cfg.oswald_efficiency:.2f}         [Span efficiency factor, e]")
        lines.append("")

        # Motor
        lines.append("  MOTOR PARAMETERS:")
        lines.append("  ──────────────────")
        motor_data = self._motors.get(r.motor_id, {})
        kv = motor_data.get('kv', 1000)
        rm = motor_data.get('rm_cold', 0.030)
        i0 = motor_data.get('i0_ref', 1.5)
        i_max = motor_data.get('i_max', 50)
        kt = 9.5493 / kv
        lines.append(f"    Motor ID             = {r.motor_id}")
        lines.append(f"    Kv (RPM/V)           = {kv:.0f} RPM/V   [Motor velocity constant]")
        lines.append(f"    Kt (Nm/A)            = {kt:.5f} Nm/A  [Torque constant, Kt = 9.5493/Kv]")
        lines.append(f"    Rm (winding resist)  = {rm:.4f} Ω       [Internal resistance at reference temp]")
        lines.append(f"    I0 (no-load current) = {i0:.2f} A        [No-load current at reference RPM]")
        lines.append(f"    I_max (rated max)    = {i_max:.0f} A        [Maximum continuous current rating]")
        lines.append("")

        # Propeller
        lines.append("  PROPELLER PARAMETERS:")
        lines.append("  ──────────────────────")
        lines.append(f"    Propeller ID         = {r.prop_id}")
        lines.append(f"    [Data from APC database interpolation tables]")
        lines.append("")

        # Battery Pack
        lines.append("  BATTERY PACK PARAMETERS:")
        lines.append("  ─────────────────────────")
        lines.append(f"    Cell Type            = {r.cell_type}")
        lines.append(f"    Configuration        = {r.pack_config} ({r.series}S{r.parallel}P)")
        lines.append(f"    Pack Voltage (nom)   = {r.pack_voltage_nominal:.2f} V    [V_pack = V_cell × S]")
        lines.append(f"    Pack Capacity        = {r.pack_capacity_mah:.0f} mAh  [C_pack = C_cell × P]")
        lines.append(f"    Pack Energy          = {r.pack_energy_wh:.1f} Wh    [E = V × C]")
        lines.append(f"    Pack Mass            = {r.pack_mass_kg:.3f} kg")
        lines.append(f"    Thermal Environment  = {r.thermal_environment}")
        lines.append("")

        # =====================================================================
        # SECTION 2: AERODYNAMIC CALCULATIONS
        # =====================================================================
        lines.append("┌" + "─" * 78 + "┐")
        lines.append("│ SECTION 2: AERODYNAMIC CALCULATIONS" + " " * 40 + "│")
        lines.append("└" + "─" * 78 + "┘")
        lines.append("")

        cr = r.cruise_result
        if self._batch_result:
            cfg = self._batch_result.config
            V = cr.airspeed
            rho = 1.225  # kg/m³
            q = 0.5 * rho * V**2
            W = cfg.weight * 9.81
            CL = W / (q * cfg.wing_area)
            AR = cfg.wingspan**2 / cfg.wing_area
            CDi = CL**2 / (np.pi * AR * cfg.oswald_efficiency)
            CD = cfg.cd0 + CDi
            D = q * cfg.wing_area * CD

            lines.append("  CRUISE CONDITION DRAG BREAKDOWN:")
            lines.append("  ─────────────────────────────────")
            lines.append(f"    Airspeed (V)         = {V:.2f} m/s ({V*2.237:.1f} mph)")
            lines.append(f"    Air Density (ρ)      = {rho:.3f} kg/m³ [ISA sea level]")
            lines.append(f"    Dynamic Pressure (q) = 0.5 × ρ × V² = 0.5 × {rho:.3f} × {V:.2f}² = {q:.2f} Pa")
            lines.append("")
            lines.append(f"    Weight (W)           = {cfg.weight:.3f} kg × 9.81 = {W:.2f} N")
            lines.append(f"    Required Lift (L=W)  = {W:.2f} N")
            lines.append("")
            lines.append(f"    LIFT COEFFICIENT:")
            lines.append(f"      CL = W / (q × S) = {W:.2f} / ({q:.2f} × {cfg.wing_area:.4f})")
            lines.append(f"      CL = {CL:.4f}")
            lines.append("")
            lines.append(f"    INDUCED DRAG:")
            lines.append(f"      CDi = CL² / (π × AR × e)")
            lines.append(f"      CDi = {CL:.4f}² / (π × {AR:.2f} × {cfg.oswald_efficiency:.2f})")
            lines.append(f"      CDi = {CDi:.5f}")
            lines.append("")
            lines.append(f"    TOTAL DRAG:")
            lines.append(f"      CD = CD0 + CDi = {cfg.cd0:.4f} + {CDi:.5f} = {CD:.5f}")
            lines.append(f"      D = q × S × CD = {q:.2f} × {cfg.wing_area:.4f} × {CD:.5f}")
            lines.append(f"      D = {D:.3f} N")
            lines.append("")
            lines.append(f"    THRUST REQUIRED:")
            lines.append(f"      T_required = D = {D:.3f} N [In level flight, T = D]")
        lines.append("")

        # =====================================================================
        # SECTION 3: PROPULSION SYSTEM CALCULATIONS
        # =====================================================================
        lines.append("┌" + "─" * 78 + "┐")
        lines.append("│ SECTION 3: PROPULSION SYSTEM CALCULATIONS" + " " * 35 + "│")
        lines.append("└" + "─" * 78 + "┘")
        lines.append("")

        # Calculate derived values (thrust = drag in level flight)
        thrust_n = cr.drag  # In level flight, thrust equals drag
        motor_voltage = cr.loaded_voltage
        # Prop power: P_prop = P_battery * η_motor (mechanical power delivered to prop)
        prop_power = cr.battery_power * cr.motor_efficiency if cr.motor_efficiency > 0 else 0

        lines.append("  PROPELLER OPERATING POINT:")
        lines.append("  ───────────────────────────")
        lines.append(f"    RPM                  = {cr.prop_rpm:.0f}")
        lines.append(f"    Thrust (T)           = {thrust_n:.3f} N [T = D in level flight]")
        lines.append(f"    Prop Mech Power (Pp) = {prop_power:.1f} W [P_motor_out]")
        lines.append(f"    Prop Efficiency (ηp) = {cr.prop_efficiency*100:.1f}%")
        useful_power = thrust_n * cr.airspeed
        lines.append(f"      [ηp = T × V / P_prop = {thrust_n:.3f} × {cr.airspeed:.2f} / {prop_power:.1f} = {useful_power/prop_power*100:.1f}%]" if prop_power > 0 else "      [ηp from APC data]")
        lines.append("")

        lines.append("  MOTOR OPERATING POINT:")
        lines.append("  ───────────────────────")
        lines.append(f"    Motor Current (Im)   = {cr.motor_current:.2f} A")
        lines.append(f"    Motor Voltage (Vm)   = {motor_voltage:.2f} V")
        lines.append(f"    Motor Elec Power     = {cr.motor_current * motor_voltage:.1f} W")
        lines.append(f"    Motor Efficiency (ηm)= {cr.motor_efficiency*100:.1f}%")
        lines.append("")
        lines.append(f"    MOTOR EFFICIENCY CALCULATION:")
        lines.append(f"      Back-EMF: V_bemf = RPM / Kv = {cr.prop_rpm:.0f} / {kv:.0f} = {cr.prop_rpm/kv:.2f} V")
        i_torque = max(0, cr.motor_current - i0)
        lines.append(f"      Torque Current: I_torque = I_motor - I0 = {cr.motor_current:.2f} - {i0:.2f} = {i_torque:.2f} A")
        lines.append(f"      Torque: τ = Kt × I_torque = {kt:.5f} × {i_torque:.2f} = {kt*i_torque:.4f} Nm")
        lines.append(f"      Mech Power: P_mech = τ × ω = τ × (RPM × 2π/60)")
        omega = cr.prop_rpm * 2 * np.pi / 60
        p_mech = kt * i_torque * omega
        lines.append(f"      P_mech = {kt*i_torque:.4f} × {omega:.1f} = {p_mech:.1f} W")
        p_elec = cr.motor_current * motor_voltage
        lines.append(f"      Elec Power: P_elec = V × I = {motor_voltage:.2f} × {cr.motor_current:.2f} = {p_elec:.1f} W")
        eta_calc = p_mech / p_elec * 100 if p_elec > 0 else 0
        lines.append(f"      Efficiency: ηm = P_mech / P_elec = {p_mech:.1f} / {p_elec:.1f} = {eta_calc:.1f}%")
        lines.append("")

        # =====================================================================
        # SECTION 4: BATTERY & THERMAL CALCULATIONS
        # =====================================================================
        lines.append("┌" + "─" * 78 + "┐")
        lines.append("│ SECTION 4: BATTERY & THERMAL CALCULATIONS" + " " * 35 + "│")
        lines.append("└" + "─" * 78 + "┘")
        lines.append("")

        lines.append("  BATTERY OPERATING POINT:")
        lines.append("  ─────────────────────────")
        lines.append(f"    Battery Current (Ib) = {cr.battery_current:.2f} A")
        lines.append(f"    Battery Voltage (Vb) = {cr.loaded_voltage:.2f} V (under load)")
        lines.append(f"    Battery Power (Pb)   = {cr.battery_power:.1f} W")
        lines.append(f"    Throttle Setting     = {cr.throttle:.1f}%")
        lines.append("")

        if cr.thermal_eval:
            te = cr.thermal_eval
            lines.append("  THERMAL CALCULATIONS:")
            lines.append("  ──────────────────────")
            lines.append(f"    Current (I)          = {te.current_a:.2f} A")
            lines.append(f"    Heat Generation      = {te.heat_generation_w:.1f} W")
            lines.append(f"      [Q = I² × R_internal, where R accounts for all cells in series/parallel]")
            lines.append(f"    Steady-State Temp    = {te.steady_state_temp_c:.1f}°C")
            lines.append(f"      [T_ss = T_ambient + Q × R_thermal]")
            lines.append(f"    Max Allowed Temp     = {te.steady_state_temp_c + te.thermal_margin_c:.0f}°C")
            lines.append(f"    Thermal Margin       = {te.thermal_margin_c:.1f}°C")
            lines.append(f"    Within Limits        = {'YES' if te.within_limits else 'NO - EXCEEDS LIMIT!'}")
            lines.append(f"    Limiting Factor      = {te.limiting_factor}")
            lines.append(f"    Max Continuous I     = {te.max_continuous_current_a:.1f} A")
        lines.append("")

        # =====================================================================
        # SECTION 5: SYSTEM EFFICIENCY & PERFORMANCE
        # =====================================================================
        lines.append("┌" + "─" * 78 + "┐")
        lines.append("│ SECTION 5: SYSTEM EFFICIENCY & PERFORMANCE" + " " * 34 + "│")
        lines.append("└" + "─" * 78 + "┘")
        lines.append("")

        lines.append("  EFFICIENCY CHAIN:")
        lines.append("  ──────────────────")
        lines.append(f"    Battery → Motor:    ηm = {cr.motor_efficiency*100:.1f}%")
        lines.append(f"    Motor → Prop:       ηp = {cr.prop_efficiency*100:.1f}%")
        lines.append(f"    System Efficiency:  ηsys = ηm × ηp = {cr.motor_efficiency*100:.1f}% × {cr.prop_efficiency*100:.1f}%")
        lines.append(f"                        ηsys = {cr.system_efficiency*100:.1f}%")
        lines.append("")
        lines.append(f"    Power Flow:")
        lines.append(f"      P_battery   = {cr.battery_power:.1f} W (electrical input)")
        lines.append(f"      P_motor_out = {cr.battery_power * cr.motor_efficiency:.1f} W (mechanical to prop)")
        lines.append(f"      P_thrust    = {cr.drag * cr.airspeed:.1f} W (useful propulsive power, T=D)")
        lines.append("")

        lines.append("  RUNTIME & ENDURANCE:")
        lines.append("  ─────────────────────")
        lines.append(f"    Pack Capacity        = {r.pack_capacity_mah:.0f} mAh = {r.pack_capacity_mah/1000:.2f} Ah")
        lines.append(f"    Cruise Current       = {cr.battery_current:.2f} A")
        lines.append(f"    Cruise Runtime       = Capacity / Current = {r.pack_capacity_mah/1000:.2f} / {cr.battery_current:.2f}")
        lines.append(f"                         = {r.cruise_runtime_minutes:.1f} minutes")
        lines.append(f"    Cruise Range         = Runtime × Speed = {r.cruise_runtime_minutes:.1f} × {cr.airspeed*60/1000:.2f}")
        lines.append(f"                         = {r.cruise_runtime_minutes * cr.airspeed * 60 / 1000:.1f} km")
        lines.append("")

        # =====================================================================
        # SECTION 6: MAX SPEED ANALYSIS
        # =====================================================================
        if r.max_speed_result and r.max_speed_result.valid:
            mr = r.max_speed_result
            lines.append("┌" + "─" * 78 + "┐")
            lines.append("│ SECTION 6: MAX SPEED ANALYSIS" + " " * 47 + "│")
            lines.append("└" + "─" * 78 + "┘")
            lines.append("")

            lines.append(f"  MAX ACHIEVABLE SPEED:")
            lines.append(f"  ──────────────────────")
            lines.append(f"    V_max                = {r.max_achievable_speed:.1f} m/s ({r.max_achievable_speed*2.237:.1f} mph)")
            lines.append(f"    Throttle at V_max    = {mr.throttle:.1f}%")
            lines.append(f"    Current at V_max     = {mr.battery_current:.1f} A")
            lines.append(f"    Power at V_max       = {mr.battery_power:.1f} W")
            lines.append(f"    RPM at V_max         = {mr.prop_rpm:.0f}")
            lines.append("")

            if mr.thermal_eval:
                lines.append(f"  THERMAL AT MAX SPEED:")
                lines.append(f"    Steady-State Temp    = {mr.thermal_eval.steady_state_temp_c:.1f}°C")
                lines.append(f"    Thermal Margin       = {mr.thermal_eval.thermal_margin_c:.1f}°C")
                lines.append(f"    Within Limits        = {'YES' if mr.thermal_eval.within_limits else 'NO - EXCEEDS LIMIT!'}")

            if r.thermal_throttle_limit:
                lines.append("")
                lines.append(f"  THERMAL THROTTLE LIMIT:")
                lines.append(f"    Max Safe Throttle    = {r.thermal_throttle_limit:.1f}%")
                lines.append(f"    [Throttle limited by thermal constraints]")
            lines.append("")

        # =====================================================================
        # SECTION 7: VALIDITY & SUMMARY
        # =====================================================================
        lines.append("┌" + "─" * 78 + "┐")
        lines.append("│ SECTION 7: VALIDITY & SUMMARY" + " " * 47 + "│")
        lines.append("└" + "─" * 78 + "┘")
        lines.append("")

        lines.append(f"  CONFIGURATION VALID:   {'YES' if r.valid else 'NO'}")
        if not r.valid:
            lines.append(f"  INVALIDITY REASON:     {r.invalidity_reason}")
        lines.append("")
        lines.append(f"  KEY METRICS:")
        lines.append(f"    System Efficiency    = {cr.system_efficiency*100:.1f}%")
        lines.append(f"    Cruise Runtime       = {r.cruise_runtime_minutes:.1f} min")
        lines.append(f"    Max Speed            = {r.max_achievable_speed:.1f} m/s")
        lines.append(f"    Energy Density       = {r.energy_density_wh_kg:.1f} Wh/kg")
        lines.append(f"    Power Density        = {r.power_density_w_kg:.1f} W/kg")
        lines.append("")
        lines.append("=" * 80)
        lines.append("END OF VERBOSE CALCULATION OUTPUT")
        lines.append("=" * 80)

        # Insert all text
        self.verbose_text.insert(tk.END, "\n".join(lines))
        self.verbose_text.config(state="disabled")

    def generate_verbose_result_string(self, r: IntegratedResult) -> str:
        """Generate verbose output string for a single result (for export)."""
        # Simplified version for batch export
        lines = [
            f"{'='*60}",
            f"RESULT: {r.motor_id} + {r.prop_id} + {r.cell_type} {r.pack_config}",
            f"{'='*60}",
            f"Valid: {r.valid}",
            f"Cruise Speed: {r.cruise_result.airspeed:.1f} m/s",
            f"Cruise Throttle: {r.cruise_result.throttle:.1f}%",
            f"Cruise Current: {r.cruise_result.battery_current:.2f} A",
            f"Cruise Power: {r.cruise_result.battery_power:.1f} W",
            f"System Efficiency: {r.cruise_result.system_efficiency*100:.1f}%",
            f"Motor Efficiency: {r.cruise_result.motor_efficiency*100:.1f}%",
            f"Prop Efficiency: {r.cruise_result.prop_efficiency*100:.1f}%",
            f"Cruise Temp: {r.cruise_result.thermal_eval.steady_state_temp_c:.1f}°C" if r.cruise_result.thermal_eval else "",
            f"Thermal Margin: {r.cruise_result.thermal_eval.thermal_margin_c:.1f}°C" if r.cruise_result.thermal_eval else "",
            f"Runtime: {r.cruise_runtime_minutes:.1f} min",
            f"Max Speed: {r.max_achievable_speed:.1f} m/s",
        ]
        if r.max_speed_result and r.max_speed_result.valid:
            lines.extend([
                f"Max Speed Throttle: {r.max_speed_result.throttle:.1f}%",
                f"Max Speed Current: {r.max_speed_result.battery_current:.1f} A",
                f"Max Speed Temp: {r.max_speed_result.thermal_eval.steady_state_temp_c:.1f}°C" if r.max_speed_result.thermal_eval else "",
            ])
        if r.thermal_throttle_limit:
            lines.append(f"Thermal Throttle Limit: {r.thermal_throttle_limit:.1f}%")
        if not r.valid:
            lines.append(f"Invalidity Reason: {r.invalidity_reason}")
        return "\n".join(lines)

    # =========================================================================
    # Temp File Management
    # =========================================================================

    def _init_temp_file(self):
        """Initialize temp file for storing batch results."""
        try:
            # Create temp file that will be deleted on exit
            fd, self._temp_results_file = tempfile.mkstemp(
                prefix="integrated_analysis_",
                suffix=".txt"
            )
            os.close(fd)  # Close the file descriptor
            # Register cleanup on exit
            atexit.register(self._cleanup_temp_file)
        except Exception as e:
            print(f"Could not create temp file: {e}")
            self._temp_results_file = None

    def _cleanup_temp_file(self):
        """Clean up temp file on exit."""
        if self._temp_results_file and os.path.exists(self._temp_results_file):
            try:
                os.remove(self._temp_results_file)
            except:
                pass

    def _write_results_to_temp(self):
        """Write current batch results to temp file."""
        if not self._temp_results_file or not self._batch_result:
            return

        try:
            with open(self._temp_results_file, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write("INTEGRATED ANALYSIS BATCH RESULTS\n")
                f.write(f"Generated: {__import__('datetime').datetime.now()}\n")
                f.write("=" * 80 + "\n\n")

                # Write config summary
                cfg = self._batch_result.config
                f.write("CONFIGURATION:\n")
                f.write(f"  Wing Area: {cfg.wing_area:.4f} m²\n")
                f.write(f"  Wingspan: {cfg.wingspan:.3f} m\n")
                f.write(f"  Weight: {cfg.weight:.3f} kg\n")
                f.write("\n")

                # Write each result
                for i, r in enumerate(self._batch_result.results):
                    f.write(self.generate_verbose_result_string(r))
                    f.write("\n\n")

                f.write(f"\nTotal Results: {len(self._batch_result.results)}\n")
                f.write(f"Valid: {sum(1 for r in self._batch_result.results if r.valid)}\n")
                f.write(f"Invalid: {sum(1 for r in self._batch_result.results if not r.valid)}\n")

        except Exception as e:
            print(f"Could not write to temp file: {e}")

    # =========================================================================
    # Export
    # =========================================================================

    def _export_csv(self):
        """Export results to CSV."""
        if not self._batch_result:
            messagebox.showwarning("No Results", "No results to export")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Export Results to CSV"
        )

        if filepath:
            try:
                analyzer = ResultAnalyzer(self._batch_result)
                analyzer.export_csv(filepath)
                messagebox.showinfo(
                    "Export Complete",
                    f"Results exported to:\n{filepath}"
                )
            except Exception as e:
                messagebox.showerror("Export Error", str(e))

    def _export_json(self):
        """Export results to JSON."""
        if not self._batch_result:
            messagebox.showwarning("No Results", "No results to export")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Export Results to JSON"
        )

        if filepath:
            try:
                analyzer = ResultAnalyzer(self._batch_result)
                analyzer.export_json(filepath)
                messagebox.showinfo(
                    "Export Complete",
                    f"Results exported to:\n{filepath}"
                )
            except Exception as e:
                messagebox.showerror("Export Error", str(e))

    def _export_verbose_csv(self):
        """Export verbose CSV with all intermediate calculations."""
        if not self._batch_result:
            messagebox.showwarning("No Results", "No results to export")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Export Verbose Results to CSV"
        )

        if not filepath:
            return

        try:
            # Define comprehensive columns
            columns = [
                # Identification
                "result_num", "motor_id", "prop_id", "cell_type", "series", "parallel",
                "pack_config", "thermal_environment", "valid", "invalidity_reason",

                # Battery Pack Properties
                "pack_voltage_nominal_v", "pack_voltage_loaded_v", "pack_capacity_mah",
                "pack_energy_wh", "pack_mass_kg", "cell_ir_mohm", "pack_ir_mohm",

                # Aerodynamic Inputs
                "wing_area_m2", "wingspan_m", "aspect_ratio", "weight_kg", "weight_n",
                "cruise_speed_ms", "cruise_speed_mph",

                # Aerodynamic Calculations
                "air_density_kgm3", "dynamic_pressure_pa", "reynolds_number",
                "cl_required", "cd_induced", "cd_parasitic", "cd_total",
                "drag_force_n", "thrust_required_n", "power_required_w",

                # Motor Inputs
                "motor_kv", "motor_i0_a", "motor_rm_ohm", "motor_max_current_a",

                # Motor Calculations
                "motor_voltage_v", "motor_current_a", "motor_power_in_w",
                "motor_power_out_w", "motor_torque_nm", "motor_rpm",
                "motor_efficiency_pct", "motor_kt_nm_a", "motor_losses_w",

                # Prop Inputs
                "prop_diameter_in", "prop_pitch_in",

                # Prop Calculations
                "prop_rpm", "prop_tip_speed_ms", "prop_advance_ratio",
                "prop_ct", "prop_cp", "prop_thrust_n", "prop_power_w",
                "prop_efficiency_pct",

                # System Totals
                "battery_current_a", "battery_power_w", "system_efficiency_pct",
                "throttle_pct",

                # Thermal Calculations
                "ambient_temp_c", "cell_heat_w", "pack_heat_w",
                "thermal_resistance_cw", "steady_state_temp_c",
                "max_temp_limit_c", "thermal_margin_c", "within_thermal_limits",
                "max_continuous_current_a", "limiting_factor",

                # Performance Summary
                "cruise_runtime_min", "max_speed_ms", "max_speed_mph",
                "max_speed_throttle_pct", "thermal_throttle_limit_pct",
                "energy_density_wh_kg", "power_density_w_kg",
            ]

            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=columns)
                writer.writeheader()

                for i, r in enumerate(self._batch_result.results):
                    row = self._build_verbose_row(i + 1, r)
                    writer.writerow(row)

            messagebox.showinfo(
                "Export Complete",
                f"Verbose results exported to:\n{filepath}\n\n"
                f"Columns: {len(columns)}\n"
                f"Rows: {len(self._batch_result.results)}"
            )

        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    def _build_verbose_row(self, result_num: int, r) -> dict:
        """Build verbose row dict for CSV export."""
        cfg = self._batch_result.config

        # Get cruise result
        cr = r.cruise_result
        te = cr.thermal_eval if cr.thermal_eval else None

        # Calculate derived values
        aspect_ratio = cfg.wingspan ** 2 / cfg.wing_area if cfg.wing_area > 0 else 0
        weight_n = cfg.weight * 9.81
        rho = 1.225  # air density at sea level

        # Dynamic pressure
        q = 0.5 * rho * cr.airspeed ** 2 if cr.airspeed > 0 else 0

        # Lift coefficient (from level flight: L = W)
        cl = weight_n / (q * cfg.wing_area) if q > 0 else 0

        # Induced drag coefficient
        e = 0.85  # Oswald efficiency
        cd_i = cl ** 2 / (3.14159 * aspect_ratio * e) if aspect_ratio > 0 else 0

        # Parasitic drag (estimate from Cd0 typical value)
        cd_0 = 0.025
        cd_total = cd_0 + cd_i

        # Forces
        drag = q * cfg.wing_area * cd_total
        thrust_req = drag  # Level flight

        # Motor calculations
        motor_kv = 0
        motor_i0 = 0
        motor_rm = 0
        motor_max_i = 0
        motor_kt = 0
        motor_losses = 0
        motor_torque = 0
        motor_power_out = 0

        try:
            # Try to get motor data from the database
            from src.motor_prop_analyzer.motor_database import MotorDatabase
            motor_db = MotorDatabase()
            motor_data = motor_db.get_motor(r.motor_id)
            if motor_data:
                motor_kv = motor_data.get('kv', 0)
                motor_i0 = motor_data.get('i0', 0)
                motor_rm = motor_data.get('rm', 0)
                motor_max_i = motor_data.get('max_current', 0)

                # Calculate Kt from Kv: Kt = 9.5493 / Kv
                if motor_kv > 0:
                    motor_kt = 9.5493 / motor_kv

                # Calculate torque: τ = Kt * (I - I0)
                motor_torque = motor_kt * (cr.motor_current - motor_i0) if cr.motor_current > motor_i0 else 0

                # Motor losses: I²R + mechanical (I0 losses)
                motor_losses = cr.motor_current ** 2 * motor_rm + cr.loaded_voltage * motor_i0

                # Motor power out
                motor_power_in = cr.loaded_voltage * cr.motor_current
                motor_power_out = motor_power_in * cr.motor_efficiency if cr.motor_efficiency else 0
        except:
            pass

        # Prop calculations
        prop_dia_in = 0
        prop_pitch_in = 0
        tip_speed = 0
        advance_ratio = 0

        try:
            # Parse prop ID for diameter and pitch
            parts = r.prop_id.replace('x', ' ').replace('X', ' ').split()
            if len(parts) >= 2:
                prop_dia_in = float(parts[0])
                prop_pitch_in = float(parts[1])
                prop_dia_m = prop_dia_in * 0.0254
                tip_speed = 3.14159 * prop_dia_m * cr.prop_rpm / 60 if cr.prop_rpm > 0 else 0
                # J = V / (n * D)
                n_rps = cr.prop_rpm / 60 if cr.prop_rpm > 0 else 1
                advance_ratio = cr.airspeed / (n_rps * prop_dia_m) if n_rps > 0 and prop_dia_m > 0 else 0
        except:
            pass

        # Thermal calculations
        cell_ir_mohm = 0
        pack_ir_mohm = 0
        cell_heat = 0
        pack_heat = 0
        thermal_r = 0

        try:
            # Get battery pack info
            if hasattr(r, '_battery_pack'):
                bp = r._battery_pack
                cell_ir_mohm = bp.cell.internal_resistance * 1000 if hasattr(bp.cell, 'internal_resistance') else 0
            else:
                # Estimate from typical values
                cell_ir_mohm = 15  # Typical for high-discharge cells
            pack_ir_mohm = cell_ir_mohm * r.series / r.parallel if r.parallel > 0 else 0

            # Heat generation: I²R
            pack_ir_ohm = pack_ir_mohm / 1000
            pack_heat = cr.battery_current ** 2 * pack_ir_ohm if cr.battery_current else 0
            cell_heat = pack_heat / (r.series * r.parallel) if r.series and r.parallel else 0

            # Estimate thermal resistance
            if te and te.heat_generation_w > 0 and te.steady_state_temp_c:
                delta_t = te.steady_state_temp_c - 25  # Assuming 25C ambient
                thermal_r = delta_t / te.heat_generation_w if te.heat_generation_w > 0 else 0
        except:
            pass

        row = {
            # Identification
            "result_num": result_num,
            "motor_id": r.motor_id,
            "prop_id": r.prop_id,
            "cell_type": r.cell_type,
            "series": r.series,
            "parallel": r.parallel,
            "pack_config": r.pack_config,
            "thermal_environment": r.thermal_environment,
            "valid": r.valid,
            "invalidity_reason": r.invalidity_reason or "",

            # Battery Pack Properties
            "pack_voltage_nominal_v": f"{r.pack_voltage_nominal:.2f}",
            "pack_voltage_loaded_v": f"{cr.loaded_voltage:.2f}" if cr.loaded_voltage else "",
            "pack_capacity_mah": f"{r.pack_capacity_mah:.0f}",
            "pack_energy_wh": f"{r.pack_energy_wh:.1f}",
            "pack_mass_kg": f"{r.pack_mass_kg:.3f}",
            "cell_ir_mohm": f"{cell_ir_mohm:.1f}",
            "pack_ir_mohm": f"{pack_ir_mohm:.1f}",

            # Aerodynamic Inputs
            "wing_area_m2": f"{cfg.wing_area:.4f}",
            "wingspan_m": f"{cfg.wingspan:.3f}",
            "aspect_ratio": f"{aspect_ratio:.2f}",
            "weight_kg": f"{cfg.weight:.3f}",
            "weight_n": f"{weight_n:.2f}",
            "cruise_speed_ms": f"{cr.airspeed:.1f}",
            "cruise_speed_mph": f"{cr.airspeed * 2.237:.1f}",

            # Aerodynamic Calculations
            "air_density_kgm3": f"{rho:.4f}",
            "dynamic_pressure_pa": f"{q:.2f}",
            "reynolds_number": "",  # Would need chord
            "cl_required": f"{cl:.4f}",
            "cd_induced": f"{cd_i:.5f}",
            "cd_parasitic": f"{cd_0:.4f}",
            "cd_total": f"{cd_total:.5f}",
            "drag_force_n": f"{drag:.3f}",
            "thrust_required_n": f"{thrust_req:.3f}",
            "power_required_w": f"{thrust_req * cr.airspeed:.1f}" if cr.airspeed else "",

            # Motor Inputs
            "motor_kv": f"{motor_kv:.0f}" if motor_kv else "",
            "motor_i0_a": f"{motor_i0:.2f}" if motor_i0 else "",
            "motor_rm_ohm": f"{motor_rm:.4f}" if motor_rm else "",
            "motor_max_current_a": f"{motor_max_i:.0f}" if motor_max_i else "",

            # Motor Calculations
            "motor_voltage_v": f"{cr.loaded_voltage:.2f}" if cr.loaded_voltage else "",
            "motor_current_a": f"{cr.motor_current:.2f}" if cr.motor_current else "",
            "motor_power_in_w": f"{cr.loaded_voltage * cr.motor_current:.1f}" if cr.loaded_voltage and cr.motor_current else "",
            "motor_power_out_w": f"{motor_power_out:.1f}" if motor_power_out else "",
            "motor_torque_nm": f"{motor_torque:.4f}" if motor_torque else "",
            "motor_rpm": f"{cr.prop_rpm:.0f}" if cr.prop_rpm else "",
            "motor_efficiency_pct": f"{cr.motor_efficiency * 100:.1f}" if cr.motor_efficiency else "",
            "motor_kt_nm_a": f"{motor_kt:.5f}" if motor_kt else "",
            "motor_losses_w": f"{motor_losses:.2f}" if motor_losses else "",

            # Prop Inputs
            "prop_diameter_in": f"{prop_dia_in:.1f}" if prop_dia_in else "",
            "prop_pitch_in": f"{prop_pitch_in:.1f}" if prop_pitch_in else "",

            # Prop Calculations
            "prop_rpm": f"{cr.prop_rpm:.0f}" if cr.prop_rpm else "",
            "prop_tip_speed_ms": f"{tip_speed:.1f}" if tip_speed else "",
            "prop_advance_ratio": f"{advance_ratio:.3f}" if advance_ratio else "",
            "prop_ct": "",  # Would need from APC data
            "prop_cp": "",  # Would need from APC data
            "prop_thrust_n": f"{cr.drag:.3f}" if cr.drag else "",  # T = D in level flight
            "prop_power_w": f"{cr.battery_power * cr.motor_efficiency:.1f}" if cr.battery_power and cr.motor_efficiency else "",
            "prop_efficiency_pct": f"{cr.prop_efficiency * 100:.1f}" if cr.prop_efficiency else "",

            # System Totals
            "battery_current_a": f"{cr.battery_current:.2f}" if cr.battery_current else "",
            "battery_power_w": f"{cr.battery_power:.1f}" if cr.battery_power else "",
            "system_efficiency_pct": f"{cr.system_efficiency * 100:.1f}" if cr.system_efficiency else "",
            "throttle_pct": f"{cr.throttle:.1f}" if cr.throttle else "",

            # Thermal Calculations
            "ambient_temp_c": "25",  # Default ambient
            "cell_heat_w": f"{cell_heat:.3f}" if cell_heat else "",
            "pack_heat_w": f"{pack_heat:.2f}" if pack_heat else "",
            "thermal_resistance_cw": f"{thermal_r:.3f}" if thermal_r else "",
            "steady_state_temp_c": f"{te.steady_state_temp_c:.1f}" if te and te.steady_state_temp_c else "",
            "max_temp_limit_c": "60",  # Typical limit
            "thermal_margin_c": f"{te.thermal_margin_c:.1f}" if te and te.thermal_margin_c else "",
            "within_thermal_limits": te.within_limits if te else "",
            "max_continuous_current_a": f"{te.max_continuous_current_a:.1f}" if te and te.max_continuous_current_a else "",
            "limiting_factor": te.limiting_factor if te else "",

            # Performance Summary
            "cruise_runtime_min": f"{r.cruise_runtime_minutes:.1f}",
            "max_speed_ms": f"{r.max_achievable_speed:.1f}" if r.max_achievable_speed > 0 else "",
            "max_speed_mph": f"{r.max_achievable_speed * 2.237:.1f}" if r.max_achievable_speed > 0 else "",
            "max_speed_throttle_pct": f"{r.max_speed_result.throttle:.1f}" if r.max_speed_result else "",
            "thermal_throttle_limit_pct": f"{r.thermal_throttle_limit:.1f}" if r.thermal_throttle_limit else "",
            "energy_density_wh_kg": f"{r.energy_density_wh_kg:.1f}",
            "power_density_w_kg": f"{r.power_density_w_kg:.1f}",
        }

        return row

    # =========================================================================
    # Defaults and Run
    # =========================================================================

    def _set_defaults(self):
        """Set default values."""
        self._update_speed_display()

    def run(self):
        """Start the UI main loop."""
        self.root.mainloop()


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    """Launch the Integrated Analyzer UI."""
    app = IntegratedAnalyzerUI()
    app.run()


if __name__ == "__main__":
    main()
