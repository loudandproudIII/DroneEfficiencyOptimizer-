"""
Integrated Solver Module
=========================

Core batch processing engine for integrated motor/prop/battery analysis.

This module handles:
- Loading motor presets, propeller database, and cell database
- Filtering based on configuration
- Generating permutations across all dimensions
- Parallel execution with ThreadPoolExecutor
- Voltage-current iteration for battery integration
- Thermal limit evaluation
- Progress tracking and cancellation

Classes:
--------
- IntegratedSolver: Main solver class

Usage:
------
    from src.integrated_analyzer import IntegratedSolver, IntegratedConfig

    config = IntegratedConfig(...)
    solver = IntegratedSolver(config)

    # Check permutation count
    count = solver.get_permutation_count()

    # Run batch with progress
    def on_progress(progress):
        print(f"{progress.percent_complete:.1f}%")

    result = solver.run_batch(progress_callback=on_progress)
"""

import re
import time
import json
import math
import os
import threading
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Callable, Dict, Any, Generator
from pathlib import Path
import sys

# Add parent for imports BEFORE other local imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Process-local storage for analyzers (created once per worker process)
_process_local = {}

from .config import (
    IntegratedConfig,
    IntegratedResult,
    IntegratedBatchResult,
    IntegratedProgress,
    SpeedPointResult,
    ThermalEvaluation,
)
from .thermal_evaluator import ThermalEvaluator

# Import analyzers
from src.motor_analyzer.core import MotorAnalyzer
from src.motor_analyzer.config import MotorAnalyzerConfig
from src.prop_analyzer.core import PropAnalyzer
from src.prop_analyzer.config import PropAnalyzerConfig
from src.flight_analyzer.flight_solver import FlightSolver
from src.flight_analyzer.drag_model import DragModel
from src.flight_analyzer.config import FlightAnalyzerConfig

# Import battery calculator
from src.battery_calculator import (
    BatteryPack,
    BatteryCalculatorConfig,
    CELL_DATABASE,
    get_cell,
)
from src.battery_calculator.config import THERMAL_RESISTANCE


# =============================================================================
# Prop Parsing Utilities (from batch_analyzer)
# =============================================================================

def parse_prop_dimensions(prop_id: str) -> Tuple[Optional[float], Optional[float]]:
    """
    Parse propeller ID to extract diameter and pitch.

    Handles various APC naming conventions.

    Returns:
        (diameter, pitch) in inches, or (None, None) if parsing fails
    """
    prop_id = prop_id.strip()

    # Pattern: "10x5", "10x4.5", "7x7E"
    match = re.match(r'^(\d+\.?\d*)x(\d+\.?\d*)', prop_id)
    if match:
        diameter = float(match.group(1))
        pitch = float(match.group(2))

        # Handle encoded dimensions (105 = 10.5)
        if diameter > 30:
            diameter = diameter / 10.0
        if pitch > 20:
            pitch = pitch / 10.0

        return diameter, pitch

    return None, None


def filter_props_by_dimensions(
    prop_ids: List[str],
    diameter_range: Tuple[float, float],
    pitch_range: Tuple[float, float]
) -> List[str]:
    """Filter props by diameter and pitch ranges."""
    filtered = []
    d_min, d_max = diameter_range
    p_min, p_max = pitch_range

    for prop_id in prop_ids:
        diameter, pitch = parse_prop_dimensions(prop_id)
        if diameter is None or pitch is None:
            continue
        if d_min <= diameter <= d_max and p_min <= pitch <= p_max:
            filtered.append(prop_id)

    return filtered


# =============================================================================
# Work Item
# =============================================================================

@dataclass
class WorkItem:
    """Single work item for batch processing."""
    motor_id: str
    prop_id: str
    cell_type: str
    series: int
    parallel: int
    thermal_environment: str


@dataclass
class WorkerContext:
    """Context data passed to worker processes."""
    # Airframe config
    wing_area: float
    wingspan: float
    weight: float
    cd0: float
    oswald_efficiency: float
    # Battery config
    ambient_temp_c: float
    max_cell_temp_c: float
    soc_for_analysis: float
    # Speed config
    cruise_speeds: List[float]
    evaluate_max_speed: bool
    cruise_speed: float
    altitude: float
    winding_temp: float
    # Motor presets
    motor_presets: Dict[str, Any]


def _init_worker_process(context_dict: Dict[str, Any]):
    """Initialize worker process with shared context."""
    global _process_local
    _process_local['context'] = context_dict
    _process_local['flight_solver'] = None
    _process_local['prop_analyzer'] = None
    _process_local['thermal_evaluator'] = None


