"""
Maximum Current and Power Limit Calculations
=============================================

Calculates the maximum sustainable current and power based on:
- Thermal limits (temperature rise)
- Cell rating limits (manufacturer spec)
- Voltage sag limits (maintain minimum voltage)
"""

import math
from typing import Tuple
from ..models.cell import CellSpec
from ..config import THERMAL_RESISTANCE
from .electrical import calculate_pack_ir, calculate_loaded_voltage


def calculate_max_current_thermal(
    cell: CellSpec,
    series: int,
    parallel: int,
    ambient_temp_c: float,
    max_temp_c: float,
    thermal_resistance_c_per_w: float,
    soc_percent: float = 50.0,
    entropic_factor: float = 1.1
) -> float:
    """
    Calculate maximum current for thermal limit.

    Uses per-cell thermal analysis:
    - Each cell generates heat P_cell = I_cell² × R_cell × entropic
    - Each cell has thermal resistance R_thermal (per cell)
    - Cell temp rise = P_cell × R_thermal
    - Max cell current = sqrt(max_temp_rise / (R_cell × entropic × R_thermal))
    - Max pack current = max_cell_current × parallel

    Parameters:
    ----------
    cell : CellSpec
        Cell specification

    series : int
        Number of cells in series

    parallel : int
        Number of cells in parallel

    ambient_temp_c : float
        Ambient temperature (°C)

    max_temp_c : float
        Maximum allowed cell temperature (°C)

    thermal_resistance_c_per_w : float
        Per-cell thermal resistance (°C/W)

    soc_percent : float
        State of charge (0-100%)

    entropic_factor : float
        Multiplier for entropic heating

    Returns:
    -------
    float
        Maximum sustainable pack current (A)
    """
    max_temp_rise = max_temp_c - ambient_temp_c
    if max_temp_rise <= 0:
        return 0.0

    # Get CELL IR (not pack IR) in Ohms
    cell_ir_mohm = cell.get_ir_adjusted(soc_percent, max_temp_c)
    cell_ir_ohm = cell_ir_mohm / 1000.0

    # Per-cell thermal limit:
    # P_cell = I_cell² × R_cell × entropic
    # ΔT = P_cell × R_thermal
    # max_temp_rise = I_cell² × R_cell × entropic × R_thermal
    # I_cell = sqrt(max_temp_rise / (R_cell × entropic × R_thermal))

    denominator = cell_ir_ohm * entropic_factor * thermal_resistance_c_per_w
    if denominator <= 0:
        return float('inf')

    max_cell_current = math.sqrt(max_temp_rise / denominator)

    # Pack current = cell current × parallel
    return max_cell_current * parallel


def calculate_max_current_rating(
    cell: CellSpec,
    parallel: int
) -> float:
    """
    Calculate maximum current from cell rating.

    I_max = Cell max continuous × Parallel

    Parameters:
    ----------
    cell : CellSpec
        Cell specification

    parallel : int
        Number of cells in parallel

    Returns:
    -------
    float
        Maximum rated current (A)
    """
    return cell.max_continuous_discharge_a * parallel


def calculate_max_current_voltage(
    cell: CellSpec,
    series: int,
    parallel: int,
    min_pack_voltage: float,
    soc_percent: float = 50.0,
    temp_c: float = 25.0
) -> float:
    """
    Calculate maximum current for voltage limit.

    Finds current where loaded voltage equals minimum allowed.

    V_min = V_oc - I × R_pack
    I_max = (V_oc - V_min) / R_pack

    Parameters:
    ----------
    cell : CellSpec
        Cell specification

    series : int
        Number of cells in series

    parallel : int
        Number of cells in parallel

    min_pack_voltage : float
        Minimum acceptable pack voltage (V)

    soc_percent : float
        State of charge (0-100%)

    temp_c : float
        Cell temperature (°C)

    Returns:
    -------
    float
        Maximum current before voltage drops below minimum (A)
    """
    from .electrical import calculate_pack_voltage

    # Open circuit voltage
    v_oc = calculate_pack_voltage(cell, series, soc_percent)

    # If OCV is already below minimum, no current is sustainable
    if v_oc <= min_pack_voltage:
        return 0.0

    # Pack IR in Ohms
    pack_ir_mohm = calculate_pack_ir(cell, series, parallel, soc_percent, temp_c)
    pack_ir_ohm = pack_ir_mohm / 1000.0

    if pack_ir_ohm <= 0:
        return float('inf')

    # I_max = (V_oc - V_min) / R
    return (v_oc - min_pack_voltage) / pack_ir_ohm


