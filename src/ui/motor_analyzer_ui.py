"""
Motor Analyzer User Interface
=============================

This module provides a graphical user interface (GUI) for the Motor Analyzer
with preset motor library support and auto-population of parameters.

Features:
---------
- Motor preset library with category filtering
- Auto-populate fields from preset selection
- Manual parameter entry/modification
- Operating point calculations
- Performance visualization

Usage:
------
    from src.ui.motor_analyzer_ui import MotorAnalyzerUI

    app = MotorAnalyzerUI()
    app.run()
"""

import tkinter as tk
from tkinter import ttk, messagebox
import json
from typing import Optional, Dict, Any
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

# Import motor analyzer modules
from src.motor_analyzer.core import MotorAnalyzer
from src.motor_analyzer.plotting import MotorPlotter
from src.motor_analyzer.config import MotorAnalyzerConfig


class MotorAnalyzerUI:
    """
    Graphical user interface for the Motor Analyzer with preset support.

    Provides:
    - Motor preset selection with category filtering
    - Auto-population of motor parameters
    - Manual parameter editing
    - Operating point calculations
    - Performance visualization
    """

    WINDOW_TITLE = "Drone Efficiency Optimizer - Motor Analyzer"
    WINDOW_MIN_WIDTH = 1100
    WINDOW_MIN_HEIGHT = 800

    FRAME_PADDING = 10
    WIDGET_PADDING = 3

    def __init__(self):
        """Initialize the Motor Analyzer UI."""
        # Initialize backend
        self.config = MotorAnalyzerConfig()
        self.analyzer = MotorAnalyzer(self.config)
        self.plotter = MotorPlotter(self.config)

        # Load motor presets
        self.presets = self._load_presets()
        self.categories = list(self.presets.get("categories", {}).keys())
        self.motors = self.presets.get("motors", {})

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

        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=2)
        self.main_frame.rowconfigure(2, weight=1)

        # Build UI
        self._create_header()
        self._create_input_panel()
        self._create_results_panel()
        self._create_plot_panel()
        self._create_status_bar()

        # Set defaults
        self._set_defaults()

    def _load_presets(self) -> Dict[str, Any]:
        """Load motor presets from JSON file."""
        preset_path = self.config.data_root / "motor_presets.json"

        if preset_path.exists():
            try:
                with open(preset_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Could not load presets: {e}")

        # Fall back to motor_database.json
        db_path = self.config.database_path
        if db_path.exists():
            try:
                with open(db_path, 'r') as f:
                    data = json.load(f)
                    # Convert to preset format
                    return {
                        "categories": {"All Motors": list(data.get("motors", {}).keys())},
                        "motors": data.get("motors", {})
                    }
            except Exception as e:
                print(f"Warning: Could not load database: {e}")

        return {"categories": {}, "motors": {}}

    def _create_header(self):
        """Create header section."""
        header_frame = ttk.Frame(self.main_frame)
        header_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        title_label = ttk.Label(
            header_frame,
            text="BLDC Motor Performance Analyzer",
            font=("Helvetica", 16, "bold")
        )
        title_label.pack(anchor="w")

        desc_label = ttk.Label(
            header_frame,
            text="Select a motor preset or enter custom parameters",
            font=("Helvetica", 10)
        )
        desc_label.pack(anchor="w")

        ttk.Separator(header_frame, orient="horizontal").pack(fill="x", pady=5)

    def _create_input_panel(self):
        """Create input controls panel with preset selection."""
        input_frame = ttk.LabelFrame(
            self.main_frame,
            text="Motor Configuration",
            padding=self.FRAME_PADDING
        )
        input_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 5), pady=5)

        # =====================================================================
        # Motor Preset Selection
        # =====================================================================
        preset_section = ttk.LabelFrame(input_frame, text="Motor Presets", padding=5)
        preset_section.pack(fill="x", pady=self.WIDGET_PADDING)

        # Category dropdown
        cat_frame = ttk.Frame(preset_section)
        cat_frame.pack(fill="x", pady=2)
        ttk.Label(cat_frame, text="Category:").pack(anchor="w")
        self.category_var = tk.StringVar()
        self.category_combo = ttk.Combobox(
            cat_frame,
            textvariable=self.category_var,
            values=["All Motors"] + self.categories,
            state="readonly",
            width=30
        )
        self.category_combo.pack(fill="x")
        self.category_combo.bind("<<ComboboxSelected>>", self._on_category_changed)

        # Motor dropdown
        motor_frame = ttk.Frame(preset_section)
        motor_frame.pack(fill="x", pady=2)
        ttk.Label(motor_frame, text="Motor Preset:").pack(anchor="w")
        self.motor_var = tk.StringVar()
        self.motor_combo = ttk.Combobox(
            motor_frame,
            textvariable=self.motor_var,
            values=list(self.motors.keys()),
            state="readonly",
            width=30
        )
        self.motor_combo.pack(fill="x")
        self.motor_combo.bind("<<ComboboxSelected>>", self._on_motor_selected)

        # Motor info display
        self.motor_info_label = ttk.Label(
            preset_section, text="", font=("Helvetica", 8),
            foreground="gray", wraplength=250
        )
        self.motor_info_label.pack(anchor="w", pady=2)

        # Load preset button
        load_btn = ttk.Button(
            preset_section,
            text="Load Preset → Auto-fill Parameters",
            command=self._load_preset_to_fields
        )
        load_btn.pack(fill="x", pady=5)

        # =====================================================================
        # Motor Parameters (Editable)
        # =====================================================================
        params_section = ttk.LabelFrame(
            input_frame, text="Motor Parameters (Editable)", padding=5
        )
        params_section.pack(fill="x", pady=self.WIDGET_PADDING)

        # Create parameter entry fields
        self.param_vars = {}

        param_defs = [
            ("kv", "Kv (RPM/V):", "1000"),
            ("rm_cold", "Rm Cold (Ω):", "0.030"),
            ("i0_ref", "I₀ No-load (A):", "1.5"),
            ("i0_rpm_ref", "I₀ Ref RPM:", "10000"),
            ("i_max", "I Max (A):", "50"),
            ("p_max", "P Max (W):", "800"),
        ]

        for param_id, label_text, default in param_defs:
            frame = ttk.Frame(params_section)
            frame.pack(fill="x", pady=1)

            label = ttk.Label(frame, text=label_text, width=15)
            label.pack(side="left")

            var = tk.StringVar(value=default)
            entry = ttk.Entry(frame, textvariable=var, width=12)
            entry.pack(side="left", padx=5)

            self.param_vars[param_id] = var

        # Use custom parameters button
        use_custom_btn = ttk.Button(
            params_section,
            text="Use Custom Parameters",
            command=self._use_custom_parameters
        )
        use_custom_btn.pack(fill="x", pady=5)

        # =====================================================================
        # Operating Conditions
        # =====================================================================
        op_section = ttk.LabelFrame(
            input_frame, text="Operating Conditions", padding=5
        )
        op_section.pack(fill="x", pady=self.WIDGET_PADDING)

        # Voltage
        v_frame = ttk.Frame(op_section)
        v_frame.pack(fill="x", pady=1)
        ttk.Label(v_frame, text="Supply Voltage (V):", width=18).pack(side="left")
        self.voltage_var = tk.StringVar(value="22.2")
        ttk.Entry(v_frame, textvariable=self.voltage_var, width=10).pack(side="left")

        # Winding temp
        temp_frame = ttk.Frame(op_section)
        temp_frame.pack(fill="x", pady=1)
        ttk.Label(temp_frame, text="Winding Temp (°C):", width=18).pack(side="left")
        self.temp_var = tk.StringVar(value="80")
        ttk.Entry(temp_frame, textvariable=self.temp_var, width=10).pack(side="left")

        # =====================================================================
        # Calculation Inputs
        # =====================================================================
        calc_section = ttk.LabelFrame(input_frame, text="Calculations", padding=5)
        calc_section.pack(fill="x", pady=self.WIDGET_PADDING)

        # RPM-based calculation
        rpm_frame = ttk.Frame(calc_section)
        rpm_frame.pack(fill="x", pady=2)
        ttk.Label(rpm_frame, text="Operating RPM:", width=15).pack(side="left")
        self.rpm_var = tk.StringVar(value="8000")
        ttk.Entry(rpm_frame, textvariable=self.rpm_var, width=10).pack(side="left")
        ttk.Button(
            rpm_frame, text="Calc @ RPM",
            command=self._calculate_at_rpm, width=12
        ).pack(side="left", padx=5)

        # Torque-based calculation
        torque_frame = ttk.Frame(calc_section)
        torque_frame.pack(fill="x", pady=2)
        ttk.Label(torque_frame, text="Load Torque (Nm):", width=15).pack(side="left")
        self.torque_var = tk.StringVar(value="0.3")
        ttk.Entry(torque_frame, textvariable=self.torque_var, width=10).pack(side="left")
        ttk.Button(
            torque_frame, text="Solve Point",
            command=self._solve_operating_point, width=12
        ).pack(side="left", padx=5)

        # =====================================================================
        # Plot Buttons
        # =====================================================================
        plot_section = ttk.LabelFrame(input_frame, text="Plots", padding=5)
        plot_section.pack(fill="x", pady=self.WIDGET_PADDING)

        ttk.Button(
            plot_section, text="Efficiency Map",
            command=self._plot_efficiency_map
        ).pack(fill="x", pady=1)

        ttk.Button(
            plot_section, text="Torque-Speed Curves",
            command=self._plot_torque_speed
        ).pack(fill="x", pady=1)

        ttk.Button(
            plot_section, text="Power Curve",
            command=self._plot_power
        ).pack(fill="x", pady=1)

    def _create_results_panel(self):
        """Create results display panel."""
        results_frame = ttk.LabelFrame(
            self.main_frame,
            text="Results",
            padding=self.FRAME_PADDING
        )
        results_frame.grid(row=1, column=1, sticky="nsew", padx=(5, 0), pady=5)

        self.results_text = tk.Text(
            results_frame,
            height=22,
            width=55,
            font=("Courier", 10),
            state="disabled"
        )
        self.results_text.pack(fill="both", expand=True)

        scrollbar = ttk.Scrollbar(
            results_frame,
            orient="vertical",
            command=self.results_text.yview
        )
        scrollbar.pack(side="right", fill="y")
        self.results_text.configure(yscrollcommand=scrollbar.set)

        btn_frame = ttk.Frame(results_frame)
        btn_frame.pack(fill="x", pady=(5, 0))

        ttk.Button(
            btn_frame, text="Clear Results",
            command=self._clear_results
        ).pack(side="left")

    def _create_plot_panel(self):
        """Create embedded plot panel."""
        plot_frame = ttk.LabelFrame(
            self.main_frame,
            text="Plot View",
            padding=self.FRAME_PADDING
        )
        plot_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=5)

        plot_frame.columnconfigure(0, weight=1)
        plot_frame.rowconfigure(0, weight=1)

        self.figure = Figure(figsize=(10, 5), dpi=100)
        self.ax = self.figure.add_subplot(111)

        self.canvas = FigureCanvasTkAgg(self.figure, master=plot_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        toolbar_frame = ttk.Frame(plot_frame)
        toolbar_frame.pack(fill="x")
        self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
        self.toolbar.update()

    def _create_status_bar(self):
        """Create status bar."""
        status_frame = ttk.Frame(self.main_frame)
        status_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(5, 0))

        self.status_var = tk.StringVar()
        self.status_var.set(f"Ready - {len(self.motors)} motor presets available")

        status_label = ttk.Label(
            status_frame,
            textvariable=self.status_var,
            relief="sunken",
            anchor="w"
        )
        status_label.pack(fill="x")

    def _set_defaults(self):
        """Set default values."""
        self.category_var.set("All Motors")
        self._update_motor_list()

        if self.motors:
            first_motor = list(self.motors.keys())[0]
            self.motor_var.set(first_motor)
            self._on_motor_selected(None)

    def _on_category_changed(self, event):
        """Handle category selection change."""
        self._update_motor_list()

    def _update_motor_list(self):
        """Update motor dropdown based on selected category."""
        category = self.category_var.get()

        if category == "All Motors" or not category:
            motor_list = list(self.motors.keys())
        else:
            motor_list = self.presets.get("categories", {}).get(category, [])

        self.motor_combo['values'] = motor_list

        if motor_list and self.motor_var.get() not in motor_list:
            self.motor_var.set(motor_list[0])
            self._on_motor_selected(None)

    def _on_motor_selected(self, event):
        """Handle motor selection - show info but don't auto-fill yet."""
        motor_id = self.motor_var.get()
        if motor_id and motor_id in self.motors:
            motor = self.motors[motor_id]

            # Display motor info
            info_parts = []
            if motor.get("manufacturer"):
                info_parts.append(motor["manufacturer"])
            info_parts.append(f"Kv={motor.get('kv', 'N/A')}")
            info_parts.append(f"Imax={motor.get('i_max', 'N/A')}A")
            info_parts.append(f"Pmax={motor.get('p_max', 'N/A')}W")

            if motor.get("recommended_voltage"):
                info_parts.append(f"Rec: {motor['recommended_voltage']}")

            self.motor_info_label.configure(text=" | ".join(info_parts))
            self.status_var.set(f"Selected: {motor_id} - Click 'Load Preset' to populate fields")

    def _load_preset_to_fields(self):
        """Load selected motor preset into parameter fields."""
        motor_id = self.motor_var.get()
        if not motor_id or motor_id not in self.motors:
            messagebox.showwarning("Warning", "Please select a motor preset first.")
            return

        motor = self.motors[motor_id]

        # Populate parameter fields
        self.param_vars["kv"].set(str(motor.get("kv", "")))
        self.param_vars["rm_cold"].set(str(motor.get("rm_cold", "")))
        self.param_vars["i0_ref"].set(str(motor.get("i0_ref", "")))
        self.param_vars["i0_rpm_ref"].set(str(motor.get("i0_rpm_ref", "")))
        self.param_vars["i_max"].set(str(motor.get("i_max", "")))
        self.param_vars["p_max"].set(str(motor.get("p_max", "")))

        # Register motor with analyzer
        self._register_current_motor()

        # Show notes if available
        notes = motor.get("notes", "")
        rec_props = motor.get("recommended_props", [])

        result = (
            f"{'='*55}\n"
            f"LOADED PRESET: {motor_id}\n"
            f"{'='*55}\n"
            f"Manufacturer:     {motor.get('manufacturer', 'N/A')}\n"
            f"Kv:               {motor.get('kv')} RPM/V\n"
            f"Rm (cold):        {motor.get('rm_cold')*1000:.1f} mΩ\n"
            f"I₀ (no-load):     {motor.get('i0_ref')} A @ {motor.get('i0_rpm_ref')} RPM\n"
            f"I max:            {motor.get('i_max')} A\n"
            f"P max:            {motor.get('p_max')} W\n"
            f"Mass:             {motor.get('mass_g', 'N/A')} g\n"
            f"Poles:            {motor.get('poles', 'N/A')}\n"
        )

        if rec_props:
            result += f"Recommended Props: {', '.join(rec_props)}\n"

        if motor.get("recommended_voltage"):
            result += f"Recommended Voltage: {motor.get('recommended_voltage')}\n"

        if notes:
            result += f"Notes: {notes}\n"

        result += f"{'='*55}\n\n"

        self._append_results(result)
        self.status_var.set(f"Loaded preset: {motor_id} - Parameters populated")

    def _use_custom_parameters(self):
        """Register custom motor parameters from input fields."""
        self._register_current_motor()
        self.status_var.set("Using custom motor parameters")

        result = (
            f"{'='*55}\n"
            f"CUSTOM MOTOR REGISTERED\n"
            f"{'='*55}\n"
            f"Kv:          {self.param_vars['kv'].get()} RPM/V\n"
            f"Rm (cold):   {self.param_vars['rm_cold'].get()} Ω\n"
            f"I₀:          {self.param_vars['i0_ref'].get()} A\n"
            f"I₀ Ref RPM:  {self.param_vars['i0_rpm_ref'].get()}\n"
            f"I max:       {self.param_vars['i_max'].get()} A\n"
            f"P max:       {self.param_vars['p_max'].get()} W\n"
            f"{'='*55}\n\n"
        )
        self._append_results(result)

    def _register_current_motor(self):
        """Register current parameter values as a motor with the analyzer."""
        try:
            params = {
                "kv": float(self.param_vars["kv"].get()),
                "rm_cold": float(self.param_vars["rm_cold"].get()),
                "i0_ref": float(self.param_vars["i0_ref"].get()),
                "i0_rpm_ref": float(self.param_vars["i0_rpm_ref"].get()),
                "i_max": float(self.param_vars["i_max"].get()),
                "p_max": float(self.param_vars["p_max"].get()),
            }

            self.analyzer.add_motor("_current_motor", params)
            return True

        except ValueError as e:
            messagebox.showerror("Invalid Parameters", f"Please check parameter values: {e}")
            return False

    def _calculate_at_rpm(self):
        """Calculate motor state at known RPM."""
        if not self._register_current_motor():
            return

        try:
            v_supply = float(self.voltage_var.get())
            rpm = float(self.rpm_var.get())
            winding_temp = float(self.temp_var.get())

            state = self.analyzer.get_state_at_rpm(
                "_current_motor", v_supply, rpm, winding_temp
            )

            result = self._format_state_result(
                "STATE AT RPM", v_supply, winding_temp, state
            )

            self._append_results(result)
            self.status_var.set(
                f"Calculated: {state['current']:.1f}A, {state['efficiency']*100:.1f}% eff"
            )

        except ValueError as e:
            messagebox.showerror("Input Error", f"Invalid input: {e}")
        except Exception as e:
            messagebox.showerror("Calculation Error", f"Error: {e}")

    def _solve_operating_point(self):
        """Solve for equilibrium operating point."""
        if not self._register_current_motor():
            return

        try:
            v_supply = float(self.voltage_var.get())
            torque_load = float(self.torque_var.get())
            winding_temp = float(self.temp_var.get())

            state = self.analyzer.solve_operating_point(
                "_current_motor", v_supply, torque_load, winding_temp
            )

            if state is None:
                self._append_results(
                    f"{'='*55}\n"
                    f"OPERATING POINT - NO SOLUTION\n"
                    f"{'='*55}\n"
                    f"No valid operating point for {torque_load:.3f} Nm\n"
                    f"{'='*55}\n\n"
                )
                self.status_var.set("No valid operating point found!")
                return

            result = self._format_state_result(
                "OPERATING POINT", v_supply, winding_temp, state,
                extra_info=f"Load Torque:     {torque_load:.4f} Nm"
            )

            self._append_results(result)
            self.status_var.set(
                f"Found: {state['rpm']:.0f} RPM, {state['current']:.1f}A"
            )

        except ValueError as e:
            messagebox.showerror("Input Error", f"Invalid input: {e}")
        except Exception as e:
            messagebox.showerror("Calculation Error", f"Error: {e}")

    def _format_state_result(
        self,
        title: str,
        v_supply: float,
        winding_temp: float,
        state: dict,
        extra_info: str = ""
    ) -> str:
        """Format motor state as result string."""
        motor_name = self.motor_var.get() or "Custom Motor"

        result = (
            f"{'='*55}\n"
            f"{title}\n"
            f"{'='*55}\n"
            f"Motor:           {motor_name}\n"
            f"Supply Voltage:  {v_supply:.1f} V\n"
            f"Winding Temp:    {winding_temp:.0f} °C\n"
        )

        if extra_info:
            result += f"{extra_info}\n"

        result += (
            f"{'-'*55}\n"
            f"RPM:             {state['rpm']:.0f}\n"
            f"Current:         {state['current']:.2f} A\n"
            f"Torque:          {state['torque']*1000:.2f} mNm\n"
            f"Back-EMF:        {state['v_bemf']:.2f} V\n"
            f"{'-'*55}\n"
            f"Electrical Power: {state['p_elec']:.1f} W\n"
            f"Mechanical Power: {state['p_mech']:.1f} W\n"
            f"Efficiency:       {state['efficiency']*100:.1f} %\n"
            f"{'-'*55}\n"
            f"Copper Losses:    {state['p_loss_copper']:.1f} W\n"
            f"Iron Losses:      {state['p_loss_iron']:.1f} W\n"
            f"{'='*55}\n\n"
        )

        return result

    def _plot_efficiency_map(self):
        """Plot efficiency map."""
        if not self._register_current_motor():
            return

        try:
            v_supply = float(self.voltage_var.get())
            winding_temp = float(self.temp_var.get())

            self.figure.clear()
            self.ax = self.figure.add_subplot(111)

            self.plotter.analyzer = self.analyzer  # Use our analyzer with current motor
            self.plotter.plot_efficiency_map(
                "_current_motor", v_supply,
                winding_temp=winding_temp,
                ax=self.ax,
                show_colorbar=True
            )

            motor_name = self.motor_var.get() or "Custom Motor"
            self.ax.set_title(f"Efficiency Map - {motor_name} @ {v_supply}V")

            self.figure.tight_layout()
            self.canvas.draw()
            self.status_var.set(f"Efficiency map displayed")

        except Exception as e:
            messagebox.showerror("Plot Error", f"Error: {e}")

    def _plot_torque_speed(self):
        """Plot torque-speed curves."""
        if not self._register_current_motor():
            return

        try:
            v_supply = float(self.voltage_var.get())

            self.figure.clear()
            self.ax = self.figure.add_subplot(111)

            self.plotter.analyzer = self.analyzer
            self.plotter.plot_torque_speed_curve(
                "_current_motor", v_supply, ax=self.ax
            )

            motor_name = self.motor_var.get() or "Custom Motor"
            self.ax.set_title(f"Torque-Speed Curves - {motor_name} @ {v_supply}V")

            self.canvas.draw()
            self.status_var.set(f"Torque-speed curves displayed")

        except Exception as e:
            messagebox.showerror("Plot Error", f"Error: {e}")

    def _plot_power(self):
        """Plot power curve."""
        if not self._register_current_motor():
            return

        try:
            v_supply = float(self.voltage_var.get())
            winding_temp = float(self.temp_var.get())

            self.figure.clear()
            self.ax = self.figure.add_subplot(111)

            self.plotter.analyzer = self.analyzer
            self.plotter.plot_power_curve(
                "_current_motor", v_supply,
                winding_temp=winding_temp,
                ax=self.ax
            )

            motor_name = self.motor_var.get() or "Custom Motor"
            self.ax.set_title(f"Power Curve - {motor_name} @ {v_supply}V")

            self.canvas.draw()
            self.status_var.set(f"Power curve displayed")

        except Exception as e:
            messagebox.showerror("Plot Error", f"Error: {e}")

    def _append_results(self, text: str):
        """Append text to results."""
        self.results_text.configure(state="normal")
        self.results_text.insert("end", text)
        self.results_text.see("end")
        self.results_text.configure(state="disabled")

    def _clear_results(self):
        """Clear results."""
        self.results_text.configure(state="normal")
        self.results_text.delete("1.0", "end")
        self.results_text.configure(state="disabled")
        self.status_var.set("Results cleared")

    def run(self):
        """Start the UI application."""
        self.root.mainloop()


def main():
    """Main entry point."""
    print("Starting Motor Analyzer UI...")
    app = MotorAnalyzerUI()
    app.run()


if __name__ == "__main__":
    main()