def _get_worker_flight_solver() -> FlightSolver:
    """Get or create process-local FlightSolver."""
    global _process_local
    if _process_local.get('flight_solver') is None:
        _process_local['flight_solver'] = FlightSolver(FlightAnalyzerConfig())
    return _process_local['flight_solver']


def _get_worker_thermal_evaluator() -> 'ThermalEvaluator':
    """Get or create process-local ThermalEvaluator."""
    global _process_local
    if _process_local.get('thermal_evaluator') is None:
        from .thermal_evaluator import ThermalEvaluator
        _process_local['thermal_evaluator'] = ThermalEvaluator()
    return _process_local['thermal_evaluator']


def _worker_calculate(work_item_tuple: Tuple) -> IntegratedResult:
    """
    Standalone worker function for multiprocessing.

    Receives work item as tuple for efficient pickling.
    Uses process-local context and analyzers.
    """
    global _process_local

    # Unpack work item
    motor_id, prop_id, cell_type, series, parallel, thermal_env = work_item_tuple

    # Get context from process-local storage
    ctx = _process_local.get('context', {})

    result = IntegratedResult(
        motor_id=motor_id,
        prop_id=prop_id,
        cell_type=cell_type,
        series=series,
        parallel=parallel,
        thermal_environment=thermal_env,
        pack_config=f"{series}S{parallel}P",
    )

    try:
        # Get process-local analyzers
        flight_solver = _get_worker_flight_solver()
        thermal_evaluator = _get_worker_thermal_evaluator()

        # Step 1: Create Battery Pack
        cell = get_cell(cell_type)
        if cell is None:
            result.valid = False
            result.invalidity_reason = f"Unknown cell type: {cell_type}"
            return result

        batt_config = BatteryCalculatorConfig(
            thermal_environment=thermal_env,
            ambient_temp_c=ctx.get('ambient_temp_c', 25.0),
            max_cell_temp_c=ctx.get('max_cell_temp_c', 60.0),
        )

        pack = BatteryPack(
            cell=cell,
            series=series,
            parallel=parallel,
            config=batt_config,
        )

        # Store pack info
        result.pack_voltage_nominal = pack.nominal_voltage
        result.pack_capacity_mah = pack.capacity_mah
        result.pack_energy_wh = pack.energy_wh
        result.pack_mass_kg = pack.get_mass_kg()
        result.energy_density_wh_kg = pack.get_energy_density_wh_kg()

        # Step 2: Create Drag Model
        drag_model = DragModel(
            method="fixed_wing",
            wing_area=ctx.get('wing_area', 0.15),
            wingspan=ctx.get('wingspan', 1.0),
            cd0=ctx.get('cd0', 0.025),
            oswald_efficiency=ctx.get('oswald_efficiency', 0.8),
            weight=ctx.get('weight', 1.0),
        )

        # Step 3: Register Motor
        motor_presets = ctx.get('motor_presets', {})
        motors_dict = motor_presets.get("motors", {})
        motor_data = motors_dict.get(motor_id)

        if motor_data is None:
            result.valid = False
            result.invalidity_reason = f"Unknown motor: {motor_id}"
            return result

        flight_solver.motor_analyzer.add_motor(motor_id, motor_data)

        # Step 4: Solve Cruise
        soc = ctx.get('soc_for_analysis', 80.0)
        cruise_speeds = ctx.get('cruise_speeds', [20.0])
        altitude = ctx.get('altitude', 0.0)
        winding_temp = ctx.get('winding_temp', 80.0)

        for cruise_speed in cruise_speeds:
            speed_result = _worker_solve_with_battery(
                flight_solver, motor_id, prop_id, pack, drag_model,
                cruise_speed, soc, altitude, winding_temp
            )

            if speed_result.valid:
                if math.isnan(speed_result.battery_current) or math.isnan(speed_result.battery_power):
                    speed_result.valid = False
                    speed_result.error_message = "Invalid current/power (NaN)"
                else:
                    thermal = thermal_evaluator.evaluate_at_current(
                        pack, speed_result.battery_current, soc
                    )
                    speed_result.thermal_eval = thermal
                    speed_result.runtime_minutes = pack.get_runtime_minutes(
                        speed_result.battery_current, start_soc=soc
                    )

            result.cruise_speed_results.append(speed_result)

        # Use first valid cruise result
        valid_cruise_results = [r for r in result.cruise_speed_results if r.valid]
        if not valid_cruise_results:
            result.valid = False
            result.invalidity_reason = "No valid cruise speed point"
            return result

        mid_idx = len(valid_cruise_results) // 2
        cruise_result = valid_cruise_results[mid_idx]
        result.cruise_result = cruise_result

        # Step 5: Check thermal
        cruise_thermal = cruise_result.thermal_eval
        result.cruise_thermal_valid = cruise_thermal.within_limits

        if not cruise_thermal.within_limits:
            result.valid = False
            result.invalidity_reason = f"Cruise exceeds thermal limit ({cruise_thermal.steady_state_temp_c:.1f}C)"
            return result

        result.cruise_runtime_minutes = cruise_result.runtime_minutes

        # Step 6: Find max speed if enabled
        if ctx.get('evaluate_max_speed', True):
            max_speed_result = _worker_find_max_speed(
                flight_solver, motor_id, prop_id, pack, drag_model,
                soc, ctx.get('cruise_speed', 20.0), altitude, winding_temp
            )

            if max_speed_result is not None and max_speed_result.valid:
                result.max_speed_result = max_speed_result
                result.max_achievable_speed = max_speed_result.airspeed

                max_thermal = thermal_evaluator.evaluate_at_current(
                    pack, max_speed_result.battery_current, soc
                )
                result.max_speed_result.thermal_eval = max_thermal
                result.max_speed_thermal_valid = max_thermal.within_limits

                if not max_thermal.within_limits:
                    safe_throttle, _ = thermal_evaluator.find_max_safe_throttle(
                        pack=pack, soc=soc,
                        cruise_throttle=cruise_result.throttle,
                        cruise_current=cruise_result.battery_current,
                        max_throttle_current=max_speed_result.battery_current,
                    )
                    result.thermal_throttle_limit = safe_throttle

        # Step 7: Compute metrics
        result.power_density_w_kg = cruise_result.battery_power / ctx.get('weight', 1.0)
        result.valid = True

    except Exception as e:
        result.valid = False
        result.invalidity_reason = f"Exception: {str(e)}"

    return result


