"""
Motor Analyzer Core Module
==========================

This module provides the core calculation functions for brushless DC motor
performance analysis using an equivalent circuit model.

The model includes:
- Back-EMF based speed-voltage relationship
- Temperature-dependent winding resistance
- RPM-dependent no-load current (iron losses)
- Optional magnetic saturation correction

Classes:
--------
- MotorAnalyzer: Main class for motor performance calculations

Theory Background:
-----------------
The brushless motor is modeled as an equivalent circuit:

    V_supply ──┬── Rm ──┬── V_bemf
               │        │
             I_total   Load

Where:
- V_bemf = RPM / Kv (back electromotive force)
- I_total = (V_supply - V_bemf) / Rm
- I_torque = I_total - I0 (current producing torque)
- Torque = I_torque × Kt

The torque constant Kt relates to velocity constant Kv:
- Kt [Nm/A] = 30 / (π × Kv [RPM/V])
"""

import json
import math
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass

import numpy as np

from .config import MotorAnalyzerConfig, DEFAULT_CONFIG


@dataclass
class MotorParameters:
    """
    Data class holding motor specification parameters.

    All parameters should be measured or from manufacturer datasheet.
    See the spec document for measurement procedures.

    Attributes:
    ----------
    kv : float
        Motor velocity constant (RPM/V)

    rm_cold : float
        Phase-to-phase winding resistance at reference temp (Ω)

    i0_ref : float
        No-load current at reference RPM (A)

    i0_rpm_ref : float
        RPM at which I0 was measured

    temp_ref : float
        Temperature at which Rm was measured (°C)

    i_max : float
        Maximum continuous current rating (A)

    p_max : float
        Maximum continuous power rating (W)

    poles : int
        Number of magnetic poles (optional, for info)

    mass_g : float
        Motor mass in grams (optional, for info)
    """
    kv: float
    rm_cold: float
    i0_ref: float
    i0_rpm_ref: float
    temp_ref: float = 25.0
    i_max: float = 50.0
    p_max: float = 1000.0
    poles: int = 14
    mass_g: float = 100.0
    source: str = "user"

    @property
    def kt(self) -> float:
        """Calculate torque constant from Kv."""
        return 30.0 / (math.pi * self.kv)


