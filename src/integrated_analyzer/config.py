"""
Integrated Analyzer Configuration Module
=========================================

Configuration dataclasses and result structures for the integrated
motor/prop/battery batch analyzer.

This module defines:
- BatteryIterationConfig: Battery pack iteration parameters
- IntegratedConfig: Complete analysis configuration
- ThermalEvaluation: Thermal status at an operating point
- SpeedPointResult: Results at a single speed point
- IntegratedResult: Complete result for one combination
- IntegratedBatchResult: Complete batch analysis results

Classes:
--------
- BatchLimits: Safety limits (imported from batch_analyzer)
- BatteryIterationConfig: Battery iteration settings
- IntegratedConfig: Full configuration
- ThermalEvaluation: Thermal evaluation result
- SpeedPointResult: Single speed point result
- IntegratedResult: Single combination result
- IntegratedBatchResult: Complete batch results
"""

from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict, Any
import os


# =============================================================================
# Safety Limits (Compatible with batch_analyzer)
# =============================================================================

@dataclass
class BatchLimits:
    """
    Safety limits for batch processing.

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
    max_permutations: int = 10_000_000  # No practical limit
    warning_permutations: int = 20_000
    max_workers: int = field(default_factory=lambda: min(os.cpu_count() or 4, 8))
    chunk_size: int = 100
    update_interval: float = 0.1
    timeout_per_calc: float = 10.0  # Higher timeout for battery iterations


DEFAULT_LIMITS = BatchLimits()


# =============================================================================
# Battery Iteration Configuration
# =============================================================================

@dataclass
class BatteryIterationConfig:
    """
    Configuration for battery pack iteration.

    Specifies which cell types, series/parallel counts, and thermal
    environments to test.

    Attributes:
    ----------
    cell_types : List[str]
        Cell names from CELL_DATABASE to test

    series_values : List[int]
        Specific series counts to test, e.g., [4, 5, 6]

    parallel_values : List[int]
        Specific parallel counts to test (for all_combinations mode)

    series_parallel_map : Dict[int, List[int]]
        Per-series parallel values, e.g., {4: [1, 2], 6: [2, 3, 4]}
        If provided, overrides parallel_values

    series_range : Tuple[int, int]
        DEPRECATED: Use series_values instead
        (min_s, max_s) series count range, e.g., (4, 6) for 4S-6S

    parallel_range : Tuple[int, int]
        DEPRECATED: Use parallel_values instead
        (min_p, max_p) parallel count range, e.g., (1, 4) for 1P-4P

    thermal_environments : List[str]
        Thermal environment names from THERMAL_RESISTANCE dict

    ambient_temp_c : float
        Ambient temperature for thermal calculations (C)

    max_cell_temp_c : float
        Maximum allowed cell temperature (C)

    soc_for_analysis : float
        State of charge to use for analysis (0-100%)
    """
    cell_types: List[str] = field(default_factory=lambda: ["Molicel P45B"])
    series_values: Optional[List[int]] = None
    parallel_values: Optional[List[int]] = None
    series_parallel_map: Optional[Dict[int, List[int]]] = None
    # Deprecated range-based config (for backwards compatibility)
    series_range: Tuple[int, int] = (4, 6)
    parallel_range: Tuple[int, int] = (1, 2)
    thermal_environments: List[str] = field(default_factory=lambda: ["drone_in_flight"])
    ambient_temp_c: float = 25.0
    max_cell_temp_c: float = 60.0
    soc_for_analysis: float = 80.0

    def get_series_values(self) -> List[int]:
        """Get list of series counts to test."""
        if self.series_values is not None:
            return sorted(self.series_values)
        return list(range(self.series_range[0], self.series_range[1] + 1))

    def get_parallel_values(self, series: Optional[int] = None) -> List[int]:
        """Get list of parallel counts to test.

        If series is provided and series_parallel_map exists, returns
        the parallel values for that specific series.
        """
        if series is not None and self.series_parallel_map:
            return sorted(self.series_parallel_map.get(series, []))
        if self.parallel_values is not None:
            return sorted(self.parallel_values)
        return list(range(self.parallel_range[0], self.parallel_range[1] + 1))

    def get_series_parallel_combinations(self) -> List[Tuple[int, int]]:
        """Get all (series, parallel) combinations to test."""
        combinations = []
        for s in self.get_series_values():
            for p in self.get_parallel_values(s):
                combinations.append((s, p))
        return combinations

    def get_permutation_count(self) -> int:
        """Get number of battery configurations to test."""
        return (
            len(self.cell_types) *
            len(self.get_series_parallel_combinations()) *
            len(self.thermal_environments)
        )

    def validate(self) -> Tuple[bool, str]:
        """Validate battery iteration configuration."""
        errors = []

        if not self.cell_types:
            errors.append("At least one cell type must be selected")

        # Validate series
        series = self.get_series_values()
        if not series:
            errors.append("At least one series value must be selected")
        elif min(series) < 1 or max(series) > 14:
            errors.append("Series values must be 1-14")

        # Validate parallel
        sp_combos = self.get_series_parallel_combinations()
        if not sp_combos:
            errors.append("At least one series/parallel combination must be selected")
        else:
            all_parallel = set(p for _, p in sp_combos)
            if min(all_parallel) < 1 or max(all_parallel) > 12:
                errors.append("Parallel values must be 1-12")

        if not self.thermal_environments:
            errors.append("At least one thermal environment must be selected")
        if not 0 <= self.soc_for_analysis <= 100:
            errors.append("SOC must be 0-100%")
        if self.max_cell_temp_c <= self.ambient_temp_c:
            errors.append("Max cell temp must be > ambient temp")

        if errors:
            return False, "; ".join(errors)
        return True, ""


# =============================================================================
# Integrated Configuration
# =============================================================================

@dataclass
class IntegratedConfig:
    """
    Complete configuration for integrated analysis.

    Combines airframe parameters, motor/prop filters, battery iteration,
    and analysis options.

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
        Oswald efficiency factor

    # Motor Filters
    motor_categories : List[str]
        Motor categories to include
    motor_ids : List[str]
        Specific motor IDs to test

    # Prop Filters
    prop_diameter_range : Tuple[float, float]
        (min, max) diameter in inches
    prop_pitch_range : Tuple[float, float]
        (min, max) pitch in inches

    # Battery Iteration
    battery_config : BatteryIterationConfig
        Battery iteration parameters

    # Speed Evaluation
    cruise_speed : float
        Target cruise speed (m/s)
    evaluate_max_speed : bool
        Whether to find max achievable speed
    speed_sweep_enabled : bool
        Whether to perform full speed sweep
    speed_sweep_points : int
        Number of points in speed sweep

    # Flight Conditions
    winding_temp : float
        Motor winding temperature (C)
    altitude : float
        Flight altitude (m)

    # Processing
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
    # Motor Filters
    # -------------------------------------------------------------------------
    motor_categories: List[str] = field(default_factory=list)
    motor_ids: List[str] = field(default_factory=list)

    # -------------------------------------------------------------------------
    # Prop Filters (in inches)
    # -------------------------------------------------------------------------
    prop_diameter_range: Tuple[float, float] = (6.0, 12.0)
    prop_pitch_range: Tuple[float, float] = (3.0, 8.0)

    # -------------------------------------------------------------------------
    # Battery Iteration
    # -------------------------------------------------------------------------
    battery_config: BatteryIterationConfig = field(default_factory=BatteryIterationConfig)

    # -------------------------------------------------------------------------
    # Speed Evaluation
    # -------------------------------------------------------------------------
    cruise_speed: float = 20.0  # m/s (used if cruise_speed_range is None)
    cruise_speed_range: Optional[Tuple[float, float]] = None  # (min, max) m/s
    cruise_speed_step: float = 2.0  # m/s step between cruise speeds
    evaluate_max_speed: bool = True
    speed_sweep_enabled: bool = False
    speed_sweep_points: int = 10

    # -------------------------------------------------------------------------
    # Flight Conditions
    # -------------------------------------------------------------------------
    winding_temp: float = 80.0  # C
    altitude: float = 0.0       # m

    # -------------------------------------------------------------------------
    # Processing Limits
    # -------------------------------------------------------------------------
    limits: BatchLimits = field(default_factory=BatchLimits)

    def get_cruise_speeds(self) -> List[float]:
        """Get list of cruise speeds to evaluate."""
        if self.cruise_speed_range is None:
            return [self.cruise_speed]

        min_speed, max_speed = self.cruise_speed_range
        speeds = []
        current = min_speed
        while current <= max_speed + 0.001:  # Small epsilon for float comparison
            speeds.append(round(current, 1))
            current += self.cruise_speed_step
        return speeds

    def validate(self) -> Tuple[bool, str]:
        """Validate all configuration parameters."""
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

        # Prop range validation
        if self.prop_diameter_range[0] >= self.prop_diameter_range[1]:
            errors.append("Prop diameter min must be less than max")
        if self.prop_pitch_range[0] >= self.prop_pitch_range[1]:
            errors.append("Prop pitch min must be less than max")

        # Speed validation
        if self.cruise_speed < 1 or self.cruise_speed > 100:
            errors.append("Cruise speed should be 1-100 m/s")

        # Battery config validation
        batt_valid, batt_errors = self.battery_config.validate()
        if not batt_valid:
            errors.append(f"Battery config: {batt_errors}")

        if errors:
            return False, "; ".join(errors)
        return True, ""