def _worker_solve_with_battery(
    flight_solver: FlightSolver,
    motor_id: str,
    prop_id: str,
    pack,
    drag_model: DragModel,
    airspeed: float,
    soc: float,
    altitude: float,
    winding_temp: float,
) -> SpeedPointResult:
    """Solve cruise with voltage-current iteration (worker version)."""
    result = SpeedPointResult(airspeed=airspeed)

    v_estimate = pack.nominal_voltage
    converged = False
    final_flight_result = None

    for iteration in range(10):
        flight_result = flight_solver.solve_cruise(
            motor_id=motor_id,
            prop_id=prop_id,
            drag_model=drag_model,
            v_battery=v_estimate,
            airspeed=airspeed,
            altitude=altitude,
            winding_temp=winding_temp,
            num_motors=1,
        )

        if not flight_result.valid:
            result.valid = False
            result.error_message = flight_result.error_message or "Flight solver failed"
            return result

        v_loaded = pack.get_voltage_at_current(
            flight_result.battery_current, soc, pack.config.ambient_temp_c
        )

        if abs(v_loaded - v_estimate) < 0.1:
            converged = True
            final_flight_result = flight_result
            break

        v_estimate = v_loaded

    if not converged:
        final_flight_result = flight_result

    if final_flight_result is None:
        result.valid = False
        result.error_message = "No valid solution found"
        return result

    result.valid = True
    result.throttle = final_flight_result.throttle
    result.motor_current = final_flight_result.motor_current
    result.battery_current = final_flight_result.battery_current
    result.battery_power = final_flight_result.battery_power
    result.loaded_voltage = v_estimate
    result.system_efficiency = final_flight_result.system_efficiency
    result.motor_efficiency = final_flight_result.motor_efficiency
    result.prop_efficiency = final_flight_result.prop_efficiency
    result.prop_rpm = final_flight_result.prop_rpm
    result.drag = final_flight_result.drag

    return result


def _worker_find_max_speed(
    flight_solver: FlightSolver,
    motor_id: str,
    prop_id: str,
    pack,
    drag_model: DragModel,
    soc: float,
    cruise_speed: float,
    altitude: float,
    winding_temp: float,
) -> Optional[SpeedPointResult]:
    """Find max speed via binary search (worker version)."""
    speed_low = cruise_speed
    speed_high = 80.0
    best_result = None

    for _ in range(15):
        speed_mid = (speed_low + speed_high) / 2.0

        result = _worker_solve_with_battery(
            flight_solver, motor_id, prop_id, pack, drag_model,
            speed_mid, soc, altitude, winding_temp
        )

        if result.valid and result.throttle <= 100.0:
            best_result = result
            speed_low = speed_mid
        else:
            speed_high = speed_mid

        if speed_high - speed_low < 0.5:
            break

    return best_result


