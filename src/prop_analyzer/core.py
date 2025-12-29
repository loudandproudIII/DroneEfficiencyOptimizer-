"""
Propeller Analyzer Core Module
==============================

This module provides the core calculation functions for propeller performance
analysis. It includes methods for calculating thrust and power based on
propeller specifications, RPM, and airspeed.

The calculations use pre-computed interpolator objects (scipy interpolators)
that were generated from APC's published performance data. These interpolators
enable fast, continuous queries within the propeller's operating envelope.

Classes:
--------
- PropAnalyzer: Main class for propeller performance calculations

Theory Background:
-----------------
Propeller performance depends on several factors:
1. Propeller geometry (diameter, pitch, blade design)
2. Rotational speed (RPM)
3. Forward airspeed (V)
4. Air density (assumed standard conditions)

The key performance parameters are:
- Thrust (T): Force produced by the propeller [Newtons]
- Power (P): Mechanical power required to turn the propeller [Watts]
- Efficiency (η): Ratio of useful power to input power (T*V/P)

Data Source:
-----------
All performance data comes from APC Propellers:
https://www.apcprop.com/technical-information/performance-data/

Units Convention:
----------------
- Speed (V): meters per second (m/s)
- RPM: revolutions per minute
- Thrust: Newtons (N)
- Power: Watts (W)
"""

import pickle
from pathlib import Path
from typing import Optional, Tuple, Union

import numpy as np
from scipy import optimize

from .config import PropAnalyzerConfig, DEFAULT_CONFIG


