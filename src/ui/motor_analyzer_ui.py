"""
Motor Analyzer User Interface
=============================

This module provides a simple graphical user interface (GUI) for the
Motor Analyzer functionality. Built using tkinter for cross-platform
compatibility and matplotlib for embedded plots.

Features:
---------
- Motor selection from database or custom input
- Operating point calculation from voltage and torque
- State calculation at known RPM
- Efficiency map visualization
- Power and torque curve plots

Usage:
------
    from src.ui.motor_analyzer_ui import MotorAnalyzerUI

    app = MotorAnalyzerUI()
    app.run()
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional
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
    Simple graphical user interface for the Motor Analyzer.

    Provides controls for:
    - Motor selection and custom motor input
    - Operating point calculations
    - Performance visualization
    """

    WINDOW_TITLE = "Drone Efficiency Optimizer - Motor Analyzer"
    WINDOW_MIN_WIDTH = 1000
    WINDOW_MIN_HEIGHT = 750

    FRAME_PADDING = 10
    WIDGET_PADDING = 5

    def __init__(self):
        """Initialize the Motor Analyzer UI."""
        # Initialize backend
        self.config = MotorAnalyzerConfig()
        self.analyzer = MotorAnalyzer(self.config)
        self.plotter = MotorPlotter(self.config)

        # Get available motors
        self.available_motors = self.analyzer.list_available_motors()

        # Create main window
        self.root = tk.Tk()
        self.root.title(self.WINDOW_TITLE)
        self.root.minsize(self.WINDOW_MIN_WIDTH, self.WINDOW_MIN_HEIGHT)

        # Configure grid
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # Create main container
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
            text="Calculate motor efficiency, torque, and power characteristics",
            font=("Helvetica", 10)
        )
        desc_label.pack(anchor="w")

        ttk.Separator(header_frame, orient="horizontal").pack(fill="x", pady=5)

    def _create_input_panel(self):
        """Create input controls panel."""
        input_frame = ttk.LabelFrame(
            self.main_frame,
            text="Motor & Operating Parameters",
            padding=self.FRAME_PADDING
        )
        input_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 5), pady=5)

        # =====================================================================
        # Motor Selection
        # =====================================================================
        motor_frame = ttk.Frame(input_frame)
        motor_frame.pack(fill="x", pady=self.WIDGET_PADDING)

        ttk.Label(motor_frame, text="Select Motor:").pack(anchor="w")

        self.motor_var = tk.StringVar()
        self.motor_combo = ttk.Combobox(
            motor_frame,
            textvariable=self.motor_var,
            values=self.available_motors,
            state="readonly",
            width=30
        )
        self.motor_combo.pack(fill="x", pady=2)

        self.motor_info_label = ttk.Label(
            motor_frame, text="", font=("Helvetica", 9), foreground="gray"
        )
        self.motor_info_label.pack(anchor="w")

        self.motor_combo.bind("<<ComboboxSelected>>", self._on_motor_selected)

        # =====================================================================
        # Operating Conditions
        # =====================================================================
        ttk.Separator(input_frame, orient="horizontal").pack(fill="x", pady=10)

        ttk.Label(input_frame, text="Operating Conditions",
                 font=("Helvetica", 10, "bold")).pack(anchor="w")

        # Voltage
        voltage_frame = ttk.Frame(input_frame)
        voltage_frame.pack(fill="x", pady=self.WIDGET_PADDING)
        ttk.Label(voltage_frame, text="Supply Voltage (V):").pack(anchor="w")
        self.voltage_var = tk.StringVar()
        self.voltage_entry = ttk.Entry(voltage_frame, textvariable=self.voltage_var)
        self.voltage_entry.pack(fill="x", pady=2)

        # Winding Temperature
        temp_frame = ttk.Frame(input_frame)
        temp_frame.pack(fill="x", pady=self.WIDGET_PADDING)
        ttk.Label(temp_frame, text="Winding Temp (°C):").pack(anchor="w")
        self.temp_var = tk.StringVar()
        self.temp_entry = ttk.Entry(temp_frame, textvariable=self.temp_var)
        self.temp_entry.pack(fill="x", pady=2)

        # =====================================================================
        # Calculation Mode: RPM-based
        # =====================================================================
        ttk.Separator(input_frame, orient="horizontal").pack(fill="x", pady=10)

        ttk.Label(input_frame, text="Calculate from RPM",
                 font=("Helvetica", 10, "bold")).pack(anchor="w")

        rpm_frame = ttk.Frame(input_frame)
        rpm_frame.pack(fill="x", pady=self.WIDGET_PADDING)
        ttk.Label(rpm_frame, text="Operating RPM:").pack(anchor="w")
        self.rpm_var = tk.StringVar()
        self.rpm_entry = ttk.Entry(rpm_frame, textvariable=self.rpm_var)
        self.rpm_entry.pack(fill="x", pady=2)

        calc_rpm_btn = ttk.Button(
            input_frame,
            text="Calculate State at RPM",
            command=self._calculate_at_rpm
        )
        calc_rpm_btn.pack(fill="x", pady=5)

        # =====================================================================
        # Calculation Mode: Torque-based
        # =====================================================================
        ttk.Separator(input_frame, orient="horizontal").pack(fill="x", pady=10)

        ttk.Label(input_frame, text="Solve Operating Point",
                 font=("Helvetica", 10, "bold")).pack(anchor="w")

        torque_frame = ttk.Frame(input_frame)
        torque_frame.pack(fill="x", pady=self.WIDGET_PADDING)
        ttk.Label(torque_frame, text="Load Torque (Nm):").pack(anchor="w")
        self.torque_var = tk.StringVar()
        self.torque_entry = ttk.Entry(torque_frame, textvariable=self.torque_var)
        self.torque_entry.pack(fill="x", pady=2)

        calc_torque_btn = ttk.Button(
            input_frame,
            text="Solve for Operating Point",
            command=self._solve_operating_point
        )
        calc_torque_btn.pack(fill="x", pady=5)

        # =====================================================================
        # Plot Buttons
        # =====================================================================
        ttk.Separator(input_frame, orient="horizontal").pack(fill="x", pady=10)

        ttk.Label(input_frame, text="Performance Plots",
                 font=("Helvetica", 10, "bold")).pack(anchor="w")

        plot_eff_btn = ttk.Button(
            input_frame,
            text="Plot Efficiency Map",
            command=self._plot_efficiency_map
        )
        plot_eff_btn.pack(fill="x", pady=2)

        plot_torque_btn = ttk.Button(
            input_frame,
            text="Plot Torque-Speed Curves",
            command=self._plot_torque_speed
        )
        plot_torque_btn.pack(fill="x", pady=2)

        plot_power_btn = ttk.Button(
            input_frame,
            text="Plot Power Curve",
            command=self._plot_power
        )
        plot_power_btn.pack(fill="x", pady=2)

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
            height=18,
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

        clear_btn = ttk.Button(
            results_frame,
            text="Clear Results",
            command=self._clear_results
        )
        clear_btn.pack(pady=(5, 0))

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
        self.status_var.set(f"Ready - {len(self.available_motors)} motors in database")

        status_label = ttk.Label(
            status_frame,
            textvariable=self.status_var,
            relief="sunken",
            anchor="w"
        )
        status_label.pack(fill="x")

    def _set_defaults(self):
        """Set default values."""
        if self.available_motors:
            default_motor = self.available_motors[0]
            self.motor_var.set(default_motor)
            self._on_motor_selected(None)

        self.voltage_var.set("22.2")  # 6S LiPo
        self.temp_var.set("80")
        self.rpm_var.set("8000")
        self.torque_var.set("0.5")

    def _on_motor_selected(self, event):
        """Handle motor selection."""
        motor_id = self.motor_var.get()
        if motor_id:
            try:
                motor = self.analyzer.get_motor(motor_id)
                info_text = (
                    f"Kv: {motor.kv} RPM/V | Rm: {motor.rm_cold*1000:.1f}mΩ | "
                    f"I_max: {motor.i_max}A"
                )
                self.motor_info_label.configure(text=info_text)
                self.status_var.set(f"Selected: {motor_id}")
            except Exception as e:
                self.motor_info_label.configure(text=str(e))

    def _calculate_at_rpm(self):
        """Calculate motor state at known RPM."""
        try:
            motor_id = self.motor_var.get()
            v_supply = float(self.voltage_var.get())
            rpm = float(self.rpm_var.get())
            winding_temp = float(self.temp_var.get())

            if not motor_id:
                messagebox.showwarning("Warning", "Please select a motor.")
                return

            state = self.analyzer.get_state_at_rpm(
                motor_id, v_supply, rpm, winding_temp
            )

            result = self._format_state_result(
                "STATE AT RPM", motor_id, v_supply, winding_temp, state
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
        try:
            motor_id = self.motor_var.get()
            v_supply = float(self.voltage_var.get())
            torque_load = float(self.torque_var.get())
            winding_temp = float(self.temp_var.get())

            if not motor_id:
                messagebox.showwarning("Warning", "Please select a motor.")
                return

            state = self.analyzer.solve_operating_point(
                motor_id, v_supply, torque_load, winding_temp
            )

            if state is None:
                self._append_results(
                    f"{'='*55}\n"
                    f"OPERATING POINT CALCULATION - FAILED\n"
                    f"{'='*55}\n"
                    f"No valid operating point for {torque_load:.3f} Nm load\n"
                    f"{'='*55}\n\n"
                )
                self.status_var.set("No valid operating point found!")
                return

            result = self._format_state_result(
                "OPERATING POINT", motor_id, v_supply, winding_temp, state,
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
        motor_id: str,
        v_supply: float,
        winding_temp: float,
        state: dict,
        extra_info: str = ""
    ) -> str:
        """Format motor state as result string."""
        result = (
            f"{'='*55}\n"
            f"{title}\n"
            f"{'='*55}\n"
            f"Motor:           {motor_id}\n"
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
        motor_id = self.motor_var.get()
        if not motor_id:
            messagebox.showwarning("Warning", "Please select a motor.")
            return

        try:
            v_supply = float(self.voltage_var.get())
            winding_temp = float(self.temp_var.get())

            self.figure.clear()
            self.ax = self.figure.add_subplot(111)

            self.plotter.plot_efficiency_map(
                motor_id, v_supply,
                winding_temp=winding_temp,
                ax=self.ax,
                show_colorbar=True
            )

            self.figure.tight_layout()
            self.canvas.draw()
            self.status_var.set(f"Efficiency map for {motor_id}")

        except Exception as e:
            messagebox.showerror("Plot Error", f"Error: {e}")

    def _plot_torque_speed(self):
        """Plot torque-speed curves."""
        motor_id = self.motor_var.get()
        if not motor_id:
            messagebox.showwarning("Warning", "Please select a motor.")
            return

        try:
            v_supply = float(self.voltage_var.get())

            self.figure.clear()
            self.ax = self.figure.add_subplot(111)

            self.plotter.plot_torque_speed_curve(
                motor_id, v_supply, ax=self.ax
            )

            self.canvas.draw()
            self.status_var.set(f"Torque-speed curves for {motor_id}")

        except Exception as e:
            messagebox.showerror("Plot Error", f"Error: {e}")

    def _plot_power(self):
        """Plot power curve."""
        motor_id = self.motor_var.get()
        if not motor_id:
            messagebox.showwarning("Warning", "Please select a motor.")
            return

        try:
            v_supply = float(self.voltage_var.get())
            winding_temp = float(self.temp_var.get())

            self.figure.clear()
            self.ax = self.figure.add_subplot(111)

            self.plotter.plot_power_curve(
                motor_id, v_supply,
                winding_temp=winding_temp,
                ax=self.ax
            )

            self.canvas.draw()
            self.status_var.set(f"Power curve for {motor_id}")

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