# =============================================================================
# Integrated Solver
# =============================================================================

class IntegratedSolver:
    """
    Integrated batch solver for motor/prop/battery analysis.

    Combines flight equilibrium solving with battery thermal modeling
    to find optimal combinations across all dimensions.

    Attributes:
    ----------
    config : IntegratedConfig
        Analysis configuration

    progress : IntegratedProgress
        Current progress state

    Methods:
    -------
    get_filtered_motors() -> List[str]
        Get motors matching filter criteria

    get_filtered_props() -> List[str]
        Get props matching filter criteria

    get_permutation_count() -> int
        Get total number of permutations

    run_batch(progress_callback) -> IntegratedBatchResult
        Run complete batch analysis

    cancel()
        Cancel running batch
    """

    def __init__(self, config: IntegratedConfig):
        """
        Initialize solver.

        Parameters:
        ----------
        config : IntegratedConfig
            Analysis configuration
        """
        self.config = config
        self.progress = IntegratedProgress()

        # Threading
        self._cancel_event = threading.Event()
        self._progress_lock = threading.Lock()

        # Cached filters
        self._filtered_motors: Optional[List[str]] = None
        self._filtered_props: Optional[List[str]] = None

        # Load motor presets
        self._motor_presets = self._load_motor_presets()

        # Initialize analyzers (will be created per-thread)
        self._motor_analyzer_config = MotorAnalyzerConfig()
        self._prop_analyzer_config = PropAnalyzerConfig()
        self._flight_config = FlightAnalyzerConfig()

        # Thermal evaluator
        self._thermal_evaluator = ThermalEvaluator()

    def _load_motor_presets(self) -> Dict[str, Any]:
        """Load motor presets from JSON file."""
        preset_path = Path(__file__).parent.parent / "motor_analyzer" / "database" / "motor_presets.json"
        if preset_path.exists():
            with open(preset_path, 'r') as f:
                return json.load(f)
        return {"categories": {}, "motors": {}}

    # =========================================================================
    # Filtering
    # =========================================================================

    def get_filtered_motors(self) -> List[str]:
        """Get list of motors matching filter criteria."""
        if self._filtered_motors is not None:
            return self._filtered_motors

        motors = []

        # If specific IDs provided, use those
        if self.config.motor_ids:
            motors = self.config.motor_ids
        else:
            # Categories dict maps category_name -> list of motor IDs
            categories = self._motor_presets.get("categories", {})

            if not self.config.motor_categories:
                # No category filter - include all motors from all categories
                for cat_motors in categories.values():
                    motors.extend(cat_motors)
            else:
                # Filter by selected categories
                for category in self.config.motor_categories:
                    if category in categories:
                        motors.extend(categories[category])

            # Remove duplicates while preserving order
            seen = set()
            unique_motors = []
            for m in motors:
                if m not in seen:
                    seen.add(m)
                    unique_motors.append(m)
            motors = unique_motors

        self._filtered_motors = motors
        return motors

    def get_filtered_props(self) -> List[str]:
        """Get list of props matching filter criteria."""
        if self._filtered_props is not None:
            return self._filtered_props

        # Get all props from PropAnalyzer
        prop_analyzer = PropAnalyzer(self._prop_analyzer_config)
        all_props = prop_analyzer.list_available_propellers()

        # Filter by dimensions
        filtered = filter_props_by_dimensions(
            all_props,
            self.config.prop_diameter_range,
            self.config.prop_pitch_range
        )

        self._filtered_props = filtered
        return filtered

    def get_available_cells(self) -> List[str]:
        """Get list of available cell types."""
        return list(CELL_DATABASE.keys())

    def get_available_thermal_environments(self) -> List[str]:
        """Get list of available thermal environments."""
        return list(THERMAL_RESISTANCE.keys())

    # =========================================================================
    # Permutation Count
    # =========================================================================

    def get_permutation_count(self) -> int:
        """Get total number of permutations to test."""
        motors = self.get_filtered_motors()
        props = self.get_filtered_props()
        battery_count = self.config.battery_config.get_permutation_count()

        return len(motors) * len(props) * battery_count

    def _get_thread_local_solver(self) -> FlightSolver:
        """Get or create thread-local FlightSolver instance."""
        if not hasattr(_thread_local, 'flight_solver'):
            _thread_local.flight_solver = FlightSolver(self._flight_config)
        return _thread_local.flight_solver

    def _get_thread_local_prop_analyzer(self) -> PropAnalyzer:
        """Get or create thread-local PropAnalyzer instance."""
        if not hasattr(_thread_local, 'prop_analyzer'):
            _thread_local.prop_analyzer = PropAnalyzer(self._prop_analyzer_config)
        return _thread_local.prop_analyzer

    def _generate_work_items(self) -> Generator[WorkItem, None, None]:
        """Generate all work items."""
        motors = self.get_filtered_motors()
        props = self.get_filtered_props()
        batt_config = self.config.battery_config

        for motor_id in motors:
            for prop_id in props:
                for cell_type in batt_config.cell_types:
                    for series in batt_config.get_series_values():
                        for parallel in batt_config.get_parallel_values(series):
                            for thermal_env in batt_config.thermal_environments:
                                yield WorkItem(
                                    motor_id=motor_id,
                                    prop_id=prop_id,
                                    cell_type=cell_type,
                                    series=series,
                                    parallel=parallel,
                                    thermal_environment=thermal_env,
                                )

    # =========================================================================
    # Single Calculation
    # =========================================================================

    def _calculate_single(
        self,
        work_item: WorkItem,
    ) -> IntegratedResult:
        """
        Calculate result for a single combination.

        This is the core calculation that:
        1. Creates battery pack
        2. Solves cruise with voltage-current iteration
        3. Evaluates thermal at cruise
        4. Optionally finds max speed
        5. Finds thermal-limited max throttle if needed

        Parameters:
        ----------
        work_item : WorkItem
            Work item specifying the combination

        Returns:
        -------
        IntegratedResult
            Complete result for this combination
        """
        # Get thread-local analyzers (created once per worker thread)
        flight_solver = self._get_thread_local_solver()
        prop_analyzer = self._get_thread_local_prop_analyzer()
        result = IntegratedResult(
            motor_id=work_item.motor_id,
            prop_id=work_item.prop_id,
            cell_type=work_item.cell_type,
            series=work_item.series,
            parallel=work_item.parallel,
            thermal_environment=work_item.thermal_environment,
            pack_config=f"{work_item.series}S{work_item.parallel}P",
        )

        try:
            # -----------------------------------------------------------------
            # Step 1: Create Battery Pack
            # -----------------------------------------------------------------
            cell = get_cell(work_item.cell_type)
            if cell is None:
                result.valid = False
                result.invalidity_reason = f"Unknown cell type: {work_item.cell_type}"
                return result

            batt_config = BatteryCalculatorConfig(
                thermal_environment=work_item.thermal_environment,
                ambient_temp_c=self.config.battery_config.ambient_temp_c,
                max_cell_temp_c=self.config.battery_config.max_cell_temp_c,
            )

            pack = BatteryPack(
                cell=cell,
                series=work_item.series,
                parallel=work_item.parallel,
                config=batt_config,
            )

            # Store pack info
            result.pack_voltage_nominal = pack.nominal_voltage
            result.pack_capacity_mah = pack.capacity_mah
            result.pack_energy_wh = pack.energy_wh
            result.pack_mass_kg = pack.get_mass_kg()
            result.energy_density_wh_kg = pack.get_energy_density_wh_kg()

            # -----------------------------------------------------------------
            # Step 2: Create Drag Model
            # -----------------------------------------------------------------
            drag_model = DragModel(
                method="fixed_wing",
                wing_area=self.config.wing_area,
                wingspan=self.config.wingspan,
                cd0=self.config.cd0,
                oswald_efficiency=self.config.oswald_efficiency,
                weight=self.config.weight,
            )

            # -----------------------------------------------------------------
            # Step 3: Register Motor
            # -----------------------------------------------------------------
            # Find motor in presets (motors is a dict: motor_name -> motor_data)
            motors_dict = self._motor_presets.get("motors", {})
            motor_data = motors_dict.get(work_item.motor_id)

            if motor_data is None:
                result.valid = False
                result.invalidity_reason = f"Unknown motor: {work_item.motor_id}"
                return result

            flight_solver.motor_analyzer.add_motor(work_item.motor_id, motor_data)

            # -----------------------------------------------------------------
            # Step 4: Solve Cruise with Voltage-Current Iteration
            # -----------------------------------------------------------------
            soc = self.config.battery_config.soc_for_analysis
            cruise_speeds = self.config.get_cruise_speeds()

            # Evaluate at all cruise speeds
            for cruise_speed in cruise_speeds:
                speed_result = self._solve_with_battery(
                    flight_solver=flight_solver,
                    motor_id=work_item.motor_id,
                    prop_id=work_item.prop_id,
                    pack=pack,
                    drag_model=drag_model,
                    airspeed=cruise_speed,
                    soc=soc,
                )

                if speed_result.valid:
                    # Check for NaN values
                    if math.isnan(speed_result.battery_current) or math.isnan(speed_result.battery_power):
                        speed_result.valid = False
                        speed_result.error_message = "Invalid current/power (NaN)"
                    else:
                        # Evaluate thermal at this speed
                        thermal = self._thermal_evaluator.evaluate_at_current(
                            pack, speed_result.battery_current, soc
                        )
                        speed_result.thermal_eval = thermal

                        # Calculate runtime at this speed
                        speed_result.runtime_minutes = pack.get_runtime_minutes(
                            speed_result.battery_current, start_soc=soc
                        )

                result.cruise_speed_results.append(speed_result)

            # Use first valid cruise result as primary
            valid_cruise_results = [r for r in result.cruise_speed_results if r.valid]
            if not valid_cruise_results:
                result.valid = False
                result.invalidity_reason = f"No valid cruise speed point"
                return result

            # Use the middle speed or first as the "primary" cruise result
            mid_idx = len(valid_cruise_results) // 2
            cruise_result = valid_cruise_results[mid_idx]
            result.cruise_result = cruise_result

            # -----------------------------------------------------------------
            # Step 5: Evaluate Thermal at Primary Cruise
            # -----------------------------------------------------------------
            cruise_thermal = cruise_result.thermal_eval
            result.cruise_thermal_valid = cruise_thermal.within_limits

            if not cruise_thermal.within_limits:
                result.valid = False
                result.invalidity_reason = f"Cruise exceeds thermal limit ({cruise_thermal.steady_state_temp_c:.1f}C)"
                return result

            # -----------------------------------------------------------------
            # Step 6: Calculate Runtime at Cruise
            # -----------------------------------------------------------------
            result.cruise_runtime_minutes = cruise_result.runtime_minutes

            # -----------------------------------------------------------------
            # Step 7: Find Max Speed (if enabled)
            # -----------------------------------------------------------------
            if self.config.evaluate_max_speed:
                max_speed_result = self._find_max_speed(
                    flight_solver=flight_solver,
                    motor_id=work_item.motor_id,
                    prop_id=work_item.prop_id,
                    pack=pack,
                    drag_model=drag_model,
                    soc=soc,
                )

                if max_speed_result is not None and max_speed_result.valid:
                    result.max_speed_result = max_speed_result
                    result.max_achievable_speed = max_speed_result.airspeed

                    # Evaluate thermal at max speed
                    max_thermal = self._thermal_evaluator.evaluate_at_current(
                        pack, max_speed_result.battery_current, soc
                    )
                    result.max_speed_result.thermal_eval = max_thermal
                    result.max_speed_thermal_valid = max_thermal.within_limits

                    # If max speed exceeds thermal, find limited throttle
                    if not max_thermal.within_limits:
                        safe_throttle, safe_current = self._thermal_evaluator.find_max_safe_throttle(
                            pack=pack,
                            soc=soc,
                            cruise_throttle=cruise_result.throttle,
                            cruise_current=cruise_result.battery_current,
                            max_throttle_current=max_speed_result.battery_current,
                        )
                        result.thermal_throttle_limit = safe_throttle

            # -----------------------------------------------------------------
            # Step 8: Compute Additional Metrics
            # -----------------------------------------------------------------
            result.power_density_w_kg = cruise_result.battery_power / self.config.weight

            # Mark as valid
            result.valid = True

        except Exception as e:
            result.valid = False
            result.invalidity_reason = f"Exception: {str(e)}"

        return result

    def _solve_with_battery(
        self,
        flight_solver: FlightSolver,
        motor_id: str,
        prop_id: str,
        pack,  # BatteryPack
        drag_model: DragModel,
        airspeed: float,
        soc: float,
    ) -> SpeedPointResult:
        """
        Solve cruise with voltage-current iteration.

        The challenge: FlightSolver needs voltage, but loaded voltage
        depends on current, which we don't know until we solve.

        Solution: Iterate until convergence.

        Parameters:
        ----------
        flight_solver : FlightSolver
            Flight solver instance
        motor_id : str
            Motor identifier
        prop_id : str
            Propeller identifier
        pack : BatteryPack
            Battery pack
        drag_model : DragModel
            Drag model
        airspeed : float
            Target airspeed (m/s)
        soc : float
            State of charge (%)

        Returns:
        -------
        SpeedPointResult
            Result at this speed point
        """
        result = SpeedPointResult(airspeed=airspeed)

        # Initial estimate: use nominal voltage
        v_estimate = pack.nominal_voltage
        converged = False
        final_flight_result = None

        for iteration in range(10):
            # Solve cruise at estimated voltage
            flight_result = flight_solver.solve_cruise(
                motor_id=motor_id,
                prop_id=prop_id,
                drag_model=drag_model,
                v_battery=v_estimate,
                airspeed=airspeed,
                altitude=self.config.altitude,
                winding_temp=self.config.winding_temp,
                num_motors=1,
            )

            if not flight_result.valid:
                result.valid = False
                result.error_message = flight_result.error_message or "Flight solver failed"
                return result

            # Get actual loaded voltage at this current
            v_loaded = pack.get_voltage_at_current(
                flight_result.battery_current, soc, pack.config.ambient_temp_c
            )

            # Check convergence (voltage within 0.1V)
            if abs(v_loaded - v_estimate) < 0.1:
                converged = True
                final_flight_result = flight_result
                break

            v_estimate = v_loaded

        if not converged:
            # Use last result anyway
            final_flight_result = flight_result

        if final_flight_result is None:
            result.valid = False
            result.error_message = "No valid solution found"
            return result

        # Copy results
        result.valid = True
        result.throttle = final_flight_result.throttle
        result.motor_current = final_flight_result.motor_current
        result.battery_current = final_flight_result.battery_current
        result.battery_power = final_flight_result.battery_power
        result.loaded_voltage = v_estimate
        result.system_efficiency = final_flight_result.system_efficiency
        result.motor_efficiency = final_flight_result.motor_efficiency
        result.prop_efficiency = final_flight_result.prop_efficiency
        result.prop_rpm = final_flight_result.prop_rpm
        result.drag = final_flight_result.drag

        return result

    def _find_max_speed(
        self,
        flight_solver: FlightSolver,
        motor_id: str,
        prop_id: str,
        pack,  # BatteryPack
        drag_model: DragModel,
        soc: float,
    ) -> Optional[SpeedPointResult]:
        """
        Find maximum achievable speed via binary search.

        Searches for the speed where throttle reaches 100%.

        Returns:
        -------
        SpeedPointResult or None
            Result at max speed, or None if search failed
        """
        speed_low = self.config.cruise_speed
        speed_high = 80.0  # m/s upper bound
        best_result: Optional[SpeedPointResult] = None

        for _ in range(15):  # Binary search iterations
            speed_mid = (speed_low + speed_high) / 2.0

            result = self._solve_with_battery(
                flight_solver=flight_solver,
                motor_id=motor_id,
                prop_id=prop_id,
                pack=pack,
                drag_model=drag_model,
                airspeed=speed_mid,
                soc=soc,
            )

            if result.valid and result.throttle <= 100.0:
                # Can achieve this speed
                best_result = result
                speed_low = speed_mid
            else:
                # Cannot achieve this speed
                speed_high = speed_mid

            if speed_high - speed_low < 0.5:
                break

        return best_result

    # =========================================================================
    # Batch Execution
    # =========================================================================

    def run_batch(
        self,
        progress_callback: Optional[Callable[[IntegratedProgress], None]] = None
    ) -> IntegratedBatchResult:
        """
        Run complete batch analysis using multiple CPU cores.

        Parameters:
        ----------
        progress_callback : Callable, optional
            Called periodically with progress updates

        Returns:
        -------
        IntegratedBatchResult
            Complete batch results
        """
        # Reset state
        self._cancel_event.clear()
        self.progress = IntegratedProgress()
        self.progress.is_running = True  # Set immediately to prevent race condition

        # Generate work items
        work_items = list(self._generate_work_items())
        self.progress.total = len(work_items)

        if len(work_items) == 0:
            self.progress.is_running = False
            return IntegratedBatchResult(
                config=self.config,
                total_combinations=0,
            )

        # Results storage
        results: List[IntegratedResult] = []
        start_time = time.time()
        last_update_time = start_time

        # Worker count - use CPU count for multiprocessing
        cpu_count = os.cpu_count() or 4
        num_workers = min(
            self.config.limits.max_workers,
            len(work_items),
            cpu_count
        )

        # Build context for workers (serializable data)
        worker_context = {
            'wing_area': self.config.wing_area,
            'wingspan': self.config.wingspan,
            'weight': self.config.weight,
            'cd0': self.config.cd0,
            'oswald_efficiency': self.config.oswald_efficiency,
            'ambient_temp_c': self.config.battery_config.ambient_temp_c,
            'max_cell_temp_c': self.config.battery_config.max_cell_temp_c,
            'soc_for_analysis': self.config.battery_config.soc_for_analysis,
            'cruise_speeds': self.config.get_cruise_speeds(),
            'evaluate_max_speed': self.config.evaluate_max_speed,
            'cruise_speed': self.config.cruise_speed,
            'altitude': self.config.altitude,
            'winding_temp': self.config.winding_temp,
            'motor_presets': self._motor_presets,
        }

        # Convert work items to tuples for efficient pickling
        work_tuples = [
            (wi.motor_id, wi.prop_id, wi.cell_type, wi.series, wi.parallel, wi.thermal_environment)
            for wi in work_items
        ]

        # Process with ProcessPoolExecutor for true multi-core parallelism
        with ProcessPoolExecutor(
            max_workers=num_workers,
            initializer=_init_worker_process,
            initargs=(worker_context,)
        ) as executor:
            # Submit all work items
            futures = {
                executor.submit(_worker_calculate, wt): work_items[i]
                for i, wt in enumerate(work_tuples)
            }

            # Process as completed
            for future in as_completed(futures):
                if self._cancel_event.is_set():
                    self.progress.is_cancelled = True
                    break

                try:
                    result = future.result(timeout=self.config.limits.timeout_per_calc)
                    results.append(result)

                    # Get work item for this future
                    work_item = futures[future]

                    # Update progress
                    with self._progress_lock:
                        self.progress.current += 1
                        self.progress.current_motor = work_item.motor_id
                        self.progress.current_prop = work_item.prop_id
                        self.progress.elapsed_seconds = time.time() - start_time

                        if result.valid:
                            self.progress.results_valid += 1
                            if result.thermal_throttle_limit is not None:
                                self.progress.results_thermal_limited += 1

                            # Track best
                            if result.cruise_result and result.cruise_result.system_efficiency > self.progress.best_efficiency:
                                self.progress.best_efficiency = result.cruise_result.system_efficiency
                                self.progress.best_combo = result.get_summary_string()

                            if result.cruise_runtime_minutes and result.cruise_runtime_minutes > self.progress.best_runtime:
                                self.progress.best_runtime = result.cruise_runtime_minutes
                        else:
                            self.progress.results_invalid += 1

                    # Callback
                    current_time = time.time()
                    if (progress_callback and
                        current_time - last_update_time >= self.config.limits.update_interval):
                        progress_callback(self.progress)
                        last_update_time = current_time

                except Exception as e:
                    # Handle timeout or exception
                    work_item = futures[future]
                    result = IntegratedResult(
                        motor_id=work_item.motor_id,
                        prop_id=work_item.prop_id,
                        cell_type=work_item.cell_type,
                        series=work_item.series,
                        parallel=work_item.parallel,
                        thermal_environment=work_item.thermal_environment,
                        valid=False,
                        invalidity_reason=f"Error: {str(e)}",
                    )
                    results.append(result)

                    with self._progress_lock:
                        self.progress.current += 1
                        self.progress.results_invalid += 1

        # Finalize
        self.progress.is_running = False
        self.progress.elapsed_seconds = time.time() - start_time

        # Final callback
        if progress_callback:
            progress_callback(self.progress)

        # Build batch result
        return self._build_batch_result(results)

    def _build_batch_result(self, results: List[IntegratedResult]) -> IntegratedBatchResult:
        """Build final batch result with statistics and best combinations."""
        batch_result = IntegratedBatchResult(
            config=self.config,
            results=results,
            total_combinations=len(results),
            elapsed_seconds=self.progress.elapsed_seconds,
        )

        # Count statistics
        for result in results:
            if result.valid:
                batch_result.valid_combinations += 1
                if result.thermal_throttle_limit is not None:
                    batch_result.thermal_limited_count += 1

                # Count limiting factors at cruise
                if result.cruise_result.thermal_eval.limiting_factor == "thermal":
                    pass  # Already counted in thermal_limited
                elif result.cruise_result.thermal_eval.limiting_factor == "rating":
                    batch_result.rating_limited_count += 1
                elif result.cruise_result.thermal_eval.limiting_factor == "voltage":
                    batch_result.voltage_limited_count += 1

        # Find best combinations
        valid_results = [r for r in results if r.valid]

        if valid_results:
            # Best by efficiency
            batch_result.best_by_efficiency = max(
                valid_results,
                key=lambda r: r.cruise_result.system_efficiency
            )

            # Best by runtime
            batch_result.best_by_runtime = max(
                valid_results,
                key=lambda r: r.cruise_runtime_minutes
            )

            # Best by max speed
            results_with_max = [r for r in valid_results if r.max_achievable_speed > 0]
            if results_with_max:
                batch_result.best_by_max_speed = max(
                    results_with_max,
                    key=lambda r: r.max_achievable_speed
                )

            # Best by power density
            batch_result.best_by_power_density = max(
                valid_results,
                key=lambda r: r.power_density_w_kg
            )

        return batch_result

    def cancel(self):
        """Cancel running batch."""
        self._cancel_event.set()
