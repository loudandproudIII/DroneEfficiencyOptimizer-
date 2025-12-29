"""
Motor Analyzer Plotting Module
==============================

This module provides visualization functions for motor performance data.
It generates various plots to help users understand motor characteristics
and make informed selection decisions.

Plot Types Available:
--------------------
- Efficiency contour map (efficiency vs RPM/torque)
- Torque-speed curves
- Power curves
- Current vs torque
- Motor comparison overlays

All plots use matplotlib and are designed for both interactive use
and export to publication-quality figures.

Classes:
--------
- MotorPlotter: Main class for generating motor performance plots

Usage:
-----
    from src.motor_analyzer import MotorPlotter

    plotter = MotorPlotter()
    plotter.plot_efficiency_map("MyMotor", v_supply=14.8)
    plt.show()
"""

import math
from typing import Optional, Tuple, List, Dict, Any

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.axes import Axes
from matplotlib import cm

from .config import MotorAnalyzerConfig, DEFAULT_CONFIG
from .core import MotorAnalyzer


class MotorPlotter:
    """
    Motor performance visualization class.

    This class generates various plots for visualizing motor performance
    characteristics from calculations.

    Attributes:
    ----------
    config : MotorAnalyzerConfig
        Configuration object containing settings.

    analyzer : MotorAnalyzer
        MotorAnalyzer instance for calculations.

    Example:
    -------
        plotter = MotorPlotter()

        # Plot efficiency map
        plotter.plot_efficiency_map("MyMotor", 14.8)

        # Plot torque-speed curve
        plotter.plot_torque_speed_curve("MyMotor", 14.8)

        plt.show()
    """

    # =========================================================================
    # Default Plot Styling
    # =========================================================================

    DEFAULT_FIGURE_SIZE = (10, 8)
    DEFAULT_CONTOUR_LEVELS = 15
    DEFAULT_COLORMAP = 'viridis'

    def __init__(self, config: Optional[MotorAnalyzerConfig] = None):
        """
        Initialize the MotorPlotter with configuration settings.

        Parameters:
        ----------
        config : MotorAnalyzerConfig, optional
            Configuration object. Uses default if not specified.
        """
        self.config = config if config is not None else DEFAULT_CONFIG
        self.analyzer = MotorAnalyzer(self.config)

    # =========================================================================
    # Efficiency Map Plotting
    # =========================================================================

    def plot_efficiency_map(
        self,
        motor_id: str,
        v_supply: float,
        rpm_range: Optional[Tuple[float, float]] = None,
        torque_range: Optional[Tuple[float, float]] = None,
        num_points: int = 50,
        winding_temp: Optional[float] = None,
        figsize: Optional[Tuple[int, int]] = None,
        ax: Optional[Axes] = None,
        show_colorbar: bool = True
    ) -> Figure:
        """
        Create efficiency contour map (efficiency vs RPM and torque).

        This is the most comprehensive visualization of motor performance,
        showing efficiency across the entire operating envelope.

        Parameters:
        ----------
        motor_id : str
            Motor identifier.

        v_supply : float
            Supply voltage (V).

        rpm_range : tuple, optional
            (min_rpm, max_rpm). Auto-calculated if not specified.

        torque_range : tuple, optional
            (min_torque, max_torque). Auto-calculated if not specified.

        num_points : int
            Resolution of the map (points per axis).

        winding_temp : float, optional
            Winding temperature (°C).

        figsize : tuple, optional
            Figure size (width, height) in inches.

        ax : Axes, optional
            Existing axes to plot on.

        show_colorbar : bool
            Whether to show the colorbar.

        Returns:
        -------
        Figure
            Matplotlib figure object.

        Example:
        -------
            plotter = MotorPlotter()
            fig = plotter.plot_efficiency_map("MyMotor", 14.8)
            fig.savefig("efficiency_map.png", dpi=150)
        """
        # Generate efficiency map data
        map_data = self.analyzer.generate_efficiency_map(
            motor_id, v_supply, rpm_range, torque_range,
            num_points, winding_temp
        )

        # Create figure if no axes provided
        if ax is None:
            fig, ax = plt.subplots(figsize=figsize or self.DEFAULT_FIGURE_SIZE)
        else:
            fig = ax.get_figure()

        # Create meshgrid for contour plot
        rpm_grid, torque_grid = np.meshgrid(
            map_data["rpm_values"],
            map_data["torque_values"]
        )

        # Plot efficiency contours
        # Mask invalid regions
        efficiency = np.ma.masked_invalid(map_data["efficiency_map"])

        # Filled contour plot
        contour_filled = ax.contourf(
            rpm_grid, torque_grid, efficiency * 100,  # Convert to percentage
            levels=self.DEFAULT_CONTOUR_LEVELS,
            cmap=self.DEFAULT_COLORMAP
        )

        # Add contour lines
        contour_lines = ax.contour(
            rpm_grid, torque_grid, efficiency * 100,
            levels=self.DEFAULT_CONTOUR_LEVELS,
            colors='white',
            linewidths=0.5,
            alpha=0.5
        )

        # Add contour labels
        ax.clabel(contour_lines, inline=True, fontsize=8, fmt='%.0f%%')

        # Add colorbar
        if show_colorbar:
            cbar = fig.colorbar(contour_filled, ax=ax)
            cbar.set_label('Efficiency (%)')

        # Plot current limit boundary
        limits = self.analyzer.get_motor_limits(motor_id, v_supply)
        motor = self.analyzer.get_motor(motor_id)

        # Calculate max torque at each RPM (current limit)
        rpm_boundary = map_data["rpm_values"]
        torque_boundary = []
        for rpm in rpm_boundary:
            max_t = self.analyzer.get_max_torque_at_rpm(
                motor_id, rpm, winding_temp or self.config.default_winding_temp
            )
            torque_boundary.append(max_t)

        ax.plot(rpm_boundary, torque_boundary, 'r--', linewidth=2,
                label=f'Max Current ({motor.i_max:.0f}A)')

        # Configure plot
        ax.set_xlabel('RPM')
        ax.set_ylabel('Torque (Nm)')
        ax.set_title(f'Motor Efficiency Map - {motor_id} @ {v_supply}V')
        ax.legend(loc='upper right')
        ax.grid(True, alpha=0.3)

        return fig

    # =========================================================================
    # Torque-Speed Curve
    # =========================================================================

    def plot_torque_speed_curve(
        self,
        motor_id: str,
        v_supply: float,
        current_levels: Optional[List[float]] = None,
        winding_temp: Optional[float] = None,
        figsize: Optional[Tuple[int, int]] = None,
        ax: Optional[Axes] = None
    ) -> Figure:
        """
        Plot torque vs RPM curves at various current levels.

        Shows the classic motor torque-speed characteristic with
        lines of constant current.

        Parameters:
        ----------
        motor_id : str
            Motor identifier.

        v_supply : float
            Supply voltage (V).

        current_levels : list, optional
            Current values to plot. Auto-generated if not specified.

        winding_temp : float, optional
            Winding temperature (°C).

        figsize : tuple, optional
            Figure size.

        ax : Axes, optional
            Existing axes.

        Returns:
        -------
        Figure
            Matplotlib figure object.
        """
        motor = self.analyzer.get_motor(motor_id)
        limits = self.analyzer.get_motor_limits(motor_id, v_supply)

        if winding_temp is None:
            winding_temp = self.config.default_winding_temp

        # Create figure if needed
        if ax is None:
            fig, ax = plt.subplots(figsize=figsize or self.DEFAULT_FIGURE_SIZE)
        else:
            fig = ax.get_figure()

        # Generate current levels if not specified
        if current_levels is None:
            current_levels = np.linspace(
                motor.i0_ref * 2,
                motor.i_max,
                5
            )

        # RPM range
        rpm_values = np.linspace(
            limits["rpm_no_load"] * 0.05,
            limits["rpm_no_load"] * 0.98,
            100
        )

        # Plot curve for each current level
        for current in current_levels:
            torque_values = []
            valid_rpm = []

            for rpm in rpm_values:
                # Calculate torque at this RPM and current
                i0 = self.config.i0_at_rpm(motor.i0_ref, motor.i0_rpm_ref, rpm)
                i_torque = current - i0

                if i_torque > 0:
                    torque = i_torque * motor.kt
                    torque_values.append(torque)
                    valid_rpm.append(rpm)

            if valid_rpm:
                ax.plot(valid_rpm, torque_values,
                       label=f'{current:.1f} A', linewidth=2)

        # Configure plot
        ax.set_xlabel('RPM')
        ax.set_ylabel('Torque (Nm)')
        ax.set_title(f'Torque-Speed Curves - {motor_id} @ {v_supply}V')
        ax.legend(title='Current', loc='upper right')
        ax.grid(True, alpha=0.3)
        ax.set_xlim(0, limits["rpm_no_load"])
        ax.set_ylim(0, None)

        return fig

    # =========================================================================
    # Power Curve
    # =========================================================================

    def plot_power_curve(
        self,
        motor_id: str,
        v_supply: float,
        winding_temp: Optional[float] = None,
        figsize: Optional[Tuple[int, int]] = None,
        ax: Optional[Axes] = None
    ) -> Figure:
        """
        Plot mechanical power output vs RPM at maximum current.

        Shows the power envelope of the motor - maximum power available
        at each RPM.

        Parameters:
        ----------
        motor_id : str
            Motor identifier.

        v_supply : float
            Supply voltage (V).

        winding_temp : float, optional
            Winding temperature (°C).

        figsize : tuple, optional
            Figure size.

        ax : Axes, optional
            Existing axes.

        Returns:
        -------
        Figure
            Matplotlib figure object.
        """
        motor = self.analyzer.get_motor(motor_id)
        limits = self.analyzer.get_motor_limits(motor_id, v_supply)

        if winding_temp is None:
            winding_temp = self.config.default_winding_temp

        # Create figure if needed
        if ax is None:
            fig, ax = plt.subplots(figsize=figsize or self.DEFAULT_FIGURE_SIZE)
        else:
            fig = ax.get_figure()

        # RPM range
        rpm_values = np.linspace(
            limits["rpm_no_load"] * 0.05,
            limits["rpm_no_load"] * 0.98,
            100
        )

        # Calculate power at max current for each RPM
        power_mech = []
        power_elec = []
        efficiency = []

        for rpm in rpm_values:
            state = self.analyzer.get_state_at_rpm(
                motor_id, v_supply, rpm, winding_temp
            )

            # Limit current to i_max
            if state["current"] > motor.i_max:
                # Recalculate at max current
                i0 = self.config.i0_at_rpm(motor.i0_ref, motor.i0_rpm_ref, rpm)
                i_torque = motor.i_max - i0
                torque = i_torque * motor.kt
                p_mech = torque * (rpm * math.pi / 30.0)
                p_elec = v_supply * motor.i_max
            else:
                p_mech = state["p_mech"]
                p_elec = state["p_elec"]

            power_mech.append(p_mech)
            power_elec.append(p_elec)
            if p_elec > 0:
                efficiency.append(p_mech / p_elec * 100)
            else:
                efficiency.append(0)

        # Plot power curves
        ax.plot(rpm_values, power_mech, 'b-', linewidth=2,
               label='Mechanical Power')
        ax.plot(rpm_values, power_elec, 'r--', linewidth=2,
               label='Electrical Power')

        # Add efficiency on secondary axis
        ax2 = ax.twinx()
        ax2.plot(rpm_values, efficiency, 'g:', linewidth=2,
                label='Efficiency')
        ax2.set_ylabel('Efficiency (%)', color='green')
        ax2.tick_params(axis='y', labelcolor='green')
        ax2.set_ylim(0, 100)

        # Add max power line
        max_power_idx = np.argmax(power_mech)
        max_power = power_mech[max_power_idx]
        max_power_rpm = rpm_values[max_power_idx]
        ax.axhline(y=max_power, color='blue', linestyle=':', alpha=0.5)
        ax.annotate(f'Max: {max_power:.0f}W @ {max_power_rpm:.0f} RPM',
                   xy=(max_power_rpm, max_power),
                   xytext=(max_power_rpm * 0.7, max_power * 1.1),
                   fontsize=10)

        # Configure plot
        ax.set_xlabel('RPM')
        ax.set_ylabel('Power (W)')
        ax.set_title(f'Power Curves - {motor_id} @ {v_supply}V (Max Current)')
        ax.legend(loc='upper left')
        ax.grid(True, alpha=0.3)
        ax.set_xlim(0, limits["rpm_no_load"])
        ax.set_ylim(0, None)

        return fig

    # =========================================================================
    # Current vs Torque
    # =========================================================================

    def plot_current_vs_torque(
        self,
        motor_id: str,
        rpm_values: Optional[List[float]] = None,
        figsize: Optional[Tuple[int, int]] = None,
        ax: Optional[Axes] = None
    ) -> Figure:
        """
        Plot current draw vs output torque at various RPM values.

        Useful for understanding the current-torque relationship and
        planning battery/ESC requirements.

        Parameters:
        ----------
        motor_id : str
            Motor identifier.

        rpm_values : list, optional
            RPM values to plot. Auto-generated if not specified.

        figsize : tuple, optional
            Figure size.

        ax : Axes, optional
            Existing axes.

        Returns:
        -------
        Figure
            Matplotlib figure object.
        """
        motor = self.analyzer.get_motor(motor_id)

        # Create figure if needed
        if ax is None:
            fig, ax = plt.subplots(figsize=figsize or self.DEFAULT_FIGURE_SIZE)
        else:
            fig = ax.get_figure()

        # Generate RPM values if not specified
        if rpm_values is None:
            rpm_values = [
                motor.i0_rpm_ref * 0.5,
                motor.i0_rpm_ref,
                motor.i0_rpm_ref * 1.5
            ]

        # Torque range
        max_torque = motor.i_max * motor.kt
        torque_range = np.linspace(0, max_torque * 0.9, 50)

        # Plot for each RPM
        for rpm in rpm_values:
            currents = []
            for torque in torque_range:
                current = self.analyzer.get_current_from_torque(
                    motor_id, torque, rpm
                )
                currents.append(current)

            ax.plot(torque_range * 1000, currents,  # Convert Nm to mNm
                   label=f'{rpm:.0f} RPM', linewidth=2)

        # Add max current line
        ax.axhline(y=motor.i_max, color='red', linestyle='--',
                  label=f'Max Current ({motor.i_max:.0f}A)')

        # Configure plot
        ax.set_xlabel('Torque (mNm)')
        ax.set_ylabel('Current (A)')
        ax.set_title(f'Current vs Torque - {motor_id}')
        ax.legend(loc='upper left')
        ax.grid(True, alpha=0.3)
        ax.set_ylim(0, motor.i_max * 1.2)

        return fig

    # =========================================================================
    # Motor Comparison
    # =========================================================================

    def compare_motors_power(
        self,
        motor_ids: List[str],
        v_supply: float,
        figsize: Optional[Tuple[int, int]] = None
    ) -> Figure:
        """
        Compare power curves of multiple motors.

        Overlays the power envelopes of several motors for selection purposes.

        Parameters:
        ----------
        motor_ids : list
            List of motor identifiers to compare.

        v_supply : float
            Supply voltage (V).

        figsize : tuple, optional
            Figure size.

        Returns:
        -------
        Figure
            Matplotlib figure object.
        """
        fig, ax = plt.subplots(figsize=figsize or self.DEFAULT_FIGURE_SIZE)

        for motor_id in motor_ids:
            try:
                motor = self.analyzer.get_motor(motor_id)
                limits = self.analyzer.get_motor_limits(motor_id, v_supply)

                rpm_values = np.linspace(
                    limits["rpm_no_load"] * 0.1,
                    limits["rpm_no_load"] * 0.95,
                    50
                )

                power_values = []
                for rpm in rpm_values:
                    # Max torque at this RPM
                    max_torque = self.analyzer.get_max_torque_at_rpm(
                        motor_id, rpm
                    )
                    power = max_torque * (rpm * math.pi / 30.0)
                    power_values.append(power)

                ax.plot(rpm_values, power_values, linewidth=2,
                       label=f'{motor_id} (Kv={motor.kv})')

            except Exception as e:
                print(f"Could not plot {motor_id}: {e}")

        ax.set_xlabel('RPM')
        ax.set_ylabel('Max Mechanical Power (W)')
        ax.set_title(f'Motor Power Comparison @ {v_supply}V')
        ax.legend(loc='best')
        ax.grid(True, alpha=0.3)

        return fig

    def compare_motors_efficiency(
        self,
        motor_ids: List[str],
        v_supply: float,
        target_rpm: float,
        figsize: Optional[Tuple[int, int]] = None
    ) -> Figure:
        """
        Compare efficiency vs torque at a fixed RPM for multiple motors.

        Parameters:
        ----------
        motor_ids : list
            List of motor identifiers to compare.

        v_supply : float
            Supply voltage (V).

        target_rpm : float
            Operating RPM for comparison.

        figsize : tuple, optional
            Figure size.

        Returns:
        -------
        Figure
            Matplotlib figure object.
        """
        fig, ax = plt.subplots(figsize=figsize or self.DEFAULT_FIGURE_SIZE)

        for motor_id in motor_ids:
            try:
                motor = self.analyzer.get_motor(motor_id)

                # Max torque at target RPM
                max_torque = self.analyzer.get_max_torque_at_rpm(
                    motor_id, target_rpm
                )

                torque_values = np.linspace(
                    0.1 * max_torque,
                    0.9 * max_torque,
                    50
                )

                efficiency_values = []
                for torque in torque_values:
                    eff = self.analyzer.get_efficiency(
                        motor_id, target_rpm, torque, v_supply
                    )
                    efficiency_values.append(eff * 100)

                ax.plot(torque_values * 1000, efficiency_values, linewidth=2,
                       label=f'{motor_id}')

            except Exception as e:
                print(f"Could not plot {motor_id}: {e}")

        ax.set_xlabel('Torque (mNm)')
        ax.set_ylabel('Efficiency (%)')
        ax.set_title(f'Motor Efficiency Comparison @ {target_rpm:.0f} RPM, {v_supply}V')
        ax.legend(loc='best')
        ax.grid(True, alpha=0.3)
        ax.set_ylim(0, 100)

        return fig