# =============================================================================
# Thermal Evaluation Result
# =============================================================================

@dataclass
class ThermalEvaluation:
    """
    Thermal evaluation result at an operating point.

    Contains steady-state temperature, heat generation, thermal margin,
    and limit status.

    Attributes:
    ----------
    current_a : float
        Operating current (A)

    steady_state_temp_c : float
        Calculated steady-state cell temperature (C)

    heat_generation_w : float
        Heat generation rate (W)

    thermal_margin_c : float
        Temperature margin below max (max_temp - steady_temp)

    within_limits : bool
        Whether operating within thermal limits

    limiting_factor : str
        What limits current: "thermal", "rating", or "voltage"

    max_continuous_current_a : float
        Maximum allowable continuous current (A)
    """
    current_a: float = 0.0
    steady_state_temp_c: float = 25.0
    heat_generation_w: float = 0.0
    thermal_margin_c: float = 35.0
    within_limits: bool = True
    limiting_factor: str = "none"
    max_continuous_current_a: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for export."""
        return {
            "current_a": self.current_a,
            "steady_state_temp_c": self.steady_state_temp_c,
            "heat_generation_w": self.heat_generation_w,
            "thermal_margin_c": self.thermal_margin_c,
            "within_limits": self.within_limits,
            "limiting_factor": self.limiting_factor,
            "max_continuous_current_a": self.max_continuous_current_a,
        }


# =============================================================================
# Speed Point Result
# =============================================================================

@dataclass
class SpeedPointResult:
    """
    Result at a single speed point.

    Contains flight performance, electrical parameters, and thermal status.

    Attributes:
    ----------
    airspeed : float
        Flight speed (m/s)

    throttle : float
        Required throttle (0-100%)

    motor_current : float
        Motor current (A)

    battery_current : float
        Total battery current (A)

    battery_power : float
        Total battery power (W)

    loaded_voltage : float
        Battery voltage under load (V)

    system_efficiency : float
        Overall system efficiency (0-1)

    motor_efficiency : float
        Motor efficiency (0-1)

    prop_efficiency : float
        Propeller efficiency (0-1)

    prop_rpm : float
        Propeller RPM

    drag : float
        Airframe drag (N)

    runtime_minutes : float
        Estimated runtime at this operating point (min)

    thermal_eval : ThermalEvaluation
        Thermal evaluation at this operating point

    valid : bool
        Whether calculation was successful

    error_message : str
        Error description if not valid
    """
    airspeed: float = 0.0
    throttle: float = 0.0
    motor_current: float = 0.0
    battery_current: float = 0.0
    battery_power: float = 0.0
    loaded_voltage: float = 0.0
    system_efficiency: float = 0.0
    motor_efficiency: float = 0.0
    prop_efficiency: float = 0.0
    prop_rpm: float = 0.0
    drag: float = 0.0
    runtime_minutes: float = 0.0
    thermal_eval: ThermalEvaluation = field(default_factory=ThermalEvaluation)
    valid: bool = False
    error_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for export."""
        return {
            "airspeed_ms": self.airspeed,
            "airspeed_mph": self.airspeed * 2.237,
            "throttle_pct": self.throttle,
            "motor_current_a": self.motor_current,
            "battery_current_a": self.battery_current,
            "battery_power_w": self.battery_power,
            "loaded_voltage_v": self.loaded_voltage,
            "system_efficiency_pct": self.system_efficiency * 100,
            "motor_efficiency_pct": self.motor_efficiency * 100,
            "prop_efficiency_pct": self.prop_efficiency * 100,
            "prop_rpm": self.prop_rpm,
            "drag_n": self.drag,
            "runtime_min": self.runtime_minutes,
            "thermal": self.thermal_eval.to_dict(),
            "valid": self.valid,
            "error": self.error_message,
        }


