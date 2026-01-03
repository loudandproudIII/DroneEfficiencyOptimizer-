"""
Energy and Runtime Calculations
================================

Calculations for battery pack energy and runtime:
- Total capacity and energy
- Available energy to cutoff
- Runtime estimation
- Peukert effect (minor for Li-ion)
"""

import math
from typing import Optional
from ..models.cell import CellSpec, CellChemistry
from ..config import PEUKERT_EXPONENT_LION
from .electrical import calculate_loaded_voltage, calculate_pack_voltage, soc_to_ocv


def calculate_pack_capacity(
    cell: CellSpec,
    parallel: int
) -> float:
    """
    Calculate total pack capacity.

    Capacity = Cell capacity × Parallel

    Parameters:
    ----------
    cell : CellSpec
        Cell specification

    parallel : int
        Number of cells in parallel

    Returns:
    -------
    float
        Total capacity (mAh)
    """
    return cell.capacity_mah * parallel


def calculate_pack_energy(
    cell: CellSpec,
    series: int,
    parallel: int
) -> float:
    """
    Calculate nominal pack energy.

    Energy = Capacity × Nominal Voltage

    Parameters:
    ----------
    cell : CellSpec
        Cell specification

    series : int
        Number of cells in series

    parallel : int
        Number of cells in parallel

    Returns:
    -------
    float
        Total energy (Wh)
    """
    capacity_ah = calculate_pack_capacity(cell, parallel) / 1000.0
    voltage = cell.nominal_voltage * series
    return capacity_ah * voltage


def calculate_effective_capacity(
    cell: CellSpec,
    parallel: int,
    current_a: float,
    peukert_exponent: float = PEUKERT_EXPONENT_LION
) -> float:
    """
    Calculate effective capacity at given discharge rate.

    Accounts for Peukert effect (minor in Li-ion batteries).

    Li-ion has much less capacity loss at high rates than lead-acid,
    but there is still some reduction.

    Parameters:
    ----------
    cell : CellSpec
        Cell specification

    parallel : int
        Number of cells in parallel

    current_a : float
        Discharge current (A)

    peukert_exponent : float
        Peukert exponent (1.02-1.08 for Li-ion)

    Returns:
    -------
    float
        Effective capacity (mAh)
    """
    nominal_capacity = calculate_pack_capacity(cell, parallel)

    # Rated current (1C rate)
    rated_current = nominal_capacity / 1000.0  # mAh to Ah

    # Current per cell (for parallel packs)
    current_per_cell = current_a / parallel

    # Peukert effect: C_eff = C_rated × (I_rated / I_actual)^(k-1)
    # For Li-ion, k is close to 1, so effect is small
    if current_per_cell > rated_current:
        ratio = rated_current / current_per_cell
        efficiency = ratio ** (peukert_exponent - 1)
        return nominal_capacity * efficiency
    else:
        return nominal_capacity


def calculate_usable_energy(
    cell: CellSpec,
    series: int,
    parallel: int,
    current_a: float,
    start_soc: float = 100.0,
    cutoff_voltage_per_cell: float = 3.0,
    temp_c: float = 25.0
) -> float:
    """
    Calculate usable energy to cutoff voltage.

    Accounts for:
    - Voltage sag under load
    - SOC at which cutoff is reached
    - Peukert capacity reduction

    Parameters:
    ----------
    cell : CellSpec
        Cell specification

    series : int
        Number of cells in series

    parallel : int
        Number of cells in parallel

    current_a : float
        Discharge current (A)

    start_soc : float
        Starting state of charge (0-100%)

    cutoff_voltage_per_cell : float
        Minimum cell voltage (V)

    temp_c : float
        Cell temperature (°C)

    Returns:
    -------
    float
        Usable energy (Wh)
    """
    # Find SOC at which loaded voltage hits cutoff
    cutoff_pack_voltage = cutoff_voltage_per_cell * series

    # Binary search for end SOC
    # Voltage decreases as SOC decreases: high SOC = high voltage, low SOC = low voltage
    # We want to find the SOC where voltage drops to cutoff
    soc_low = 0.0
    soc_high = start_soc

    for _ in range(30):
        soc_mid = (soc_low + soc_high) / 2.0
        v_loaded = calculate_loaded_voltage(
            cell, series, parallel, current_a, soc_mid, temp_c
        )

        if v_loaded > cutoff_pack_voltage:
            # Voltage is still above cutoff at this SOC
            # The transition is at an even LOWER SOC, narrow search downward
            soc_high = soc_mid
        else:
            # Voltage dropped below cutoff at this SOC
            # The transition is at a HIGHER SOC, narrow search upward
            soc_low = soc_mid

        if soc_high - soc_low < 0.5:
            break

    # End SOC is soc_high (the lowest SOC where voltage is still above cutoff)
    end_soc = soc_high

    # Calculate usable capacity (SOC range)
    soc_used = start_soc - end_soc
    capacity_used_fraction = soc_used / 100.0

    # Get effective capacity
    effective_capacity = calculate_effective_capacity(cell, parallel, current_a)

    # Usable capacity
    usable_capacity_mah = effective_capacity * capacity_used_fraction
    usable_capacity_ah = usable_capacity_mah / 1000.0

    # Average voltage during discharge
    # Use midpoint SOC for approximation
    mid_soc = (start_soc + end_soc) / 2.0
    avg_voltage = calculate_loaded_voltage(
        cell, series, parallel, current_a, mid_soc, temp_c
    )

    # Usable energy
    return usable_capacity_ah * avg_voltage


