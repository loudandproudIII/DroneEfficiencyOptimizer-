"""
Result Analyzer Module
=======================

Processes and analyzes batch results for the integrated analyzer.

This module provides:
- Finding best combinations by various metrics
- Generating comparison matrices
- Filtering and sorting results
- Export to CSV and JSON formats

Classes:
--------
- ResultAnalyzer: Main analyzer class

Usage:
------
    from src.integrated_analyzer import ResultAnalyzer, IntegratedBatchResult

    analyzer = ResultAnalyzer(batch_result)

    # Get top combinations
    top_10 = analyzer.get_top_by_efficiency(10)

    # Export to CSV
    analyzer.export_csv("results.csv")
"""

import csv
import json
from typing import List, Dict, Optional, Callable, Any
from pathlib import Path

from .config import IntegratedResult, IntegratedBatchResult


class ResultAnalyzer:
    """
    Analyzes and processes batch results.

    Provides methods for filtering, sorting, comparing, and exporting
    integrated analysis results.

    Attributes:
    ----------
    batch_result : IntegratedBatchResult
        The batch result to analyze

    Methods:
    -------
    get_valid_results() -> List[IntegratedResult]
    get_top_by_efficiency(n) -> List[IntegratedResult]
    get_top_by_runtime(n) -> List[IntegratedResult]
    get_top_by_max_speed(n) -> List[IntegratedResult]
    get_results_for_battery(cell, series, parallel) -> List[IntegratedResult]
    get_comparison_matrix() -> Dict
    export_csv(filepath)
    export_json(filepath)
    """

    def __init__(self, batch_result: IntegratedBatchResult):
        """
        Initialize analyzer with batch result.

        Parameters:
        ----------
        batch_result : IntegratedBatchResult
            The batch result to analyze
        """
        self.batch_result = batch_result

    # =========================================================================
    # Filtering
    # =========================================================================

    def get_valid_results(self) -> List[IntegratedResult]:
        """Get all valid results."""
        return [r for r in self.batch_result.results if r.valid]

    def get_invalid_results(self) -> List[IntegratedResult]:
        """Get all invalid results."""
        return [r for r in self.batch_result.results if not r.valid]

    def get_thermal_limited_results(self) -> List[IntegratedResult]:
        """Get results that are thermally limited at max speed."""
        return [
            r for r in self.batch_result.results
            if r.valid and r.thermal_throttle_limit is not None
        ]

    def get_results_for_battery(
        self,
        cell_type: Optional[str] = None,
        series: Optional[int] = None,
        parallel: Optional[int] = None,
        thermal_environment: Optional[str] = None,
    ) -> List[IntegratedResult]:
        """
        Get results matching battery configuration.

        Parameters:
        ----------
        cell_type : str, optional
            Filter by cell type
        series : int, optional
            Filter by series count
        parallel : int, optional
            Filter by parallel count
        thermal_environment : str, optional
            Filter by thermal environment

        Returns:
        -------
        List[IntegratedResult]
            Matching results
        """
        results = self.get_valid_results()

        if cell_type is not None:
            results = [r for r in results if r.cell_type == cell_type]
        if series is not None:
            results = [r for r in results if r.series == series]
        if parallel is not None:
            results = [r for r in results if r.parallel == parallel]
        if thermal_environment is not None:
            results = [r for r in results if r.thermal_environment == thermal_environment]

        return results

    def get_results_for_motor_prop(
        self,
        motor_id: str,
        prop_id: str
    ) -> List[IntegratedResult]:
        """Get all results for a specific motor/prop combination."""
        return [
            r for r in self.get_valid_results()
            if r.motor_id == motor_id and r.prop_id == prop_id
        ]

    # =========================================================================
    # Sorting / Top N
    # =========================================================================

    def get_top_by_metric(
        self,
        metric_fn: Callable[[IntegratedResult], float],
        n: int = 10,
        reverse: bool = True
    ) -> List[IntegratedResult]:
        """
        Get top N results by custom metric.

        Parameters:
        ----------
        metric_fn : Callable
            Function that takes IntegratedResult and returns float
        n : int
            Number of results to return
        reverse : bool
            If True, higher values are better

        Returns:
        -------
        List[IntegratedResult]
            Top N results
        """
        valid = self.get_valid_results()
        sorted_results = sorted(valid, key=metric_fn, reverse=reverse)
        return sorted_results[:n]

    def get_top_by_efficiency(self, n: int = 10) -> List[IntegratedResult]:
        """Get top N results by system efficiency."""
        return self.get_top_by_metric(
            lambda r: r.cruise_result.system_efficiency, n, reverse=True
        )

    def get_top_by_runtime(self, n: int = 10) -> List[IntegratedResult]:
        """Get top N results by cruise runtime."""
        return self.get_top_by_metric(
            lambda r: r.cruise_runtime_minutes, n, reverse=True
        )

    def get_top_by_max_speed(self, n: int = 10) -> List[IntegratedResult]:
        """Get top N results by max achievable speed."""
        return self.get_top_by_metric(
            lambda r: r.max_achievable_speed, n, reverse=True
        )

    def get_top_by_power_density(self, n: int = 10) -> List[IntegratedResult]:
        """Get top N results by power density."""
        return self.get_top_by_metric(
            lambda r: r.power_density_w_kg, n, reverse=True
        )

    def get_top_by_energy_density(self, n: int = 10) -> List[IntegratedResult]:
        """Get top N results by pack energy density."""
        return self.get_top_by_metric(
            lambda r: r.energy_density_wh_kg, n, reverse=True
        )

    def get_lowest_current(self, n: int = 10) -> List[IntegratedResult]:
        """Get top N results by lowest cruise current."""
        return self.get_top_by_metric(
            lambda r: r.cruise_result.battery_current, n, reverse=False
        )

    # =========================================================================
    # Comparison Matrix
    # =========================================================================

    def get_comparison_matrix(self) -> Dict[str, Dict[str, IntegratedResult]]:
        """
        Generate comparison matrix.

        Outer keys: battery configurations (cell_series_parallel_thermal)
        Inner keys: motor_prop combinations
        Values: best result for that combination

        Returns:
        -------
        Dict[str, Dict[str, IntegratedResult]]
            Nested dict structure for matrix display
        """
        return self.batch_result.get_comparison_matrix()

    def get_best_for_each_battery_config(self) -> Dict[str, IntegratedResult]:
        """
        Get best motor/prop for each battery configuration.

        Returns dict where keys are battery configs and values are
        the best IntegratedResult for that config.
        """
        best: Dict[str, IntegratedResult] = {}
        valid = self.get_valid_results()

        for result in valid:
            key = f"{result.cell_type}_{result.pack_config}_{result.thermal_environment}"
            if key not in best:
                best[key] = result
            elif result.cruise_result.system_efficiency > best[key].cruise_result.system_efficiency:
                best[key] = result

        return best

    def get_best_for_each_motor_prop(self) -> Dict[str, IntegratedResult]:
        """
        Get best battery config for each motor/prop combination.

        Returns dict where keys are motor_prop combos and values are
        the best IntegratedResult for that combo.
        """
        best: Dict[str, IntegratedResult] = {}
        valid = self.get_valid_results()

        for result in valid:
            key = f"{result.motor_id}_{result.prop_id}"
            if key not in best:
                best[key] = result
            elif result.cruise_result.system_efficiency > best[key].cruise_result.system_efficiency:
                best[key] = result

        return best

    # =========================================================================
    # Statistics
    # =========================================================================

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get summary statistics for the batch.

        Returns:
        -------
        Dict
            Statistics including counts, ranges, averages
        """
        valid = self.get_valid_results()

        if not valid:
            return {
                "total": len(self.batch_result.results),
                "valid": 0,
                "invalid": len(self.batch_result.results),
            }

        efficiencies = [r.cruise_result.system_efficiency for r in valid]
        runtimes = [r.cruise_runtime_minutes for r in valid]
        max_speeds = [r.max_achievable_speed for r in valid if r.max_achievable_speed > 0]
        currents = [r.cruise_result.battery_current for r in valid]

        return {
            "total": len(self.batch_result.results),
            "valid": len(valid),
            "invalid": len(self.batch_result.results) - len(valid),
            "thermal_limited": len(self.get_thermal_limited_results()),
            "efficiency": {
                "min": min(efficiencies),
                "max": max(efficiencies),
                "avg": sum(efficiencies) / len(efficiencies),
            },
            "runtime_min": {
                "min": min(runtimes),
                "max": max(runtimes),
                "avg": sum(runtimes) / len(runtimes),
            },
            "max_speed_ms": {
                "min": min(max_speeds) if max_speeds else 0,
                "max": max(max_speeds) if max_speeds else 0,
                "avg": sum(max_speeds) / len(max_speeds) if max_speeds else 0,
            },
            "cruise_current_a": {
                "min": min(currents),
                "max": max(currents),
                "avg": sum(currents) / len(currents),
            },
            "elapsed_seconds": self.batch_result.elapsed_seconds,
        }

    # =========================================================================
    # Export
    # =========================================================================

    def export_csv(self, filepath: str, include_invalid: bool = False):
        """
        Export results to CSV file.

        Parameters:
        ----------
        filepath : str
            Path to CSV file
        include_invalid : bool
            Whether to include invalid results
        """
        results = self.batch_result.results if include_invalid else self.get_valid_results()

        if not results:
            return

        # Define columns
        columns = [
            "motor_id", "prop_id", "cell_type", "series", "parallel",
            "thermal_environment", "pack_config",
            "pack_voltage_v", "pack_capacity_mah", "pack_energy_wh", "pack_mass_kg",
            "cruise_speed_ms", "cruise_speed_mph",
            "cruise_throttle_pct", "cruise_current_a", "cruise_power_w",
            "cruise_efficiency_pct", "cruise_motor_eff_pct", "cruise_prop_eff_pct",
            "cruise_rpm", "cruise_temp_c", "cruise_thermal_margin_c",
            "max_speed_ms", "max_speed_mph", "max_speed_throttle_pct",
            "thermal_throttle_limit_pct",
            "runtime_min", "energy_density_wh_kg", "power_density_w_kg",
            "valid", "invalidity_reason",
        ]

        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()

            for result in results:
                row = {
                    "motor_id": result.motor_id,
                    "prop_id": result.prop_id,
                    "cell_type": result.cell_type,
                    "series": result.series,
                    "parallel": result.parallel,
                    "thermal_environment": result.thermal_environment,
                    "pack_config": result.pack_config,
                    "pack_voltage_v": f"{result.pack_voltage_nominal:.2f}",
                    "pack_capacity_mah": f"{result.pack_capacity_mah:.0f}",
                    "pack_energy_wh": f"{result.pack_energy_wh:.1f}",
                    "pack_mass_kg": f"{result.pack_mass_kg:.3f}",
                    "cruise_speed_ms": f"{result.cruise_result.airspeed:.1f}",
                    "cruise_speed_mph": f"{result.cruise_result.airspeed * 2.237:.1f}",
                    "cruise_throttle_pct": f"{result.cruise_result.throttle:.1f}",
                    "cruise_current_a": f"{result.cruise_result.battery_current:.2f}",
                    "cruise_power_w": f"{result.cruise_result.battery_power:.1f}",
                    "cruise_efficiency_pct": f"{result.cruise_result.system_efficiency * 100:.1f}",
                    "cruise_motor_eff_pct": f"{result.cruise_result.motor_efficiency * 100:.1f}",
                    "cruise_prop_eff_pct": f"{result.cruise_result.prop_efficiency * 100:.1f}",
                    "cruise_rpm": f"{result.cruise_result.prop_rpm:.0f}",
                    "cruise_temp_c": f"{result.cruise_result.thermal_eval.steady_state_temp_c:.1f}",
                    "cruise_thermal_margin_c": f"{result.cruise_result.thermal_eval.thermal_margin_c:.1f}",
                    "max_speed_ms": f"{result.max_achievable_speed:.1f}" if result.max_achievable_speed > 0 else "",
                    "max_speed_mph": f"{result.max_achievable_speed * 2.237:.1f}" if result.max_achievable_speed > 0 else "",
                    "max_speed_throttle_pct": f"{result.max_speed_result.throttle:.1f}" if result.max_speed_result else "",
                    "thermal_throttle_limit_pct": f"{result.thermal_throttle_limit:.1f}" if result.thermal_throttle_limit else "",
                    "runtime_min": f"{result.cruise_runtime_minutes:.1f}",
                    "energy_density_wh_kg": f"{result.energy_density_wh_kg:.1f}",
                    "power_density_w_kg": f"{result.power_density_w_kg:.1f}",
                    "valid": result.valid,
                    "invalidity_reason": result.invalidity_reason,
                }
                writer.writerow(row)

    def export_json(self, filepath: str, include_invalid: bool = False):
        """
        Export results to JSON file.

        Parameters:
        ----------
        filepath : str
            Path to JSON file
        include_invalid : bool
            Whether to include invalid results
        """
        results = self.batch_result.results if include_invalid else self.get_valid_results()

        data = {
            "config": {
                "wing_area": self.batch_result.config.wing_area,
                "wingspan": self.batch_result.config.wingspan,
                "weight": self.batch_result.config.weight,
                "cruise_speed": self.batch_result.config.cruise_speed,
            },
            "statistics": self.get_statistics(),
            "results": [r.to_dict() for r in results],
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def get_summary_report(self) -> str:
        """
        Generate text summary report.

        Returns:
        -------
        str
            Formatted summary report
        """
        stats = self.get_statistics()
        lines = [
            "=" * 60,
            "INTEGRATED ANALYSIS SUMMARY",
            "=" * 60,
            "",
            f"Total Combinations: {stats['total']}",
            f"Valid: {stats['valid']} | Invalid: {stats['invalid']}",
            f"Thermally Limited: {stats['thermal_limited']}",
            f"Elapsed Time: {stats['elapsed_seconds']:.1f} seconds",
            "",
        ]

        if stats['valid'] > 0:
            lines.extend([
                "EFFICIENCY:",
                f"  Range: {stats['efficiency']['min']*100:.1f}% - {stats['efficiency']['max']*100:.1f}%",
                f"  Average: {stats['efficiency']['avg']*100:.1f}%",
                "",
                "RUNTIME:",
                f"  Range: {stats['runtime_min']['min']:.1f} - {stats['runtime_min']['max']:.1f} min",
                f"  Average: {stats['runtime_min']['avg']:.1f} min",
                "",
                "MAX SPEED:",
                f"  Range: {stats['max_speed_ms']['min']:.1f} - {stats['max_speed_ms']['max']:.1f} m/s",
                f"  Average: {stats['max_speed_ms']['avg']:.1f} m/s",
                "",
            ])

            # Best combinations
            if self.batch_result.best_by_efficiency:
                best = self.batch_result.best_by_efficiency
                lines.extend([
                    "BEST BY EFFICIENCY:",
                    f"  {best.get_summary_string()}",
                    "",
                ])

            if self.batch_result.best_by_runtime:
                best = self.batch_result.best_by_runtime
                lines.extend([
                    "BEST BY RUNTIME:",
                    f"  {best.get_summary_string()}",
                    "",
                ])

            if self.batch_result.best_by_max_speed:
                best = self.batch_result.best_by_max_speed
                lines.extend([
                    "BEST BY MAX SPEED:",
                    f"  {best.get_summary_string()}",
                    "",
                ])

        lines.append("=" * 60)
        return "\n".join(lines)
