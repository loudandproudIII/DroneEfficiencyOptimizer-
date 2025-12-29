"""
Drag Model Module
=================

This module provides drag calculation methods for various aircraft types
including multirotors, fixed-wing aircraft, and hybrid configurations.

Drag Calculation Methods:
------------------------
1. Raw Drag Value: Direct input in Newtons
2. Parasitic Drag: D = 0.5 × ρ × V² × Cd × A
3. Fixed-Wing Total: Parasitic + Induced drag
4. Flat Plate Equivalent: D = 0.5 × ρ × V² × f

Theory Background:
-----------------

**Parasitic Drag (Form + Friction):**
    D_parasitic = 0.5 × ρ × V² × S × Cd0

    Where:
    - ρ = air density (kg/m³)
    - V = velocity (m/s)
    - S = reference area (m²)
    - Cd0 = zero-lift drag coefficient

**Induced Drag (Lift-dependent):**
    D_induced = 0.5 × ρ × V² × S × Cdi

    Where:
    Cdi = CL² / (π × AR × e)
    CL = 2W / (ρ × V² × S)  (for level flight)
    AR = b² / S  (aspect ratio)
    e = Oswald efficiency factor (0.7-0.9)

**Total Drag:**
    D_total = D_parasitic + D_induced

For multirotors in forward flight, induced drag from lift is typically
small compared to parasitic drag from the frame.

Classes:
--------
- DragModel: Configurable drag calculator

Usage:
------
    from src.flight_analyzer.drag_model import DragModel

    # Simple coefficient-based drag
    model = DragModel(method="coefficient", cd=0.5, reference_area=0.02)
    drag = model.calculate_drag(velocity=15.0, altitude=0)

    # Fixed-wing with induced drag
    model = DragModel(
        method="fixed_wing",
        cd0=0.025,
        wing_area=0.8,
        wingspan=2.0,
        weight=25.0,
        oswald_efficiency=0.85
    )
    drag = model.calculate_drag(velocity=20.0)
"""

import math
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Literal
from enum import Enum

from .config import FlightAnalyzerConfig, DEFAULT_CONFIG, AIR_DENSITY_SEA_LEVEL


class DragMethod(Enum):
    """Enumeration of available drag calculation methods."""
    RAW = "raw"                    # Direct drag value input
    COEFFICIENT = "coefficient"    # Cd × Area method
    FLAT_PLATE = "flat_plate"      # Flat plate equivalent area
    FIXED_WING = "fixed_wing"      # Full fixed-wing model with induced drag
    MULTIROTOR = "multirotor"      # Multirotor-specific model