# =============================================================================
# Integrated Result
# =============================================================================

@dataclass
class IntegratedResult:
    """
    Complete result for one motor/prop/battery combination.

    Contains component identifiers, pack summary, cruise and max speed
    results, thermal status, and computed metrics.

    Attributes:
    ----------
    # Component Identifiers
    motor_id : str
        Motor identifier
    prop_id : str
        Propeller identifier
    cell_type : str
        Cell type name
    series : int
        Number of cells in series
    parallel : int
        Number of cells in parallel
    thermal_environment : str
        Thermal environment name

    # Pack Summary
    pack_config : str
        Configuration string (e.g., "6S2P")
    pack_voltage_nominal : float
        Nominal pack voltage (V)
    pack_capacity_mah : float
        Pack capacity (mAh)
    pack_energy_wh : float
        Pack energy (Wh)
    pack_mass_kg : float
        Pack mass (kg)

    # Results
    cruise_result : SpeedPointResult
        Results at cruise speed
    max_speed_result : Optional[SpeedPointResult]
        Results at max speed (if evaluated)
    max_achievable_speed : float
        Maximum achievable speed (m/s)

    # Thermal Status
    cruise_thermal_valid : bool
        Whether cruise is within thermal limits
    max_speed_thermal_valid : bool
        Whether max speed is within thermal limits
    thermal_throttle_limit : Optional[float]
        Max safe throttle if thermally limited (%)

    # Overall Status
    valid : bool
        Whether combination is valid
    invalidity_reason : str
        Reason if invalid

    # Computed Metrics
    energy_density_wh_kg : float
        Pack energy density (Wh/kg)
    power_density_w_kg : float
        Power per kg aircraft weight (W/kg)
    cruise_runtime_minutes : float
        Runtime at cruise speed (min)
    """
    # Component identifiers
    motor_id: str = ""
    prop_id: str = ""
    cell_type: str = ""
    series: int = 0
    parallel: int = 0
    thermal_environment: str = ""

    # Pack summary
    pack_config: str = ""
    pack_voltage_nominal: float = 0.0
    pack_capacity_mah: float = 0.0
    pack_energy_wh: float = 0.0
    pack_mass_kg: float = 0.0

    # Results
    cruise_result: SpeedPointResult = field(default_factory=SpeedPointResult)  # Primary cruise (first or single)
    cruise_speed_results: List[SpeedPointResult] = field(default_factory=list)  # All cruise speed evaluations
    max_speed_result: Optional[SpeedPointResult] = None
    max_achievable_speed: float = 0.0
    speed_sweep_results: List[SpeedPointResult] = field(default_factory=list)

    # Thermal status
    cruise_thermal_valid: bool = True
    max_speed_thermal_valid: bool = True
    thermal_throttle_limit: Optional[float] = None

    # Overall status
    valid: bool = False
    invalidity_reason: str = ""

    # Computed metrics
    energy_density_wh_kg: float = 0.0
    power_density_w_kg: float = 0.0
    cruise_runtime_minutes: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for export."""
        result = {
            "motor_id": self.motor_id,
            "prop_id": self.prop_id,
            "cell_type": self.cell_type,
            "series": self.series,
            "parallel": self.parallel,
            "thermal_environment": self.thermal_environment,
            "pack_config": self.pack_config,
            "pack_voltage_nominal": self.pack_voltage_nominal,
            "pack_capacity_mah": self.pack_capacity_mah,
            "pack_energy_wh": self.pack_energy_wh,
            "pack_mass_kg": self.pack_mass_kg,
            "cruise": self.cruise_result.to_dict(),
            "cruise_speed_results": [r.to_dict() for r in self.cruise_speed_results],
            "max_achievable_speed_ms": self.max_achievable_speed,
            "max_achievable_speed_mph": self.max_achievable_speed * 2.237,
            "cruise_thermal_valid": self.cruise_thermal_valid,
            "max_speed_thermal_valid": self.max_speed_thermal_valid,
            "thermal_throttle_limit_pct": self.thermal_throttle_limit,
            "valid": self.valid,
            "invalidity_reason": self.invalidity_reason,
            "energy_density_wh_kg": self.energy_density_wh_kg,
            "power_density_w_kg": self.power_density_w_kg,
            "cruise_runtime_min": self.cruise_runtime_minutes,
        }
        if self.max_speed_result:
            result["max_speed"] = self.max_speed_result.to_dict()
        return result

    def get_summary_string(self) -> str:
        """Get one-line summary string."""
        thermal_note = ""
        if self.thermal_throttle_limit is not None:
            thermal_note = f" (thermal limit @ {self.thermal_throttle_limit:.0f}%)"

        if not self.valid:
            return f"{self.motor_id} + {self.prop_id} + {self.pack_config}: INVALID - {self.invalidity_reason}"

        return (
            f"{self.motor_id} + {self.prop_id} + {self.cell_type} {self.pack_config}: "
            f"Cruise {self.cruise_result.airspeed:.0f}m/s @ {self.cruise_result.throttle:.0f}% | "
            f"Max {self.max_achievable_speed:.0f}m/s{thermal_note} | "
            f"Runtime {self.cruise_runtime_minutes:.0f}min | "
            f"Eff {self.cruise_result.system_efficiency*100:.1f}%"
        )


# =============================================================================
# Batch Progress
# =============================================================================

@dataclass
class IntegratedProgress:
    """
    Progress tracking for batch execution.

    Attributes:
    ----------
    current : int
        Current permutation being processed
    total : int
        Total permutations to process
    current_motor : str
        Motor ID currently being processed
    current_prop : str
        Propeller ID currently being processed
    results_valid : int
        Count of valid results
    results_invalid : int
        Count of invalid results
    results_thermal_limited : int
        Count of thermally limited (but valid) results
    elapsed_seconds : float
        Time elapsed since start
    best_efficiency : float
        Best system efficiency found so far
    best_runtime : float
        Best runtime found so far (minutes)
    best_combo : str
        Best combination description
    is_running : bool
        Whether batch is currently running
    is_cancelled : bool
        Whether batch was cancelled
    """
    current: int = 0
    total: int = 0
    current_motor: str = ""
    current_prop: str = ""
    results_valid: int = 0
    results_invalid: int = 0
    results_thermal_limited: int = 0
    elapsed_seconds: float = 0.0
    best_efficiency: float = 0.0
    best_runtime: float = 0.0
    best_combo: str = ""
    is_running: bool = False
    is_cancelled: bool = False

    @property
    def percent_complete(self) -> float:
        """Get completion percentage."""
        if self.total == 0:
            return 0.0
        return (self.current / self.total) * 100.0

    @property
    def rate_per_second(self) -> float:
        """Get processing rate."""
        if self.elapsed_seconds == 0:
            return 0.0
        return self.current / self.elapsed_seconds

    @property
    def estimated_remaining_seconds(self) -> float:
        """Get estimated remaining time."""
        if self.rate_per_second == 0:
            return float('inf')
        remaining = self.total - self.current
        return remaining / self.rate_per_second


# =============================================================================
# Integrated Batch Result
# =============================================================================

@dataclass
class IntegratedBatchResult:
    """
    Complete batch analysis result.

    Contains configuration, all results, summary statistics, and
    best combinations by various metrics.

    Attributes:
    ----------
    config : IntegratedConfig
        Configuration used for analysis

    results : List[IntegratedResult]
        All individual results

    # Summary statistics
    total_combinations : int
        Total combinations tested
    valid_combinations : int
        Number of valid combinations
    thermal_limited_count : int
        Number of thermally limited combinations
    rating_limited_count : int
        Number of rating limited combinations
    voltage_limited_count : int
        Number of voltage limited combinations

    # Best combinations
    best_by_efficiency : Optional[IntegratedResult]
        Best by system efficiency
    best_by_runtime : Optional[IntegratedResult]
        Best by runtime
    best_by_max_speed : Optional[IntegratedResult]
        Best by max achievable speed
    best_by_power_density : Optional[IntegratedResult]
        Best by power density

    elapsed_seconds : float
        Total analysis time
    """
    config: IntegratedConfig = field(default_factory=IntegratedConfig)
    results: List[IntegratedResult] = field(default_factory=list)

    # Summary statistics
    total_combinations: int = 0
    valid_combinations: int = 0
    thermal_limited_count: int = 0
    rating_limited_count: int = 0
    voltage_limited_count: int = 0

    # Best combinations
    best_by_efficiency: Optional[IntegratedResult] = None
    best_by_runtime: Optional[IntegratedResult] = None
    best_by_max_speed: Optional[IntegratedResult] = None
    best_by_power_density: Optional[IntegratedResult] = None

    elapsed_seconds: float = 0.0

    def get_valid_results(self) -> List[IntegratedResult]:
        """Get only valid results."""
        return [r for r in self.results if r.valid]

    def get_results_by_battery_config(self) -> Dict[str, List[IntegratedResult]]:
        """Group results by battery configuration."""
        grouped: Dict[str, List[IntegratedResult]] = {}
        for result in self.results:
            key = f"{result.cell_type}_{result.pack_config}_{result.thermal_environment}"
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(result)
        return grouped

    def get_comparison_matrix(self) -> Dict[str, Dict[str, IntegratedResult]]:
        """
        Generate comparison matrix.

        Returns dict where:
        - Keys are battery configs (e.g., "P45B_6S2P_drone_in_flight")
        - Values are dicts mapping motor/prop combos to best result
        """
        matrix: Dict[str, Dict[str, IntegratedResult]] = {}
        grouped = self.get_results_by_battery_config()

        for batt_key, results in grouped.items():
            valid_results = [r for r in results if r.valid]
            if not valid_results:
                continue

            # Find best for each motor/prop combo
            combo_best: Dict[str, IntegratedResult] = {}
            for result in valid_results:
                mp_key = f"{result.motor_id}_{result.prop_id}"
                if mp_key not in combo_best:
                    combo_best[mp_key] = result
                elif result.cruise_result.system_efficiency > combo_best[mp_key].cruise_result.system_efficiency:
                    combo_best[mp_key] = result

            matrix[batt_key] = combo_best

        return matrix
