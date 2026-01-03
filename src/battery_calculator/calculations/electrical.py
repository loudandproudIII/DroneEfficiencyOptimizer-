"""
Electrical Calculations
=======================

Core electrical calculations for battery packs:
- SOC to OCV conversion
- Voltage sag calculation
- Pack voltage under load
- Internal resistance calculations

All calculations verified against Battery Mooch testing methodology.
"""

import math
from typing import Optional
from ..models.cell import CellSpec, CellChemistry
from ..config import SOC_TO_OCV_NMC, SOC_TO_OCV_LFP


def soc_to_ocv(
    soc_percent: float,
    chemistry: CellChemistry = CellChemistry.NMC
) -> float:
    """
    Convert State of Charge to Open Circuit Voltage.

    Uses lookup table with linear interpolation.
    Data based on manufacturer curves and Battery Mooch testing.

    Parameters:
    ----------
    soc_percent : float
        State of charge (0-100%)

    chemistry : CellChemistry
        Cell chemistry type

    Returns:
    -------
    float
        Open circuit voltage (V)
    """
    # Clamp SOC to valid range
    soc = max(0.0, min(100.0, soc_percent))

    # Select lookup table based on chemistry
    if chemistry == CellChemistry.LFP:
        lookup = SOC_TO_OCV_LFP
    else:
        # NMC, NCA, LiPo all use similar curves
        lookup = SOC_TO_OCV_NMC

    # Find bounding SOC points
    soc_points = sorted(lookup.keys())

    # Exact match
    if soc in lookup:
        return lookup[soc]

    # Find lower and upper bounds
    lower_soc = 0
    upper_soc = 100
    for point in soc_points:
        if point <= soc:
            lower_soc = point
        if point >= soc:
            upper_soc = point
            break

    # Handle edge cases
    if lower_soc == upper_soc:
        return lookup[lower_soc]

    # Linear interpolation
    lower_ocv = lookup[lower_soc]
    upper_ocv = lookup[upper_soc]
    fraction = (soc - lower_soc) / (upper_soc - lower_soc)

    return lower_ocv + fraction * (upper_ocv - lower_ocv)


def calculate_pack_ir(
    cell: CellSpec,
    series: int,
    parallel: int,
    soc_percent: float = 50.0,
    temp_c: float = 25.0
) -> float:
    """
    Calculate total pack internal resistance.

    Pack IR = (Cell IR × Series) / Parallel

    IR is adjusted for SOC and temperature effects.

    Parameters:
    ----------
    cell : CellSpec
        Cell specification

    series : int
        Number of cells in series

    parallel : int
        Number of cells in parallel

    soc_percent : float
        State of charge (0-100%)

    temp_c : float
        Cell temperature (°C)

    Returns:
    -------
    float
        Total pack internal resistance (mΩ)
    """
    # Get adjusted cell IR
    cell_ir = cell.get_ir_adjusted(soc_percent, temp_c)

    # Pack IR: series increases, parallel decreases
    return (cell_ir * series) / parallel


def calculate_voltage_sag(
    cell: CellSpec,
    series: int,
    parallel: int,
    current_a: float,
    soc_percent: float = 50.0,
    temp_c: float = 25.0
) -> float:
    """
    Calculate voltage sag due to internal resistance.

    V_sag = I × R_pack

    Parameters:
    ----------
    cell : CellSpec
        Cell specification

    series : int
        Number of cells in series

    parallel : int
        Number of cells in parallel

    current_a : float
        Total pack current (A)

    soc_percent : float
        State of charge (0-100%)

    temp_c : float
        Cell temperature (°C)

    Returns:
    -------
    float
        Voltage sag (V)
    """
    # Get pack IR in Ohms
    pack_ir_mohm = calculate_pack_ir(cell, series, parallel, soc_percent, temp_c)
    pack_ir_ohm = pack_ir_mohm / 1000.0

    return current_a * pack_ir_ohm


def calculate_pack_voltage(
    cell: CellSpec,
    series: int,
    soc_percent: float = 100.0
) -> float:
    """
    Calculate pack open circuit voltage at given SOC.

    V_pack = V_cell × Series

    Parameters:
    ----------
    cell : CellSpec
        Cell specification

    series : int
        Number of cells in series

    soc_percent : float
        State of charge (0-100%)

    Returns:
    -------
    float
        Pack open circuit voltage (V)
    """
    cell_ocv = soc_to_ocv(soc_percent, cell.chemistry)
    return cell_ocv * series


