"""
Batch Solver Module
===================

This module provides the core batch processing engine for finding optimal
motor and propeller combinations for fixed-wing FPV aircraft.

The BatchSolver class handles:
- Filtering motors and propellers based on user criteria
- Calculating permutation counts
- Running batch calculations with progress callbacks
- Threading/multiprocessing for performance
- Finding best combinations by various metrics

Usage:
------
    from src.batch_analyzer import BatchSolver, BatchConfig

    config = BatchConfig(...)
    solver = BatchSolver(config)

    # Check permutation count
    count = solver.get_permutation_count()

    # Run batch with progress updates
    def on_progress(current, total, result):
        print(f"{current}/{total}: {result.motor_id} + {result.prop_id}")

    results = solver.run_batch(progress_callback=on_progress)

    # Get top 10 by efficiency
    best = solver.find_best_combinations(results, metric="efficiency", top_n=10)
"""

import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Optional, List, Tuple, Callable, Dict, Any
from pathlib import Path
import sys

# Add parent for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from .config import BatchConfig, BatchResult, DEFAULT_LIMITS

from src.motor_analyzer.core import MotorAnalyzer
from src.motor_analyzer.config import MotorAnalyzerConfig
from src.prop_analyzer.core import PropAnalyzer
from src.prop_analyzer.config import PropAnalyzerConfig
from src.flight_analyzer.flight_solver import FlightSolver
from src.flight_analyzer.drag_model import DragModel
from src.flight_analyzer.config import FlightAnalyzerConfig


# =============================================================================
# Prop Parsing Utilities
# =============================================================================

def parse_prop_dimensions(prop_id: str) -> Tuple[Optional[float], Optional[float]]:
    """
    Parse propeller ID to extract diameter and pitch.

    Handles various APC naming conventions:
    - "10x5" -> (10.0, 5.0)
    - "10x4.5" -> (10.0, 4.5)
    - "10x45MR" -> (10.0, 4.5)  # pitch encoded as 45 = 4.5
    - "7x7E" -> (7.0, 7.0)
    - "105x45" -> (10.5, 4.5)

    Parameters:
    ----------
    prop_id : str
        Propeller identifier string

    Returns:
    -------
    Tuple[Optional[float], Optional[float]]
        (diameter, pitch) in inches, or (None, None) if parsing fails
    """
    # Clean up the prop_id
    prop_id = prop_id.strip()

    # Pattern 1: Standard format like "10x5", "10x4.5", "7x7E"
    # The 'x' separates diameter from pitch
    match = re.match(r'^(\d+\.?\d*)x(\d+\.?\d*)', prop_id)
    if match:
        diameter_str = match.group(1)
        pitch_str = match.group(2)

        # Handle encoded dimensions (e.g., "105" = 10.5, "45" = 4.5)
        diameter = float(diameter_str)
        pitch = float(pitch_str)

        # If diameter > 30, it's likely encoded (e.g., 105 = 10.5)
        if diameter > 30:
            diameter = diameter / 10.0

        # If pitch > 20 and diameter <= 20, pitch might be encoded
        # e.g., "10x45MR" where 45 = 4.5 pitch
        if pitch > 20 and diameter <= 20:
            pitch = pitch / 10.0

        return diameter, pitch

    # Pattern 2: Three-digit diameter format like "105x45" (10.5 x 4.5)
    match = re.match(r'^(\d{3})x(\d+\.?\d*)', prop_id)
    if match:
        diameter = float(match.group(1)) / 10.0
        pitch = float(match.group(2))
        if pitch > 20:
            pitch = pitch / 10.0
        return diameter, pitch

    return None, None


def filter_props_by_dimensions(
    prop_ids: List[str],
    diameter_range: Tuple[float, float],
    pitch_range: Tuple[float, float]
) -> List[str]:
    """
    Filter propeller list by diameter and pitch ranges.

    Parameters:
    ----------
    prop_ids : List[str]
        List of propeller identifiers

    diameter_range : Tuple[float, float]
        (min_diameter, max_diameter) in inches

    pitch_range : Tuple[float, float]
        (min_pitch, max_pitch) in inches

    Returns:
    -------
    List[str]
        Filtered list of prop IDs within the specified ranges
    """
    filtered = []
    d_min, d_max = diameter_range
    p_min, p_max = pitch_range

    for prop_id in prop_ids:
        diameter, pitch = parse_prop_dimensions(prop_id)
        if diameter is not None and pitch is not None:
            if d_min <= diameter <= d_max and p_min <= pitch <= p_max:
                filtered.append(prop_id)

    return filtered


