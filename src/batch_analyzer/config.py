"""
Batch Analyzer Configuration Module
====================================

This module contains configuration dataclasses and constants for the
batch analyzer. It defines the structure for batch analysis parameters
and result storage.

Classes:
--------
- BatchConfig: Configuration for a batch analysis run
- BatchResult: Result from a single motor/prop/speed combination
- BatchLimits: Safety limits for batch processing

Constants:
----------
- DEFAULT_LIMITS: Default safety limits for batch processing
- MAX_PERMUTATIONS: Hard limit on number of combinations
"""

from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Callable
import os


# =============================================================================
# Safety Limits
# =============================================================================

@dataclass
class BatchLimits:
    """
    Safety limits for batch processing.

    These limits prevent runaway calculations and memory issues.

    Attributes:
    ----------
    max_permutations : int
        Maximum number of combinations to test (hard limit)

    warning_permutations : int
        Number of combinations that triggers a warning

    max_workers : int
        Maximum number of concurrent workers

    chunk_size : int
        Number of calculations per chunk for progress updates

    update_interval : float
        Minimum seconds between progress updates

    timeout_per_calc : float
        Timeout in seconds for each individual calculation
    """
    max_permutations: int = 500_000
    warning_permutations: int = 50_000
    max_workers: int = field(default_factory=lambda: min(os.cpu_count() or 4, 8))
    chunk_size: int = 100
    update_interval: float = 0.1
    timeout_per_calc: float = 5.0


# Default limits instance
DEFAULT_LIMITS = BatchLimits()


# =============================================================================
# Result Dataclass
# =============================================================================

@dataclass
class BatchResult:
    """
    Result from a single batch calculation.

    Stores all relevant performance data for a motor/prop/speed combination.

    Attributes:
    ----------
    motor_id : str
        Motor identifier

    prop_id : str
        Propeller identifier

    airspeed : float
        Flight speed (m/s)

    throttle : float
        Required throttle (0-100%)

    motor_current : float
        Motor current (A)

    battery_power : float
        Battery power (W)

    system_efficiency : float
        Overall system efficiency (0-1)

    motor_efficiency : float
        Motor efficiency (0-1)

    prop_efficiency : float
        Propeller efficiency (0-1)

    prop_rpm : float
        Propeller RPM

    drag : float
        Total drag (N)

    valid : bool
        Whether calculation was successful

    error_message : str
        Error description if not valid
    """
    motor_id: str = ""
    prop_id: str = ""
    airspeed: float = 0.0

    # Performance metrics
    throttle: float = 0.0
    motor_current: float = 0.0
    battery_power: float = 0.0
    system_efficiency: float = 0.0
    motor_efficiency: float = 0.0
    prop_efficiency: float = 0.0
    prop_rpm: float = 0.0
    drag: float = 0.0

    # Status
    valid: bool = False
    error_message: str = ""

    def to_dict(self) -> dict:
        """Convert result to dictionary for export."""
        return {
            "motor_id": self.motor_id,
            "prop_id": self.prop_id,
            "airspeed_ms": self.airspeed,
            "airspeed_mph": self.airspeed * 2.237,
            "throttle_pct": self.throttle,
            "current_a": self.motor_current,
            "power_w": self.battery_power,
            "system_eff_pct": self.system_efficiency * 100,
            "motor_eff_pct": self.motor_efficiency * 100,
            "prop_eff_pct": self.prop_efficiency * 100,
            "rpm": self.prop_rpm,
            "drag_n": self.drag,
            "valid": self.valid,
            "error": self.error_message
        }


# =============================================================================
# Configuration Dataclass
# =============================================================================