def calculate_loaded_voltage(
    cell: CellSpec,
    series: int,
    parallel: int,
    current_a: float,
    soc_percent: float = 50.0,
    temp_c: float = 25.0
) -> float:
    """
    Calculate pack voltage under load.

    V_loaded = V_oc - V_sag

    Parameters:
    ----------
    cell : CellSpec
        Cell specification

    series : int
        Number of cells in series

    parallel : int
        Number of cells in parallel

    current_a : float
        Total pack current (A)

    soc_percent : float
        State of charge (0-100%)

    temp_c : float
        Cell temperature (°C)

    Returns:
    -------
    float
        Loaded pack voltage (V)
    """
    v_oc = calculate_pack_voltage(cell, series, soc_percent)
    v_sag = calculate_voltage_sag(
        cell, series, parallel, current_a, soc_percent, temp_c
    )
    return v_oc - v_sag


def calculate_power_at_current(
    cell: CellSpec,
    series: int,
    parallel: int,
    current_a: float,
    soc_percent: float = 50.0,
    temp_c: float = 25.0
) -> float:
    """
    Calculate power output at given current.

    P = V_loaded × I

    Parameters:
    ----------
    cell : CellSpec
        Cell specification

    series : int
        Number of cells in series

    parallel : int
        Number of cells in parallel

    current_a : float
        Total pack current (A)

    soc_percent : float
        State of charge (0-100%)

    temp_c : float
        Cell temperature (°C)

    Returns:
    -------
    float
        Power output (W)
    """
    v_loaded = calculate_loaded_voltage(
        cell, series, parallel, current_a, soc_percent, temp_c
    )
    return v_loaded * current_a


def calculate_current_from_power(
    cell: CellSpec,
    series: int,
    parallel: int,
    power_w: float,
    soc_percent: float = 50.0,
    temp_c: float = 25.0,
    tolerance: float = 0.01
) -> float:
    """
    Calculate current required for target power output.

    Uses iterative solver since P = V(I) × I is non-linear.

    Parameters:
    ----------
    cell : CellSpec
        Cell specification

    series : int
        Number of cells in series

    parallel : int
        Number of cells in parallel

    power_w : float
        Target power output (W)

    soc_percent : float
        State of charge (0-100%)

    temp_c : float
        Cell temperature (°C)

    tolerance : float
        Power tolerance for convergence (W)

    Returns:
    -------
    float
        Required current (A)
    """
    # Initial guess using OCV
    v_oc = calculate_pack_voltage(cell, series, soc_percent)
    current_guess = power_w / v_oc

    # Iterative refinement
    for _ in range(20):
        actual_power = calculate_power_at_current(
            cell, series, parallel, current_guess, soc_percent, temp_c
        )
        error = power_w - actual_power

        if abs(error) < tolerance:
            break

        # Adjust current based on error
        v_loaded = calculate_loaded_voltage(
            cell, series, parallel, current_guess, soc_percent, temp_c
        )
        if v_loaded > 0:
            current_guess += error / v_loaded

        # Clamp to reasonable range
        current_guess = max(0.0, current_guess)

    return current_guess


def calculate_heat_generation(
    cell: CellSpec,
    series: int,
    parallel: int,
    current_a: float,
    soc_percent: float = 50.0,
    temp_c: float = 25.0,
    entropic_factor: float = 1.1
) -> float:
    """
    Calculate heat generation from I²R losses.

    P_heat = I² × R × entropic_factor

    Parameters:
    ----------
    cell : CellSpec
        Cell specification

    series : int
        Number of cells in series

    parallel : int
        Number of cells in parallel

    current_a : float
        Total pack current (A)

    soc_percent : float
        State of charge (0-100%)

    temp_c : float
        Cell temperature (°C)

    entropic_factor : float
        Multiplier for entropic heating (typically 1.05-1.15)

    Returns:
    -------
    float
        Heat generation rate (W)
    """
    pack_ir_mohm = calculate_pack_ir(cell, series, parallel, soc_percent, temp_c)
    pack_ir_ohm = pack_ir_mohm / 1000.0

    joule_heating = current_a ** 2 * pack_ir_ohm
    return joule_heating * entropic_factor
