"""
Powertrain Analyzer User Interface
==================================

This module provides a combined Motor + Propeller analysis interface
with the ability to solve in both directions:

- Motor → Prop: Given motor and throttle, find propeller operating point
- Prop → Motor: Given thrust requirement, find motor operating state

Features:
---------
- Toggle between analysis modes
- Combined efficiency calculations
- System power and performance metrics
- Integrated visualization

Usage:
------
    from src.ui.powertrain_ui import PowertrainUI

    app = PowertrainUI()
    app.run()
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional
import sys
import math
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

# Import analyzer modules
from src.motor_analyzer.core import MotorAnalyzer
from src.motor_analyzer.plotting import MotorPlotter
from src.motor_analyzer.config import MotorAnalyzerConfig

from src.prop_analyzer.core import PropAnalyzer
from src.prop_analyzer.plotting import PropPlotter
from src.prop_analyzer.config import PropAnalyzerConfig


class PowertrainUI:
    """
    Combined Motor + Propeller powertrain analyzer interface.

    Allows bidirectional analysis:
    - Motor → Prop: Find equilibrium given motor/voltage/throttle
    - Prop → Motor: Find motor state for thrust requirement
    """

    WINDOW_TITLE = "Drone Efficiency Optimizer - Powertrain Analyzer"
    WINDOW_MIN_WIDTH = 1100
    WINDOW_MIN_HEIGHT = 800

    FRAME_PADDING = 10
    WIDGET_PADDING = 5

    # Analysis modes
    MODE_MOTOR_TO_PROP = "Motor → Prop"
    MODE_PROP_TO_MOTOR = "Prop → Motor"

    def __init__(self):
        """Initialize the Powertrain UI."""
        # Initialize backends
        self.motor_config = MotorAnalyzerConfig()
        self.prop_config = PropAnalyzerConfig()

        self.motor_analyzer = MotorAnalyzer(self.motor_config)
        self.prop_analyzer = PropAnalyzer(self.prop_config)

        self.motor_plotter = MotorPlotter(self.motor_config)
        self.prop_plotter = PropPlotter(self.prop_config)

        # Get available components
        self.available_motors = self.motor_analyzer.list_available_motors()
        self.available_props = self.prop_analyzer.list_available_propellers()

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

    def _create_header(self):
        """Create header with mode toggle."""
        header_frame = ttk.Frame(self.main_frame)
        header_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        # Title
        title_label = ttk.Label(
            header_frame,
            text="Powertrain Analyzer - Motor + Propeller Integration",
            font=("Helvetica", 16, "bold")
        )
        title_label.pack(anchor="w")

        # Mode selection frame
        mode_frame = ttk.Frame(header_frame)
        mode_frame.pack(fill="x", pady=5)

        ttk.Label(mode_frame, text="Analysis Mode:",
                 font=("Helvetica", 10, "bold")).pack(side="left", padx=(0, 10))

        # Mode toggle
        self.mode_var = tk.StringVar(value=self.MODE_MOTOR_TO_PROP)

        mode_motor_to_prop = ttk.Radiobutton(
            mode_frame,
            text=self.MODE_MOTOR_TO_PROP,
            variable=self.mode_var,
            value=self.MODE_MOTOR_TO_PROP,
            command=self._on_mode_changed
        )
        mode_motor_to_prop.pack(side="left", padx=5)

        mode_prop_to_motor = ttk.Radiobutton(
            mode_frame,
            text=self.MODE_PROP_TO_MOTOR,
            variable=self.mode_var,
            value=self.MODE_PROP_TO_MOTOR,
            command=self._on_mode_changed
        )
        mode_prop_to_motor.pack(side="left", padx=5)

        # Mode description
        self.mode_desc_var = tk.StringVar()
        self.mode_desc_label = ttk.Label(
            header_frame,
            textvariable=self.mode_desc_var,
            font=("Helvetica", 9),
            foreground="gray"
        )
        self.mode_desc_label.pack(anchor="w")

        ttk.Separator(header_frame, orient="horizontal").pack(fill="x", pady=5)

    def _create_input_panel(self):
        """Create input panel with all controls."""
        input_frame = ttk.LabelFrame(
            self.main_frame,
            text="Powertrain Configuration",
            padding=self.FRAME_PADDING
        )
        input_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 5), pady=5)

        # =====================================================================
        # Motor Selection
        # =====================================================================
        motor_section = ttk.LabelFrame(input_frame, text="Motor", padding=5)
        motor_section.pack(fill="x", pady=self.WIDGET_PADDING)

        ttk.Label(motor_section, text="Select Motor:").pack(anchor="w")
        self.motor_var = tk.StringVar()
        self.motor_combo = ttk.Combobox(
            motor_section,
            textvariable=self.motor_var,
            values=self.available_motors,
            state="readonly",
            width=28
        )
        self.motor_combo.pack(fill="x", pady=2)

        self.motor_info_label = ttk.Label(
            motor_section, text="", font=("Helvetica", 8), foreground="gray"
        )
        self.motor_info_label.pack(anchor="w")

        self.motor_combo.bind("<<ComboboxSelected>>", self._on_motor_selected)

        # =====================================================================
        # Propeller Selection
        # =====================================================================
        prop_section = ttk.LabelFrame(input_frame, text="Propeller", padding=5)
        prop_section.pack(fill="x", pady=self.WIDGET_PADDING)

        ttk.Label(prop_section, text="Select Propeller:").pack(anchor="w")
        self.prop_var = tk.StringVar()
        self.prop_combo = ttk.Combobox(
            prop_section,
            textvariable=self.prop_var,
            values=self.available_props,
            state="readonly",
            width=28
        )
        self.prop_combo.pack(fill="x", pady=2)

        self.prop_info_label = ttk.Label(
            prop_section, text="", font=("Helvetica", 8), foreground="gray"
        )
        self.prop_info_label.pack(anchor="w")

        self.prop_combo.bind("<<ComboboxSelected>>", self._on_prop_selected)

        # =====================================================================
        # Common Parameters
        # =====================================================================
        common_section = ttk.LabelFrame(input_frame, text="Operating Conditions", padding=5)
        common_section.pack(fill="x", pady=self.WIDGET_PADDING)

        # Voltage
        v_frame = ttk.Frame(common_section)
        v_frame.pack(fill="x", pady=2)
        ttk.Label(v_frame, text="Battery Voltage (V):").pack(anchor="w")
        self.voltage_var = tk.StringVar()
        ttk.Entry(v_frame, textvariable=self.voltage_var).pack(fill="x")

        # Airspeed
        speed_frame = ttk.Frame(common_section)
        speed_frame.pack(fill="x", pady=2)
        ttk.Label(speed_frame, text="Airspeed (m/s):").pack(anchor="w")
        self.airspeed_var = tk.StringVar()
        ttk.Entry(speed_frame, textvariable=self.airspeed_var).pack(fill="x")

        # Winding temp
        temp_frame = ttk.Frame(common_section)
        temp_frame.pack(fill="x", pady=2)
        ttk.Label(temp_frame, text="Motor Winding Temp (°C):").pack(anchor="w")
        self.temp_var = tk.StringVar()
        ttk.Entry(temp_frame, textvariable=self.temp_var).pack(fill="x")

        # =====================================================================
        # Mode-specific inputs (Motor → Prop)
        # =====================================================================
        self.motor_to_prop_frame = ttk.LabelFrame(
            input_frame, text="Motor → Prop: Input", padding=5
        )
        self.motor_to_prop_frame.pack(fill="x", pady=self.WIDGET_PADDING)

        throttle_frame = ttk.Frame(self.motor_to_prop_frame)
        throttle_frame.pack(fill="x", pady=2)
        ttk.Label(throttle_frame, text="Throttle (0-100%):").pack(anchor="w")
        self.throttle_var = tk.StringVar()
        ttk.Entry(throttle_frame, textvariable=self.throttle_var).pack(fill="x")

        # =====================================================================
        # Mode-specific inputs (Prop → Motor)
        # =====================================================================
        self.prop_to_motor_frame = ttk.LabelFrame(
            input_frame, text="Prop → Motor: Input", padding=5
        )
        self.prop_to_motor_frame.pack(fill="x", pady=self.WIDGET_PADDING)

        thrust_frame = ttk.Frame(self.prop_to_motor_frame)
        thrust_frame.pack(fill="x", pady=2)
        ttk.Label(thrust_frame, text="Required Thrust (N):").pack(anchor="w")
        self.thrust_var = tk.StringVar()
        ttk.Entry(thrust_frame, textvariable=self.thrust_var).pack(fill="x")

        # =====================================================================
        # Calculate Button
        # =====================================================================
        self.calc_btn = ttk.Button(
            input_frame,
            text="Calculate Powertrain",
            command=self._calculate
        )
        self.calc_btn.pack(fill="x", pady=10)

        # =====================================================================
        # Plot Buttons
        # =====================================================================
        plot_section = ttk.LabelFrame(input_frame, text="Plots", padding=5)
        plot_section.pack(fill="x", pady=self.WIDGET_PADDING)

        ttk.Button(
            plot_section,
            text="System Operating Point",
            command=self._plot_system_operating_point
        ).pack(fill="x", pady=2)

        ttk.Button(
            plot_section,
            text="Motor Efficiency Map",
            command=self._plot_motor_efficiency
        ).pack(fill="x", pady=2)

        ttk.Button(
            plot_section,
            text="Prop Thrust Curves",
            command=self._plot_prop_thrust
        ).pack(fill="x", pady=2)

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
            height=20,
            width=60,
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
            text="Visualization",
            padding=self.FRAME_PADDING
        )
        plot_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=5)

        plot_frame.columnconfigure(0, weight=1)
        plot_frame.rowconfigure(0, weight=1)

        self.figure = Figure(figsize=(12, 5), dpi=100)
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
        self.status_var.set(
            f"Ready - {len(self.available_motors)} motors, "
            f"{len(self.available_props)} propellers available"
        )

        status_label = ttk.Label(
            status_frame,
            textvariable=self.status_var,
            relief="sunken",
            anchor="w"
        )
        status_label.pack(fill="x")

    def _set_defaults(self):
        """Set default values."""
        # Motor
        if self.available_motors:
            self.motor_var.set(self.available_motors[0])
            self._on_motor_selected(None)

        # Prop
        if self.available_props:
            default_prop = "10x5" if "10x5" in self.available_props else self.available_props[0]
            self.prop_var.set(default_prop)
            self._on_prop_selected(None)

        # Operating conditions
        self.voltage_var.set("22.2")  # 6S
        self.airspeed_var.set("15.0")
        self.temp_var.set("80")
        self.throttle_var.set("70")
        self.thrust_var.set("15.0")

        # Update mode
        self._on_mode_changed()

    def _on_mode_changed(self):
        """Handle mode toggle."""
        mode = self.mode_var.get()

        if mode == self.MODE_MOTOR_TO_PROP:
            self.mode_desc_var.set(
                "Given motor voltage & throttle → Find propeller equilibrium RPM, thrust, and efficiency"
            )
            self.motor_to_prop_frame.pack(fill="x", pady=self.WIDGET_PADDING)
            self.prop_to_motor_frame.pack_forget()
        else:
            self.mode_desc_var.set(
                "Given thrust requirement → Find required motor current, power, and throttle"
            )
            self.prop_to_motor_frame.pack(fill="x", pady=self.WIDGET_PADDING)
            self.motor_to_prop_frame.pack_forget()

    def _on_motor_selected(self, event):
        """Handle motor selection."""
        motor_id = self.motor_var.get()
        if motor_id:
            try:
                motor = self.motor_analyzer.get_motor(motor_id)
                self.motor_info_label.configure(
                    text=f"Kv={motor.kv}, Imax={motor.i_max}A, Pmax={motor.p_max}W"
                )
            except Exception as e:
                self.motor_info_label.configure(text=str(e))

    def _on_prop_selected(self, event):
        """Handle prop selection."""
        prop_id = self.prop_var.get()
        if prop_id:
            try:
                envelope = self.prop_analyzer.get_prop_operating_envelope(prop_id)
                self.prop_info_label.configure(
                    text=f"RPM: {envelope['min_rpm']:.0f}-{envelope['max_rpm']:.0f}"
                )
            except Exception as e:
                self.prop_info_label.configure(text=str(e))

    def _calculate(self):
        """Run calculation based on current mode."""
        mode = self.mode_var.get()

        if mode == self.MODE_MOTOR_TO_PROP:
            self._calculate_motor_to_prop()
        else:
            self._calculate_prop_to_motor()

    def _calculate_motor_to_prop(self):
        """Calculate equilibrium: Motor drives the analysis."""
        try:
            # Get inputs
            motor_id = self.motor_var.get()
            prop_id = self.prop_var.get()
            v_battery = float(self.voltage_var.get())
            throttle = float(self.throttle_var.get()) / 100.0
            v_motor = v_battery * throttle
            airspeed = float(self.airspeed_var.get())
            winding_temp = float(self.temp_var.get())

            if not motor_id or not prop_id:
                messagebox.showwarning("Warning", "Select both motor and propeller.")
                return

            motor = self.motor_analyzer.get_motor(motor_id)

            # Iterative solution: Find RPM where motor torque = prop torque
            rpm_guess = motor.kv * v_motor * 0.85

            for iteration in range(30):
                # Get prop power requirement at this RPM
                prop_power = self.prop_analyzer.get_power_from_rpm_speed(
                    prop_id, airspeed, rpm_guess
                )

                if prop_power < 0:  # Out of bounds
                    rpm_guess *= 0.9
                    continue

                # Calculate prop torque from power and RPM
                omega = rpm_guess * math.pi / 30.0
                if omega > 0:
                    torque_prop = prop_power / omega
                else:
                    torque_prop = 0

                # Solve motor at this torque
                motor_state = self.motor_analyzer.solve_operating_point(
                    motor_id, v_motor, torque_prop, winding_temp
                )

                if motor_state is None:
                    rpm_guess *= 0.9
                    continue

                # Check convergence
                if abs(motor_state['rpm'] - rpm_guess) < 5:
                    break

                # Update guess with damping
                rpm_guess = 0.7 * motor_state['rpm'] + 0.3 * rpm_guess

            # Final state
            motor_state = self.motor_analyzer.get_state_at_rpm(
                motor_id, v_motor, rpm_guess, winding_temp
            )

            # Get final prop performance
            prop_thrust = self.prop_analyzer.get_thrust_from_rpm_speed(
                prop_id, airspeed, rpm_guess
            )
            prop_power = self.prop_analyzer.get_power_from_rpm_speed(
                prop_id, airspeed, rpm_guess
            )
            prop_efficiency = self.prop_analyzer.get_efficiency(
                prop_id, airspeed, rpm_guess
            )

            # System efficiency
            system_efficiency = motor_state['efficiency'] * prop_efficiency

            # Format result
            result = (
                f"{'='*60}\n"
                f"POWERTRAIN ANALYSIS: Motor → Prop\n"
                f"{'='*60}\n"
                f"Motor:       {motor_id}\n"
                f"Propeller:   {prop_id}\n"
                f"Battery:     {v_battery:.1f} V\n"
                f"Throttle:    {throttle*100:.0f}% ({v_motor:.1f} V to motor)\n"
                f"Airspeed:    {airspeed:.1f} m/s\n"
                f"{'-'*60}\n"
                f"EQUILIBRIUM POINT:\n"
                f"  RPM:               {rpm_guess:.0f}\n"
                f"  Thrust:            {prop_thrust:.2f} N\n"
                f"{'-'*60}\n"
                f"MOTOR PERFORMANCE:\n"
                f"  Current:           {motor_state['current']:.2f} A\n"
                f"  Electrical Power:  {motor_state['p_elec']:.1f} W\n"
                f"  Mechanical Power:  {motor_state['p_mech']:.1f} W\n"
                f"  Motor Efficiency:  {motor_state['efficiency']*100:.1f}%\n"
                f"  Torque:            {motor_state['torque']*1000:.2f} mNm\n"
                f"{'-'*60}\n"
                f"PROPELLER PERFORMANCE:\n"
                f"  Thrust:            {prop_thrust:.2f} N\n"
                f"  Prop Power:        {prop_power:.1f} W\n"
                f"  Prop Efficiency:   {prop_efficiency*100:.1f}%\n"
                f"{'-'*60}\n"
                f"SYSTEM TOTALS:\n"
                f"  System Efficiency: {system_efficiency*100:.1f}%\n"
                f"  Battery Current:   {motor_state['current']:.2f} A\n"
                f"  Battery Power:     {motor_state['p_elec']:.1f} W\n"
                f"{'='*60}\n\n"
            )

            self._append_results(result)
            self.status_var.set(
                f"Equilibrium: {rpm_guess:.0f} RPM, {prop_thrust:.1f}N thrust, "
                f"{system_efficiency*100:.0f}% system eff"
            )

            # Store for plotting
            self._last_result = {
                'rpm': rpm_guess,
                'thrust': prop_thrust,
                'motor_state': motor_state,
                'prop_efficiency': prop_efficiency
            }

        except Exception as e:
            messagebox.showerror("Error", str(e))
            import traceback
            traceback.print_exc()

    def _calculate_prop_to_motor(self):
        """Calculate: Thrust requirement drives the analysis."""
        try:
            # Get inputs
            motor_id = self.motor_var.get()
            prop_id = self.prop_var.get()
            v_battery = float(self.voltage_var.get())
            thrust_required = float(self.thrust_var.get())
            airspeed = float(self.airspeed_var.get())
            winding_temp = float(self.temp_var.get())

            if not motor_id or not prop_id:
                messagebox.showwarning("Warning", "Select both motor and propeller.")
                return

            # Get prop requirement for this thrust
            result = self.prop_analyzer.get_power_from_thrust_speed(
                prop_id, thrust_required, airspeed, return_rpm=True
            )

            if result is None:
                self._append_results(
                    f"{'='*60}\n"
                    f"ANALYSIS FAILED\n"
                    f"{'='*60}\n"
                    f"Thrust requirement ({thrust_required:.1f} N) exceeds\n"
                    f"propeller capability at {airspeed:.1f} m/s\n"
                    f"{'='*60}\n\n"
                )
                return

            prop_power, rpm_required = result
            prop_efficiency = self.prop_analyzer.get_efficiency(
                prop_id, airspeed, rpm_required
            )

            # Now find motor state at this RPM
            # We need to find the voltage that achieves this RPM with this torque
            omega = rpm_required * math.pi / 30.0
            torque_required = prop_power / omega if omega > 0 else 0

            # Get motor state at required RPM with battery voltage
            motor_state = self.motor_analyzer.get_state_at_rpm(
                motor_id, v_battery, rpm_required, winding_temp
            )

            # Calculate effective throttle
            motor = self.motor_analyzer.get_motor(motor_id)
            rm = self.motor_analyzer.config.resistance_at_temp(
                motor.rm_cold, winding_temp
            )
            v_bemf = rpm_required / motor.kv
            v_motor_needed = v_bemf + motor_state['current'] * rm
            throttle = v_motor_needed / v_battery * 100

            # System efficiency
            system_efficiency = motor_state['efficiency'] * prop_efficiency

            # Format result
            result_text = (
                f"{'='*60}\n"
                f"POWERTRAIN ANALYSIS: Prop → Motor\n"
                f"{'='*60}\n"
                f"Motor:       {motor_id}\n"
                f"Propeller:   {prop_id}\n"
                f"Battery:     {v_battery:.1f} V\n"
                f"Airspeed:    {airspeed:.1f} m/s\n"
                f"Target Thrust: {thrust_required:.1f} N\n"
                f"{'-'*60}\n"
                f"REQUIRED OPERATING POINT:\n"
                f"  RPM:               {rpm_required:.0f}\n"
                f"  Throttle:          {throttle:.1f}%\n"
                f"{'-'*60}\n"
                f"MOTOR REQUIREMENTS:\n"
                f"  Current:           {motor_state['current']:.2f} A\n"
                f"  Motor Voltage:     {v_motor_needed:.1f} V\n"
                f"  Electrical Power:  {motor_state['p_elec']:.1f} W\n"
                f"  Mechanical Power:  {motor_state['p_mech']:.1f} W\n"
                f"  Motor Efficiency:  {motor_state['efficiency']*100:.1f}%\n"
                f"  Torque Required:   {torque_required*1000:.2f} mNm\n"
                f"{'-'*60}\n"
                f"PROPELLER PERFORMANCE:\n"
                f"  Thrust:            {thrust_required:.2f} N\n"
                f"  Prop Power:        {prop_power:.1f} W\n"
                f"  Prop Efficiency:   {prop_efficiency*100:.1f}%\n"
                f"{'-'*60}\n"
                f"SYSTEM TOTALS:\n"
                f"  System Efficiency: {system_efficiency*100:.1f}%\n"
                f"  Battery Current:   {motor_state['current']:.2f} A\n"
                f"  Battery Power:     {motor_state['p_elec']:.1f} W\n"
            )

            # Check limits
            if motor_state['current'] > motor.i_max:
                result_text += (
                    f"\n⚠️  WARNING: Current exceeds motor rating "
                    f"({motor.i_max:.0f}A)\n"
                )

            if throttle > 100:
                result_text += (
                    f"\n⚠️  WARNING: Required throttle exceeds 100%\n"
                    f"    Need higher voltage battery\n"
                )

            result_text += f"{'='*60}\n\n"

            self._append_results(result_text)
            self.status_var.set(
                f"For {thrust_required:.1f}N: {rpm_required:.0f} RPM, "
                f"{motor_state['current']:.1f}A, {throttle:.0f}% throttle"
            )

            # Store for plotting
            self._last_result = {
                'rpm': rpm_required,
                'thrust': thrust_required,
                'motor_state': motor_state,
                'prop_efficiency': prop_efficiency
            }

        except Exception as e:
            messagebox.showerror("Error", str(e))
            import traceback
            traceback.print_exc()

    def _plot_system_operating_point(self):
        """Plot showing the system operating point."""
        try:
            motor_id = self.motor_var.get()
            prop_id = self.prop_var.get()
            v_battery = float(self.voltage_var.get())
            airspeed = float(self.airspeed_var.get())

            if not motor_id or not prop_id:
                messagebox.showwarning("Warning", "Select both motor and propeller.")
                return

            self.figure.clear()
            ax1 = self.figure.add_subplot(121)
            ax2 = self.figure.add_subplot(122)

            motor = self.motor_analyzer.get_motor(motor_id)

            # RPM range
            rpm_range = np.linspace(1000, motor.kv * v_battery * 0.95, 50)

            # Calculate prop torque requirement at each RPM
            prop_torques = []
            prop_thrusts = []
            for rpm in rpm_range:
                power = self.prop_analyzer.get_power_from_rpm_speed(
                    prop_id, airspeed, rpm
                )
                if power > 0:
                    omega = rpm * math.pi / 30.0
                    prop_torques.append(power / omega * 1000)  # mNm
                else:
                    prop_torques.append(np.nan)

                thrust = self.prop_analyzer.get_thrust_from_rpm_speed(
                    prop_id, airspeed, rpm
                )
                prop_thrusts.append(thrust if thrust > 0 else np.nan)

            # Calculate motor torque available at each RPM (at various throttles)
            for throttle in [0.5, 0.7, 0.9, 1.0]:
                v_motor = v_battery * throttle
                motor_torques = []
                for rpm in rpm_range:
                    state = self.motor_analyzer.get_state_at_rpm(
                        motor_id, v_motor, rpm
                    )
                    if state['valid'] and state['current'] <= motor.i_max:
                        motor_torques.append(state['torque'] * 1000)  # mNm
                    else:
                        motor_torques.append(np.nan)

                ax1.plot(rpm_range, motor_torques, '--',
                        label=f'Motor @ {throttle*100:.0f}%')

            # Plot prop torque requirement
            ax1.plot(rpm_range, prop_torques, 'b-', linewidth=2,
                    label=f'Prop load ({prop_id})')

            ax1.set_xlabel('RPM')
            ax1.set_ylabel('Torque (mNm)')
            ax1.set_title('Torque Balance')
            ax1.legend(loc='best', fontsize=8)
            ax1.grid(True, alpha=0.3)

            # Thrust vs RPM plot
            ax2.plot(rpm_range, prop_thrusts, 'g-', linewidth=2)
            ax2.set_xlabel('RPM')
            ax2.set_ylabel('Thrust (N)')
            ax2.set_title(f'Thrust vs RPM @ {airspeed} m/s')
            ax2.grid(True, alpha=0.3)

            self.figure.tight_layout()
            self.canvas.draw()

        except Exception as e:
            messagebox.showerror("Plot Error", str(e))

    def _plot_motor_efficiency(self):
        """Plot motor efficiency map."""
        motor_id = self.motor_var.get()
        if not motor_id:
            messagebox.showwarning("Warning", "Select a motor.")
            return

        try:
            v_supply = float(self.voltage_var.get())
            winding_temp = float(self.temp_var.get())

            self.figure.clear()
            self.ax = self.figure.add_subplot(111)

            self.motor_plotter.plot_efficiency_map(
                motor_id, v_supply,
                winding_temp=winding_temp,
                ax=self.ax
            )

            self.figure.tight_layout()
            self.canvas.draw()

        except Exception as e:
            messagebox.showerror("Plot Error", str(e))

    def _plot_prop_thrust(self):
        """Plot prop thrust curves."""
        prop_id = self.prop_var.get()
        if not prop_id:
            messagebox.showwarning("Warning", "Select a propeller.")
            return

        try:
            self.figure.clear()
            self.ax = self.figure.add_subplot(111)

            self.prop_plotter.plot_thrust_curves(prop_id, ax=self.ax)

            self.canvas.draw()

        except Exception as e:
            messagebox.showerror("Plot Error", str(e))

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

    def run(self):
        """Start the application."""
        self.root.mainloop()


def main():
    """Main entry point."""
    print("Starting Powertrain Analyzer UI...")
    app = PowertrainUI()
    app.run()


if __name__ == "__main__":
    main()