class PropAnalyzer:
    """
    Propeller performance analyzer using APC propeller data.

    This class provides methods to query propeller performance based on
    operating conditions (RPM and airspeed) or design requirements (thrust).

    The analyzer uses pre-computed scipy interpolator objects to provide
    continuous performance predictions within each propeller's operating
    envelope.

    Attributes:
    ----------
    config : PropAnalyzerConfig
        Configuration object containing paths and settings.

    _interpolator_cache : dict
        Cache for loaded interpolator objects to avoid repeated file I/O.

    Example:
    -------
        # Create analyzer with default configuration
        analyzer = PropAnalyzer()

        # Get thrust for a specific operating point
        thrust = analyzer.get_thrust_from_rpm_speed(
            prop="7x7E",
            v_ms=30.0,
            rpm=22500
        )
        print(f"Thrust: {thrust:.2f} N")

        # Get power required for a thrust target
        power, rpm = analyzer.get_power_from_thrust_speed(
            prop="7x7E",
            thrust_required=25.0,
            v_ms=30.0,
            return_rpm=True
        )
        print(f"Power: {power:.0f} W at {rpm} RPM")
    """

    def __init__(self, config: Optional[PropAnalyzerConfig] = None):
        """
        Initialize the PropAnalyzer with configuration settings.

        Parameters:
        ----------
        config : PropAnalyzerConfig, optional
            Configuration object specifying paths and settings.
            If None, uses the default configuration.

        Raises:
        ------
        FileNotFoundError
            If the configured data directories do not exist.
        """
        # Use provided config or fall back to default
        self.config = config if config is not None else DEFAULT_CONFIG

        # Initialize interpolator cache for performance optimization
        # Interpolators are loaded from disk on first use and cached
        self._interpolator_cache = {}

        # Validate that data paths exist
        path_status = self.config.validate_paths()
        if not path_status["interpolator_dir"]:
            raise FileNotFoundError(
                f"Interpolator directory not found: {self.config.interpolator_path}\n"
                "Please ensure the APC interpolator files are in place."
            )

    # -------------------------------------------------------------------------
    # Interpolator Loading and Caching
    # -------------------------------------------------------------------------

    def _load_interpolator(self, prop: str, interp_type: str) -> object:
        """
        Load an interpolator from disk or retrieve from cache.

        This method implements a simple caching strategy to avoid repeatedly
        loading the same interpolator files from disk during multiple queries.

        Parameters:
        ----------
        prop : str
            Propeller identifier (e.g., "7x7E", "10x5").

        interp_type : str
            Type of interpolator to load. Must be either "thrust" or "power".

        Returns:
        -------
        object
            Scipy interpolator object (typically LinearNDInterpolator).

        Raises:
        ------
        FileNotFoundError
            If the interpolator file does not exist.

        ValueError
            If interp_type is not "thrust" or "power".
        """
        # Validate interpolator type
        if interp_type not in ("thrust", "power"):
            raise ValueError(
                f"Invalid interpolator type: {interp_type}. "
                "Must be 'thrust' or 'power'."
            )

        # Create cache key for this interpolator
        cache_key = f"{prop}_{interp_type}"

        # Return cached interpolator if available
        if cache_key in self._interpolator_cache:
            return self._interpolator_cache[cache_key]

        # Determine file path based on type
        if interp_type == "thrust":
            filepath = self.config.get_thrust_interpolator_path(prop)
        else:  # power
            filepath = self.config.get_power_interpolator_path(prop)

        # Check if file exists
        if not filepath.exists():
            raise FileNotFoundError(
                f"Interpolator file not found: {filepath}\n"
                f"Available propellers: {self.config.list_available_props()[:10]}..."
            )

        # Load interpolator from pickle file
        with open(filepath, "rb") as f:
            interpolator = pickle.load(f)

        # Cache for future use
        self._interpolator_cache[cache_key] = interpolator

        return interpolator

    def _get_interpolator_bounds(self, interpolator: object) -> dict:
        """
        Extract the operating bounds from an interpolator object.

        The interpolator's points attribute contains all the data points
        used to create the interpolation surface. This method extracts
        the min/max values for speed and RPM.

        Parameters:
        ----------
        interpolator : object
            Scipy interpolator object with a 'points' attribute.

        Returns:
        -------
        dict
            Dictionary containing:
            - 'min_speed': Minimum airspeed in m/s
            - 'max_speed': Maximum airspeed in m/s
            - 'min_rpm': Minimum RPM
            - 'max_rpm': Maximum RPM
        """
        # Extract speed and RPM arrays from interpolator points
        # Points are stored as [(speed, RPM), ...] tuples
        speeds = [point[0] for point in interpolator.points]
        rpms = [point[1] for point in interpolator.points]

        return {
            "min_speed": min(speeds),
            "max_speed": max(speeds),
            "min_rpm": min(rpms),
            "max_rpm": max(rpms),
        }

    # -------------------------------------------------------------------------
    # Core Calculation Methods
    # -------------------------------------------------------------------------

    def get_thrust_from_rpm_speed(
        self,
        prop: str,
        v_ms: float,
        rpm: float,
        verbose: bool = False
    ) -> float:
        """
        Calculate propeller thrust for a given RPM and airspeed.

        This method uses bilinear interpolation on the APC performance data
        to estimate thrust at any operating point within the propeller's
        tested envelope.

        Parameters:
        ----------
        prop : str
            Propeller identifier (e.g., "7x7E", "10x5", "12x6E").
            Use config.list_available_props() to see available options.

        v_ms : float
            Forward airspeed in meters per second (m/s).
            Must be within the propeller's tested speed range.

        rpm : float
            Rotational speed in revolutions per minute.
            Must be within the propeller's tested RPM range.

        verbose : bool, optional
            If True, print warnings when parameters are out of bounds.
            Default is False.

        Returns:
        -------
        float
            Thrust in Newtons (N).
            Returns -99.0 if the query point is outside the data envelope.

        Example:
        -------
            analyzer = PropAnalyzer()

            # Calculate thrust at cruise condition
            thrust = analyzer.get_thrust_from_rpm_speed(
                prop="7x7E",
                v_ms=30.0,    # 30 m/s forward speed
                rpm=22500     # 22500 RPM
            )
            print(f"Thrust: {thrust:.2f} N")

        Notes:
        -----
        - The interpolator returns -99.0 for out-of-bounds queries
        - Higher airspeeds generally reduce thrust at a given RPM
        - Maximum thrust occurs at zero airspeed (static thrust)
        """
        # Load the thrust interpolator for this propeller
        interpolator = self._load_interpolator(prop, "thrust")

        # Query the interpolator at the specified operating point
        # Interpolator expects (speed, RPM) as input
        thrust_n = interpolator(v_ms, rpm)

        # Check for out-of-bounds condition
        if thrust_n == self.config.out_of_bounds_value and verbose:
            print(
                f"Warning: Parameters are outside the propeller's tested envelope.\n"
                f"  Prop: {prop}, Speed: {v_ms} m/s, RPM: {rpm}"
            )

        return float(thrust_n)

    def get_power_from_rpm_speed(
        self,
        prop: str,
        v_ms: float,
        rpm: float,
        verbose: bool = False
    ) -> float:
        """
        Calculate propeller power consumption for a given RPM and airspeed.

        This method estimates the mechanical shaft power required to drive
        the propeller at the specified operating conditions.

        Parameters:
        ----------
        prop : str
            Propeller identifier (e.g., "7x7E", "10x5", "12x6E").

        v_ms : float
            Forward airspeed in meters per second (m/s).

        rpm : float
            Rotational speed in revolutions per minute.

        verbose : bool, optional
            If True, print warnings when parameters are out of bounds.
            Default is False.

        Returns:
        -------
        float
            Power in Watts (W).
            Returns -99.0 if the query point is outside the data envelope.

        Example:
        -------
            analyzer = PropAnalyzer()

            # Calculate power requirement
            power = analyzer.get_power_from_rpm_speed(
                prop="7x7E",
                v_ms=30.0,
                rpm=22500
            )
            print(f"Power required: {power:.0f} W")

        Notes:
        -----
        - Power increases approximately with RPM^3
        - Power consumption is relatively independent of airspeed
        - This is the mechanical shaft power, not electrical motor input power
        """
        # Load the power interpolator for this propeller
        interpolator = self._load_interpolator(prop, "power")

        # Query the interpolator at the specified operating point
        power_w = interpolator(v_ms, rpm)

        # Check for out-of-bounds condition
        if power_w == self.config.out_of_bounds_value and verbose:
            print(
                f"Warning: Parameters are outside the propeller's tested envelope.\n"
                f"  Prop: {prop}, Speed: {v_ms} m/s, RPM: {rpm}"
            )

        return float(power_w)

    def get_power_from_thrust_speed(
        self,
        prop: str,
        thrust_required: float,
        v_ms: float,
        return_rpm: bool = False,
        verbose: bool = False
    ) -> Union[float, Tuple[float, int]]:
        """
        Calculate the power required to achieve a target thrust at a given airspeed.

        This is an inverse calculation that finds the RPM needed to produce
        the requested thrust, then calculates the corresponding power. This
        is useful for mission analysis where thrust requirements are known.

        The method uses scipy's root_scalar function to solve for the RPM
        that produces the target thrust.

        Parameters:
        ----------
        prop : str
            Propeller identifier (e.g., "7x7E", "10x5", "12x6E").

        thrust_required : float
            Required thrust in Newtons (N).
            Must be achievable within the propeller's capabilities.

        v_ms : float
            Forward airspeed in meters per second (m/s).

        return_rpm : bool, optional
            If True, also return the calculated RPM value.
            Default is False.

        verbose : bool, optional
            If True, print status messages during calculation.
            Default is False.

        Returns:
        -------
        float or tuple
            If return_rpm is False: Power in Watts (W)
            If return_rpm is True: Tuple of (power_w, rpm)

        Returns None if the thrust requirement exceeds the propeller's limits.

        Example:
        -------
            analyzer = PropAnalyzer()

            # Find power needed for 25N thrust at 30 m/s
            power, rpm = analyzer.get_power_from_thrust_speed(
                prop="7x7E",
                thrust_required=25.0,
                v_ms=30.0,
                return_rpm=True
            )
            print(f"Need {power:.0f} W at {rpm} RPM for 25N thrust")

        Notes:
        -----
        - Uses Brent's method for robust root finding
        - Returns None if thrust exceeds the propeller's maximum capability
        - The calculation may fail if the thrust is below the minimum producible
        """
        # Define the objective function for root finding
        # We want to find RPM where thrust(RPM) - thrust_required = 0
        def thrust_residual(rpm: float, interp: object, t_req: float, v: float) -> float:
            """
            Calculate the difference between produced and required thrust.

            Parameters:
            ----------
            rpm : float
                Candidate RPM value.
            interp : object
                Thrust interpolator.
            t_req : float
                Required thrust in Newtons.
            v : float
                Airspeed in m/s.

            Returns:
            -------
            float
                Thrust residual (positive if producing more than required).
            """
            thrust_n = interp(v, rpm)
            return thrust_n - t_req

        # Load the thrust interpolator
        thrust_interp = self._load_interpolator(prop, "thrust")

        # Get RPM bounds from the interpolator
        bounds = self._get_interpolator_bounds(thrust_interp)
        min_rpm = bounds["min_rpm"]
        max_rpm = bounds["max_rpm"]

        # Check if the required thrust is achievable at maximum RPM
        max_thrust = thrust_interp(v_ms, max_rpm)

        if thrust_required > max_thrust:
            print(
                f"Thrust request ({thrust_required:.1f} N) exceeds propeller limits!\n"
                f"Maximum available thrust at {v_ms} m/s: {max_thrust:.1f} N"
            )
            return None

        # Use scipy's root_scalar to find the required RPM
        # We use the bracket method (Brent's method) for robust convergence
        try:
            result = optimize.root_scalar(
                thrust_residual,
                args=(thrust_interp, thrust_required, v_ms),
                bracket=(min_rpm, max_rpm),
                rtol=self.config.root_finding_tolerance
            )

            # Extract the RPM solution
            rpm_solution = int(result.root)

            # Calculate the corresponding power
            power_w = self.get_power_from_rpm_speed(
                prop, v_ms, rpm_solution, verbose=verbose
            )

            # Return based on user preference
            if return_rpm:
                return power_w, rpm_solution
            else:
                return power_w

        except ValueError as e:
            # Root finding failed - likely thrust not achievable
            if verbose:
                print(f"Could not find RPM for requested thrust: {e}")
            return None

    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------

    def get_prop_operating_envelope(self, prop: str) -> dict:
        """
        Get the operating envelope (bounds) for a propeller.

        Returns the minimum and maximum values for airspeed and RPM
        that are covered by the interpolator data.

        Parameters:
        ----------
        prop : str
            Propeller identifier.

        Returns:
        -------
        dict
            Dictionary containing speed and RPM bounds.

        Example:
        -------
            analyzer = PropAnalyzer()
            envelope = analyzer.get_prop_operating_envelope("7x7E")
            print(f"Speed range: {envelope['min_speed']}-{envelope['max_speed']} m/s")
            print(f"RPM range: {envelope['min_rpm']}-{envelope['max_rpm']}")
        """
        interpolator = self._load_interpolator(prop, "thrust")
        return self._get_interpolator_bounds(interpolator)

    def get_max_thrust(self, prop: str, v_ms: float) -> float:
        """
        Get the maximum thrust available at a given airspeed.

        This is the thrust produced at the propeller's maximum rated RPM.

        Parameters:
        ----------
        prop : str
            Propeller identifier.

        v_ms : float
            Airspeed in meters per second.

        Returns:
        -------
        float
            Maximum thrust in Newtons.
        """
        envelope = self.get_prop_operating_envelope(prop)
        return self.get_thrust_from_rpm_speed(prop, v_ms, envelope["max_rpm"])

    def get_efficiency(self, prop: str, v_ms: float, rpm: float) -> float:
        """
        Calculate propeller efficiency at a given operating point.

        Efficiency is defined as the ratio of useful power (thrust * velocity)
        to mechanical input power.

        Parameters:
        ----------
        prop : str
            Propeller identifier.

        v_ms : float
            Airspeed in meters per second.

        rpm : float
            Rotational speed in RPM.

        Returns:
        -------
        float
            Propeller efficiency (0-1 range, or >1 at very low speeds).
            Returns 0 at zero airspeed (by convention, as thrust*0=0).

        Notes:
        -----
        - Efficiency approaches zero at very low and very high airspeeds
        - Maximum efficiency typically occurs at a specific advance ratio
        - At zero airspeed, efficiency is zero by definition
        """
        # Handle zero speed case
        if v_ms == 0:
            return 0.0

        thrust = self.get_thrust_from_rpm_speed(prop, v_ms, rpm)
        power = self.get_power_from_rpm_speed(prop, v_ms, rpm)

        # Check for valid values
        if power <= 0 or thrust < 0:
            return 0.0

        # Efficiency = Useful power / Input power = (Thrust * Velocity) / Power
        efficiency = (thrust * v_ms) / power

        return efficiency

    def list_available_propellers(self) -> list:
        """
        Get a list of all available propeller models.

        Returns:
        -------
        list
            Sorted list of propeller identifiers.

        Example:
        -------
            analyzer = PropAnalyzer()
            props = analyzer.list_available_propellers()
            print(f"Found {len(props)} propellers")
            print(f"Examples: {props[:5]}")
        """
        return self.config.list_available_props()

    def clear_cache(self):
        """
        Clear the interpolator cache.

        Use this method if you need to free memory or reload interpolators
        from disk (e.g., after updating interpolator files).
        """
        self._interpolator_cache.clear()