class MotorAnalyzer:
    """
    Brushless DC motor performance analyzer.

    This class provides methods to calculate motor performance based on
    operating conditions using an equivalent circuit model with corrections
    for temperature and RPM-dependent losses.

    Attributes:
    ----------
    config : MotorAnalyzerConfig
        Configuration object containing settings and physical constants.

    _motors : dict
        Dictionary of loaded motor parameters, keyed by motor_id.

    Example:
    -------
        analyzer = MotorAnalyzer()

        # Add a motor
        analyzer.add_motor("TestMotor", {
            "kv": 1000,
            "rm_cold": 0.020,
            "i0_ref": 2.0,
            "i0_rpm_ref": 10000,
            "i_max": 50,
            "p_max": 800
        })

        # Calculate operating point
        state = analyzer.solve_operating_point(
            "TestMotor",
            v_supply=14.8,
            torque_load=0.3
        )
    """

    def __init__(self, config: Optional[MotorAnalyzerConfig] = None):
        """
        Initialize the MotorAnalyzer with configuration settings.

        Parameters:
        ----------
        config : MotorAnalyzerConfig, optional
            Configuration object specifying settings.
            If None, uses the default configuration.
        """
        # Use provided config or fall back to default
        self.config = config if config is not None else DEFAULT_CONFIG

        # Motor database (loaded on demand or added by user)
        self._motors: Dict[str, MotorParameters] = {}

        # Try to load default database if it exists
        self._load_database_if_exists()

    # =========================================================================
    # Database Management
    # =========================================================================

    def _load_database_if_exists(self):
        """Load motor database from JSON file if it exists."""
        if self.config.database_path.exists():
            try:
                self.load_database(self.config.database_path)
            except Exception as e:
                print(f"Warning: Could not load motor database: {e}")

    def load_database(self, filepath: Optional[Path] = None):
        """
        Load motors from a JSON database file.

        Parameters:
        ----------
        filepath : Path, optional
            Path to JSON database file. Uses config default if not specified.

        Raises:
        ------
        FileNotFoundError
            If the database file does not exist.

        ValueError
            If the database format is invalid.
        """
        if filepath is None:
            filepath = self.config.database_path

        if not filepath.exists():
            raise FileNotFoundError(f"Motor database not found: {filepath}")

        with open(filepath, 'r') as f:
            data = json.load(f)

        # Parse motors from database
        motors_data = data.get("motors", data)

        for motor_id, params in motors_data.items():
            self.add_motor(motor_id, params)

    def add_motor(self, motor_id: str, params: Dict[str, Any]):
        """
        Add a motor to the runtime database.

        Parameters:
        ----------
        motor_id : str
            Unique identifier for the motor.

        params : dict
            Motor parameters. Required keys:
            - kv: Velocity constant (RPM/V)
            - rm_cold: Winding resistance at ref temp (Ω)
            - i0_ref: No-load current at ref RPM (A)
            - i0_rpm_ref: Reference RPM for I0 measurement

            Optional keys:
            - temp_ref: Reference temperature (°C), default 25
            - i_max: Maximum current (A), default 50
            - p_max: Maximum power (W), default 1000
            - poles: Number of poles, default 14
            - mass_g: Mass in grams, default 100

        Example:
        -------
            analyzer.add_motor("MyMotor", {
                "kv": 1000,
                "rm_cold": 0.020,
                "i0_ref": 2.0,
                "i0_rpm_ref": 10000,
                "i_max": 50,
                "p_max": 800
            })
        """
        # Create MotorParameters from dict
        motor = MotorParameters(
            kv=float(params["kv"]),
            rm_cold=float(params["rm_cold"]),
            i0_ref=float(params["i0_ref"]),
            i0_rpm_ref=float(params["i0_rpm_ref"]),
            temp_ref=float(params.get("temp_ref", 25.0)),
            i_max=float(params.get("i_max", 50.0)),
            p_max=float(params.get("p_max", 1000.0)),
            poles=int(params.get("poles", 14)),
            mass_g=float(params.get("mass_g", 100.0)),
            source=str(params.get("source", "user"))
        )

        self._motors[motor_id] = motor

    def get_motor(self, motor_id: str) -> MotorParameters:
        """
        Get motor parameters by ID.

        Parameters:
        ----------
        motor_id : str
            Motor identifier.

        Returns:
        -------
        MotorParameters
            Motor parameter object.

        Raises:
        ------
        KeyError
            If motor_id is not found.
        """
        if motor_id not in self._motors:
            available = list(self._motors.keys())
            raise KeyError(
                f"Motor '{motor_id}' not found. "
                f"Available motors: {available}"
            )
        return self._motors[motor_id]

    def list_available_motors(self) -> List[str]:
        """
        Get a list of all available motor IDs.

        Returns:
        -------
        list
            Sorted list of motor identifiers.
        """
        return sorted(self._motors.keys())

    # =========================================================================
    # Core Calculation Methods
    # =========================================================================

    def _get_resistance_at_temp(
        self,
        motor: MotorParameters,
        winding_temp: float
    ) -> float:
        """
        Calculate winding resistance at operating temperature.

        Parameters:
        ----------
        motor : MotorParameters
            Motor parameters.

        winding_temp : float
            Winding temperature in °C.

        Returns:
        -------
        float
            Resistance in Ohms.
        """
        return self.config.resistance_at_temp(motor.rm_cold, winding_temp)

    def _get_i0_at_rpm(self, motor: MotorParameters, rpm: float) -> float:
        """
        Calculate no-load current at operating RPM.

        Parameters:
        ----------
        motor : MotorParameters
            Motor parameters.

        rpm : float
            Operating RPM.

        Returns:
        -------
        float
            No-load current in Amps.
        """
        return self.config.i0_at_rpm(motor.i0_ref, motor.i0_rpm_ref, rpm)

    def _get_kt_effective(
        self,
        motor: MotorParameters,
        current: float
    ) -> float:
        """
        Calculate effective torque constant with saturation correction.

        At high currents, magnetic saturation reduces the effective Kt:
            Kt_eff = Kt × (1 - k_sat × (I / I_rated)²)

        Parameters:
        ----------
        motor : MotorParameters
            Motor parameters.

        current : float
            Motor current in Amps.

        Returns:
        -------
        float
            Effective Kt in Nm/A.
        """
        kt_base = motor.kt

        if not self.config.enable_saturation_correction:
            return kt_base

        # Saturation correction factor
        current_ratio = current / motor.i_max
        saturation_factor = 1.0 - self.config.saturation_coeff * (current_ratio ** 2)

        # Clamp to reasonable range
        saturation_factor = max(0.8, min(1.0, saturation_factor))

        return kt_base * saturation_factor

    def get_state_at_rpm(
        self,
        motor_id: str,
        v_supply: float,
        rpm: float,
        winding_temp: Optional[float] = None
    ) -> Dict[str, float]:
        """
        Calculate motor state when RPM is known.

        This is the direct calculation method used when the propeller
        or load has already determined the operating RPM.

        Parameters:
        ----------
        motor_id : str
            Motor identifier.

        v_supply : float
            Supply voltage (V).

        rpm : float
            Operating RPM.

        winding_temp : float, optional
            Winding temperature (°C). Uses config default if not specified.

        Returns:
        -------
        dict
            Motor state with keys:
            - rpm: Operating RPM
            - current: Motor current (A)
            - torque: Output torque (Nm)
            - p_elec: Electrical input power (W)
            - p_mech: Mechanical output power (W)
            - efficiency: Motor efficiency (0-1)
            - p_loss_copper: I²R copper losses (W)
            - p_loss_iron: Iron/no-load losses (W)
            - v_bemf: Back-EMF voltage (V)
            - i_torque: Torque-producing current (A)

        Example:
        -------
            state = analyzer.get_state_at_rpm("MyMotor", 14.8, 12000)
            print(f"Current: {state['current']:.1f} A")
            print(f"Efficiency: {state['efficiency']:.1%}")
        """
        # Get motor parameters
        motor = self.get_motor(motor_id)

        # Use default temperature if not specified
        if winding_temp is None:
            winding_temp = self.config.default_winding_temp

        # Calculate temperature-corrected resistance
        rm = self._get_resistance_at_temp(motor, winding_temp)

        # Calculate back-EMF voltage
        # V_bemf = RPM / Kv
        v_bemf = rpm / motor.kv

        # Check if operating point is valid
        if v_bemf >= v_supply:
            # Motor cannot run at this RPM with given voltage
            return self._create_invalid_state(rpm, "V_bemf >= V_supply")

        # Calculate total current
        # I_total = (V_supply - V_bemf) / Rm
        current = (v_supply - v_bemf) / rm

        # Calculate no-load current at this RPM
        i0 = self._get_i0_at_rpm(motor, rpm)

        # Calculate torque-producing current
        i_torque = current - i0

        # Get effective Kt (with optional saturation correction)
        kt = self._get_kt_effective(motor, current)

        # Calculate torque
        # Torque = I_torque × Kt
        torque = i_torque * kt

        # Calculate powers
        p_elec = v_supply * current  # Electrical input
        p_mech = torque * (rpm * math.pi / 30.0)  # Mechanical output

        # Calculate losses
        p_loss_copper = current ** 2 * rm  # I²R losses
        p_loss_iron = i0 * v_bemf  # Iron losses (approximation)

        # Calculate efficiency
        if p_elec > 0:
            efficiency = p_mech / p_elec
        else:
            efficiency = 0.0

        # Clamp efficiency to valid range
        efficiency = max(0.0, min(1.0, efficiency))

        return {
            "rpm": rpm,
            "current": current,
            "torque": torque,
            "p_elec": p_elec,
            "p_mech": p_mech,
            "efficiency": efficiency,
            "p_loss_copper": p_loss_copper,
            "p_loss_iron": p_loss_iron,
            "v_bemf": v_bemf,
            "i_torque": i_torque,
            "i0": i0,
            "rm": rm,
            "valid": True
        }

    def solve_operating_point(
        self,
        motor_id: str,
        v_supply: float,
        torque_load: float,
        winding_temp: Optional[float] = None
    ) -> Optional[Dict[str, float]]:
        """
        Find equilibrium operating point for a given load torque.

        Uses iterative solution since RPM and no-load current are coupled.
        The motor will settle at the RPM where motor torque equals load torque.

        Parameters:
        ----------
        motor_id : str
            Motor identifier.

        v_supply : float
            Supply voltage (V).

        torque_load : float
            Load torque requirement (Nm).

        winding_temp : float, optional
            Winding temperature (°C). Uses config default if not specified.

        Returns:
        -------
        dict or None
            Motor state dict (same keys as get_state_at_rpm).
            Returns None if no valid operating point exists.

        Algorithm:
        ---------
        1. Initial guess: RPM = Kv × V_supply × 0.8
        2. Iterate until convergence:
           a. Calculate motor state at current RPM guess
           b. Calculate torque error (motor torque - load torque)
           c. Adjust RPM based on torque error
           d. Check convergence
        3. Return final state

        Example:
        -------
            state = analyzer.solve_operating_point(
                "MyMotor",
                v_supply=14.8,
                torque_load=0.3
            )
            if state:
                print(f"Equilibrium at {state['rpm']:.0f} RPM")
        """
        # Get motor parameters
        motor = self.get_motor(motor_id)

        # Use default temperature if not specified
        if winding_temp is None:
            winding_temp = self.config.default_winding_temp

        # Calculate temperature-corrected resistance
        rm = self._get_resistance_at_temp(motor, winding_temp)

        # Get Kt for torque calculations
        kt = motor.kt

        # Initial RPM guess (80% of no-load speed)
        rpm = motor.kv * v_supply * 0.8

        # Iterative solver
        for iteration in range(self.config.solver_max_iterations):
            # Calculate no-load current at current RPM
            i0 = self._get_i0_at_rpm(motor, rpm)

            # Calculate back-EMF
            v_bemf = rpm / motor.kv

            # Calculate current from voltage balance
            if v_supply <= v_bemf:
                # Motor would need to be a generator
                rpm = rpm * 0.9  # Reduce RPM guess
                continue

            current = (v_supply - v_bemf) / rm

            # Calculate torque-producing current
            i_torque = current - i0

            # Calculate motor torque
            kt_eff = self._get_kt_effective(motor, current)
            torque_motor = i_torque * kt_eff

            # Calculate torque error
            torque_error = torque_motor - torque_load

            # Check for excessive current
            if current > motor.i_max * 1.5:
                # Operating point requires too much current
                return None

            # Check convergence
            # Use torque error to estimate RPM correction
            # ∂Torque/∂RPM ≈ -Kt/(Rm × Kv)
            d_torque_d_rpm = -kt / (rm * motor.kv)

            if abs(d_torque_d_rpm) > 1e-10:
                rpm_correction = -torque_error / d_torque_d_rpm
            else:
                rpm_correction = 0

            # Apply damping for stability
            rpm_new = rpm + self.config.solver_damping * rpm_correction

            # Ensure RPM stays positive and reasonable
            rpm_new = max(100, min(motor.kv * v_supply * 1.1, rpm_new))

            # Check convergence
            if abs(rpm_new - rpm) < self.config.solver_rpm_tolerance:
                # Converged - return final state
                return self.get_state_at_rpm(
                    motor_id, v_supply, rpm_new, winding_temp
                )

            rpm = rpm_new

        # Failed to converge
        print(f"Warning: Solver did not converge after "
              f"{self.config.solver_max_iterations} iterations")
        return self.get_state_at_rpm(motor_id, v_supply, rpm, winding_temp)

    def get_torque_from_current(
        self,
        motor_id: str,
        current: float,
        rpm: float
    ) -> float:
        """
        Calculate output torque for a given current and RPM.

        Parameters:
        ----------
        motor_id : str
            Motor identifier.

        current : float
            Motor current (A).

        rpm : float
            Operating RPM.

        Returns:
        -------
        float
            Output torque (Nm).

        Example:
        -------
            torque = analyzer.get_torque_from_current("MyMotor", 25.0, 10000)
        """
        motor = self.get_motor(motor_id)

        # Get no-load current at this RPM
        i0 = self._get_i0_at_rpm(motor, rpm)

        # Calculate torque-producing current
        i_torque = current - i0

        # Get effective Kt
        kt = self._get_kt_effective(motor, current)

        return i_torque * kt

    def get_current_from_torque(
        self,
        motor_id: str,
        torque: float,
        rpm: float
    ) -> float:
        """
        Calculate current required for a given torque and RPM.

        Parameters:
        ----------
        motor_id : str
            Motor identifier.

        torque : float
            Required torque (Nm).

        rpm : float
            Operating RPM.

        Returns:
        -------
        float
            Required current (A).
        """
        motor = self.get_motor(motor_id)

        # Get no-load current at this RPM
        i0 = self._get_i0_at_rpm(motor, rpm)

        # Calculate torque-producing current needed
        i_torque = torque / motor.kt

        return i_torque + i0

    def get_max_torque_at_rpm(
        self,
        motor_id: str,
        rpm: float,
        winding_temp: Optional[float] = None
    ) -> float:
        """
        Calculate maximum available torque at given RPM.

        This is the torque produced at maximum rated current.

        Parameters:
        ----------
        motor_id : str
            Motor identifier.

        rpm : float
            Operating RPM.

        winding_temp : float, optional
            Winding temperature (°C).

        Returns:
        -------
        float
            Maximum torque (Nm).
        """
        motor = self.get_motor(motor_id)

        # Get no-load current at this RPM
        i0 = self._get_i0_at_rpm(motor, rpm)

        # Maximum torque-producing current
        i_torque_max = motor.i_max - i0

        # Get effective Kt at max current
        kt = self._get_kt_effective(motor, motor.i_max)

        return i_torque_max * kt

    def get_motor_limits(
        self,
        motor_id: str,
        v_supply: float
    ) -> Dict[str, float]:
        """
        Get operating envelope for motor at given voltage.

        Parameters:
        ----------
        motor_id : str
            Motor identifier.

        v_supply : float
            Supply voltage (V).

        Returns:
        -------
        dict
            Dictionary with:
            - rpm_no_load: No-load RPM (theoretical max)
            - torque_stall: Stall torque (theoretical max)
            - i_max: Maximum rated current
            - p_max: Maximum rated power
            - kt: Torque constant
            - kv: Velocity constant
        """
        motor = self.get_motor(motor_id)

        # No-load RPM (theoretical maximum)
        rpm_no_load = motor.kv * v_supply

        # Stall torque (at zero RPM, ignoring thermal limits)
        # At stall: V_bemf = 0, I = V/Rm
        rm_hot = self._get_resistance_at_temp(
            motor, self.config.default_winding_temp
        )
        i_stall = v_supply / rm_hot
        torque_stall = i_stall * motor.kt

        return {
            "rpm_no_load": rpm_no_load,
            "torque_stall": torque_stall,
            "i_max": motor.i_max,
            "p_max": motor.p_max,
            "kt": motor.kt,
            "kv": motor.kv,
            "rm_cold": motor.rm_cold,
            "rm_hot": rm_hot
        }

    def get_efficiency(
        self,
        motor_id: str,
        rpm: float,
        torque: float,
        v_supply: float,
        winding_temp: Optional[float] = None
    ) -> float:
        """
        Calculate efficiency at a specific operating point.

        Parameters:
        ----------
        motor_id : str
            Motor identifier.

        rpm : float
            Operating RPM.

        torque : float
            Output torque (Nm).

        v_supply : float
            Supply voltage (V).

        winding_temp : float, optional
            Winding temperature (°C).

        Returns:
        -------
        float
            Efficiency (0-1).
        """
        motor = self.get_motor(motor_id)

        if winding_temp is None:
            winding_temp = self.config.default_winding_temp

        # Get resistance at temperature
        rm = self._get_resistance_at_temp(motor, winding_temp)

        # Calculate required current for this torque
        current = self.get_current_from_torque(motor_id, torque, rpm)

        # Calculate powers
        p_elec = v_supply * current
        p_mech = torque * (rpm * math.pi / 30.0)

        if p_elec > 0:
            return p_mech / p_elec
        return 0.0

    def generate_efficiency_map(
        self,
        motor_id: str,
        v_supply: float,
        rpm_range: Tuple[float, float] = None,
        torque_range: Tuple[float, float] = None,
        num_points: int = 50,
        winding_temp: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Generate 2D efficiency map for visualization.

        Creates a grid of efficiency values across RPM and torque ranges,
        useful for contour plotting.

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
            Number of points in each dimension.

        winding_temp : float, optional
            Winding temperature (°C).

        Returns:
        -------
        dict
            Dictionary with:
            - rpm_values: 1D array of RPM values
            - torque_values: 1D array of torque values
            - efficiency_map: 2D array of efficiency values
            - valid_mask: 2D boolean array (within motor limits)
            - current_map: 2D array of current values
        """
        motor = self.get_motor(motor_id)
        limits = self.get_motor_limits(motor_id, v_supply)

        if winding_temp is None:
            winding_temp = self.config.default_winding_temp

        # Set default ranges if not specified
        if rpm_range is None:
            rpm_range = (limits["rpm_no_load"] * 0.1, limits["rpm_no_load"] * 0.95)

        if torque_range is None:
            max_torque = self.get_max_torque_at_rpm(
                motor_id, rpm_range[0], winding_temp
            )
            torque_range = (0.05 * max_torque, 0.9 * max_torque)

        # Create grids
        rpm_values = np.linspace(rpm_range[0], rpm_range[1], num_points)
        torque_values = np.linspace(torque_range[0], torque_range[1], num_points)

        # Initialize output arrays
        efficiency_map = np.zeros((num_points, num_points))
        current_map = np.zeros((num_points, num_points))
        valid_mask = np.zeros((num_points, num_points), dtype=bool)

        # Calculate efficiency at each point
        for i, rpm in enumerate(rpm_values):
            for j, torque in enumerate(torque_values):
                # Check if point is within motor capability
                max_torque_at_rpm = self.get_max_torque_at_rpm(
                    motor_id, rpm, winding_temp
                )

                if torque > max_torque_at_rpm:
                    efficiency_map[j, i] = np.nan
                    current_map[j, i] = np.nan
                    valid_mask[j, i] = False
                    continue

                # Calculate current and efficiency
                current = self.get_current_from_torque(motor_id, torque, rpm)

                if current > motor.i_max:
                    efficiency_map[j, i] = np.nan
                    current_map[j, i] = current
                    valid_mask[j, i] = False
                    continue

                efficiency = self.get_efficiency(
                    motor_id, rpm, torque, v_supply, winding_temp
                )

                efficiency_map[j, i] = efficiency
                current_map[j, i] = current
                valid_mask[j, i] = True

        return {
            "rpm_values": rpm_values,
            "torque_values": torque_values,
            "efficiency_map": efficiency_map,
            "current_map": current_map,
            "valid_mask": valid_mask
        }

    def estimate_winding_temp(
        self,
        motor_id: str,
        p_loss: float,
        ambient_temp: Optional[float] = None,
        thermal_resistance: Optional[float] = None
    ) -> float:
        """
        Estimate steady-state winding temperature.

        Uses simple thermal resistance model:
            T_winding = T_ambient + P_loss × R_thermal

        Parameters:
        ----------
        motor_id : str
            Motor identifier.

        p_loss : float
            Total power loss (copper + iron) in Watts.

        ambient_temp : float, optional
            Ambient temperature (°C).

        thermal_resistance : float, optional
            Thermal resistance (°C/W).

        Returns:
        -------
        float
            Estimated winding temperature (°C).
        """
        if ambient_temp is None:
            ambient_temp = self.config.default_ambient_temp

        if thermal_resistance is None:
            thermal_resistance = self.config.default_thermal_resistance

        return ambient_temp + p_loss * thermal_resistance

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _create_invalid_state(self, rpm: float, reason: str) -> Dict[str, Any]:
        """Create an invalid state dictionary."""
        return {
            "rpm": rpm,
            "current": 0.0,
            "torque": 0.0,
            "p_elec": 0.0,
            "p_mech": 0.0,
            "efficiency": 0.0,
            "p_loss_copper": 0.0,
            "p_loss_iron": 0.0,
            "v_bemf": 0.0,
            "i_torque": 0.0,
            "i0": 0.0,
            "rm": 0.0,
            "valid": False,
            "error": reason
        }
