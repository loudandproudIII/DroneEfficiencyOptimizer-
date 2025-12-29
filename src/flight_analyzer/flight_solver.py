"""
Flight Equilibrium Solver Module
================================

This module solves for complete flight equilibrium by integrating:
- Airframe drag model
- Propeller performance
- Motor performance

For level cruise flight, the equilibrium condition is:
    Thrust = Drag

The solver finds the throttle setting, motor current, and system
efficiency required to maintain a given airspeed.

Classes:
--------
- FlightResult: Dataclass holding complete solution
- FlightSolver: Main solver class

Usage:
------
    from src.flight_analyzer import FlightSolver, DragModel

    solver = FlightSolver()

    # Configure drag
    drag_model = DragModel(method="coefficient", cd=0.5, reference_area=0.02)

    # Solve cruise condition
    result = solver.solve_cruise(
        motor_id="Scorpion SII-3014-830",
        prop_id="10x5",
        drag_model=drag_model,
        v_battery=22.2,
        airspeed=20.0
    )

    print(f"Throttle: {result.throttle:.1f}%")
    print(f"Current: {result.current:.1f} A")
    print(f"System Efficiency: {result.system_efficiency:.1%}")
"""

import math
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
import sys
from pathlib import Path

# Add parent for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from .config import FlightAnalyzerConfig, DEFAULT_CONFIG
from .drag_model import DragModel

# Import motor and prop analyzers
from src.motor_analyzer.core import MotorAnalyzer
from src.motor_analyzer.config import MotorAnalyzerConfig

from src.prop_analyzer.core import PropAnalyzer
from src.prop_analyzer.config import PropAnalyzerConfig


@dataclass
class FlightResult:
    """
    Complete flight equilibrium solution.

    Contains all operating parameters for the motor-prop-airframe system
    at equilibrium flight conditions.

    Attributes:
    ----------
    valid : bool
        Whether a valid solution was found

    # Flight Conditions
    airspeed : float
        Flight speed (m/s)

    altitude : float
        Flight altitude (m)

    # Drag
    drag : float
        Total drag (N)

    thrust_required : float
        Required thrust (N) - equals drag for level flight

    # Propeller Performance
    prop_rpm : float
        Propeller RPM at equilibrium

    prop_power : float
        Propeller shaft power (W)

    prop_efficiency : float
        Propeller efficiency (0-1)

    # Motor Performance
    motor_rpm : float
        Motor RPM (same as prop for direct drive)

    motor_current : float
        Motor current (A)

    motor_voltage : float
        Motor terminal voltage (V)

    motor_power_elec : float
        Motor electrical input power (W)

    motor_power_mech : float
        Motor mechanical output power (W)

    motor_efficiency : float
        Motor efficiency (0-1)

    motor_torque : float
        Motor torque (Nm)

    # System Totals
    throttle : float
        Required throttle (0-100%)

    battery_current : float
        Battery current draw (A)

    battery_power : float
        Battery power (W)

    system_efficiency : float
        Overall system efficiency (0-1)
        = (Thrust × Velocity) / Battery_Power

    # Multi-motor support
    num_motors : int
        Number of motors (for multi-rotor)

    per_motor_current : float
        Current per motor (A)

    per_motor_thrust : float
        Thrust per motor (N)
    """

    valid: bool = False
    error_message: str = ""

    # Flight conditions
    airspeed: float = 0.0
    altitude: float = 0.0

    # Drag
    drag: float = 0.0
    thrust_required: float = 0.0

    # Propeller
    prop_id: str = ""
    prop_rpm: float = 0.0
    prop_power: float = 0.0
    prop_efficiency: float = 0.0

    # Motor
    motor_id: str = ""
    motor_rpm: float = 0.0
    motor_current: float = 0.0
    motor_voltage: float = 0.0
    motor_power_elec: float = 0.0
    motor_power_mech: float = 0.0
    motor_efficiency: float = 0.0
    motor_torque: float = 0.0

    # System
    throttle: float = 0.0
    battery_voltage: float = 0.0
    battery_current: float = 0.0
    battery_power: float = 0.0
    system_efficiency: float = 0.0

    # Multi-motor
    num_motors: int = 1
    per_motor_current: float = 0.0
    per_motor_thrust: float = 0.0

    def summary(self) -> str:
        """Generate a formatted summary string."""
        if not self.valid:
            return f"Invalid Solution: {self.error_message}"

        return (
            f"Flight Equilibrium @ {self.airspeed:.1f} m/s\n"
            f"{'='*50}\n"
            f"Drag/Thrust: {self.drag:.2f} N\n"
            f"Throttle: {self.throttle:.1f}%\n"
            f"RPM: {self.prop_rpm:.0f}\n"
            f"{'='*50}\n"
            f"Motor: {self.motor_current:.1f}A, {self.motor_efficiency*100:.1f}% eff\n"
            f"Prop: {self.prop_power:.0f}W, {self.prop_efficiency*100:.1f}% eff\n"
            f"{'='*50}\n"
            f"Battery: {self.battery_current:.1f}A, {self.battery_power:.0f}W\n"
            f"System Efficiency: {self.system_efficiency*100:.1f}%\n"
        )


