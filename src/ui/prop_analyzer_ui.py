"""
Propeller Analyzer User Interface
=================================

This module provides a simple graphical user interface (GUI) for the
Propeller Analyzer functionality. Built using tkinter for cross-platform
compatibility and matplotlib for embedded plots.

Features:
---------
- Propeller selection from available APC props
- Thrust and power calculation from RPM and airspeed
- Power calculation from thrust requirement
- Interactive performance plots
- Results display and export

Usage:
------
    from src.ui.prop_analyzer_ui import PropAnalyzerUI

    app = PropAnalyzerUI()
    app.run()

    # Or run directly from command line:
    # python -m src.ui.prop_analyzer_ui
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Optional
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import matplotlib with TkAgg backend for embedding
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

# Import propeller analyzer modules
from src.prop_analyzer.core import PropAnalyzer
from src.prop_analyzer.plotting import PropPlotter
from src.prop_analyzer.config import PropAnalyzerConfig


class PropAnalyzerUI:
    """
    Simple graphical user interface for the Propeller Analyzer.

    This class creates a tkinter-based GUI that allows users to:
    - Select a propeller from the APC database
    - Calculate thrust and power for given operating conditions
    - Calculate required power for a thrust target
    - View interactive performance plots

    Attributes:
    ----------
    root : tk.Tk
        The main tkinter window.

    analyzer : PropAnalyzer
        PropAnalyzer instance for calculations.

    plotter : PropPlotter
        PropPlotter instance for generating plots.

    Example:
    -------
        app = PropAnalyzerUI()
        app.run()
    """

    # -------------------------------------------------------------------------
    # Window Configuration
    # -------------------------------------------------------------------------

    WINDOW_TITLE = "Drone Efficiency Optimizer - Propeller Analyzer"
    WINDOW_MIN_WIDTH = 900
    WINDOW_MIN_HEIGHT = 700

    # Padding constants
    FRAME_PADDING = 10
    WIDGET_PADDING = 5

    def __init__(self):
        """
        Initialize the Propeller Analyzer UI.

        Creates the main window and all UI components. Does not start
        the event loop - call run() to start the application.
        """
        # -------------------------------------------------------------------------
        # Initialize Backend Components
        # -------------------------------------------------------------------------

        # Create configuration and analyzer instances
        self.config = PropAnalyzerConfig()
        self.analyzer = PropAnalyzer(self.config)
        self.plotter = PropPlotter(self.config)

        # Get list of available propellers
        self.available_props = self.analyzer.list_available_propellers()

        # -------------------------------------------------------------------------
        # Create Main Window
        # -------------------------------------------------------------------------

        self.root = tk.Tk()
        self.root.title(self.WINDOW_TITLE)
        self.root.minsize(self.WINDOW_MIN_WIDTH, self.WINDOW_MIN_HEIGHT)

        # Configure grid weights for resizing
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # -------------------------------------------------------------------------
        # Create Main Container Frame
        # -------------------------------------------------------------------------

        self.main_frame = ttk.Frame(self.root, padding=self.FRAME_PADDING)
        self.main_frame.grid(row=0, column=0, sticky="nsew")

        # Configure main frame grid
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=2)
        self.main_frame.rowconfigure(2, weight=1)

        # -------------------------------------------------------------------------
        # Build UI Components
        # -------------------------------------------------------------------------

        self._create_header()
        self._create_input_panel()
        self._create_results_panel()
        self._create_plot_panel()
        self._create_status_bar()

        # Set default values
        self._set_defaults()

    # -------------------------------------------------------------------------
    # UI Creation Methods
    # -------------------------------------------------------------------------

    def _create_header(self):
        """Create the header section with title and description."""
        header_frame = ttk.Frame(self.main_frame)
        header_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        # Title label
        title_label = ttk.Label(
            header_frame,
            text="APC Propeller Performance Analyzer",
            font=("Helvetica", 16, "bold")
        )
        title_label.pack(anchor="w")

        # Description label
        desc_label = ttk.Label(
            header_frame,
            text="Calculate thrust, power, and efficiency for APC propellers",
            font=("Helvetica", 10)
        )
        desc_label.pack(anchor="w")

        # Separator
        ttk.Separator(header_frame, orient="horizontal").pack(fill="x", pady=5)

    def _create_input_panel(self):
        """Create the left panel with input controls."""
        # -------------------------------------------------------------------------
        # Input Frame Container
        # -------------------------------------------------------------------------

        input_frame = ttk.LabelFrame(
            self.main_frame,
            text="Input Parameters",
            padding=self.FRAME_PADDING
        )
        input_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 5), pady=5)

        # -------------------------------------------------------------------------
        # Propeller Selection
        # -------------------------------------------------------------------------

        prop_frame = ttk.Frame(input_frame)
        prop_frame.pack(fill="x", pady=self.WIDGET_PADDING)

        ttk.Label(prop_frame, text="Propeller:").pack(anchor="w")

        self.prop_var = tk.StringVar()
        self.prop_combo = ttk.Combobox(
            prop_frame,
            textvariable=self.prop_var,
            values=self.available_props,
            state="readonly",
            width=30
        )
        self.prop_combo.pack(fill="x", pady=2)

        # Prop info label
        self.prop_info_label = ttk.Label(
            prop_frame,
            text="",
            font=("Helvetica", 9),
            foreground="gray"
        )
        self.prop_info_label.pack(anchor="w")

        # Bind selection event
        self.prop_combo.bind("<<ComboboxSelected>>", self._on_prop_selected)

        # -------------------------------------------------------------------------
        # Operating Conditions
        # -------------------------------------------------------------------------

        ttk.Separator(input_frame, orient="horizontal").pack(fill="x", pady=10)

        conditions_label = ttk.Label(
            input_frame,
            text="Operating Conditions",
            font=("Helvetica", 10, "bold")
        )
        conditions_label.pack(anchor="w")

        # Airspeed input
        speed_frame = ttk.Frame(input_frame)
        speed_frame.pack(fill="x", pady=self.WIDGET_PADDING)

        ttk.Label(speed_frame, text="Airspeed (m/s):").pack(anchor="w")
        self.speed_var = tk.StringVar()
        self.speed_entry = ttk.Entry(speed_frame, textvariable=self.speed_var)
        self.speed_entry.pack(fill="x", pady=2)

        # RPM input
        rpm_frame = ttk.Frame(input_frame)
        rpm_frame.pack(fill="x", pady=self.WIDGET_PADDING)

        ttk.Label(rpm_frame, text="RPM:").pack(anchor="w")
        self.rpm_var = tk.StringVar()
        self.rpm_entry = ttk.Entry(rpm_frame, textvariable=self.rpm_var)
        self.rpm_entry.pack(fill="x", pady=2)

        # -------------------------------------------------------------------------
        # Calculate Button (Thrust/Power from RPM)
        # -------------------------------------------------------------------------

        calc_btn = ttk.Button(
            input_frame,
            text="Calculate Thrust & Power",
            command=self._calculate_from_rpm
        )
        calc_btn.pack(fill="x", pady=10)

        # -------------------------------------------------------------------------
        # Thrust Requirement Section
        # -------------------------------------------------------------------------

        ttk.Separator(input_frame, orient="horizontal").pack(fill="x", pady=10)

        thrust_req_label = ttk.Label(
            input_frame,
            text="Find Power for Thrust Requirement",
            font=("Helvetica", 10, "bold")
        )
        thrust_req_label.pack(anchor="w")

        # Thrust requirement input
        thrust_frame = ttk.Frame(input_frame)
        thrust_frame.pack(fill="x", pady=self.WIDGET_PADDING)

        ttk.Label(thrust_frame, text="Required Thrust (N):").pack(anchor="w")
        self.thrust_req_var = tk.StringVar()
        self.thrust_req_entry = ttk.Entry(thrust_frame, textvariable=self.thrust_req_var)
        self.thrust_req_entry.pack(fill="x", pady=2)

        # Calculate power from thrust button
        calc_power_btn = ttk.Button(
            input_frame,
            text="Calculate Required Power",
            command=self._calculate_from_thrust
        )
        calc_power_btn.pack(fill="x", pady=10)

        # -------------------------------------------------------------------------
        # Plot Buttons
        # -------------------------------------------------------------------------

        ttk.Separator(input_frame, orient="horizontal").pack(fill="x", pady=10)

        plot_label = ttk.Label(
            input_frame,
            text="Performance Plots",
            font=("Helvetica", 10, "bold")
        )
        plot_label.pack(anchor="w")

        plot_thrust_btn = ttk.Button(
            input_frame,
            text="Plot Thrust Curves",
            command=self._plot_thrust
        )
        plot_thrust_btn.pack(fill="x", pady=2)

        plot_power_btn = ttk.Button(
            input_frame,
            text="Plot Power Curves",
            command=self._plot_power
        )
        plot_power_btn.pack(fill="x", pady=2)

        plot_max_thrust_btn = ttk.Button(
            input_frame,
            text="Plot Max Thrust Envelope",
            command=self._plot_max_thrust
        )
        plot_max_thrust_btn.pack(fill="x", pady=2)

        plot_efficiency_btn = ttk.Button(
            input_frame,
            text="Plot Efficiency",
            command=self._plot_efficiency
        )
        plot_efficiency_btn.pack(fill="x", pady=2)

    def _create_results_panel(self):
        """Create the results display panel."""
        results_frame = ttk.LabelFrame(
            self.main_frame,
            text="Results",
            padding=self.FRAME_PADDING
        )
        results_frame.grid(row=1, column=1, sticky="nsew", padx=(5, 0), pady=5)

        # Results text display
        self.results_text = tk.Text(
            results_frame,
            height=15,
            width=50,
            font=("Courier", 10),
            state="disabled"
        )
        self.results_text.pack(fill="both", expand=True)

        # Scrollbar for results
        scrollbar = ttk.Scrollbar(
            results_frame,
            orient="vertical",
            command=self.results_text.yview
        )
        scrollbar.pack(side="right", fill="y")
        self.results_text.configure(yscrollcommand=scrollbar.set)

        # Clear button
        clear_btn = ttk.Button(
            results_frame,
            text="Clear Results",
            command=self._clear_results
        )
        clear_btn.pack(pady=(5, 0))

    def _create_plot_panel(self):
        """Create the embedded plot panel."""
        plot_frame = ttk.LabelFrame(
            self.main_frame,
            text="Plot View",
            padding=self.FRAME_PADDING
        )
        plot_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=5)

        # Configure plot frame
        plot_frame.columnconfigure(0, weight=1)
        plot_frame.rowconfigure(0, weight=1)

        # Create matplotlib figure
        self.figure = Figure(figsize=(10, 5), dpi=100)
        self.ax = self.figure.add_subplot(111)

        # Create canvas
        self.canvas = FigureCanvasTkAgg(self.figure, master=plot_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        # Add matplotlib toolbar
        toolbar_frame = ttk.Frame(plot_frame)
        toolbar_frame.pack(fill="x")
        self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
        self.toolbar.update()

    def _create_status_bar(self):
        """Create the status bar at the bottom of the window."""
        status_frame = ttk.Frame(self.main_frame)
        status_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(5, 0))

        self.status_var = tk.StringVar()
        self.status_var.set(f"Ready - {len(self.available_props)} propellers available")

        status_label = ttk.Label(
            status_frame,
            textvariable=self.status_var,
            relief="sunken",
            anchor="w"
        )
        status_label.pack(fill="x")

    # -------------------------------------------------------------------------
    # Initialization Helpers
    # -------------------------------------------------------------------------

    def _set_defaults(self):
        """Set default values for input fields."""
        # Set default propeller
        if self.available_props:
            default_prop = "7x7E" if "7x7E" in self.available_props else self.available_props[0]
            self.prop_var.set(default_prop)
            self._on_prop_selected(None)

        # Set default operating conditions
        self.speed_var.set("30.0")
        self.rpm_var.set("22500")
        self.thrust_req_var.set("25.0")

    # -------------------------------------------------------------------------
    # Event Handlers
    # -------------------------------------------------------------------------

    def _on_prop_selected(self, event):
        """Handle propeller selection change."""
        prop = self.prop_var.get()
        if prop:
            try:
                # Get operating envelope
                envelope = self.analyzer.get_prop_operating_envelope(prop)
                info_text = (
                    f"Speed: {envelope['min_speed']:.1f}-{envelope['max_speed']:.1f} m/s | "
                    f"RPM: {envelope['min_rpm']:.0f}-{envelope['max_rpm']:.0f}"
                )
                self.prop_info_label.configure(text=info_text)
                self.status_var.set(f"Selected propeller: {prop}")
            except Exception as e:
                self.prop_info_label.configure(text=str(e))

    def _calculate_from_rpm(self):
        """Calculate thrust and power from RPM and airspeed."""
        try:
            # Get input values
            prop = self.prop_var.get()
            v_ms = float(self.speed_var.get())
            rpm = float(self.rpm_var.get())

            if not prop:
                messagebox.showwarning("Warning", "Please select a propeller.")
                return

            # Calculate thrust and power
            thrust = self.analyzer.get_thrust_from_rpm_speed(prop, v_ms, rpm)
            power = self.analyzer.get_power_from_rpm_speed(prop, v_ms, rpm)
            efficiency = self.analyzer.get_efficiency(prop, v_ms, rpm)

            # Format and display results
            result = (
                f"{'='*50}\n"
                f"THRUST & POWER CALCULATION\n"
                f"{'='*50}\n"
                f"Propeller:    {prop}\n"
                f"Airspeed:     {v_ms:.2f} m/s\n"
                f"RPM:          {rpm:.0f}\n"
                f"{'-'*50}\n"
                f"Thrust:       {thrust:.2f} N\n"
                f"Power:        {power:.1f} W\n"
                f"Efficiency:   {efficiency:.3f}\n"
                f"{'='*50}\n\n"
            )

            self._append_results(result)
            self.status_var.set(f"Calculated: {thrust:.2f} N thrust, {power:.1f} W power")

        except ValueError as e:
            messagebox.showerror("Input Error", f"Invalid input: {e}")
        except Exception as e:
            messagebox.showerror("Calculation Error", f"Error: {e}")

    def _calculate_from_thrust(self):
        """Calculate power required for a thrust target."""
        try:
            # Get input values
            prop = self.prop_var.get()
            v_ms = float(self.speed_var.get())
            thrust_req = float(self.thrust_req_var.get())

            if not prop:
                messagebox.showwarning("Warning", "Please select a propeller.")
                return

            # Calculate power and RPM
            result = self.analyzer.get_power_from_thrust_speed(
                prop, thrust_req, v_ms, return_rpm=True
            )

            if result is None:
                self._append_results(
                    f"{'='*50}\n"
                    f"POWER FOR THRUST CALCULATION - FAILED\n"
                    f"{'='*50}\n"
                    f"Thrust requirement ({thrust_req:.1f} N) exceeds\n"
                    f"propeller limits at {v_ms:.2f} m/s\n"
                    f"{'='*50}\n\n"
                )
                self.status_var.set("Thrust requirement exceeds propeller limits!")
                return

            power, rpm = result
            efficiency = self.analyzer.get_efficiency(prop, v_ms, rpm)

            # Format and display results
            output = (
                f"{'='*50}\n"
                f"POWER FOR THRUST CALCULATION\n"
                f"{'='*50}\n"
                f"Propeller:       {prop}\n"
                f"Airspeed:        {v_ms:.2f} m/s\n"
                f"Thrust Required: {thrust_req:.2f} N\n"
                f"{'-'*50}\n"
                f"Required RPM:    {rpm}\n"
                f"Required Power:  {power:.1f} W\n"
                f"Efficiency:      {efficiency:.3f}\n"
                f"{'='*50}\n\n"
            )

            self._append_results(output)
            self.status_var.set(f"Need {power:.1f} W at {rpm} RPM for {thrust_req:.1f} N")

        except ValueError as e:
            messagebox.showerror("Input Error", f"Invalid input: {e}")
        except Exception as e:
            messagebox.showerror("Calculation Error", f"Error: {e}")

    # -------------------------------------------------------------------------
    # Plot Methods
    # -------------------------------------------------------------------------

    def _plot_thrust(self):
        """Plot thrust curves for the selected propeller."""
        prop = self.prop_var.get()
        if not prop:
            messagebox.showwarning("Warning", "Please select a propeller.")
            return

        try:
            # Clear current plot
            self.figure.clear()
            self.ax = self.figure.add_subplot(111)

            # Generate plot
            self.plotter.plot_thrust_curves(prop, ax=self.ax)

            # Refresh canvas
            self.canvas.draw()
            self.status_var.set(f"Displaying thrust curves for {prop}")

        except Exception as e:
            messagebox.showerror("Plot Error", f"Error generating plot: {e}")

    def _plot_power(self):
        """Plot power curves for the selected propeller."""
        prop = self.prop_var.get()
        if not prop:
            messagebox.showwarning("Warning", "Please select a propeller.")
            return

        try:
            # Clear current plot
            self.figure.clear()
            self.ax = self.figure.add_subplot(111)

            # Generate plot
            self.plotter.plot_power_curves(prop, ax=self.ax)

            # Refresh canvas
            self.canvas.draw()
            self.status_var.set(f"Displaying power curves for {prop}")

        except Exception as e:
            messagebox.showerror("Plot Error", f"Error generating plot: {e}")

    def _plot_max_thrust(self):
        """Plot maximum thrust envelope for the selected propeller."""
        prop = self.prop_var.get()
        if not prop:
            messagebox.showwarning("Warning", "Please select a propeller.")
            return

        try:
            # Clear current plot
            self.figure.clear()
            self.ax = self.figure.add_subplot(111)

            # Generate plot
            self.plotter.plot_max_thrust(prop, ax=self.ax)

            # Refresh canvas
            self.canvas.draw()
            self.status_var.set(f"Displaying max thrust envelope for {prop}")

        except Exception as e:
            messagebox.showerror("Plot Error", f"Error generating plot: {e}")

    def _plot_efficiency(self):
        """Plot efficiency map for the selected propeller."""
        prop = self.prop_var.get()
        if not prop:
            messagebox.showwarning("Warning", "Please select a propeller.")
            return

        try:
            # Clear current plot
            self.figure.clear()
            self.ax = self.figure.add_subplot(111)

            # Generate plot
            self.plotter.plot_efficiency_map(prop, ax=self.ax)

            # Refresh canvas
            self.canvas.draw()
            self.status_var.set(f"Displaying efficiency map for {prop}")

        except Exception as e:
            messagebox.showerror("Plot Error", f"Error generating plot: {e}")

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _append_results(self, text: str):
        """Append text to the results display."""
        self.results_text.configure(state="normal")
        self.results_text.insert("end", text)
        self.results_text.see("end")
        self.results_text.configure(state="disabled")

    def _clear_results(self):
        """Clear the results display."""
        self.results_text.configure(state="normal")
        self.results_text.delete("1.0", "end")
        self.results_text.configure(state="disabled")
        self.status_var.set("Results cleared")

    # -------------------------------------------------------------------------
    # Main Entry Point
    # -------------------------------------------------------------------------

    def run(self):
        """Start the UI application main loop."""
        self.root.mainloop()


# -------------------------------------------------------------------------
# Script Entry Point
# -------------------------------------------------------------------------

def main():
    """Main function to launch the Propeller Analyzer UI."""
    print("Starting Propeller Analyzer UI...")
    app = PropAnalyzerUI()
    app.run()


if __name__ == "__main__":
    main()
