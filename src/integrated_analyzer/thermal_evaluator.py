"""
Thermal Evaluator Module
=========================

Evaluates thermal limits for battery packs at various operating points.

This module determines:
- Steady-state temperature at a given current
- Thermal margin (distance from limit)
- Maximum safe throttle when thermally limited
- Whether an operating point is within limits

Classes:
--------
- ThermalEvaluator: Main evaluator class

Key Methods:
-----------
- evaluate_at_current(): Get thermal status at a given current
- find_max_safe_throttle(): Binary search for thermal-limited max throttle
- is_cruise_valid(): Quick check if cruise current is within limits
"""

import sys
from pathlib import Path
from typing import Tuple, Optional, Callable

# Add parent for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from .config import ThermalEvaluation


class ThermalEvaluator:
    """
    Evaluates thermal limits for battery packs.

    The thermal limit depends on current draw, which creates a coupling
    between flight performance and battery thermal state. This class
    handles that evaluation.

    Key insight: A pack may be valid at cruise but exceed limits at max
    throttle. In that case, we binary search to find the max safe throttle.

    Attributes:
    ----------
    _verbose : bool
        Whether to print debug info

    Methods:
    -------
    evaluate_at_current(pack, current_a, soc) -> ThermalEvaluation
        Get complete thermal status at given current

    find_max_safe_throttle(...) -> Tuple[float, float]
        Binary search for max throttle before thermal limit

    is_cruise_valid(pack, cruise_current, soc) -> bool
        Quick check if cruise is within limits
    """

    def __init__(self, verbose: bool = False):
        """
        Initialize thermal evaluator.

        Parameters:
        ----------
        verbose : bool
            Whether to print debug information
        """
        self._verbose = verbose

    def evaluate_at_current(
        self,
        pack,  # BatteryPack
        current_a: float,
        soc: float
    ) -> ThermalEvaluation:
        """
        Evaluate thermal status at given current.

        Uses the BatteryPack's iterative steady-state solver to find
        the self-consistent temperature at this current draw.

        Parameters:
        ----------
        pack : BatteryPack
            Battery pack instance

        current_a : float
            Operating current (A)

        soc : float
            State of charge (0-100%)

        Returns:
        -------
        ThermalEvaluation
            Complete thermal evaluation with temperature, margin, limits
        """
        if current_a <= 0:
            # No current = no heating = ambient temperature
            return ThermalEvaluation(
                current_a=0.0,
                steady_state_temp_c=pack.config.ambient_temp_c,
                heat_generation_w=0.0,
                thermal_margin_c=pack.config.max_cell_temp_c - pack.config.ambient_temp_c,
                within_limits=True,
                limiting_factor="none",
                max_continuous_current_a=pack.get_max_continuous_current(soc)[0],
            )

        # Get steady-state temperature (uses iterative solver in BatteryPack)
        steady_temp = pack.get_steady_state_temp(current_a, soc)

        # Calculate heat generation at steady state
        heat_w = pack.get_heat_generation_w(current_a, soc, steady_temp)

        # Get max continuous current and limiting factor
        max_i, limiting_factor = pack.get_max_continuous_current(soc, steady_temp)

        # Calculate thermal margin
        thermal_margin = pack.config.max_cell_temp_c - steady_temp

        # Determine if within limits
        # Within limits if:
        # 1. Temperature is below max
        # 2. Current is below max continuous
        temp_ok = steady_temp <= pack.config.max_cell_temp_c
        current_ok = current_a <= max_i
        within_limits = temp_ok and current_ok

        # If not within limits, determine the actual limiting factor
        if not within_limits:
            if not temp_ok:
                limiting_factor = "thermal"
            # Otherwise keep the limiting_factor from get_max_continuous_current

        return ThermalEvaluation(
            current_a=current_a,
            steady_state_temp_c=steady_temp,
            heat_generation_w=heat_w,
            thermal_margin_c=thermal_margin,
            within_limits=within_limits,
            limiting_factor=limiting_factor,
            max_continuous_current_a=max_i,
        )

    def is_cruise_valid(
        self,
        pack,  # BatteryPack
        cruise_current: float,
        soc: float
    ) -> bool:
        """
        Quick check if cruise current is within thermal limits.

        Parameters:
        ----------
        pack : BatteryPack
            Battery pack instance

        cruise_current : float
            Current draw at cruise (A)

        soc : float
            State of charge (0-100%)

        Returns:
        -------
        bool
            True if cruise is within limits
        """
        thermal_eval = self.evaluate_at_current(pack, cruise_current, soc)
        return thermal_eval.within_limits

    def find_max_safe_throttle(
        self,
        pack,  # BatteryPack
        soc: float,
        cruise_throttle: float,
        cruise_current: float,
        max_throttle_current: float,
        throttle_to_current_fn: Optional[Callable[[float], float]] = None,
        tolerance: float = 1.0
    ) -> Tuple[float, float]:
        """
        Binary search for maximum safe throttle before thermal limit.

        When max throttle exceeds thermal limits but cruise does not,
        this finds the highest throttle that stays within limits.

        Parameters:
        ----------
        pack : BatteryPack
            Battery pack instance

        soc : float
            State of charge (0-100%)

        cruise_throttle : float
            Throttle at cruise (%)

        cruise_current : float
            Current at cruise (A)

        max_throttle_current : float
            Current at 100% throttle (A)

        throttle_to_current_fn : Callable[[float], float], optional
            Function that converts throttle % to current A.
            If not provided, assumes linear interpolation.

        tolerance : float
            Throttle tolerance for binary search convergence (%)

        Returns:
        -------
        Tuple[float, float]
            (max_safe_throttle_percent, current_at_safe_throttle)
        """
        # First verify cruise is valid
        cruise_eval = self.evaluate_at_current(pack, cruise_current, soc)
        if not cruise_eval.within_limits:
            # Even cruise exceeds limits - no safe throttle
            return (0.0, 0.0)

        # Check if max throttle is already safe
        max_eval = self.evaluate_at_current(pack, max_throttle_current, soc)
        if max_eval.within_limits:
            # Max throttle is safe - no limiting needed
            return (100.0, max_throttle_current)

        # Binary search between cruise and 100%
        low_throttle = cruise_throttle
        high_throttle = 100.0
        safe_throttle = cruise_throttle
        safe_current = cruise_current

        # If no conversion function provided, use linear interpolation
        if throttle_to_current_fn is None:
            def throttle_to_current_fn(throttle):
                # Linear interpolation between cruise and max
                if high_throttle == cruise_throttle:
                    return cruise_current
                frac = (throttle - cruise_throttle) / (100.0 - cruise_throttle)
                return cruise_current + frac * (max_throttle_current - cruise_current)

        for iteration in range(20):  # Max iterations
            mid_throttle = (low_throttle + high_throttle) / 2.0

            # Get current at this throttle
            mid_current = throttle_to_current_fn(mid_throttle)

            # Evaluate thermal
            mid_eval = self.evaluate_at_current(pack, mid_current, soc)

            if mid_eval.within_limits:
                # This throttle is safe - try higher
                safe_throttle = mid_throttle
                safe_current = mid_current
                low_throttle = mid_throttle
            else:
                # This throttle exceeds limits - try lower
                high_throttle = mid_throttle

            # Check convergence
            if high_throttle - low_throttle < tolerance:
                break

            if self._verbose:
                print(f"  Binary search {iteration}: {mid_throttle:.1f}% @ {mid_current:.1f}A "
                      f"-> {mid_eval.steady_state_temp_c:.1f}C "
                      f"({'OK' if mid_eval.within_limits else 'EXCEED'})")

        return (safe_throttle, safe_current)

    def get_thermal_curve(
        self,
        pack,  # BatteryPack
        soc: float,
        current_range: Tuple[float, float] = (0, 100),
        num_points: int = 20
    ) -> list:
        """
        Generate temperature vs current curve for plotting.

        Parameters:
        ----------
        pack : BatteryPack
            Battery pack instance

        soc : float
            State of charge (0-100%)

        current_range : Tuple[float, float]
            (min_current, max_current) in A

        num_points : int
            Number of points to calculate

        Returns:
        -------
        list
            List of ThermalEvaluation objects at each current
        """
        results = []
        current_step = (current_range[1] - current_range[0]) / max(1, num_points - 1)

        for i in range(num_points):
            current = current_range[0] + i * current_step
            eval_result = self.evaluate_at_current(pack, current, soc)
            results.append(eval_result)

        return results

    def find_thermal_limit_current(
        self,
        pack,  # BatteryPack
        soc: float,
        tolerance: float = 0.5
    ) -> float:
        """
        Find the current at which thermal limit is reached.

        Uses binary search to find the current where steady-state
        temperature equals max allowed temperature.

        Parameters:
        ----------
        pack : BatteryPack
            Battery pack instance

        soc : float
            State of charge (0-100%)

        tolerance : float
            Current tolerance for convergence (A)

        Returns:
        -------
        float
            Current (A) at thermal limit
        """
        # Get max current from pack's own calculation
        max_i, limiting_factor = pack.get_max_continuous_current(soc)

        # If not thermally limited, return the rating/voltage limit
        if limiting_factor != "thermal":
            return max_i

        # Binary search to verify
        low_current = 0.0
        high_current = max_i * 1.5  # Search beyond calculated limit

        for _ in range(20):
            mid_current = (low_current + high_current) / 2.0
            eval_result = self.evaluate_at_current(pack, mid_current, soc)

            if eval_result.within_limits:
                low_current = mid_current
            else:
                high_current = mid_current

            if high_current - low_current < tolerance:
                break

        return low_current