# =============================================================================
# Progress Tracking
# =============================================================================

@dataclass
class BatchProgress:
    """Progress information for batch processing."""
    current: int = 0
    total: int = 0
    current_motor: str = ""
    current_prop: str = ""
    current_speed: float = 0.0
    elapsed_seconds: float = 0.0
    estimated_remaining_seconds: float = 0.0
    results_valid: int = 0
    results_invalid: int = 0
    best_efficiency: float = 0.0
    best_combo: str = ""
    is_running: bool = False
    is_cancelled: bool = False
    error_message: str = ""

    @property
    def percent_complete(self) -> float:
        if self.total == 0:
            return 0.0
        return (self.current / self.total) * 100.0

    @property
    def rate_per_second(self) -> float:
        if self.elapsed_seconds <= 0:
            return 0.0
        return self.current / self.elapsed_seconds


# =============================================================================
# Batch Solver Class
# =============================================================================

class BatchSolver:
    """
    Batch processing engine for motor/prop optimization.

    This class handles the complete batch analysis workflow:
    1. Load and filter motors and propellers
    2. Calculate total permutations
    3. Run batch calculations with threading
    4. Track progress and allow cancellation
    5. Rank and return results

    Attributes:
    ----------
    config : BatchConfig
        Configuration for this batch run

    progress : BatchProgress
        Current progress information

    Example:
    -------
        config = BatchConfig(
            wing_area=0.15,
            wingspan=1.0,
            weight=1.0,
            voltage=14.8
        )

        solver = BatchSolver(config)

        # Check if permutations are reasonable
        count = solver.get_permutation_count()
        if count > 100000:
            print("Warning: Large batch!")

        # Run with progress callback
        results = solver.run_batch(
            progress_callback=lambda p: print(f"{p.percent_complete:.1f}%")
        )

        # Get best results
        best = solver.find_best_combinations(results)
    """

    def __init__(self, config: BatchConfig):
        """
        Initialize the BatchSolver.

        Parameters:
        ----------
        config : BatchConfig
            Configuration for batch analysis
        """
        self.config = config
        self.progress = BatchProgress()

        # Initialize analyzers
        self._motor_config = MotorAnalyzerConfig()
        self._prop_config = PropAnalyzerConfig()
        self._flight_config = FlightAnalyzerConfig()

        self._motor_analyzer = MotorAnalyzer(self._motor_config)
        self._prop_analyzer = PropAnalyzer(self._prop_config)

        # Load motor presets
        self._motor_presets = self._load_motor_presets()

        # Cache filtered lists
        self._filtered_motors: Optional[List[str]] = None
        self._filtered_props: Optional[List[str]] = None

        # Threading control
        self._cancel_event = threading.Event()
        self._lock = threading.Lock()

    def _load_motor_presets(self) -> Dict[str, Any]:
        """Load motor presets from JSON file."""
        import json
        preset_path = self._motor_config.data_root / "motor_presets.json"

        if preset_path.exists():
            try:
                with open(preset_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Could not load motor presets: {e}")
                return {"categories": {}, "motors": {}}

        return {"categories": {}, "motors": {}}

    # -------------------------------------------------------------------------
    # Filtering Methods
    # -------------------------------------------------------------------------

    def get_available_motor_categories(self) -> List[str]:
        """Get list of available motor categories."""
        return list(self._motor_presets.get("categories", {}).keys())

    def get_motors_in_category(self, category: str) -> List[str]:
        """Get motor IDs in a specific category."""
        return self._motor_presets.get("categories", {}).get(category, [])

    def get_filtered_motors(self) -> List[str]:
        """
        Get list of motors matching the filter criteria.

        Returns motors based on:
        1. Specific motor_ids if provided
        2. Motors in selected categories if provided
        3. All motors if no filters

        Returns:
        -------
        List[str]
            List of motor IDs to test
        """
        if self._filtered_motors is not None:
            return self._filtered_motors

        motors = self._motor_presets.get("motors", {})

        # If specific motor IDs provided, use those
        if self.config.motor_ids:
            self._filtered_motors = [
                m for m in self.config.motor_ids if m in motors
            ]
            return self._filtered_motors

        # If categories specified, get motors from those categories
        if self.config.motor_categories:
            motor_set = set()
            for category in self.config.motor_categories:
                motor_set.update(self.get_motors_in_category(category))
            self._filtered_motors = list(motor_set)
            return self._filtered_motors

        # Default: all motors
        self._filtered_motors = list(motors.keys())
        return self._filtered_motors

    def get_filtered_props(self) -> List[str]:
        """
        Get list of propellers matching the filter criteria.

        Filters by diameter and pitch ranges.

        Returns:
        -------
        List[str]
            List of prop IDs to test
        """
        if self._filtered_props is not None:
            return self._filtered_props

        # Get all available props
        all_props = self._prop_analyzer.list_available_propellers()

        # Filter by dimensions
        self._filtered_props = filter_props_by_dimensions(
            all_props,
            (self.config.prop_diameter_min, self.config.prop_diameter_max),
            (self.config.prop_pitch_min, self.config.prop_pitch_max)
        )

        return self._filtered_props

    def get_speed_points(self) -> List[float]:
        """Get list of speed points to test."""
        return self.config.get_speed_points()

    def clear_filter_cache(self):
        """Clear cached filter results (call after changing config)."""
        self._filtered_motors = None
        self._filtered_props = None

    # -------------------------------------------------------------------------
    # Permutation Counting
    # -------------------------------------------------------------------------

    def get_permutation_count(self) -> int:
        """
        Calculate total number of combinations to test.

        Returns:
        -------
        int
            Total permutations (motors × props × speeds)
        """
        motors = len(self.get_filtered_motors())
        props = len(self.get_filtered_props())
        speeds = len(self.get_speed_points())

        return motors * props * speeds

    def get_filter_summary(self) -> Dict[str, Any]:
        """
        Get summary of current filter settings.

        Returns:
        -------
        dict
            Summary with counts and sample items
        """
        motors = self.get_filtered_motors()
        props = self.get_filtered_props()
        speeds = self.get_speed_points()

        return {
            "motor_count": len(motors),
            "prop_count": len(props),
            "speed_count": len(speeds),
            "total_permutations": len(motors) * len(props) * len(speeds),
            "sample_motors": motors[:5] if motors else [],
            "sample_props": props[:5] if props else [],
            "speed_range": (speeds[0], speeds[-1]) if speeds else (0, 0),
            "exceeds_limit": len(motors) * len(props) * len(speeds) > self.config.limits.max_permutations,
            "exceeds_warning": len(motors) * len(props) * len(speeds) > self.config.limits.warning_permutations,
        }

    # -------------------------------------------------------------------------
    # Single Calculation
    # -------------------------------------------------------------------------

    def _calculate_single(
        self,
        motor_id: str,
        prop_id: str,
        airspeed: float,
        flight_solver: FlightSolver
    ) -> BatchResult:
        """
        Run a single motor/prop/speed calculation.

        Parameters:
        ----------
        motor_id : str
            Motor identifier
        prop_id : str
            Propeller identifier
        airspeed : float
            Target airspeed (m/s)
        flight_solver : FlightSolver
            Pre-configured flight solver instance

        Returns:
        -------
        BatchResult
            Result of the calculation
        """
        result = BatchResult(
            motor_id=motor_id,
            prop_id=prop_id,
            airspeed=airspeed
        )

        try:
            # Build drag model for fixed-wing
            weight_n = self.config.weight * 9.81
            drag_model = DragModel(
                method="fixed_wing",
                cd0=self.config.cd0,
                wing_area=self.config.wing_area,
                wingspan=self.config.wingspan,
                weight=weight_n,
                oswald_efficiency=self.config.oswald_efficiency
            )

            # Register motor with solver
            motor_data = self._motor_presets.get("motors", {}).get(motor_id, {})
            if not motor_data:
                result.error_message = f"Motor not found: {motor_id}"
                return result

            flight_solver.motor_analyzer.add_motor(motor_id, motor_data)

            # Solve cruise
            flight_result = flight_solver.solve_cruise(
                motor_id=motor_id,
                prop_id=prop_id,
                drag_model=drag_model,
                v_battery=self.config.voltage,
                airspeed=airspeed,
                altitude=self.config.altitude,
                winding_temp=self.config.winding_temp,
                num_motors=1
            )

            # Transfer results
            if flight_result.valid:
                result.valid = True
                result.throttle = flight_result.throttle
                result.motor_current = flight_result.motor_current
                result.battery_power = flight_result.battery_power
                result.system_efficiency = flight_result.system_efficiency
                result.motor_efficiency = flight_result.motor_efficiency
                result.prop_efficiency = flight_result.prop_efficiency
                result.prop_rpm = flight_result.prop_rpm
                result.drag = flight_result.drag

                # Mark as invalid if throttle > 100%
                if result.throttle > 100:
                    result.valid = False
                    result.error_message = f"Throttle exceeds 100%: {result.throttle:.1f}%"
            else:
                result.error_message = flight_result.error_message

        except Exception as e:
            result.error_message = str(e)

        return result

    # -------------------------------------------------------------------------
    # Batch Execution
    # -------------------------------------------------------------------------

    def run_batch(
        self,
        progress_callback: Optional[Callable[[BatchProgress], None]] = None
    ) -> List[BatchResult]:
        """
        Run the batch analysis.

        Executes all motor/prop/speed combinations using thread pooling
        for performance. Progress is reported via callback.

        Parameters:
        ----------
        progress_callback : Callable, optional
            Function called with BatchProgress updates

        Returns:
        -------
        List[BatchResult]
            All results (valid and invalid)

        Raises:
        ------
        ValueError
            If configuration is invalid or permutations exceed limit
        """
        # Validate configuration
        is_valid, error = self.config.validate()
        if not is_valid:
            raise ValueError(f"Invalid configuration: {error}")

        # Check permutation limits
        total = self.get_permutation_count()
        if total > self.config.limits.max_permutations:
            raise ValueError(
                f"Permutation count ({total:,}) exceeds limit "
                f"({self.config.limits.max_permutations:,}). "
                "Please narrow your search criteria."
            )

        if total == 0:
            raise ValueError(
                "No valid combinations to test. Check motor/prop filters."
            )

        # Reset state
        self._cancel_event.clear()
        self.progress = BatchProgress(
            total=total,
            is_running=True
        )

        results: List[BatchResult] = []
        start_time = time.time()

        # Get all combinations
        motors = self.get_filtered_motors()
        props = self.get_filtered_props()
        speeds = self.get_speed_points()

        # Build work items
        work_items = []
        for motor_id in motors:
            for prop_id in props:
                for speed in speeds:
                    work_items.append((motor_id, prop_id, speed))

        # Determine worker count
        num_workers = min(
            self.config.limits.max_workers,
            len(work_items),
            8  # Cap at 8 workers
        )

        # Track best result
        best_efficiency = 0.0
        best_combo = ""

        # Process with thread pool
        last_update_time = 0.0

        def process_item(item: Tuple[str, str, float]) -> BatchResult:
            """Process a single work item in a thread."""
            motor_id, prop_id, speed = item
            # Each thread gets its own FlightSolver to avoid conflicts
            solver = FlightSolver(self._flight_config)
            return self._calculate_single(motor_id, prop_id, speed, solver)

        try:
            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                # Submit all tasks
                future_to_item = {
                    executor.submit(process_item, item): item
                    for item in work_items
                }

                # Process completed results
                for future in as_completed(future_to_item):
                    # Check for cancellation
                    if self._cancel_event.is_set():
                        self.progress.is_cancelled = True
                        break

                    try:
                        result = future.result(
                            timeout=self.config.limits.timeout_per_calc
                        )
                        results.append(result)

                        # Update progress
                        with self._lock:
                            self.progress.current = len(results)
                            self.progress.elapsed_seconds = time.time() - start_time

                            if result.valid:
                                self.progress.results_valid += 1
                                if result.system_efficiency > best_efficiency:
                                    best_efficiency = result.system_efficiency
                                    best_combo = f"{result.motor_id} + {result.prop_id} @ {result.airspeed:.0f}m/s"
                                    self.progress.best_efficiency = best_efficiency
                                    self.progress.best_combo = best_combo
                            else:
                                self.progress.results_invalid += 1

                            self.progress.current_motor = result.motor_id
                            self.progress.current_prop = result.prop_id
                            self.progress.current_speed = result.airspeed

                            # Estimate remaining time
                            if self.progress.current > 0:
                                rate = self.progress.current / self.progress.elapsed_seconds
                                remaining = self.progress.total - self.progress.current
                                self.progress.estimated_remaining_seconds = remaining / rate

                        # Rate-limit progress callbacks
                        current_time = time.time()
                        if current_time - last_update_time >= self.config.limits.update_interval:
                            last_update_time = current_time
                            if progress_callback:
                                progress_callback(self.progress)

                    except Exception as e:
                        # Handle timeout or other errors
                        item = future_to_item[future]
                        results.append(BatchResult(
                            motor_id=item[0],
                            prop_id=item[1],
                            airspeed=item[2],
                            valid=False,
                            error_message=str(e)
                        ))

        finally:
            self.progress.is_running = False
            self.progress.elapsed_seconds = time.time() - start_time

            # Final callback
            if progress_callback:
                progress_callback(self.progress)

        return results

    def cancel(self):
        """Request cancellation of running batch."""
        self._cancel_event.set()

    # -------------------------------------------------------------------------
    # Result Analysis
    # -------------------------------------------------------------------------

    def find_best_combinations(
        self,
        results: List[BatchResult],
        metric: str = "efficiency",
        top_n: int = 10,
        valid_only: bool = True,
        max_throttle: float = 95.0
    ) -> List[BatchResult]:
        """
        Find the best motor/prop combinations.

        Parameters:
        ----------
        results : List[BatchResult]
            Results from run_batch()

        metric : str
            Metric to optimize: "efficiency", "current", "power", "throttle"

        top_n : int
            Number of top results to return

        valid_only : bool
            Only include valid results

        max_throttle : float
            Maximum throttle percentage to consider

        Returns:
        -------
        List[BatchResult]
            Top N results sorted by metric
        """
        # Filter results
        filtered = results
        if valid_only:
            filtered = [r for r in filtered if r.valid]

        filtered = [r for r in filtered if r.throttle <= max_throttle]

        if not filtered:
            return []

        # Sort by metric
        if metric == "efficiency":
            filtered.sort(key=lambda r: r.system_efficiency, reverse=True)
        elif metric == "current":
            filtered.sort(key=lambda r: r.motor_current)  # Lower is better
        elif metric == "power":
            filtered.sort(key=lambda r: r.battery_power)  # Lower is better
        elif metric == "throttle":
            filtered.sort(key=lambda r: r.throttle)  # Lower is better
        else:
            filtered.sort(key=lambda r: r.system_efficiency, reverse=True)

        return filtered[:top_n]

    def get_best_for_each_speed(
        self,
        results: List[BatchResult],
        metric: str = "efficiency",
        max_throttle: float = 95.0
    ) -> Dict[float, BatchResult]:
        """
        Get the best motor/prop combination for each speed point.

        Parameters:
        ----------
        results : List[BatchResult]
            Results from run_batch()

        metric : str
            Metric to optimize

        max_throttle : float
            Maximum throttle percentage

        Returns:
        -------
        Dict[float, BatchResult]
            Best result for each airspeed
        """
        # Group by speed
        by_speed: Dict[float, List[BatchResult]] = {}
        for r in results:
            if r.valid and r.throttle <= max_throttle:
                if r.airspeed not in by_speed:
                    by_speed[r.airspeed] = []
                by_speed[r.airspeed].append(r)

        # Find best at each speed
        best_by_speed = {}
        for speed, speed_results in by_speed.items():
            best = self.find_best_combinations(
                speed_results, metric=metric, top_n=1
            )
            if best:
                best_by_speed[speed] = best[0]

        return best_by_speed

    def export_results_csv(
        self,
        results: List[BatchResult],
        filepath: str,
        valid_only: bool = True
    ):
        """
        Export results to CSV file.

        Parameters:
        ----------
        results : List[BatchResult]
            Results to export

        filepath : str
            Output file path

        valid_only : bool
            Only export valid results
        """
        import csv

        filtered = results if not valid_only else [r for r in results if r.valid]

        if not filtered:
            return

        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(filtered[0].to_dict().keys()))
            writer.writeheader()
            for r in filtered:
                writer.writerow(r.to_dict())
