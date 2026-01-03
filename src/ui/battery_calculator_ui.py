"""
Battery Pack Calculator User Interface
=======================================

This module provides a graphical user interface (GUI) for the Battery Pack Calculator
with cell library support and optional physical layout calculations.

Features:
---------
- Cell preset library with form factor filtering
- Pack configuration (1S-12S, 1P-8P)
- Electrical calculations (voltage sag, IR, power limits)
- Thermal analysis (heat generation, temperature rise)
- OPTIONAL physical layout (dimensions, COG) - user selectable
- Energy/runtime calculations

Usage:
------
    from src.ui.battery_calculator_ui import BatteryCalculatorUI

    app = BatteryCalculatorUI()
    app.run()
"""

import tkinter as tk
from tkinter import ttk, messagebox
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

# Import battery calculator modules
from src.battery_calculator import (
    BatteryPack,
    CellSpec,
    CELL_DATABASE,
    get_cell,
    list_cells,
    list_cells_by_form_factor,
    BatteryCalculatorConfig,
    FormFactor,
    PackArrangement,
    trace_all_calculations,
)


class BatteryCalculatorUI:
    """
    Graphical user interface for the Battery Pack Calculator.

    Provides:
    - Cell preset selection with form factor filtering
    - Pack configuration (series/parallel)
    - Electrical performance calculations
    - Thermal analysis
    - Optional physical layout calculations
    """

    WINDOW_TITLE = "Drone Efficiency Optimizer - Battery Pack Calculator"
    WINDOW_MIN_WIDTH = 1200
    WINDOW_MIN_HEIGHT = 850

    FRAME_PADDING = 10
    WIDGET_PADDING = 3

    def __init__(self):
        """Initialize the Battery Calculator UI."""
        # Initialize configuration
        self.config = BatteryCalculatorConfig()

        # Current pack (will be created when calculate is pressed)
        self.current_pack: Optional[BatteryPack] = None

        # Create main window
        self.root = tk.Tk()
        self.root.title(self.WINDOW_TITLE)
        self.root.minsize(self.WINDOW_MIN_WIDTH, self.WINDOW_MIN_HEIGHT)

        # Configure grid
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # Main container with scrollbar
        self.main_canvas = tk.Canvas(self.root)
        self.scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.main_canvas.yview)
        self.scrollable_frame = ttk.Frame(self.main_canvas, padding=self.FRAME_PADDING)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))
        )

        self.main_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.main_canvas.configure(yscrollcommand=self.scrollbar.set)

        self.main_canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")

        # Bind mouse wheel
        self.main_canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        # Configure main frame columns
        self.scrollable_frame.columnconfigure(0, weight=1)
        self.scrollable_frame.columnconfigure(1, weight=2)

        # Build UI
        self._create_header()
        self._create_cell_selection()
        self._create_pack_config()
        self._create_operating_conditions()
        self._create_geometry_toggle()
        self._create_calculate_button()
        self._create_results_panel()
        self._create_plot_panel()
        self._create_status_bar()

        # Set defaults
        self._set_defaults()

    def _on_mousewheel(self, event):
        """Handle mouse wheel scrolling."""
        self.main_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _create_header(self):
        """Create header section."""
        header_frame = ttk.Frame(self.scrollable_frame)
        header_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        title_label = ttk.Label(
            header_frame,
            text="Battery Pack Performance Calculator",
            font=("Helvetica", 16, "bold")
        )
        title_label.pack(anchor="w")

        desc_label = ttk.Label(
            header_frame,
            text="Configure pack parameters and analyze electrical/thermal performance",
            font=("Helvetica", 10)
        )
        desc_label.pack(anchor="w")

        ttk.Separator(header_frame, orient="horizontal").pack(fill="x", pady=5)

    def _create_cell_selection(self):
        """Create cell selection panel."""
        cell_frame = ttk.LabelFrame(
            self.scrollable_frame,
            text="Cell Selection",
            padding=self.FRAME_PADDING
        )
        cell_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 5), pady=5)

        # Form factor filter
        ff_frame = ttk.Frame(cell_frame)
        ff_frame.pack(fill="x", pady=self.WIDGET_PADDING)
        ttk.Label(ff_frame, text="Form Factor:").pack(anchor="w")
        self.form_factor_var = tk.StringVar()
        self.form_factor_combo = ttk.Combobox(
            ff_frame,
            textvariable=self.form_factor_var,
            values=["All", "21700", "18650", "Pouch (LiPo)"],
            state="readonly",
            width=30
        )
        self.form_factor_combo.pack(fill="x")
        self.form_factor_combo.bind("<<ComboboxSelected>>", self._on_form_factor_changed)

        # Cell selection
        cell_sel_frame = ttk.Frame(cell_frame)
        cell_sel_frame.pack(fill="x", pady=self.WIDGET_PADDING)
        ttk.Label(cell_sel_frame, text="Cell:").pack(anchor="w")
        self.cell_var = tk.StringVar()
        self.cell_combo = ttk.Combobox(
            cell_sel_frame,
            textvariable=self.cell_var,
            values=list(CELL_DATABASE.keys()),
            state="readonly",
            width=30
        )
        self.cell_combo.pack(fill="x")
        self.cell_combo.bind("<<ComboboxSelected>>", self._on_cell_selected)

        # Cell info display
        self.cell_info_frame = ttk.LabelFrame(cell_frame, text="Cell Specifications", padding=5)
        self.cell_info_frame.pack(fill="x", pady=self.WIDGET_PADDING)

        self.cell_info_text = tk.Text(
            self.cell_info_frame,
            height=10,
            width=35,
            state="disabled",
            font=("Courier", 9)
        )
        self.cell_info_text.pack(fill="x")

    def _create_pack_config(self):
        """Create pack configuration panel."""
        config_frame = ttk.LabelFrame(
            self.scrollable_frame,
            text="Pack Configuration",
            padding=self.FRAME_PADDING
        )
        config_frame.grid(row=2, column=0, sticky="nsew", padx=(0, 5), pady=5)

        # Series configuration
        series_frame = ttk.Frame(config_frame)
        series_frame.pack(fill="x", pady=self.WIDGET_PADDING)
        ttk.Label(series_frame, text="Series (S):").pack(anchor="w")
        self.series_var = tk.StringVar(value="6")
        self.series_combo = ttk.Combobox(
            series_frame,
            textvariable=self.series_var,
            values=[str(i) for i in range(1, 13)],
            state="readonly",
            width=10
        )
        self.series_combo.pack(anchor="w")
        self.series_combo.bind("<<ComboboxSelected>>", self._update_config_display)

        # Parallel configuration
        parallel_frame = ttk.Frame(config_frame)
        parallel_frame.pack(fill="x", pady=self.WIDGET_PADDING)
        ttk.Label(parallel_frame, text="Parallel (P):").pack(anchor="w")
        self.parallel_var = tk.StringVar(value="2")
        self.parallel_combo = ttk.Combobox(
            parallel_frame,
            textvariable=self.parallel_var,
            values=[str(i) for i in range(1, 9)],
            state="readonly",
            width=10
        )
        self.parallel_combo.pack(anchor="w")
        self.parallel_combo.bind("<<ComboboxSelected>>", self._update_config_display)

        # Config summary
        self.config_summary_label = ttk.Label(
            config_frame,
            text="Configuration: 6S2P (12 cells)",
            font=("Helvetica", 10, "bold")
        )
        self.config_summary_label.pack(anchor="w", pady=5)

    def _create_operating_conditions(self):
        """Create operating conditions panel."""
        cond_frame = ttk.LabelFrame(
            self.scrollable_frame,
            text="Operating Conditions",
            padding=self.FRAME_PADDING
        )
        cond_frame.grid(row=3, column=0, sticky="nsew", padx=(0, 5), pady=5)

        # SOC
        soc_frame = ttk.Frame(cond_frame)
        soc_frame.pack(fill="x", pady=self.WIDGET_PADDING)
        ttk.Label(soc_frame, text="State of Charge (%):").pack(anchor="w")
        self.soc_var = tk.StringVar(value="80")
        self.soc_entry = ttk.Entry(soc_frame, textvariable=self.soc_var, width=10)
        self.soc_entry.pack(anchor="w")

        # Temperature
        temp_frame = ttk.Frame(cond_frame)
        temp_frame.pack(fill="x", pady=self.WIDGET_PADDING)
        ttk.Label(temp_frame, text="Ambient Temperature (C):").pack(anchor="w")
        self.temp_var = tk.StringVar(value="25")
        self.temp_entry = ttk.Entry(temp_frame, textvariable=self.temp_var, width=10)
        self.temp_entry.pack(anchor="w")

        # Test current
        current_frame = ttk.Frame(cond_frame)
        current_frame.pack(fill="x", pady=self.WIDGET_PADDING)
        ttk.Label(current_frame, text="Test Current (A):").pack(anchor="w")
        self.test_current_var = tk.StringVar(value="30")
        self.test_current_entry = ttk.Entry(current_frame, textvariable=self.test_current_var, width=10)
        self.test_current_entry.pack(anchor="w")

        # Cutoff voltage
        cutoff_frame = ttk.Frame(cond_frame)
        cutoff_frame.pack(fill="x", pady=self.WIDGET_PADDING)
        ttk.Label(cutoff_frame, text="Cutoff Voltage (V/cell):").pack(anchor="w")
        self.cutoff_var = tk.StringVar(value="3.0")
        self.cutoff_entry = ttk.Entry(cutoff_frame, textvariable=self.cutoff_var, width=10)
        self.cutoff_entry.pack(anchor="w")

        # Thermal environment
        thermal_frame = ttk.Frame(cond_frame)
        thermal_frame.pack(fill="x", pady=self.WIDGET_PADDING)
        ttk.Label(thermal_frame, text="Thermal Environment:").pack(anchor="w")
        self.thermal_env_var = tk.StringVar(value="drone_in_flight")
        self.thermal_env_combo = ttk.Combobox(
            thermal_frame,
            textvariable=self.thermal_env_var,
            values=[
                "still_air",
                "light_airflow",
                "drone_in_flight",
                "high_airflow",
                "active_cooling"
            ],
            state="readonly",
            width=20
        )
        self.thermal_env_combo.pack(anchor="w")

        # Thermal environment help text
        thermal_help = ttk.Label(
            cond_frame,
            text="Cruising: drone_in_flight (4 C/W)\nRacing: high_airflow (2.5 C/W)\nBench: still_air (18 C/W)",
            font=("Helvetica", 8),
            foreground="gray"
        )
        thermal_help.pack(anchor="w")

    def _create_geometry_toggle(self):
        """Create optional geometry section toggle."""
        geo_frame = ttk.LabelFrame(
            self.scrollable_frame,
            text="Physical Layout (Optional)",
            padding=self.FRAME_PADDING
        )
        geo_frame.grid(row=4, column=0, sticky="nsew", padx=(0, 5), pady=5)

        # Enable checkbox
        self.enable_geometry_var = tk.BooleanVar(value=False)
        self.geometry_check = ttk.Checkbutton(
            geo_frame,
            text="Calculate physical dimensions and layout",
            variable=self.enable_geometry_var,
            command=self._toggle_geometry_options
        )
        self.geometry_check.pack(anchor="w")

        # Geometry options (initially hidden)
        self.geometry_options_frame = ttk.Frame(geo_frame)

        # Arrangement
        arr_frame = ttk.Frame(self.geometry_options_frame)
        arr_frame.pack(fill="x", pady=self.WIDGET_PADDING)
        ttk.Label(arr_frame, text="Cell Arrangement:").pack(anchor="w")
        self.arrangement_var = tk.StringVar(value="inline")
        self.arrangement_combo = ttk.Combobox(
            arr_frame,
            textvariable=self.arrangement_var,
            values=["inline", "staggered", "stacked"],
            state="readonly",
            width=15
        )
        self.arrangement_combo.pack(anchor="w")

        # Cell gap
        gap_frame = ttk.Frame(self.geometry_options_frame)
        gap_frame.pack(fill="x", pady=self.WIDGET_PADDING)
        ttk.Label(gap_frame, text="Cell Gap (mm):").pack(anchor="w")
        self.cell_gap_var = tk.StringVar(value="0.5")
        self.cell_gap_entry = ttk.Entry(gap_frame, textvariable=self.cell_gap_var, width=10)
        self.cell_gap_entry.pack(anchor="w")

        # Include BMS mass
        self.include_bms_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            self.geometry_options_frame,
            text="Include BMS mass estimate",
            variable=self.include_bms_var
        ).pack(anchor="w", pady=2)

        # Include enclosure mass
        self.include_enclosure_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            self.geometry_options_frame,
            text="Include enclosure mass estimate",
            variable=self.include_enclosure_var
        ).pack(anchor="w", pady=2)

    def _toggle_geometry_options(self):
        """Show/hide geometry options based on checkbox."""
        if self.enable_geometry_var.get():
            self.geometry_options_frame.pack(fill="x", pady=5)
        else:
            self.geometry_options_frame.pack_forget()

    def _create_calculate_button(self):
        """Create calculate button."""
        btn_frame = ttk.Frame(self.scrollable_frame)
        btn_frame.grid(row=5, column=0, sticky="ew", padx=(0, 5), pady=10)

        self.calculate_btn = ttk.Button(
            btn_frame,
            text="Calculate Pack Performance",
            command=self._calculate_pack
        )
        self.calculate_btn.pack(fill="x")

    def _create_results_panel(self):
        """Create results display panel."""
        results_frame = ttk.LabelFrame(
            self.scrollable_frame,
            text="Results",
            padding=self.FRAME_PADDING
        )
        results_frame.grid(row=1, column=1, rowspan=5, sticky="nsew", padx=(5, 0), pady=5)

        # Create notebook for tabbed results
        self.results_notebook = ttk.Notebook(results_frame)
        self.results_notebook.pack(fill="both", expand=True)

        # Electrical tab
        self.electrical_frame = ttk.Frame(self.results_notebook, padding=5)
        self.results_notebook.add(self.electrical_frame, text="Electrical")

        self.electrical_text = tk.Text(
            self.electrical_frame,
            height=20,
            width=50,
            state="disabled",
            font=("Courier", 10)
        )
        self.electrical_text.pack(fill="both", expand=True)

        # Thermal tab
        self.thermal_frame = ttk.Frame(self.results_notebook, padding=5)
        self.results_notebook.add(self.thermal_frame, text="Thermal")

        self.thermal_text = tk.Text(
            self.thermal_frame,
            height=20,
            width=50,
            state="disabled",
            font=("Courier", 10)
        )
        self.thermal_text.pack(fill="both", expand=True)

        # Physical tab (geometry)
        self.physical_frame = ttk.Frame(self.results_notebook, padding=5)
        self.results_notebook.add(self.physical_frame, text="Physical")

        self.physical_text = tk.Text(
            self.physical_frame,
            height=20,
            width=50,
            state="disabled",
            font=("Courier", 10)
        )
        self.physical_text.pack(fill="both", expand=True)

        # Comparison tab
        self.comparison_frame = ttk.Frame(self.results_notebook, padding=5)
        self.results_notebook.add(self.comparison_frame, text="Voltage Curve")

        # Debug tab
        self.debug_frame = ttk.Frame(self.results_notebook, padding=5)
        self.results_notebook.add(self.debug_frame, text="Debug")

        # Debug text with scrollbar
        debug_container = ttk.Frame(self.debug_frame)
        debug_container.pack(fill="both", expand=True)

        debug_scrollbar = ttk.Scrollbar(debug_container)
        debug_scrollbar.pack(side="right", fill="y")

        self.debug_text = tk.Text(
            debug_container,
            height=25,
            width=80,
            state="disabled",
            font=("Courier", 9),
            wrap="none",
            yscrollcommand=debug_scrollbar.set
        )
        self.debug_text.pack(side="left", fill="both", expand=True)
        debug_scrollbar.config(command=self.debug_text.yview)

        # Horizontal scrollbar for debug
        debug_hscroll = ttk.Scrollbar(self.debug_frame, orient="horizontal", command=self.debug_text.xview)
        debug_hscroll.pack(fill="x")
        self.debug_text.config(xscrollcommand=debug_hscroll.set)

        # Debug info label
        debug_info = ttk.Label(
            self.debug_frame,
            text="Shows all calculation steps with formulas, variables, and results",
            font=("Helvetica", 8),
            foreground="gray"
        )
        debug_info.pack(anchor="w", pady=(5, 0))

    def _create_plot_panel(self):
        """Create plot panel for voltage curves."""
        # Create figure for voltage vs current plot
        self.fig = Figure(figsize=(6, 4), dpi=100)
        self.ax = self.fig.add_subplot(111)

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.comparison_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        # Add toolbar
        toolbar_frame = ttk.Frame(self.comparison_frame)
        toolbar_frame.pack(fill="x")
        toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
        toolbar.update()

    def _create_status_bar(self):
        """Create status bar."""
        self.status_var = tk.StringVar(value="Ready - Select a cell and configure pack parameters")
        status_bar = ttk.Label(
            self.scrollable_frame,
            textvariable=self.status_var,
            relief="sunken",
            anchor="w"
        )
        status_bar.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(10, 0))

    def _set_defaults(self):
        """Set default values."""
        self.form_factor_combo.set("All")
        self._update_cell_list()

        if list(CELL_DATABASE.keys()):
            # Default to Molicel P45B if available
            if "Molicel P45B" in CELL_DATABASE:
                self.cell_combo.set("Molicel P45B")
            else:
                self.cell_combo.set(list(CELL_DATABASE.keys())[0])
            self._on_cell_selected(None)

    def _update_cell_list(self):
        """Update cell list based on form factor filter."""
        form_factor = self.form_factor_var.get()

        if form_factor == "All":
            cells = list(CELL_DATABASE.keys())
        elif form_factor == "21700":
            cells = list_cells_by_form_factor(FormFactor.CYLINDRICAL_21700)
        elif form_factor == "18650":
            cells = list_cells_by_form_factor(FormFactor.CYLINDRICAL_18650)
        elif form_factor == "Pouch (LiPo)":
            cells = list_cells_by_form_factor(FormFactor.POUCH)
        else:
            cells = list(CELL_DATABASE.keys())

        self.cell_combo['values'] = cells
        if cells and self.cell_var.get() not in cells:
            self.cell_combo.set(cells[0])
            self._on_cell_selected(None)

    def _on_form_factor_changed(self, event):
        """Handle form factor selection change."""
        self._update_cell_list()

    def _on_cell_selected(self, event):
        """Handle cell selection change."""
        cell_name = self.cell_var.get()
        if not cell_name or cell_name not in CELL_DATABASE:
            return

        cell = CELL_DATABASE[cell_name]

        # Update cell info display
        info_text = self._format_cell_info(cell)

        self.cell_info_text.config(state="normal")
        self.cell_info_text.delete(1.0, tk.END)
        self.cell_info_text.insert(tk.END, info_text)
        self.cell_info_text.config(state="disabled")

        self._update_config_display(None)
        self.status_var.set(f"Selected: {cell.manufacturer} {cell.name}")

    def _format_cell_info(self, cell: CellSpec) -> str:
        """Format cell specification for display."""
        lines = [
            f"Manufacturer: {cell.manufacturer}",
            f"Model: {cell.name}",
            f"Chemistry: {cell.chemistry.value}",
            f"Form Factor: {cell.form_factor.value}",
            f"",
            f"Capacity: {cell.capacity_mah} mAh",
            f"Nominal Voltage: {cell.nominal_voltage} V",
            f"Max Voltage: {cell.max_voltage} V",
            f"Min Voltage: {cell.min_voltage} V",
            f"",
            f"DC IR: {cell.dc_ir_mohm} mOhm",
            f"Max Continuous: {cell.max_continuous_discharge_a} A",
            f"",
            f"Mass: {cell.mass_g} g",
        ]

        if cell.form_factor == FormFactor.POUCH:
            lines.append(f"Dimensions: {cell.width_mm}x{cell.height_mm}x{cell.thickness_mm} mm")
        else:
            lines.append(f"Size: {cell.diameter_mm}x{cell.length_mm} mm")

        lines.append(f"")
        lines.append(f"Data Source: {cell.data_source}")
        lines.append(f"Verified: {'Yes' if cell.verified else 'No'}")

        return "\n".join(lines)

    def _update_config_display(self, event):
        """Update configuration summary display."""
        try:
            series = int(self.series_var.get())
            parallel = int(self.parallel_var.get())
            total_cells = series * parallel
            self.config_summary_label.config(
                text=f"Configuration: {series}S{parallel}P ({total_cells} cells)"
            )
        except ValueError:
            pass

    def _calculate_pack(self):
        """Calculate pack performance."""
        try:
            # Get inputs
            cell_name = self.cell_var.get()
            if not cell_name or cell_name not in CELL_DATABASE:
                messagebox.showerror("Error", "Please select a valid cell")
                return

            cell = CELL_DATABASE[cell_name]
            series = int(self.series_var.get())
            parallel = int(self.parallel_var.get())
            soc = float(self.soc_var.get())
            temp_c = float(self.temp_var.get())
            test_current = float(self.test_current_var.get())
            cutoff_v = float(self.cutoff_var.get())

            # Configure
            config = BatteryCalculatorConfig(
                enable_geometry=self.enable_geometry_var.get(),
                ambient_temp_c=temp_c,
                cutoff_voltage=cutoff_v,
                thermal_environment=self.thermal_env_var.get(),
                include_bms_mass=self.include_bms_var.get() if self.enable_geometry_var.get() else False,
                include_enclosure_mass=self.include_enclosure_var.get() if self.enable_geometry_var.get() else False,
            )

            if self.enable_geometry_var.get():
                config.cell_gap_mm = float(self.cell_gap_var.get())

            # Create pack
            self.current_pack = BatteryPack(cell, series, parallel, config)

            # Calculate and display results
            self._display_electrical_results(soc, temp_c, test_current)
            self._display_thermal_results(soc, temp_c, test_current)
            self._display_physical_results()
            self._plot_voltage_curve(soc, temp_c)
            self._display_debug_trace(soc, temp_c, test_current, cutoff_v)

            self.status_var.set(f"Calculated: {series}S{parallel}P pack with {cell.manufacturer} {cell.name}")

        except ValueError as e:
            messagebox.showerror("Input Error", f"Invalid input: {e}")
        except Exception as e:
            messagebox.showerror("Calculation Error", f"Error during calculation: {e}")

    def _display_electrical_results(self, soc: float, temp_c: float, test_current: float):
        """Display electrical calculation results."""
        pack = self.current_pack

        # Get max current/power
        max_i, limit_i = pack.get_max_continuous_current(soc, temp_c)
        max_p, limit_p = pack.get_max_continuous_power(soc, temp_c)

        # Get voltages
        v_oc = pack.get_open_circuit_voltage(soc)
        v_loaded = pack.get_voltage_at_current(test_current, soc, temp_c)
        v_sag = pack.get_voltage_sag(test_current, soc, temp_c)
        pack_ir = pack.get_pack_ir_mohm(soc, temp_c)

        # Runtime
        runtime = pack.get_runtime_minutes(test_current, soc)

        # Calculate power at test current
        power_at_test = v_loaded * test_current
        power_per_cell = power_at_test / pack.total_cells

        # Cell-level values
        cell_ir = pack.cell.get_ir_adjusted(soc, temp_c)
        current_per_cell = test_current / pack.parallel

        lines = [
            f"Pack Configuration: {pack.configuration_string}",
            f"Cell: {pack.cell.manufacturer} {pack.cell.name}",
            f"Total Cells: {pack.total_cells}",
            f"",
            "=" * 45,
            "VOLTAGE",
            "=" * 45,
            f"Nominal Voltage:      {pack.nominal_voltage:>8.2f} V",
            f"Max Voltage (full):   {pack.max_voltage:>8.2f} V",
            f"Min Voltage (cutoff): {pack.min_voltage:>8.2f} V",
            f"OCV at {soc:.0f}% SOC:       {v_oc:>8.2f} V",
            f"",
            f"At {test_current:.1f}A pack load:",
            f"  Loaded Voltage:     {v_loaded:>8.2f} V",
            f"  Voltage Sag:        {v_sag:>8.2f} V",
            f"",
            "=" * 45,
            "POWER (at {:.1f}A)".format(test_current),
            "=" * 45,
            f"Pack Power:           {power_at_test:>8.0f} W",
            f"Power per Cell:       {power_per_cell:>8.1f} W",
            f"Current per Cell:     {current_per_cell:>8.1f} A",
            f"",
            "=" * 45,
            "CAPACITY & ENERGY",
            "=" * 45,
            f"Capacity:             {pack.capacity_mah:>8.0f} mAh",
            f"Energy (nominal):     {pack.energy_wh:>8.1f} Wh",
            f"Energy Density:       {pack.get_energy_density_wh_kg():>8.0f} Wh/kg",
            f"",
            f"Runtime at {test_current:.1f}A:    {runtime:>8.1f} min",
            f"",
            "=" * 45,
            "RESISTANCE & LIMITS",
            "=" * 45,
            f"Pack IR:              {pack_ir:>8.1f} mOhm",
            f"Cell IR (adjusted):   {cell_ir:>8.1f} mOhm",
            f"",
            f"Max Continuous I:     {max_i:>8.1f} A  ({limit_i} limited)",
            f"Max Continuous P:     {max_p:>8.0f} W",
            f"Max Power per Cell:   {max_p / pack.total_cells:>8.1f} W",
            f"",
            f"Cell Rating:          {pack.cell.max_continuous_discharge_a:>8.0f} A",
            f"Pack Rating ({pack.parallel}P):      {pack.cell.max_continuous_discharge_a * pack.parallel:>8.0f} A",
            f"",
            "=" * 45,
            "MASS",
            "=" * 45,
            f"Total Pack Mass:      {pack.get_total_mass_g():>8.0f} g",
            f"                      {pack.get_mass_kg():>8.3f} kg",
            f"Cell Mass Only:       {pack.get_cell_mass_g():>8.0f} g",
        ]

        self.electrical_text.config(state="normal")
        self.electrical_text.delete(1.0, tk.END)
        self.electrical_text.insert(tk.END, "\n".join(lines))
        self.electrical_text.config(state="disabled")

    def _display_thermal_results(self, soc: float, temp_c: float, test_current: float):
        """Display thermal calculation results."""
        pack = self.current_pack

        # Heat generation at test current
        heat_w = pack.get_heat_generation_w(test_current, soc, temp_c)

        # Steady state temperature
        steady_temp = pack.get_steady_state_temp(test_current, soc)

        # Get max thermal current
        max_i_thermal, _ = pack.get_max_continuous_current(soc, temp_c)

        lines = [
            f"Thermal Analysis at {test_current:.1f}A",
            f"Ambient Temperature: {temp_c:.1f} C",
            f"",
            "=" * 45,
            "HEAT GENERATION",
            "=" * 45,
            f"I2R Heating:          {heat_w:>8.2f} W",
            f"Heat per Cell:        {heat_w / pack.total_cells:>8.3f} W",
            f"",
            "=" * 45,
            "TEMPERATURE",
            "=" * 45,
            f"Steady State Temp:    {steady_temp:>8.1f} C",
            f"Temperature Rise:     {steady_temp - temp_c:>8.1f} C",
            f"Max Allowed:          {pack.config.max_cell_temp_c:>8.1f} C",
            f"",
            "=" * 45,
            "THERMAL LIMITS",
            "=" * 45,
            f"Max Current (thermal):{max_i_thermal:>8.1f} A",
            f"Thermal Resistance:   {pack.config.thermal_resistance:>8.1f} C/W",
            f"",
        ]

        # Current vs temperature analysis
        lines.append("=" * 45)
        lines.append("CURRENT vs STEADY STATE TEMP")
        lines.append("=" * 45)
        lines.append(f"{'Current (A)':<12} {'Temp Rise (C)':<15} {'Final (C)':<12}")
        lines.append("-" * 45)

        for i in [10, 20, 30, 40, 50, 60, 80, 100]:
            if i <= max_i_thermal * 1.2:
                ss_temp = pack.get_steady_state_temp(i, soc)
                rise = ss_temp - temp_c
                marker = " *" if ss_temp > pack.config.max_cell_temp_c else ""
                lines.append(f"{i:<12.0f} {rise:<15.1f} {ss_temp:<12.1f}{marker}")

        lines.append("")
        lines.append("* Exceeds max temperature limit")

        self.thermal_text.config(state="normal")
        self.thermal_text.delete(1.0, tk.END)
        self.thermal_text.insert(tk.END, "\n".join(lines))
        self.thermal_text.config(state="disabled")

    def _display_physical_results(self):
        """Display physical layout results (if enabled)."""
        pack = self.current_pack

        lines = [
            f"Physical Properties - {pack.configuration_string}",
            f"",
            "=" * 45,
            "MASS BREAKDOWN",
            "=" * 45,
        ]

        mass_bd = pack.get_mass_breakdown()
        lines.append(f"Cells ({pack.total_cells}x):      {mass_bd['cells']:>8.0f} g")
        lines.append(f"Interconnects:        {mass_bd['interconnects']:>8.0f} g")
        lines.append(f"Enclosure/Wrap:       {mass_bd['enclosure']:>8.0f} g")
        lines.append(f"BMS:                  {mass_bd['bms']:>8.0f} g")
        lines.append(f"-" * 30)
        lines.append(f"Total Mass:           {mass_bd['total']:>8.0f} g")
        lines.append(f"                      {pack.get_mass_kg():>8.3f} kg")
        lines.append(f"")

        if pack.config.enable_geometry:
            lines.append("=" * 45)
            lines.append("PHYSICAL DIMENSIONS")
            lines.append("=" * 45)

            try:
                # Get arrangement
                arr_map = {
                    "inline": PackArrangement.INLINE,
                    "staggered": PackArrangement.STAGGERED,
                    "stacked": PackArrangement.STACKED,
                }
                arrangement = arr_map.get(self.arrangement_var.get(), PackArrangement.INLINE)

                dims = pack.get_dimensions_mm(arrangement)
                cog = pack.get_cog_mm(arrangement)

                lines.append(f"Arrangement:          {self.arrangement_var.get()}")
                lines.append(f"")
                lines.append(f"Bounding Box:")
                lines.append(f"  Length:             {dims[0]:>8.1f} mm")
                lines.append(f"  Width:              {dims[1]:>8.1f} mm")
                lines.append(f"  Height:             {dims[2]:>8.1f} mm")
                lines.append(f"")
                volume_ml = dims[0] * dims[1] * dims[2] / 1000
                lines.append(f"  Volume:             {volume_ml:>8.0f} mL")
                lines.append(f"")
                lines.append(f"Center of Gravity:")
                lines.append(f"  X:                  {cog[0]:>8.1f} mm")
                lines.append(f"  Y:                  {cog[1]:>8.1f} mm")
                lines.append(f"  Z:                  {cog[2]:>8.1f} mm")

            except Exception as e:
                lines.append(f"Error calculating geometry: {e}")
        else:
            lines.append("=" * 45)
            lines.append("PHYSICAL DIMENSIONS - DISABLED")
            lines.append("=" * 45)
            lines.append("")
            lines.append("Enable 'Calculate physical dimensions'")
            lines.append("checkbox to see geometry calculations.")

        self.physical_text.config(state="normal")
        self.physical_text.delete(1.0, tk.END)
        self.physical_text.insert(tk.END, "\n".join(lines))
        self.physical_text.config(state="disabled")

    def _plot_voltage_curve(self, soc: float, temp_c: float):
        """Plot voltage vs current curve."""
        pack = self.current_pack

        # Clear previous plot
        self.ax.clear()

        # Generate data
        max_i, _ = pack.get_max_continuous_current(soc, temp_c)
        currents = np.linspace(0, max_i * 1.2, 50)

        voltages = []
        powers = []
        for i in currents:
            v = pack.get_voltage_at_current(i, soc, temp_c)
            voltages.append(v)
            powers.append(v * i)

        # Plot voltage curve
        color1 = 'tab:blue'
        self.ax.set_xlabel('Current (A)')
        self.ax.set_ylabel('Voltage (V)', color=color1)
        self.ax.plot(currents, voltages, color=color1, linewidth=2, label='Voltage')
        self.ax.tick_params(axis='y', labelcolor=color1)

        # Add horizontal lines for key voltages
        self.ax.axhline(y=pack.nominal_voltage, color='gray', linestyle='--', alpha=0.5, label='Nominal')
        self.ax.axhline(y=pack.min_voltage, color='red', linestyle='--', alpha=0.5, label='Cutoff')

        # Add vertical line for max current
        self.ax.axvline(x=max_i, color='orange', linestyle='--', alpha=0.5, label=f'Max I ({max_i:.0f}A)')

        # Secondary axis for power
        ax2 = self.ax.twinx()
        color2 = 'tab:green'
        ax2.set_ylabel('Power (W)', color=color2)
        ax2.plot(currents, powers, color=color2, linewidth=2, linestyle=':', label='Power')
        ax2.tick_params(axis='y', labelcolor=color2)

        # Title and grid
        self.ax.set_title(f'{pack.configuration_string} at {soc:.0f}% SOC, {temp_c:.0f}C')
        self.ax.grid(True, alpha=0.3)
        self.ax.legend(loc='upper left')

        self.fig.tight_layout()
        self.canvas.draw()

    def _display_debug_trace(self, soc: float, temp_c: float, test_current: float, cutoff_v: float):
        """Display calculation debug trace."""
        pack = self.current_pack

        try:
            # Generate debug trace
            debugger = trace_all_calculations(
                pack=pack,
                soc_percent=soc,
                temp_c=temp_c,
                test_current_a=test_current,
                cutoff_voltage_per_cell=cutoff_v
            )

            # Get report
            report = debugger.get_report()

            # Display in debug text widget
            self.debug_text.config(state="normal")
            self.debug_text.delete(1.0, tk.END)
            self.debug_text.insert(tk.END, report)
            self.debug_text.config(state="disabled")

            # Scroll to top
            self.debug_text.see("1.0")

        except Exception as e:
            self.debug_text.config(state="normal")
            self.debug_text.delete(1.0, tk.END)
            self.debug_text.insert(tk.END, f"Error generating debug trace:\n{str(e)}")
            self.debug_text.config(state="disabled")

    def run(self):
        """Run the UI application."""
        self.root.mainloop()


def main():
    """Main entry point."""
    app = BatteryCalculatorUI()
    app.run()


if __name__ == "__main__":
    main()