@dataclass
class BatchConfig:
    """
    Configuration for a batch analysis run.

    Specifies the airframe, motor/prop filters, speed range, and
    processing parameters.

    Attributes:
    ----------
    # Airframe Configuration
    wing_area : float
        Wing area (m^2)

    wingspan : float
        Wingspan (m)

    weight : float
        Aircraft weight (kg)

    cd0 : float
        Parasitic drag coefficient

    oswald_efficiency : float
        Oswald efficiency factor (0.7-0.85 typical)

    # Battery
    voltage : float
        Battery voltage (V)

    # Motor Filters
    motor_categories : List[str]
        Categories to include (empty = all)

    motor_ids : List[str]
        Specific motor IDs to test (empty = use categories)

    # Prop Filters
    prop_diameter_min : float
        Minimum prop diameter (inches)

    prop_diameter_max : float
        Maximum prop diameter (inches)

    prop_pitch_min : float
        Minimum prop pitch (inches)

    prop_pitch_max : float
        Maximum prop pitch (inches)

    # Speed Range
    speed_min : float
        Minimum airspeed (m/s)

    speed_max : float
        Maximum airspeed (m/s)

    speed_step : float
        Speed step size (m/s)

    # Processing
    winding_temp : float
        Motor winding temperature (C)

    altitude : float
        Flight altitude (m)

    limits : BatchLimits
        Safety limits for processing
    """

    # -------------------------------------------------------------------------
    # Airframe Configuration
    # -------------------------------------------------------------------------
    wing_area: float = 0.15  # m^2
    wingspan: float = 1.0    # m
    weight: float = 1.0      # kg
    cd0: float = 0.025       # parasitic drag coefficient
    oswald_efficiency: float = 0.8  # Oswald efficiency

    # -------------------------------------------------------------------------
    # Battery
    # -------------------------------------------------------------------------
    voltage: float = 14.8  # V (4S default)

    # -------------------------------------------------------------------------
    # Motor Filters
    # -------------------------------------------------------------------------
    motor_categories: List[str] = field(default_factory=list)
    motor_ids: List[str] = field(default_factory=list)

    # -------------------------------------------------------------------------
    # Prop Filters (in inches)
    # -------------------------------------------------------------------------
    prop_diameter_min: float = 6.0
    prop_diameter_max: float = 12.0
    prop_pitch_min: float = 3.0
    prop_pitch_max: float = 8.0

    # -------------------------------------------------------------------------
    # Speed Range (m/s)
    # -------------------------------------------------------------------------
    speed_min: float = 10.0
    speed_max: float = 30.0
    speed_step: float = 2.0

    # -------------------------------------------------------------------------
    # Flight Conditions
    # -------------------------------------------------------------------------
    winding_temp: float = 80.0  # C
    altitude: float = 0.0       # m

    # -------------------------------------------------------------------------
    # Processing Limits
    # -------------------------------------------------------------------------
    limits: BatchLimits = field(default_factory=BatchLimits)

    def get_speed_points(self) -> List[float]:
        """Get list of speed points to test."""
        speeds = []
        speed = self.speed_min
        while speed <= self.speed_max:
            speeds.append(speed)
            speed += self.speed_step
        return speeds

    def validate(self) -> Tuple[bool, str]:
        """
        Validate configuration parameters.

        Returns:
        -------
        Tuple[bool, str]
            (is_valid, error_message)
        """
        errors = []

        # Airframe validation
        if self.wing_area <= 0:
            errors.append("Wing area must be positive")
        if self.wingspan <= 0:
            errors.append("Wingspan must be positive")
        if self.weight <= 0:
            errors.append("Weight must be positive")
        if not 0 < self.cd0 < 1:
            errors.append("Cd0 must be between 0 and 1")
        if not 0 < self.oswald_efficiency <= 1:
            errors.append("Oswald efficiency must be between 0 and 1")

        # Battery validation
        if self.voltage <= 0:
            errors.append("Voltage must be positive")

        # Prop range validation
        if self.prop_diameter_min >= self.prop_diameter_max:
            errors.append("Prop diameter min must be less than max")
        if self.prop_pitch_min >= self.prop_pitch_max:
            errors.append("Prop pitch min must be less than max")
        if self.prop_diameter_min < 3 or self.prop_diameter_max > 30:
            errors.append("Prop diameter range seems unrealistic (3-30 inches)")

        # Speed validation
        if self.speed_min >= self.speed_max:
            errors.append("Speed min must be less than max")
        if self.speed_step <= 0:
            errors.append("Speed step must be positive")
        if self.speed_min < 1:
            errors.append("Minimum speed too low (< 1 m/s)")
        if self.speed_max > 100:
            errors.append("Maximum speed too high (> 100 m/s)")

        if errors:
            return False, "; ".join(errors)
        return True, ""