def calculate_max_continuous_current(
    cell: CellSpec,
    series: int,
    parallel: int,
    ambient_temp_c: float = 25.0,
    max_temp_c: float = 60.0,
    thermal_resistance_c_per_w: float = 20.0,
    min_voltage_per_cell: float = 3.0,
    soc_percent: float = 50.0
) -> Tuple[float, str]:
    """
    Calculate maximum continuous current considering all limits.

    Returns the most restrictive limit.

    Parameters:
    ----------
    cell : CellSpec
        Cell specification

    series : int
        Number of cells in series

    parallel : int
        Number of cells in parallel

    ambient_temp_c : float
        Ambient temperature (°C)

    max_temp_c : float
        Maximum allowed cell temperature (°C)

    thermal_resistance_c_per_w : float
        Pack-to-ambient thermal resistance (°C/W)

    min_voltage_per_cell : float
        Minimum cell voltage (V)

    soc_percent : float
        State of charge (0-100%)

    Returns:
    -------
    Tuple[float, str]
        (max_current, limiting_factor)
        limiting_factor is one of: "thermal", "rating", "voltage"
    """
    # Calculate each limit
    i_thermal = calculate_max_current_thermal(
        cell, series, parallel, ambient_temp_c, max_temp_c,
        thermal_resistance_c_per_w, soc_percent
    )

    i_rating = calculate_max_current_rating(cell, parallel)

    min_pack_voltage = min_voltage_per_cell * series
    i_voltage = calculate_max_current_voltage(
        cell, series, parallel, min_pack_voltage, soc_percent, max_temp_c
    )

    # Find minimum (most restrictive)
    limits = [
        (i_thermal, "thermal"),
        (i_rating, "rating"),
        (i_voltage, "voltage"),
    ]

    min_current, limiting_factor = min(limits, key=lambda x: x[0])
    return min_current, limiting_factor


def calculate_max_continuous_power(
    cell: CellSpec,
    series: int,
    parallel: int,
    ambient_temp_c: float = 25.0,
    max_temp_c: float = 60.0,
    thermal_resistance_c_per_w: float = 20.0,
    min_voltage_per_cell: float = 3.0,
    soc_percent: float = 50.0
) -> Tuple[float, str]:
    """
    Calculate maximum continuous power.

    P_max = I_max × V_loaded(I_max)

    Parameters:
    ----------
    (same as calculate_max_continuous_current)

    Returns:
    -------
    Tuple[float, str]
        (max_power_w, limiting_factor)
    """
    max_current, limiting_factor = calculate_max_continuous_current(
        cell, series, parallel, ambient_temp_c, max_temp_c,
        thermal_resistance_c_per_w, min_voltage_per_cell, soc_percent
    )

    # Calculate voltage at max current
    v_loaded = calculate_loaded_voltage(
        cell, series, parallel, max_current, soc_percent, max_temp_c
    )

    max_power = max_current * v_loaded
    return max_power, limiting_factor


def calculate_c_rate_at_current(
    cell: CellSpec,
    parallel: int,
    current_a: float
) -> float:
    """
    Calculate C-rate for given current.

    C-rate = Current / Capacity (in Ah)

    Parameters:
    ----------
    cell : CellSpec
        Cell specification

    parallel : int
        Number of cells in parallel

    current_a : float
        Total pack current (A)

    Returns:
    -------
    float
        C-rate
    """
    capacity_ah = (cell.capacity_mah * parallel) / 1000.0
    if capacity_ah <= 0:
        return 0.0
    return current_a / capacity_ah


def calculate_current_at_c_rate(
    cell: CellSpec,
    parallel: int,
    c_rate: float
) -> float:
    """
    Calculate current for given C-rate.

    Current = C-rate × Capacity (in Ah)

    Parameters:
    ----------
    cell : CellSpec
        Cell specification

    parallel : int
        Number of cells in parallel

    c_rate : float
        Desired C-rate

    Returns:
    -------
    float
        Current (A)
    """
    capacity_ah = (cell.capacity_mah * parallel) / 1000.0
    return c_rate * capacity_ah