class FlightSolver:
    """
    Flight equilibrium solver.

    Integrates drag model, propeller analyzer, and motor analyzer to
    solve for complete flight equilibrium.

    The solver finds the operating point where:
    - Thrust (from prop) = Drag (from airframe)
    - Motor provides required power to prop
    - All components operate within limits

    Attributes:
    ----------
    config : FlightAnalyzerConfig
        Configuration settings

    motor_analyzer : MotorAnalyzer
        Motor performance calculator

    prop_analyzer : PropAnalyzer
        Propeller performance calculator

    Example:
    -------
        solver = FlightSolver()

        drag_model = DragModel(method="coefficient", cd=0.5, reference_area=0.02)

        result = solver.solve_cruise(
            motor_id="MyMotor",
            prop_id="10x5",
            drag_model=drag_model,
            v_battery=22.2,
            airspeed=20.0,
            num_motors=4
        )
    """

    def __init__(self, config: Optional[FlightAnalyzerConfig] = None):
        """
        Initialize the FlightSolver.

        Parameters:
        ----------
        config : FlightAnalyzerConfig, optional
            Configuration settings
        """
        self.config = config if config is not None else DEFAULT_CONFIG

        # Initialize sub-analyzers
        self.motor_analyzer = MotorAnalyzer()
        self.prop_analyzer = PropAnalyzer()

    def solve_cruise(
        self,
        motor_id: str,
        prop_id: str,
        drag_model: DragModel,
        v_battery: float,
        airspeed: float,
        altitude: float = 0.0,
        winding_temp: float = 80.0,
        num_motors: int = 1
    ) -> FlightResult:
        """
        Solve for cruise flight equilibrium.

        For level cruise: Thrust = Drag

        Parameters:
        ----------
        motor_id : str
            Motor identifier (must be registered with motor_analyzer)

        prop_id : str
            Propeller identifier

        drag_model : DragModel
            Configured drag model

        v_battery : float
            Battery voltage (V)

        airspeed : float
            Target cruise airspeed (m/s)

        altitude : float
            Flight altitude (m)

        winding_temp : float
            Motor winding temperature (°C)

        num_motors : int
            Number of motors (thrust is divided among them)

        Returns:
        -------
        FlightResult
            Complete solution with all operating parameters
        """
        result = FlightResult(
            airspeed=airspeed,
            altitude=altitude,
            battery_voltage=v_battery,
            motor_id=motor_id,
            prop_id=prop_id,
            num_motors=num_motors,
        )

        try:
            # Step 1: Calculate drag at cruise speed
            drag = drag_model.calculate_drag(airspeed, altitude)
            result.drag = drag
            result.thrust_required = drag  # Level flight: T = D

            # Thrust per motor/prop
            thrust_per_motor = drag / num_motors
            result.per_motor_thrust = thrust_per_motor

            # Step 2: Find prop operating point for required thrust
            prop_result = self.prop_analyzer.get_power_from_thrust_speed(
                prop_id, thrust_per_motor, airspeed, return_rpm=True
            )

            if prop_result is None:
                result.error_message = (
                    f"Propeller {prop_id} cannot produce {thrust_per_motor:.2f}N "
                    f"thrust at {airspeed:.1f} m/s"
                )
                return result

            prop_power, prop_rpm = prop_result
            result.prop_rpm = prop_rpm
            result.prop_power = prop_power

            # Get prop efficiency
            prop_efficiency = self.prop_analyzer.get_efficiency(
                prop_id, airspeed, prop_rpm
            )
            result.prop_efficiency = prop_efficiency

            # Step 3: Calculate motor operating point at this RPM/power
            # Motor RPM = Prop RPM (direct drive assumed)
            motor_rpm = prop_rpm
            result.motor_rpm = motor_rpm

            # Get motor state at this RPM
            motor_state = self.motor_analyzer.get_state_at_rpm(
                motor_id, v_battery, motor_rpm, winding_temp
            )

            if not motor_state.get('valid', True):
                result.error_message = f"Motor cannot operate at {motor_rpm:.0f} RPM"
                return result

            result.motor_current = motor_state['current']
            result.motor_power_elec = motor_state['p_elec']
            result.motor_power_mech = motor_state['p_mech']
            result.motor_efficiency = motor_state['efficiency']
            result.motor_torque = motor_state['torque']

            # Step 4: Calculate throttle
            motor = self.motor_analyzer.get_motor(motor_id)
            rm = self.motor_analyzer.config.resistance_at_temp(
                motor.rm_cold, winding_temp
            )
            v_bemf = motor_rpm / motor.kv
            v_motor_needed = v_bemf + motor_state['current'] * rm

            throttle = (v_motor_needed / v_battery) * 100.0
            result.throttle = throttle
            result.motor_voltage = v_motor_needed

            # Step 5: Check motor limits
            if motor_state['current'] > motor.i_max:
                result.error_message = (
                    f"Motor current ({motor_state['current']:.1f}A) exceeds "
                    f"limit ({motor.i_max:.0f}A)"
                )
                # Still return partial result but mark as concerning

            if throttle > 100:
                result.error_message = (
                    f"Required throttle ({throttle:.1f}%) exceeds 100%. "
                    "Need higher voltage or different motor/prop."
                )
                # Still return partial result

            # Step 6: Calculate system totals (for all motors)
            result.per_motor_current = motor_state['current']
            result.battery_current = motor_state['current'] * num_motors
            result.battery_power = motor_state['p_elec'] * num_motors

            # System efficiency = useful_power / battery_power
            # Useful power = Thrust × Velocity
            useful_power = drag * airspeed
            if result.battery_power > 0:
                result.system_efficiency = useful_power / result.battery_power
            else:
                result.system_efficiency = 0

            result.valid = True

        except Exception as e:
            result.error_message = str(e)
            result.valid = False

        return result

    def solve_throttle_sweep(
        self,
        motor_id: str,
        prop_id: str,
        drag_model: DragModel,
        v_battery: float,
        altitude: float = 0.0,
        winding_temp: float = 80.0,
        num_motors: int = 1,
        throttle_range: tuple = (20, 100),
        num_points: int = 20
    ) -> List[Dict[str, float]]:
        """
        Sweep throttle settings and calculate resulting flight conditions.

        Useful for understanding the performance envelope.

        Parameters:
        ----------
        motor_id : str
            Motor identifier

        prop_id : str
            Propeller identifier

        drag_model : DragModel
            Drag model

        v_battery : float
            Battery voltage

        altitude : float
            Flight altitude

        winding_temp : float
            Motor winding temperature

        num_motors : int
            Number of motors

        throttle_range : tuple
            (min_throttle, max_throttle) in percent

        num_points : int
            Number of points in sweep

        Returns:
        -------
        list
            List of dicts with performance at each throttle setting
        """
        import numpy as np

        results = []
        throttles = np.linspace(throttle_range[0], throttle_range[1], num_points)

        motor = self.motor_analyzer.get_motor(motor_id)

        for throttle in throttles:
            v_motor = v_battery * (throttle / 100.0)

            # Iterate to find equilibrium airspeed at this throttle
            # Start with a guess and iterate

            airspeed_guess = 10.0
            for _ in range(30):
                # Get prop thrust at current guess
                rpm_guess = motor.kv * v_motor * 0.85

                # Try to find equilibrium
                try:
                    # Get max thrust from prop at this voltage
                    thrust = self.prop_analyzer.get_thrust_from_rpm_speed(
                        prop_id, airspeed_guess, rpm_guess
                    )

                    if thrust < 0:
                        break

                    total_thrust = thrust * num_motors

                    # What airspeed gives this drag?
                    # D = 0.5 * rho * V^2 * Cd * A
                    # Solve for V: V = sqrt(2D / (rho * Cd * A))
                    drag_for_airspeed = drag_model.calculate_drag(
                        airspeed_guess, altitude
                    )

                    # If thrust > drag, speed will increase, if thrust < drag, decrease
                    if abs(total_thrust - drag_for_airspeed) < 0.1:
                        break

                    # Adjust airspeed
                    if total_thrust > drag_for_airspeed:
                        airspeed_guess *= 1.05
                    else:
                        airspeed_guess *= 0.95

                    # Clamp to reasonable range
                    airspeed_guess = max(1, min(100, airspeed_guess))

                except Exception:
                    break

            # Record result at this throttle
            try:
                result = self.solve_cruise(
                    motor_id, prop_id, drag_model, v_battery,
                    airspeed_guess, altitude, winding_temp, num_motors
                )

                results.append({
                    'throttle': throttle,
                    'airspeed': result.airspeed if result.valid else 0,
                    'thrust': result.thrust_required if result.valid else 0,
                    'current': result.battery_current if result.valid else 0,
                    'power': result.battery_power if result.valid else 0,
                    'efficiency': result.system_efficiency if result.valid else 0,
                    'valid': result.valid
                })
            except Exception:
                results.append({
                    'throttle': throttle,
                    'airspeed': 0,
                    'thrust': 0,
                    'current': 0,
                    'power': 0,
                    'efficiency': 0,
                    'valid': False
                })

        return results

    def solve_speed_sweep(
        self,
        motor_id: str,
        prop_id: str,
        drag_model: DragModel,
        v_battery: float,
        speed_range: tuple = (5, 40),
        altitude: float = 0.0,
        winding_temp: float = 80.0,
        num_motors: int = 1,
        num_points: int = 20
    ) -> List[FlightResult]:
        """
        Sweep airspeeds and solve for required throttle at each.

        Parameters:
        ----------
        motor_id : str
            Motor identifier

        prop_id : str
            Propeller identifier

        drag_model : DragModel
            Drag model

        v_battery : float
            Battery voltage

        speed_range : tuple
            (min_speed, max_speed) in m/s

        altitude : float
            Flight altitude

        winding_temp : float
            Motor winding temperature

        num_motors : int
            Number of motors

        num_points : int
            Number of speed points

        Returns:
        -------
        list
            List of FlightResult objects for each speed
        """
        import numpy as np

        results = []
        speeds = np.linspace(speed_range[0], speed_range[1], num_points)

        for speed in speeds:
            result = self.solve_cruise(
                motor_id, prop_id, drag_model, v_battery,
                speed, altitude, winding_temp, num_motors
            )
            results.append(result)

        return results

    def find_max_speed(
        self,
        motor_id: str,
        prop_id: str,
        drag_model: DragModel,
        v_battery: float,
        altitude: float = 0.0,
        winding_temp: float = 80.0,
        num_motors: int = 1
    ) -> FlightResult:
        """
        Find maximum achievable airspeed (at 100% throttle).

        Parameters:
        ----------
        motor_id : str
            Motor identifier

        prop_id : str
            Propeller identifier

        drag_model : DragModel
            Drag model

        v_battery : float
            Battery voltage

        altitude : float
            Flight altitude

        winding_temp : float
            Motor winding temperature

        num_motors : int
            Number of motors

        Returns:
        -------
        FlightResult
            Solution at maximum speed
        """
        # Binary search for max speed
        speed_low = 1.0
        speed_high = 100.0

        best_result = None

        for _ in range(20):  # Binary search iterations
            speed_mid = (speed_low + speed_high) / 2

            result = self.solve_cruise(
                motor_id, prop_id, drag_model, v_battery,
                speed_mid, altitude, winding_temp, num_motors
            )

            if result.valid and result.throttle <= 100:
                best_result = result
                speed_low = speed_mid
            else:
                speed_high = speed_mid

            if speed_high - speed_low < 0.1:
                break

        if best_result is None:
            best_result = FlightResult(
                valid=False,
                error_message="Could not find valid max speed"
            )

        return best_result

    def find_best_efficiency_speed(
        self,
        motor_id: str,
        prop_id: str,
        drag_model: DragModel,
        v_battery: float,
        altitude: float = 0.0,
        winding_temp: float = 80.0,
        num_motors: int = 1
    ) -> FlightResult:
        """
        Find the airspeed that maximizes system efficiency.

        Parameters:
        ----------
        (same as solve_cruise)

        Returns:
        -------
        FlightResult
            Solution at best efficiency speed
        """
        # Sweep speeds and find max efficiency
        results = self.solve_speed_sweep(
            motor_id, prop_id, drag_model, v_battery,
            speed_range=(5, 50), altitude=altitude,
            winding_temp=winding_temp, num_motors=num_motors,
            num_points=30
        )

        best_result = None
        best_efficiency = 0

        for result in results:
            if result.valid and result.system_efficiency > best_efficiency:
                best_efficiency = result.system_efficiency
                best_result = result

        if best_result is None:
            return FlightResult(
                valid=False,
                error_message="Could not find best efficiency speed"
            )

        return best_result
