"""
Batch Analyzer User Interface
==============================

This module provides a comprehensive GUI for batch analysis of motor and
propeller combinations for fixed-wing FPV aircraft.

Features:
---------
- Airframe configuration (drag, weight, wing geometry)
- Motor selection by category and size range
- Propeller filtering by diameter and pitch
- Speed range with configurable step
- Live permutation counter
- Threaded batch execution with progress
- Sortable results table
- Export to CSV

Usage:
------
    from src.ui.batch_analyzer_ui import BatchAnalyzerUI

    app = BatchAnalyzerUI()
    app.run()
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import json
from typing import Optional, Dict, Any, List
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.batch_analyzer import BatchSolver, BatchConfig, BatchResult, DEFAULT_LIMITS
from src.batch_analyzer.batch_solver import parse_prop_dimensions
from src.motor_analyzer.config import MotorAnalyzerConfig
from src.prop_analyzer.core import PropAnalyzer
from src.prop_analyzer.config import PropAnalyzerConfig


class BatchAnalyzerUI:
    """
    Batch analyzer GUI for motor/prop optimization.

    This interface allows users to:
    1. Configure airframe parameters
    2. Set motor and prop filter ranges
    3. Define speed sweep parameters
    4. Run batch analysis with live progress
    5. View and export results
    """

    # =========================================================================
    # UI Constants
    # =========================================================================

    WINDOW_TITLE = "Batch Motor/Prop Optimizer - Fixed-Wing FPV"
    WINDOW_MIN_WIDTH = 1400
    WINDOW_MIN_HEIGHT = 900

    FRAME_PADDING = 10
    WIDGET_PADDING = 3
    SECTION_PADDING = 5

    # Battery options
    BATTERY_OPTIONS = {
        "3S (11.1V)": 11.1,
        "4S (14.8V)": 14.8,
        "5S (18.5V)": 18.5,
        "6S (22.2V)": 22.2,
    }

    # Warning thresholds
    WARNING_PERMUTATIONS = 50_000
    MAX_PERMUTATIONS = 500_000

    def __init__(self):
        """Initialize the Batch Analyzer UI."""
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

        # Batch solver instance (created on run)
        self._solver: Optional[BatchSolver] = None
        self._results: List[BatchResult] = []
        self._batch_thread: Optional[threading.Thread] = None

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
            text="Batch Motor/Prop Optimizer",
            font=("Helvetica", 18, "bold")
        ).pack(anchor="w")

        ttk.Label(
            header_frame,
            text="Find optimal motor and propeller combinations for your fixed-wing FPV aircraft",
            font=("Helvetica", 10)
        ).pack(anchor="w")

    def _create_left_panel(self):
        """Create left panel with all input sections."""
        # Scrollable left panel
        left_canvas = tk.Canvas(self.main_frame, width=480)
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

        # Build sections
        self._create_airframe_section(left_frame)
        self._create_battery_section(left_frame)
        self._create_motor_section(left_frame)
        self._create_prop_section(left_frame)
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
        ttk.Label(row, text="Wing Area:", width=20).pack(side="left")
        self.wing_area_var = tk.StringVar(value="0.15")
        ttk.Entry(row, textvariable=self.wing_area_var, width=10).pack(side="left")
        ttk.Label(row, text="m²").pack(side="left", padx=5)

        # Wingspan
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Wingspan:", width=20).pack(side="left")
        self.wingspan_var = tk.StringVar(value="1.0")
        ttk.Entry(row, textvariable=self.wingspan_var, width=10).pack(side="left")
        ttk.Label(row, text="m").pack(side="left", padx=5)

        # Weight
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Aircraft Weight:", width=20).pack(side="left")
        self.weight_var = tk.StringVar(value="1.0")
        ttk.Entry(row, textvariable=self.weight_var, width=10).pack(side="left")
        ttk.Label(row, text="kg").pack(side="left", padx=5)

        # Cd0
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Cd0 (parasitic drag):", width=20).pack(side="left")
        self.cd0_var = tk.StringVar(value="0.025")
        ttk.Entry(row, textvariable=self.cd0_var, width=10).pack(side="left")
        ttk.Label(row, text="(0.02-0.04)").pack(side="left", padx=5)

        # Oswald efficiency
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Oswald Efficiency:", width=20).pack(side="left")
        self.oswald_var = tk.StringVar(value="0.8")
        ttk.Entry(row, textvariable=self.oswald_var, width=10).pack(side="left")
        ttk.Label(row, text="(0.7-0.85)").pack(side="left", padx=5)

    def _create_battery_section(self, parent):
        """Create battery configuration section."""
        frame = ttk.LabelFrame(
            parent, text="Battery Configuration", padding=self.SECTION_PADDING
        )
        frame.pack(fill="x", pady=self.WIDGET_PADDING, padx=self.WIDGET_PADDING)

        row = ttk.Frame(frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Battery:", width=20).pack(side="left")
        self.battery_var = tk.StringVar()
        battery_combo = ttk.Combobox(
            row,
            textvariable=self.battery_var,
            values=list(self.BATTERY_OPTIONS.keys()),
            state="readonly",
            width=15
        )
        battery_combo.pack(side="left", padx=5)
        battery_combo.bind("<<ComboboxSelected>>", self._on_battery_change)

        row = ttk.Frame(frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Voltage:", width=20).pack(side="left")
        self.voltage_var = tk.StringVar(value="14.8")
        ttk.Entry(row, textvariable=self.voltage_var, width=10).pack(side="left")
        ttk.Label(row, text="V").pack(side="left", padx=5)

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
        self.prop_dia_min_var = tk.StringVar(value="6")
        self.prop_dia_max_var = tk.StringVar(value="12")
        ttk.Entry(row, textvariable=self.prop_dia_min_var, width=6).pack(side="left")
        ttk.Label(row, text=" to ").pack(side="left")
        ttk.Entry(row, textvariable=self.prop_dia_max_var, width=6).pack(side="left")
        ttk.Label(row, text=" inches").pack(side="left", padx=5)

        # Pitch range
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Pitch Range:", width=20).pack(side="left")
        self.prop_pitch_min_var = tk.StringVar(value="3")
        self.prop_pitch_max_var = tk.StringVar(value="8")
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

    def _create_speed_section(self, parent):
        """Create speed range section."""
        frame = ttk.LabelFrame(
            parent, text="Speed Range", padding=self.SECTION_PADDING
        )
        frame.pack(fill="x", pady=self.WIDGET_PADDING, padx=self.WIDGET_PADDING)

        # Min speed
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Minimum Speed:", width=20).pack(side="left")
        self.speed_min_var = tk.StringVar(value="10")
        ttk.Entry(row, textvariable=self.speed_min_var, width=8).pack(side="left")
        ttk.Label(row, text="m/s").pack(side="left", padx=5)
        self.speed_min_mph = ttk.Label(row, text="(22.4 mph)")
        self.speed_min_mph.pack(side="left")

        # Max speed
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Maximum Speed:", width=20).pack(side="left")
        self.speed_max_var = tk.StringVar(value="30")
        ttk.Entry(row, textvariable=self.speed_max_var, width=8).pack(side="left")
        ttk.Label(row, text="m/s").pack(side="left", padx=5)
        self.speed_max_mph = ttk.Label(row, text="(67.1 mph)")
        self.speed_max_mph.pack(side="left")

        # Step
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Speed Step:", width=20).pack(side="left")
        self.speed_step_var = tk.StringVar(value="2")
        ttk.Entry(row, textvariable=self.speed_step_var, width=8).pack(side="left")
        ttk.Label(row, text="m/s").pack(side="left", padx=5)

        # Bind updates
        for var in [self.speed_min_var, self.speed_max_var, self.speed_step_var]:
            var.trace_add("write", lambda *a: self._schedule_permutation_update())

        # Speed points display
        self.speed_count_var = tk.StringVar(value="0 speed points")
        ttk.Label(
            frame, textvariable=self.speed_count_var,
            font=("Helvetica", 9, "italic")
        ).pack(anchor="w", pady=(5, 0))

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
        right_frame.rowconfigure(1, weight=1)

        self._create_progress_section(right_frame)
        self._create_results_section(right_frame)

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

        # Best so far
        self.progress_best_var = tk.StringVar(value="")
        ttk.Label(
            frame, textvariable=self.progress_best_var,
            font=("Helvetica", 10), foreground="green"
        ).pack(anchor="w", pady=(5, 0))

    def _create_results_section(self, parent):
        """Create results table section."""
        frame = ttk.LabelFrame(
            parent, text="Results", padding=self.SECTION_PADDING
        )
        frame.grid(row=1, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        # Toolbar
        toolbar = ttk.Frame(frame)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 5))

        ttk.Label(toolbar, text="Sort by:").pack(side="left")
        self.sort_var = tk.StringVar(value="efficiency")
        sort_combo = ttk.Combobox(
            toolbar,
            textvariable=self.sort_var,
            values=["efficiency", "current", "power", "throttle"],
            state="readonly",
            width=12
        )
        sort_combo.pack(side="left", padx=5)
        sort_combo.bind("<<ComboboxSelected>>", self._on_sort_change)

        ttk.Label(toolbar, text="Show top:").pack(side="left", padx=(10, 0))
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
            toolbar, text="Export CSV", width=12,
            command=self._export_results
        ).pack(side="right", padx=5)

        self.result_count_var = tk.StringVar(value="")
        ttk.Label(
            toolbar, textvariable=self.result_count_var,
            font=("Helvetica", 9)
        ).pack(side="right", padx=10)

        # Results treeview
        tree_frame = ttk.Frame(frame)
        tree_frame.grid(row=1, column=0, sticky="nsew")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        columns = (
            "rank", "motor", "prop", "speed", "throttle",
            "current", "power", "sys_eff", "motor_eff", "prop_eff", "rpm"
        )
        self.results_tree = ttk.Treeview(
            tree_frame, columns=columns, show="headings", height=20
        )

        # Configure columns
        col_config = {
            "rank": ("Rank", 50),
            "motor": ("Motor", 180),
            "prop": ("Prop", 80),
            "speed": ("Speed (m/s)", 90),
            "throttle": ("Throttle %", 90),
            "current": ("Current (A)", 90),
            "power": ("Power (W)", 90),
            "sys_eff": ("Sys Eff %", 80),
            "motor_eff": ("Motor Eff %", 90),
            "prop_eff": ("Prop Eff %", 80),
            "rpm": ("RPM", 70),
        }

        for col, (heading, width) in col_config.items():
            self.results_tree.heading(col, text=heading)
            self.results_tree.column(col, width=width, anchor="center")

        # Scrollbars
        y_scroll = ttk.Scrollbar(
            tree_frame, orient="vertical", command=self.results_tree.yview
        )
        x_scroll = ttk.Scrollbar(
            tree_frame, orient="horizontal", command=self.results_tree.xview
        )
        self.results_tree.configure(
            yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set
        )

        self.results_tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")

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

    def _on_battery_change(self, event=None):
        """Handle battery selection."""
        battery = self.battery_var.get()
        voltage = self.BATTERY_OPTIONS.get(battery, 14.8)
        self.voltage_var.set(str(voltage))

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
        self._update_results_display()

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

            # Count speed points
            try:
                speed_min = float(self.speed_min_var.get())
                speed_max = float(self.speed_max_var.get())
                speed_step = float(self.speed_step_var.get())

                if speed_step > 0 and speed_max > speed_min:
                    speed_count = int((speed_max - speed_min) / speed_step) + 1
                else:
                    speed_count = 0

                # Update mph labels
                self.speed_min_mph.config(text=f"({speed_min * 2.237:.1f} mph)")
                self.speed_max_mph.config(text=f"({speed_max * 2.237:.1f} mph)")
            except ValueError:
                speed_count = 0
            self.speed_count_var.set(f"{speed_count} speed points")

            # Total permutations
            total = motor_count * prop_count * speed_count
            self.perm_count_var.set(f"{total:,}")

            # Breakdown
            self.perm_breakdown_var.set(
                f"({motor_count} motors × {prop_count} props × {speed_count} speeds)"
            )

            # Warning/color
            if total > self.MAX_PERMUTATIONS:
                self.perm_count_label.config(foreground="red")
                self.perm_warning_var.set(
                    f"Exceeds maximum ({self.MAX_PERMUTATIONS:,}). Reduce range."
                )
                self.run_btn.config(state="disabled")
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

    def _build_config(self) -> BatchConfig:
        """Build BatchConfig from UI values."""
        # Get selected motor categories
        selected_categories = [
            cat for cat, var in self.motor_category_vars.items()
            if var.get()
        ]

        return BatchConfig(
            wing_area=float(self.wing_area_var.get()),
            wingspan=float(self.wingspan_var.get()),
            weight=float(self.weight_var.get()),
            cd0=float(self.cd0_var.get()),
            oswald_efficiency=float(self.oswald_var.get()),
            voltage=float(self.voltage_var.get()),
            motor_categories=selected_categories,
            prop_diameter_min=float(self.prop_dia_min_var.get()),
            prop_diameter_max=float(self.prop_dia_max_var.get()),
            prop_pitch_min=float(self.prop_pitch_min_var.get()),
            prop_pitch_max=float(self.prop_pitch_max_var.get()),
            speed_min=float(self.speed_min_var.get()),
            speed_max=float(self.speed_max_var.get()),
            speed_step=float(self.speed_step_var.get()),
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
            self._solver = BatchSolver(config)

            # Check permutation count
            total = self._solver.get_permutation_count()
            if total > self.MAX_PERMUTATIONS:
                messagebox.showerror(
                    "Too Many Combinations",
                    f"Total combinations ({total:,}) exceeds limit "
                    f"({self.MAX_PERMUTATIONS:,}).\n\n"
                    "Please reduce your search range."
                )
                return

            if total > self.WARNING_PERMUTATIONS:
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
            self._clear_results_display()

            # Reset progress
            self.progress_var.set(0)
            self.progress_status_var.set("Starting batch analysis...")
            self.progress_detail_var.set("")
            self.progress_stats_var.set("")
            self.progress_time_var.set("")
            self.progress_best_var.set("")

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
            self._results = self._solver.run_batch(
                progress_callback=self._on_progress_update
            )
        except Exception as e:
            # Store error for main thread
            self._batch_error = str(e)

    def _on_progress_update(self, progress):
        """Handle progress update from solver (called from worker thread)."""
        # This is called from the worker thread, so we can't update UI directly
        # The polling mechanism will read the progress state
        pass

    def _poll_progress(self):
        """Poll progress and update UI."""
        if self._solver is None:
            return

        progress = self._solver.progress

        # Update progress bar
        self.progress_var.set(progress.percent_complete)

        # Update status
        if progress.is_running:
            self.progress_status_var.set(
                f"Processing {progress.current:,} / {progress.total:,} "
                f"({progress.percent_complete:.1f}%)"
            )
            self.progress_detail_var.set(
                f"Current: {progress.current_motor} + {progress.current_prop} "
                f"@ {progress.current_speed:.0f} m/s"
            )
            self.progress_stats_var.set(
                f"Valid: {progress.results_valid:,} | "
                f"Invalid: {progress.results_invalid:,}"
            )

            # Time estimates
            if progress.elapsed_seconds > 0:
                rate = progress.rate_per_second
                remaining = progress.estimated_remaining_seconds
                self.progress_time_var.set(
                    f"Rate: {rate:.0f}/sec | "
                    f"Elapsed: {progress.elapsed_seconds:.0f}s | "
                    f"Remaining: ~{remaining:.0f}s"
                )

            # Best so far
            if progress.best_efficiency > 0:
                self.progress_best_var.set(
                    f"Best so far: {progress.best_efficiency*100:.1f}% efficiency - "
                    f"{progress.best_combo}"
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

        if self._solver.progress.is_cancelled:
            self.progress_status_var.set("Cancelled")
            self.status_var.set("Batch analysis cancelled")
        else:
            self.progress_status_var.set("Complete!")
            valid_count = len([r for r in self._results if r.valid])
            self.status_var.set(
                f"Batch complete: {valid_count:,} valid results "
                f"from {len(self._results):,} combinations"
            )

        # Update results display
        self._update_results_display()

    def _cancel_batch(self):
        """Cancel running batch."""
        if self._solver:
            self._solver.cancel()
        self.progress_status_var.set("Cancelling...")

    # =========================================================================
    # Results Display
    # =========================================================================

    def _clear_results_display(self):
        """Clear results table."""
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        self.result_count_var.set("")

    def _update_results_display(self):
        """Update results table with current results."""
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
        valid_results = [r for r in self._results if r.valid and r.throttle <= 100]

        if metric == "efficiency":
            valid_results.sort(key=lambda r: r.system_efficiency, reverse=True)
        elif metric == "current":
            valid_results.sort(key=lambda r: r.motor_current)
        elif metric == "power":
            valid_results.sort(key=lambda r: r.battery_power)
        elif metric == "throttle":
            valid_results.sort(key=lambda r: r.throttle)

        # Display top N
        display_results = valid_results[:top_n]

        for i, r in enumerate(display_results, 1):
            self.results_tree.insert("", "end", values=(
                i,
                r.motor_id,
                r.prop_id,
                f"{r.airspeed:.1f}",
                f"{r.throttle:.1f}",
                f"{r.motor_current:.2f}",
                f"{r.battery_power:.0f}",
                f"{r.system_efficiency*100:.1f}",
                f"{r.motor_efficiency*100:.1f}",
                f"{r.prop_efficiency*100:.1f}",
                f"{r.prop_rpm:.0f}",
            ))

        self.result_count_var.set(
            f"Showing {len(display_results)} of {len(valid_results)} valid results"
        )

    def _export_results(self):
        """Export results to CSV."""
        if not self._results:
            messagebox.showwarning("No Results", "No results to export")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Export Results"
        )

        if filepath:
            try:
                self._solver.export_results_csv(
                    self._results, filepath, valid_only=True
                )
                messagebox.showinfo(
                    "Export Complete",
                    f"Results exported to:\n{filepath}"
                )
            except Exception as e:
                messagebox.showerror("Export Error", str(e))

    # =========================================================================
    # Defaults and Run
    # =========================================================================

    def _set_defaults(self):
        """Set default values."""
        self.battery_var.set("4S (14.8V)")

    def run(self):
        """Start the UI main loop."""
        self.root.mainloop()


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    """Launch the Batch Analyzer UI."""
    app = BatchAnalyzerUI()
    app.run()


if __name__ == "__main__":
    main()