def calculate_runtime(
    cell: CellSpec,
    series: int,
    parallel: int,
    current_a: float,
    start_soc: float = 100.0,
    cutoff_voltage_per_cell: float = 3.0,
    temp_c: float = 25.0
) -> float:
    """
    Calculate runtime at constant current.

    Parameters:
    ----------
    cell : CellSpec
        Cell specification

    series : int
        Number of cells in series

    parallel : int
        Number of cells in parallel

    current_a : float
        Discharge current (A)

    start_soc : float
        Starting state of charge (0-100%)

    cutoff_voltage_per_cell : float
        Minimum cell voltage (V)

    temp_c : float
        Cell temperature (°C)

    Returns:
    -------
    float
        Runtime (minutes)
    """
    if current_a <= 0:
        return float('inf')

    usable_energy = calculate_usable_energy(
        cell, series, parallel, current_a,
        start_soc, cutoff_voltage_per_cell, temp_c
    )

    # Average voltage for power calculation
    mid_soc = (start_soc + calculate_end_soc(
        cell, series, parallel, current_a,
        cutoff_voltage_per_cell, temp_c
    )) / 2.0
    avg_voltage = calculate_loaded_voltage(
        cell, series, parallel, current_a, mid_soc, temp_c
    )

    # Power = V × I
    power_w = avg_voltage * current_a

    if power_w <= 0:
        return float('inf')

    # Runtime = Energy / Power
    runtime_hours = usable_energy / power_w
    return runtime_hours * 60.0  # Convert to minutes


def calculate_end_soc(
    cell: CellSpec,
    series: int,
    parallel: int,
    current_a: float,
    cutoff_voltage_per_cell: float = 3.0,
    temp_c: float = 25.0
) -> float:
    """
    Calculate SOC at which cutoff voltage is reached under load.

    Parameters:
    ----------
    cell : CellSpec
        Cell specification

    series : int
        Number of cells in series

    parallel : int
        Number of cells in parallel

    current_a : float
        Discharge current (A)

    cutoff_voltage_per_cell : float
        Minimum cell voltage (V)

    temp_c : float
        Cell temperature (°C)

    Returns:
    -------
    float
        End SOC (%)
    """
    cutoff_pack_voltage = cutoff_voltage_per_cell * series

    # Binary search for end SOC
    # Voltage decreases as SOC decreases: high SOC = high voltage, low SOC = low voltage
    # We want to find the SOC where voltage drops to cutoff
    soc_low = 0.0
    soc_high = 100.0

    for _ in range(30):
        soc_mid = (soc_low + soc_high) / 2.0
        v_loaded = calculate_loaded_voltage(
            cell, series, parallel, current_a, soc_mid, temp_c
        )

        if v_loaded > cutoff_pack_voltage:
            # Voltage still above cutoff, transition is at LOWER SOC
            soc_high = soc_mid
        else:
            # Voltage below cutoff, transition is at HIGHER SOC
            soc_low = soc_mid

        if soc_high - soc_low < 0.5:
            break

    # Return soc_high: the lowest SOC where voltage is still above cutoff
    return soc_high


def calculate_energy_density(
    cell: CellSpec,
    series: int,
    parallel: int,
    total_mass_g: float
) -> float:
    """
    Calculate pack gravimetric energy density.

    Parameters:
    ----------
    cell : CellSpec
        Cell specification

    series : int
        Number of cells in series

    parallel : int
        Number of cells in parallel

    total_mass_g : float
        Total pack mass (g) including accessories

    Returns:
    -------
    float
        Energy density (Wh/kg)
    """
    energy_wh = calculate_pack_energy(cell, series, parallel)
    mass_kg = total_mass_g / 1000.0

    if mass_kg <= 0:
        return 0.0

    return energy_wh / mass_kg