@dataclass
class DragModel:
    """
    Configurable drag calculation model.

    Supports multiple calculation methods from simple coefficient-based
    to full fixed-wing with induced drag components.

    Attributes:
    ----------
    method : str
        Calculation method: "raw", "coefficient", "flat_plate",
        "fixed_wing", or "multirotor"

    # For RAW method:
    raw_drag : float
        Direct drag value in Newtons (only used with method="raw")

    # For COEFFICIENT method:
    cd : float
        Drag coefficient (dimensionless)

    reference_area : float
        Reference area for Cd (m²)
        - For multirotors: typically frontal area
        - For fixed-wing: typically wing area

    # For FLAT_PLATE method:
    flat_plate_area : float
        Equivalent flat plate area (m²)
        f = Cd × S (common shorthand)

    # For FIXED_WING method (adds induced drag):
    cd0 : float
        Zero-lift (parasitic) drag coefficient

    wing_area : float
        Wing planform area (m²)

    wingspan : float
        Wing span (m)

    weight : float
        Aircraft weight (N) - needed for lift/induced drag

    oswald_efficiency : float
        Oswald span efficiency factor (0.7-0.9 typical)

    # For MULTIROTOR method:
    frontal_area : float
        Frontal area of multirotor frame (m²)

    frame_cd : float
        Frame drag coefficient (typically 0.5-1.5)

    Example:
    -------
        # Multirotor
        model = DragModel(
            method="multirotor",
            frontal_area=0.02,
            frame_cd=1.0
        )

        # Fixed-wing
        model = DragModel(
            method="fixed_wing",
            cd0=0.025,
            wing_area=0.5,
            wingspan=1.8,
            weight=30.0,
            oswald_efficiency=0.85
        )

        drag = model.calculate_drag(velocity=20.0, altitude=0)
    """

    # Calculation method
    method: str = "coefficient"

    # -------------------------------------------------------------------------
    # Raw Method Parameters
    # -------------------------------------------------------------------------
    raw_drag: float = 0.0

    # -------------------------------------------------------------------------
    # Coefficient Method Parameters
    # -------------------------------------------------------------------------
    cd: float = 0.5
    reference_area: float = 0.01  # m²

    # -------------------------------------------------------------------------
    # Flat Plate Method Parameters
    # -------------------------------------------------------------------------
    flat_plate_area: float = 0.005  # m² (Cd × S equivalent)

    # -------------------------------------------------------------------------
    # Fixed-Wing Method Parameters
    # -------------------------------------------------------------------------
    cd0: float = 0.025          # Zero-lift drag coefficient
    wing_area: float = 0.5      # m²
    wingspan: float = 1.5       # m
    weight: float = 20.0        # N (aircraft weight)
    oswald_efficiency: float = 0.8

    # -------------------------------------------------------------------------
    # Multirotor Method Parameters
    # -------------------------------------------------------------------------
    frontal_area: float = 0.02  # m²
    frame_cd: float = 1.0       # Typical multirotor frame Cd

    # -------------------------------------------------------------------------
    # Configuration
    # -------------------------------------------------------------------------
    config: FlightAnalyzerConfig = field(default_factory=FlightAnalyzerConfig)

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------

    @property
    def aspect_ratio(self) -> float:
        """Calculate wing aspect ratio (AR = b²/S)."""
        if self.wing_area > 0:
            return self.wingspan ** 2 / self.wing_area
        return 0.0

    # -------------------------------------------------------------------------
    # Main Calculation Method
    # -------------------------------------------------------------------------

    def calculate_drag(
        self,
        velocity: float,
        altitude: float = 0.0,
        temperature_offset: float = 0.0,
        air_density: Optional[float] = None
    ) -> float:
        """
        Calculate aerodynamic drag at given flight conditions.

        Parameters:
        ----------
        velocity : float
            Airspeed (m/s)

        altitude : float, optional
            Altitude above sea level (m). Default 0.

        temperature_offset : float, optional
            Temperature deviation from ISA (°C). Default 0.

        air_density : float, optional
            Override air density (kg/m³). If provided, altitude
            and temperature_offset are ignored.

        Returns:
        -------
        float
            Drag force in Newtons (N)

        Raises:
        ------
        ValueError
            If an unknown method is specified.
        """
        # Get air density
        if air_density is not None:
            rho = air_density
        else:
            rho = self.config.get_air_density(altitude, temperature_offset)

        # Dynamic pressure
        q = 0.5 * rho * velocity ** 2

        # Calculate based on method
        method = self.method.lower()

        if method == "raw":
            return self.raw_drag

        elif method == "coefficient":
            return self._calc_coefficient_drag(q)

        elif method == "flat_plate":
            return self._calc_flat_plate_drag(q)

        elif method == "fixed_wing":
            return self._calc_fixed_wing_drag(q, rho, velocity)

        elif method == "multirotor":
            return self._calc_multirotor_drag(q)

        else:
            raise ValueError(
                f"Unknown drag method: {self.method}. "
                f"Use: raw, coefficient, flat_plate, fixed_wing, or multirotor"
            )

    # -------------------------------------------------------------------------
    # Method-Specific Calculations
    # -------------------------------------------------------------------------

    def _calc_coefficient_drag(self, q: float) -> float:
        """
        Calculate drag using simple coefficient method.

        D = q × Cd × A = 0.5 × ρ × V² × Cd × A

        Parameters:
        ----------
        q : float
            Dynamic pressure (Pa)

        Returns:
        -------
        float
            Drag force (N)
        """
        return q * self.cd * self.reference_area

    def _calc_flat_plate_drag(self, q: float) -> float:
        """
        Calculate drag using flat plate equivalent area.

        D = q × f

        Where f = Cd × S (flat plate area)

        Parameters:
        ----------
        q : float
            Dynamic pressure (Pa)

        Returns:
        -------
        float
            Drag force (N)
        """
        return q * self.flat_plate_area

    def _calc_multirotor_drag(self, q: float) -> float:
        """
        Calculate multirotor frame drag.

        Uses frontal area and frame drag coefficient.
        D = q × Cd_frame × A_frontal

        Parameters:
        ----------
        q : float
            Dynamic pressure (Pa)

        Returns:
        -------
        float
            Drag force (N)
        """
        return q * self.frame_cd * self.frontal_area

    def _calc_fixed_wing_drag(
        self,
        q: float,
        rho: float,
        velocity: float
    ) -> float:
        """
        Calculate total fixed-wing drag including induced drag.

        D_total = D_parasitic + D_induced

        Where:
        D_parasitic = q × S × Cd0
        D_induced = q × S × (CL² / (π × AR × e))

        For level flight: L = W, so CL = W / (q × S)

        Parameters:
        ----------
        q : float
            Dynamic pressure (Pa)

        rho : float
            Air density (kg/m³)

        velocity : float
            Airspeed (m/s)

        Returns:
        -------
        float
            Total drag force (N)
        """
        # Parasitic drag
        d_parasitic = q * self.wing_area * self.cd0

        # Calculate lift coefficient for level flight (L = W)
        if q > 0 and self.wing_area > 0:
            cl = self.weight / (q * self.wing_area)
        else:
            cl = 0.0

        # Induced drag coefficient
        ar = self.aspect_ratio
        if ar > 0 and self.oswald_efficiency > 0:
            cdi = cl ** 2 / (math.pi * ar * self.oswald_efficiency)
        else:
            cdi = 0.0

        # Induced drag
        d_induced = q * self.wing_area * cdi

        return d_parasitic + d_induced

    # -------------------------------------------------------------------------
    # Analysis Methods
    # -------------------------------------------------------------------------

    def get_drag_breakdown(
        self,
        velocity: float,
        altitude: float = 0.0
    ) -> Dict[str, float]:
        """
        Get detailed breakdown of drag components.

        Parameters:
        ----------
        velocity : float
            Airspeed (m/s)

        altitude : float
            Altitude (m)

        Returns:
        -------
        dict
            Dictionary with drag components:
            - total_drag: Total drag (N)
            - parasitic_drag: Form + friction drag (N)
            - induced_drag: Lift-dependent drag (N)
            - dynamic_pressure: q (Pa)
            - air_density: ρ (kg/m³)
        """
        rho = self.config.get_air_density(altitude)
        q = 0.5 * rho * velocity ** 2

        total_drag = self.calculate_drag(velocity, altitude)

        # Calculate components based on method
        if self.method.lower() == "fixed_wing":
            d_parasitic = q * self.wing_area * self.cd0
            d_induced = total_drag - d_parasitic
        else:
            d_parasitic = total_drag
            d_induced = 0.0

        return {
            "total_drag": total_drag,
            "parasitic_drag": d_parasitic,
            "induced_drag": d_induced,
            "dynamic_pressure": q,
            "air_density": rho,
            "velocity": velocity,
            "altitude": altitude,
        }

    def get_drag_polar(
        self,
        velocity_range: tuple = (5.0, 40.0),
        num_points: int = 50,
        altitude: float = 0.0
    ) -> Dict[str, list]:
        """
        Generate drag vs velocity data for plotting.

        Parameters:
        ----------
        velocity_range : tuple
            (min_velocity, max_velocity) in m/s

        num_points : int
            Number of data points

        altitude : float
            Altitude for calculations

        Returns:
        -------
        dict
            Dictionary with:
            - velocities: List of velocities (m/s)
            - drags: List of drag values (N)
            - powers: List of power values (W) (D × V)
        """
        import numpy as np

        velocities = np.linspace(velocity_range[0], velocity_range[1], num_points)
        drags = []
        powers = []

        for v in velocities:
            d = self.calculate_drag(v, altitude)
            drags.append(d)
            powers.append(d * v)  # Power = Drag × Velocity

        return {
            "velocities": list(velocities),
            "drags": drags,
            "powers": powers,
        }

    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------

    def estimate_frontal_area_from_frame(
        self,
        arm_count: int = 4,
        arm_length: float = 0.2,
        arm_width: float = 0.02,
        body_width: float = 0.1,
        body_height: float = 0.05
    ) -> float:
        """
        Estimate multirotor frontal area from frame dimensions.

        Rough estimate for multirotor frames.

        Parameters:
        ----------
        arm_count : int
            Number of arms

        arm_length : float
            Length of each arm (m)

        arm_width : float
            Width/diameter of arms (m)

        body_width : float
            Center body width (m)

        body_height : float
            Center body height (m)

        Returns:
        -------
        float
            Estimated frontal area (m²)
        """
        # Arms visible from front (assume half are visible)
        arm_area = (arm_count / 2) * arm_length * arm_width

        # Body
        body_area = body_width * body_height

        return arm_area + body_area

    @staticmethod
    def estimate_cd_from_reynolds(reynolds: float) -> float:
        """
        Estimate drag coefficient based on Reynolds number.

        Rough approximation for streamlined bodies.

        Parameters:
        ----------
        reynolds : float
            Reynolds number

        Returns:
        -------
        float
            Estimated Cd
        """
        if reynolds < 1e4:
            return 1.0  # Low Re, laminar separation
        elif reynolds < 1e5:
            return 0.5  # Transitional
        elif reynolds < 1e6:
            return 0.3  # Turbulent
        else:
            return 0.2  # High Re, turbulent

    def copy_with(self, **kwargs) -> 'DragModel':
        """
        Create a copy of this model with modified parameters.

        Parameters:
        ----------
        **kwargs
            Parameters to override

        Returns:
        -------
        DragModel
            New model with updated parameters
        """
        from dataclasses import asdict

        params = asdict(self)
        params.update(kwargs)

        # Remove config from dict (can't serialize cleanly)
        params.pop('config', None)

        return DragModel(**params, config=self.config)
