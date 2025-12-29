"""
Propeller Analyzer Plotting Module
==================================

This module provides visualization functions for propeller performance data.
It generates various plots to help users understand propeller characteristics
and make informed selection decisions.

Plot Types Available:
--------------------
- Thrust vs Airspeed curves (for multiple RPM values)
- Power vs Airspeed curves (for multiple RPM values)
- Maximum thrust envelope (thrust at max RPM vs airspeed)
- Efficiency maps

All plots use matplotlib and are designed for both interactive use
and export to publication-quality figures.

Classes:
--------
- PropPlotter: Main class for generating propeller performance plots

Usage:
-----
    from src.prop_analyzer.plotting import PropPlotter

    plotter = PropPlotter()
    fig = plotter.plot_thrust_curves("7x7E")
    plt.show()
"""

import pickle
from pathlib import Path
from typing import Optional, Tuple, List

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.axes import Axes

from .config import PropAnalyzerConfig, DEFAULT_CONFIG
from .core import PropAnalyzer


class PropPlotter:
    """
    Propeller performance visualization class.

    This class generates various plots for visualizing propeller performance
    data from the APC database.

    Attributes:
    ----------
    config : PropAnalyzerConfig
        Configuration object containing paths and settings.

    analyzer : PropAnalyzer
        PropAnalyzer instance for accessing performance calculations.

    _database : pd.DataFrame or None
        Cached propeller database (loaded on first use).

    Example:
    -------
        plotter = PropPlotter()

        # Plot all thrust curves for a propeller
        plotter.plot_thrust_curves("7x7E")

        # Plot maximum thrust envelope
        plotter.plot_max_thrust("7x7E")

        plt.show()
    """

    # -------------------------------------------------------------------------
    # Default Plot Styling
    # -------------------------------------------------------------------------

    # Default figure sizes for different plot types
    DEFAULT_FIGURE_SIZE = (12, 8)
    DEFAULT_ENVELOPE_SIZE = (10, 6)

    # Default styling options
    DEFAULT_GRID = True
    DEFAULT_LEGEND_COLS = 2
    DEFAULT_LEGEND_LOC = "best"

    def __init__(self, config: Optional[PropAnalyzerConfig] = None):
        """
        Initialize the PropPlotter with configuration settings.

        Parameters:
        ----------
        config : PropAnalyzerConfig, optional
            Configuration object specifying paths and settings.
            If None, uses the default configuration.
        """
        # Use provided config or fall back to default
        self.config = config if config is not None else DEFAULT_CONFIG

        # Create analyzer instance for calculations
        self.analyzer = PropAnalyzer(self.config)

        # Database cache (loaded on first use)
        self._database = None

    # -------------------------------------------------------------------------
    # Database Access
    # -------------------------------------------------------------------------

    def _load_database(self) -> pd.DataFrame:
        """
        Load the propeller database from disk (with caching).

        The database contains all performance data points for all propellers,
        organized with columns for prop name, RPM, airspeed, thrust, power, etc.

        Returns:
        -------
        pd.DataFrame
            Propeller performance database.

        Raises:
        ------
        FileNotFoundError
            If the database file does not exist.
        """
        # Return cached database if available
        if self._database is not None:
            return self._database

        # Check if database file exists
        if not self.config.database_path.exists():
            raise FileNotFoundError(
                f"Database file not found: {self.config.database_path}\n"
                "Please ensure the APC-Prop-DB.pkl file is in place."
            )

        # Load database from pickle file
        self._database = pd.read_pickle(self.config.database_path)

        return self._database

    def _get_prop_data(self, prop: str) -> pd.DataFrame:
        """
        Extract data for a specific propeller from the database.

        Parameters:
        ----------
        prop : str
            Propeller identifier (e.g., "7x7E").

        Returns:
        -------
        pd.DataFrame
            Filtered dataframe containing only data for the specified prop.

        Raises:
        ------
        ValueError
            If the propeller is not found in the database.
        """
        df = self._load_database()

        # Filter for the specified propeller
        prop_df = df[df.PROP == prop]

        if prop_df.empty:
            available_props = df.PROP.unique()[:10]
            raise ValueError(
                f"Propeller '{prop}' not found in database.\n"
                f"Example available propellers: {list(available_props)}"
            )

        return prop_df

    # -------------------------------------------------------------------------
    # Thrust Plotting Methods
    # -------------------------------------------------------------------------

    def plot_thrust_curves(
        self,
        prop: str,
        figsize: Optional[Tuple[int, int]] = None,
        show_legend: bool = True,
        ax: Optional[Axes] = None
    ) -> Figure:
        """
        Plot thrust vs airspeed curves for all RPM values.

        Creates a multi-line plot showing how thrust varies with airspeed
        for each tested RPM value. This is useful for understanding the
        propeller's thrust characteristics across its operating envelope.

        Parameters:
        ----------
        prop : str
            Propeller identifier (e.g., "7x7E", "10x5").

        figsize : tuple, optional
            Figure size as (width, height) in inches.
            Default is (12, 8).

        show_legend : bool, optional
            Whether to display the legend. Default is True.

        ax : matplotlib.axes.Axes, optional
            Existing axes to plot on. If None, creates new figure.

        Returns:
        -------
        matplotlib.figure.Figure
            The matplotlib figure object.

        Example:
        -------
            plotter = PropPlotter()
            fig = plotter.plot_thrust_curves("7x7E")
            fig.savefig("thrust_curves.png", dpi=150)
            plt.show()

        Notes:
        -----
        - Each line represents thrust at a specific RPM
        - Higher RPM values produce more thrust at all airspeeds
        - Thrust generally decreases with increasing airspeed
        """
        # Get data for this propeller
        prop_df = self._get_prop_data(prop)

        # Create figure if no axes provided
        if ax is None:
            fig, ax = plt.subplots(
                1,
                figsize=figsize or self.DEFAULT_FIGURE_SIZE
            )
        else:
            fig = ax.get_figure()

        # Plot thrust curve for each RPM value
        for rpm in sorted(prop_df.RPM.unique()):
            # Filter data for this RPM
            rpm_data = prop_df[prop_df.RPM == rpm]

            # Plot thrust vs speed
            ax.plot(
                rpm_data.V_ms,
                rpm_data.Thrust_N,
                label=f"RPM = {rpm}"
            )

        # Configure plot appearance
        ax.set_xlabel("Airspeed [m/s]")
        ax.set_ylabel("Thrust [N]")
        ax.set_title(f"Propeller Thrust Mapping - APC {prop}")
        ax.grid(self.DEFAULT_GRID)

        if show_legend:
            ax.legend(
                loc=self.DEFAULT_LEGEND_LOC,
                ncol=self.DEFAULT_LEGEND_COLS
            )

        return fig

    def plot_max_thrust(
        self,
        prop: str,
        num_points: int = 50,
        figsize: Optional[Tuple[int, int]] = None,
        ax: Optional[Axes] = None
    ) -> Figure:
        """
        Plot maximum thrust envelope vs airspeed.

        Creates a plot showing the maximum achievable thrust at each airspeed
        (i.e., thrust at maximum RPM). This defines the propeller's thrust
        capability boundary.

        Parameters:
        ----------
        prop : str
            Propeller identifier.

        num_points : int, optional
            Number of points to sample across the speed range.
            Default is 50.

        figsize : tuple, optional
            Figure size as (width, height) in inches.
            Default is (10, 6).

        ax : matplotlib.axes.Axes, optional
            Existing axes to plot on. If None, creates new figure.

        Returns:
        -------
        matplotlib.figure.Figure
            The matplotlib figure object.

        Example:
        -------
            plotter = PropPlotter()
            fig = plotter.plot_max_thrust("7x7E")
            plt.show()

        Notes:
        -----
        - This represents the absolute maximum thrust the propeller can produce
        - Useful for determining if a propeller can meet thrust requirements
        - The curve typically decreases with increasing airspeed
        """
        # Load the thrust interpolator to get bounds and data
        thrust_interp = self.analyzer._load_interpolator(prop, "thrust")
        bounds = self.analyzer._get_interpolator_bounds(thrust_interp)

        # Extract bounds
        min_speed = bounds["min_speed"]
        max_speed = bounds["max_speed"]
        max_rpm = bounds["max_rpm"]

        # Generate array of airspeeds to sample
        speeds = np.linspace(min_speed, max_speed, num_points)

        # Calculate thrust at max RPM for each speed
        thrusts = []
        for speed in speeds:
            thrust = thrust_interp(speed, max_rpm)
            thrusts.append(thrust)

        # Create figure if no axes provided
        if ax is None:
            fig, ax = plt.subplots(
                1,
                figsize=figsize or self.DEFAULT_ENVELOPE_SIZE
            )
        else:
            fig = ax.get_figure()

        # Plot the maximum thrust envelope
        ax.plot(speeds, thrusts, linewidth=2)

        # Configure plot appearance
        ax.set_xlabel("Airspeed [m/s]")
        ax.set_ylabel("Thrust [N]")
        ax.set_title(f"Maximum Thrust Envelope - APC {prop} @ {max_rpm} RPM")
        ax.grid(True, which="both")

        # Set y-axis to start at 0 for better visualization
        ax.set_ylim(0, max(thrusts) * 1.1)

        return fig

    # -------------------------------------------------------------------------
    # Power Plotting Methods
    # -------------------------------------------------------------------------

    def plot_power_curves(
        self,
        prop: str,
        figsize: Optional[Tuple[int, int]] = None,
        show_legend: bool = True,
        ax: Optional[Axes] = None
    ) -> Figure:
        """
        Plot power vs airspeed curves for all RPM values.

        Creates a multi-line plot showing how power consumption varies with
        airspeed for each tested RPM value.

        Parameters:
        ----------
        prop : str
            Propeller identifier (e.g., "7x7E", "10x5").

        figsize : tuple, optional
            Figure size as (width, height) in inches.
            Default is (12, 8).

        show_legend : bool, optional
            Whether to display the legend. Default is True.

        ax : matplotlib.axes.Axes, optional
            Existing axes to plot on. If None, creates new figure.

        Returns:
        -------
        matplotlib.figure.Figure
            The matplotlib figure object.

        Example:
        -------
            plotter = PropPlotter()
            fig = plotter.plot_power_curves("7x7E")
            plt.show()

        Notes:
        -----
        - Each line represents power at a specific RPM
        - Power is relatively constant with airspeed (slight decrease)
        - Power increases approximately with RPM^3
        """
        # Get data for this propeller
        prop_df = self._get_prop_data(prop)

        # Create figure if no axes provided
        if ax is None:
            fig, ax = plt.subplots(
                1,
                figsize=figsize or self.DEFAULT_FIGURE_SIZE
            )
        else:
            fig = ax.get_figure()

        # Plot power curve for each RPM value
        for rpm in sorted(prop_df.RPM.unique()):
            # Filter data for this RPM
            rpm_data = prop_df[prop_df.RPM == rpm]

            # Plot power vs speed
            ax.plot(
                rpm_data.V_ms,
                rpm_data.PWR_W,
                label=f"RPM = {rpm}"
            )

        # Configure plot appearance
        ax.set_xlabel("Airspeed [m/s]")
        ax.set_ylabel("Power [W]")
        ax.set_title(f"Propeller Power Mapping - APC {prop}")
        ax.grid(self.DEFAULT_GRID)

        if show_legend:
            ax.legend(
                loc=self.DEFAULT_LEGEND_LOC,
                ncol=self.DEFAULT_LEGEND_COLS
            )

        return fig

    # -------------------------------------------------------------------------
    # Combined / Advanced Plots
    # -------------------------------------------------------------------------

    def plot_thrust_and_power(
        self,
        prop: str,
        figsize: Optional[Tuple[int, int]] = None
    ) -> Figure:
        """
        Create a side-by-side plot of thrust and power curves.

        Generates a 1x2 subplot figure with thrust curves on the left
        and power curves on the right for easy comparison.

        Parameters:
        ----------
        prop : str
            Propeller identifier.

        figsize : tuple, optional
            Figure size as (width, height) in inches.
            Default is (16, 6).

        Returns:
        -------
        matplotlib.figure.Figure
            The matplotlib figure object.

        Example:
        -------
            plotter = PropPlotter()
            fig = plotter.plot_thrust_and_power("7x7E")
            fig.savefig("prop_performance.png", dpi=150, bbox_inches='tight')
            plt.show()
        """
        # Create figure with two subplots
        fig, (ax_thrust, ax_power) = plt.subplots(
            1, 2,
            figsize=figsize or (16, 6)
        )

        # Plot thrust curves on left subplot
        self.plot_thrust_curves(prop, ax=ax_thrust)

        # Plot power curves on right subplot
        self.plot_power_curves(prop, ax=ax_power)

        # Adjust layout for better spacing
        fig.tight_layout()

        return fig

    def plot_efficiency_map(
        self,
        prop: str,
        rpm_values: Optional[List[float]] = None,
        figsize: Optional[Tuple[int, int]] = None,
        ax: Optional[Axes] = None
    ) -> Figure:
        """
        Plot propeller efficiency vs airspeed for selected RPM values.

        Efficiency is calculated as (Thrust * Velocity) / Power.
        Higher values indicate better conversion of power to useful thrust.

        Parameters:
        ----------
        prop : str
            Propeller identifier.

        rpm_values : list, optional
            Specific RPM values to plot. If None, uses evenly spaced values.

        figsize : tuple, optional
            Figure size as (width, height) in inches.

        ax : matplotlib.axes.Axes, optional
            Existing axes to plot on. If None, creates new figure.

        Returns:
        -------
        matplotlib.figure.Figure
            The matplotlib figure object.

        Notes:
        -----
        - Efficiency is zero at zero airspeed (by definition)
        - Maximum efficiency typically occurs at moderate airspeeds
        - Very high airspeeds can reduce efficiency
        """
        # Get data for this propeller
        prop_df = self._get_prop_data(prop)

        # Determine RPM values to plot
        if rpm_values is None:
            all_rpms = sorted(prop_df.RPM.unique())
            # Select approximately 5 evenly spaced RPM values
            step = max(1, len(all_rpms) // 5)
            rpm_values = all_rpms[::step]

        # Create figure if no axes provided
        if ax is None:
            fig, ax = plt.subplots(
                1,
                figsize=figsize or self.DEFAULT_FIGURE_SIZE
            )
        else:
            fig = ax.get_figure()

        # Plot efficiency curve for each RPM value
        for rpm in rpm_values:
            rpm_data = prop_df[prop_df.RPM == rpm].copy()

            # Calculate efficiency (avoid division by zero)
            rpm_data["efficiency"] = np.where(
                (rpm_data.PWR_W > 0) & (rpm_data.V_ms > 0),
                (rpm_data.Thrust_N * rpm_data.V_ms) / rpm_data.PWR_W,
                0
            )

            # Plot efficiency vs speed
            ax.plot(
                rpm_data.V_ms,
                rpm_data.efficiency,
                label=f"RPM = {rpm}"
            )

        # Configure plot appearance
        ax.set_xlabel("Airspeed [m/s]")
        ax.set_ylabel("Efficiency (η)")
        ax.set_title(f"Propeller Efficiency - APC {prop}")
        ax.grid(self.DEFAULT_GRID)
        ax.legend(loc=self.DEFAULT_LEGEND_LOC)

        # Set y-axis limits for better visualization
        ax.set_ylim(0, None)

        return fig

    # -------------------------------------------------------------------------
    # Comparison Plots
    # -------------------------------------------------------------------------

    def compare_props_max_thrust(
        self,
        props: List[str],
        figsize: Optional[Tuple[int, int]] = None
    ) -> Figure:
        """
        Compare maximum thrust envelopes for multiple propellers.

        Creates an overlay plot of maximum thrust vs airspeed for
        several propellers, useful for propeller selection.

        Parameters:
        ----------
        props : list
            List of propeller identifiers to compare.

        figsize : tuple, optional
            Figure size as (width, height) in inches.

        Returns:
        -------
        matplotlib.figure.Figure
            The matplotlib figure object.

        Example:
        -------
            plotter = PropPlotter()
            fig = plotter.compare_props_max_thrust(["7x7E", "8x6", "9x6E"])
            plt.show()
        """
        # Create figure
        fig, ax = plt.subplots(
            1,
            figsize=figsize or self.DEFAULT_FIGURE_SIZE
        )

        # Plot each propeller's max thrust envelope
        for prop in props:
            try:
                # Load interpolator and get bounds
                thrust_interp = self.analyzer._load_interpolator(prop, "thrust")
                bounds = self.analyzer._get_interpolator_bounds(thrust_interp)

                min_speed = bounds["min_speed"]
                max_speed = bounds["max_speed"]
                max_rpm = bounds["max_rpm"]

                # Generate sample points
                speeds = np.linspace(min_speed, max_speed, 50)
                thrusts = [thrust_interp(s, max_rpm) for s in speeds]

                # Plot
                ax.plot(speeds, thrusts, label=f"{prop} @ {max_rpm} RPM", linewidth=2)

            except FileNotFoundError:
                print(f"Warning: Propeller '{prop}' not found, skipping.")
                continue

        # Configure plot appearance
        ax.set_xlabel("Airspeed [m/s]")
        ax.set_ylabel("Maximum Thrust [N]")
        ax.set_title("Propeller Comparison - Maximum Thrust Envelopes")
        ax.grid(True, which="both")
        ax.legend(loc=self.DEFAULT_LEGEND_LOC)
        ax.set_ylim(0, None)

        return fig
