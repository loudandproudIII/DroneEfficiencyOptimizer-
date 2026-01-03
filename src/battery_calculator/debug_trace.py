"""
Debug Trace Functions
=====================

Functions to trace all battery pack calculations with detailed output.
"""

from .debugger import CalculationDebugger
from .models.cell import CellSpec, CellChemistry
from .models.pack import BatteryPack
from .config import (
    BatteryCalculatorConfig,
    SOC_TO_OCV_NMC,
    SOC_TO_OCV_LFP,
    THERMAL_RESISTANCE,
    DEFAULT_IR_TEMP_COEFF,
    REFERENCE_TEMP_C,
)
from .calculations.electrical import (
    soc_to_ocv,
    calculate_pack_voltage,
    calculate_pack_ir,
    calculate_voltage_sag,
    calculate_loaded_voltage,
)
from .calculations.limits import (
    calculate_max_current_thermal,
    calculate_max_current_rating,
    calculate_max_current_voltage,
    calculate_max_continuous_current,
)
from .calculations.energy import (
    calculate_pack_capacity,
    calculate_pack_energy,
    calculate_effective_capacity,
    calculate_usable_energy,
    calculate_runtime,
    calculate_end_soc,
)


def trace_all_calculations(
    pack: BatteryPack,
    soc_percent: float,
    temp_c: float,
    test_current_a: float,
    cutoff_voltage_per_cell: float = 3.0
) -> CalculationDebugger:
    """
    Trace all battery pack calculations with detailed step-by-step output.

    Parameters:
    ----------
    pack : BatteryPack
        The battery pack to analyze

    soc_percent : float
        State of charge (0-100%)

    temp_c : float
        Cell/ambient temperature (C)

    test_current_a : float
        Test current for analysis (A)

    cutoff_voltage_per_cell : float
        Cutoff voltage per cell (V)

    Returns:
    -------
    CalculationDebugger
        Debugger with all calculation steps recorded
    """
    debugger = CalculationDebugger()
    cell = pack.cell
    series = pack.series
    parallel = pack.parallel
    config = pack.config

    # Start debugging session
    debugger.start(
        cell_name=f"{cell.manufacturer} {cell.name}",
        configuration=f"{series}S{parallel}P",
        soc=f"{soc_percent}%",
        temperature=f"{temp_c}C",
        test_current=f"{test_current_a}A"
    )

    # ==========================================================================
    # SECTION 1: INPUT PARAMETERS
    # ==========================================================================
    debugger.start_section("INPUT PARAMETERS")

    debugger.add_step(
        category="Input",
        description="Cell specification",
        formula="",
        variables={},
        result=f"{cell.manufacturer} {cell.name}",
        result_name="cell",
        result_unit="",
        comment=f"Chemistry: {cell.chemistry.value}, Form Factor: {cell.form_factor.value}"
    )

    debugger.add_step(
        category="Input",
        description="Cell capacity (manufacturer spec)",
        formula="",
        variables={},
        result=cell.capacity_mah,
        result_name="C_cell",
        result_unit="mAh"
    )

    debugger.add_step(
        category="Input",
        description="Cell nominal voltage",
        formula="",
        variables={},
        result=cell.nominal_voltage,
        result_name="V_nom_cell",
        result_unit="V"
    )

    debugger.add_step(
        category="Input",
        description="Cell DC internal resistance (at 25C, 50% SOC)",
        formula="",
        variables={},
        result=cell.dc_ir_mohm,
        result_name="R_dc_cell",
        result_unit="mOhm",
        comment="From Battery Mooch testing or datasheet"
    )

    debugger.add_step(
        category="Input",
        description="Cell max continuous discharge current",
        formula="",
        variables={},
        result=cell.max_continuous_discharge_a,
        result_name="I_max_cell",
        result_unit="A"
    )

    debugger.add_step(
        category="Input",
        description="Cell mass",
        formula="",
        variables={},
        result=cell.mass_g,
        result_name="m_cell",
        result_unit="g"
    )

    debugger.add_step(
        category="Input",
        description="Pack series count",
        formula="",
        variables={},
        result=series,
        result_name="S",
        result_unit="cells"
    )

    debugger.add_step(
        category="Input",
        description="Pack parallel count",
        formula="",
        variables={},
        result=parallel,
        result_name="P",
        result_unit="cells"
    )

    total_cells = series * parallel
    debugger.add_step(
        category="Input",
        description="Total cells in pack",
        formula="Total = S * P",
        variables={"S": series, "P": parallel},
        result=total_cells,
        result_name="N_cells",
        result_unit="cells"
    )

    debugger.add_step(
        category="Input",
        description="State of charge",
        formula="",
        variables={},
        result=soc_percent,
        result_name="SOC",
        result_unit="%"
    )

    debugger.add_step(
        category="Input",
        description="Cell/ambient temperature",
        formula="",
        variables={},
        result=temp_c,
        result_name="T",
        result_unit="C"
    )

    debugger.add_step(
        category="Input",
        description="Test current (pack level)",
        formula="",
        variables={},
        result=test_current_a,
        result_name="I_test",
        result_unit="A"
    )

    # ==========================================================================
    # SECTION 2: CONFIGURATION PARAMETERS
    # ==========================================================================
    debugger.start_section("CONFIGURATION PARAMETERS")

    debugger.add_step(
        category="Config",
        description="Thermal environment",
        formula="",
        variables={},
        result=config.thermal_environment,
        result_name="thermal_env",
        result_unit=""
    )

    thermal_r = config.thermal_resistance
    debugger.add_step(
        category="Config",
        description="Thermal resistance (per cell)",
        formula="R_th = lookup[thermal_env]",
        variables={"thermal_env": config.thermal_environment},
        result=thermal_r,
        result_name="R_th",
        result_unit="C/W",
        comment="Based on convection coefficient for environment"
    )

    debugger.add_step(
        category="Config",
        description="Maximum cell temperature limit",
        formula="",
        variables={},
        result=config.max_cell_temp_c,
        result_name="T_max",
        result_unit="C"
    )

    debugger.add_step(
        category="Config",
        description="Cutoff voltage per cell",
        formula="",
        variables={},
        result=cutoff_voltage_per_cell,
        result_name="V_cutoff_cell",
        result_unit="V"
    )

    debugger.add_step(
        category="Config",
        description="IR temperature coefficient",
        formula="",
        variables={},
        result=DEFAULT_IR_TEMP_COEFF,
        result_name="alpha_IR",
        result_unit="/C",
        comment="IR changes by this fraction per degree from 25C"
    )

    # ==========================================================================
    # SECTION 3: SOC TO OCV CONVERSION
    # ==========================================================================
    debugger.start_section("SOC TO OPEN CIRCUIT VOLTAGE")

    # Get chemistry-specific OCV table
    if cell.chemistry == CellChemistry.LFP:
        ocv_table = SOC_TO_OCV_LFP
        chemistry_name = "LFP"
    else:
        ocv_table = SOC_TO_OCV_NMC
        chemistry_name = "NMC"

    debugger.add_step(
        category="OCV",
        description="Select SOC-OCV lookup table for chemistry",
        formula="table = SOC_TO_OCV[chemistry]",
        variables={"chemistry": chemistry_name},
        result=f"{len(ocv_table)} points",
        result_name="ocv_table",
        result_unit="",
        comment="Based on Battery Mooch testing and manufacturer data"
    )

    # Find surrounding points for interpolation
    soc_points = sorted(ocv_table.keys())
    soc_low = max([s for s in soc_points if s <= soc_percent], default=soc_points[0])
    soc_high = min([s for s in soc_points if s >= soc_percent], default=soc_points[-1])

    ocv_low = ocv_table[soc_low]
    ocv_high = ocv_table[soc_high]

    debugger.add_step(
        category="OCV",
        description="Find surrounding SOC points in table",
        formula="",
        variables={"SOC": soc_percent},
        result=f"[{soc_low}%, {soc_high}%]",
        result_name="soc_bounds",
        result_unit="",
        comment=f"OCV values: [{ocv_low}V, {ocv_high}V]"
    )

    # Interpolate
    if soc_high != soc_low:
        fraction = (soc_percent - soc_low) / (soc_high - soc_low)
        ocv_cell = ocv_low + fraction * (ocv_high - ocv_low)
        debugger.add_step(
            category="OCV",
            description="Linear interpolation for OCV",
            formula="OCV = OCV_low + (SOC - SOC_low)/(SOC_high - SOC_low) * (OCV_high - OCV_low)",
            variables={
                "OCV_low": ocv_low,
                "OCV_high": ocv_high,
                "SOC": soc_percent,
                "SOC_low": soc_low,
                "SOC_high": soc_high
            },
            result=ocv_cell,
            result_name="V_ocv_cell",
            result_unit="V"
        )
    else:
        ocv_cell = ocv_low
        debugger.add_step(
            category="OCV",
            description="Exact SOC match in table",
            formula="OCV = table[SOC]",
            variables={"SOC": soc_percent},
            result=ocv_cell,
            result_name="V_ocv_cell",
            result_unit="V"
        )

    # Pack OCV
    pack_ocv = ocv_cell * series
    debugger.add_step(
        category="OCV",
        description="Pack open circuit voltage",
        formula="V_oc_pack = V_ocv_cell * S",
        variables={"V_ocv_cell": ocv_cell, "S": series},
        result=pack_ocv,
        result_name="V_oc_pack",
        result_unit="V"
    )

    # ==========================================================================
    # SECTION 4: INTERNAL RESISTANCE CALCULATIONS
    # ==========================================================================
    debugger.start_section("INTERNAL RESISTANCE CALCULATIONS")

    # Base cell IR
    ir_base = cell.dc_ir_mohm
    debugger.add_step(
        category="IR",
        description="Base cell IR (at 25C, 50% SOC)",
        formula="",
        variables={},
        result=ir_base,
        result_name="R_base",
        result_unit="mOhm"
    )

    # Temperature adjustment
    temp_diff = temp_c - REFERENCE_TEMP_C
    temp_factor = 1.0 + DEFAULT_IR_TEMP_COEFF * (-temp_diff)  # IR increases as temp decreases
    debugger.add_step(
        category="IR",
        description="Temperature adjustment factor",
        formula="k_temp = 1 + alpha_IR * (T_ref - T)",
        variables={
            "alpha_IR": DEFAULT_IR_TEMP_COEFF,
            "T_ref": REFERENCE_TEMP_C,
            "T": temp_c
        },
        result=temp_factor,
        result_name="k_temp",
        result_unit="",
        comment="IR increases at low temperatures, decreases at high temperatures"
    )

    # SOC adjustment (U-shaped curve)
    if soc_percent >= 50:
        soc_factor = 1.0 + 0.003 * (soc_percent - 50)
    else:
        soc_factor = 1.0 + 0.008 * (50 - soc_percent)

    debugger.add_step(
        category="IR",
        description="SOC adjustment factor (U-shaped curve)",
        formula="k_soc = 1 + 0.003*(SOC-50) if SOC>=50 else 1 + 0.008*(50-SOC)",
        variables={"SOC": soc_percent},
        result=soc_factor,
        result_name="k_soc",
        result_unit="",
        comment="IR is lowest around 50% SOC"
    )

    # Adjusted cell IR
    ir_adjusted = ir_base * temp_factor * soc_factor
    debugger.add_step(
        category="IR",
        description="Adjusted cell IR",
        formula="R_cell = R_base * k_temp * k_soc",
        variables={
            "R_base": ir_base,
            "k_temp": temp_factor,
            "k_soc": soc_factor
        },
        result=ir_adjusted,
        result_name="R_cell",
        result_unit="mOhm"
    )

    # Pack IR calculation
    pack_ir = (ir_adjusted * series) / parallel
    debugger.add_step(
        category="IR",
        description="Pack internal resistance",
        formula="R_pack = (R_cell * S) / P",
        variables={
            "R_cell": ir_adjusted,
            "S": series,
            "P": parallel
        },
        result=pack_ir,
        result_name="R_pack",
        result_unit="mOhm",
        comment="Series adds resistance, parallel reduces it"
    )

    # ==========================================================================
    # SECTION 5: VOLTAGE SAG UNDER LOAD
    # ==========================================================================
    debugger.start_section("VOLTAGE SAG CALCULATIONS")

    # Voltage sag
    pack_ir_ohm = pack_ir / 1000.0
    v_sag = test_current_a * pack_ir_ohm
    debugger.add_step(
        category="Voltage",
        description="Voltage sag under load (Ohm's Law)",
        formula="V_sag = I * R_pack",
        variables={
            "I": test_current_a,
            "R_pack": pack_ir_ohm
        },
        result=v_sag,
        result_name="V_sag",
        result_unit="V",
        comment="Ohm's Law: V = IR"
    )

    # Loaded voltage
    v_loaded = pack_ocv - v_sag
    debugger.add_step(
        category="Voltage",
        description="Loaded pack voltage",
        formula="V_loaded = V_oc - V_sag",
        variables={
            "V_oc": pack_ocv,
            "V_sag": v_sag
        },
        result=v_loaded,
        result_name="V_loaded",
        result_unit="V"
    )

    # Loaded voltage per cell
    v_loaded_per_cell = v_loaded / series
    debugger.add_step(
        category="Voltage",
        description="Loaded voltage per cell",
        formula="V_cell_loaded = V_loaded / S",
        variables={
            "V_loaded": v_loaded,
            "S": series
        },
        result=v_loaded_per_cell,
        result_name="V_cell_loaded",
        result_unit="V"
    )

    # ==========================================================================
    # SECTION 6: POWER CALCULATIONS
    # ==========================================================================
    debugger.start_section("POWER CALCULATIONS")

    # Pack power
    power_pack = v_loaded * test_current_a
    debugger.add_step(
        category="Power",
        description="Pack power output",
        formula="P_pack = V_loaded * I",
        variables={
            "V_loaded": v_loaded,
            "I": test_current_a
        },
        result=power_pack,
        result_name="P_pack",
        result_unit="W"
    )

    # Current per cell
    current_per_cell = test_current_a / parallel
    debugger.add_step(
        category="Power",
        description="Current per cell",
        formula="I_cell = I_pack / P",
        variables={
            "I_pack": test_current_a,
            "P": parallel
        },
        result=current_per_cell,
        result_name="I_cell",
        result_unit="A"
    )

    # Power per cell
    power_per_cell = power_pack / total_cells
    debugger.add_step(
        category="Power",
        description="Power per cell",
        formula="P_cell = P_pack / N_cells",
        variables={
            "P_pack": power_pack,
            "N_cells": total_cells
        },
        result=power_per_cell,
        result_name="P_cell",
        result_unit="W"
    )

    # ==========================================================================
    # SECTION 7: THERMAL CALCULATIONS
    # ==========================================================================
    debugger.start_section("THERMAL CALCULATIONS")

    # Heat generation per cell (I²R)
    cell_ir_ohm = ir_adjusted / 1000.0
    heat_per_cell = current_per_cell ** 2 * cell_ir_ohm
    debugger.add_step(
        category="Thermal",
        description="Heat generation per cell (I²R losses)",
        formula="P_heat_cell = I_cell² * R_cell",
        variables={
            "I_cell": current_per_cell,
            "R_cell": cell_ir_ohm
        },
        result=heat_per_cell,
        result_name="P_heat_cell",
        result_unit="W"
    )

    # Entropic heat factor
    entropic_factor = 1.1
    heat_per_cell_total = heat_per_cell * entropic_factor
    debugger.add_step(
        category="Thermal",
        description="Total heat per cell (with entropic heating)",
        formula="P_heat_total = P_heat_cell * k_entropic",
        variables={
            "P_heat_cell": heat_per_cell,
            "k_entropic": entropic_factor
        },
        result=heat_per_cell_total,
        result_name="P_heat_total",
        result_unit="W",
        comment="Entropic heating adds ~10% to I²R losses"
    )

    # Total pack heat
    heat_pack = heat_per_cell_total * total_cells
    debugger.add_step(
        category="Thermal",
        description="Total pack heat generation",
        formula="P_heat_pack = P_heat_total * N_cells",
        variables={
            "P_heat_total": heat_per_cell_total,
            "N_cells": total_cells
        },
        result=heat_pack,
        result_name="P_heat_pack",
        result_unit="W"
    )

    # Temperature rise per cell
    temp_rise_cell = heat_per_cell_total * thermal_r
    debugger.add_step(
        category="Thermal",
        description="Steady-state temperature rise per cell",
        formula="dT_cell = P_heat_total * R_th",
        variables={
            "P_heat_total": heat_per_cell_total,
            "R_th": thermal_r
        },
        result=temp_rise_cell,
        result_name="dT_cell",
        result_unit="C",
        comment="Assumes steady-state equilibrium with environment"
    )

    # Final cell temperature
    final_temp = temp_c + temp_rise_cell
    debugger.add_step(
        category="Thermal",
        description="Final steady-state cell temperature",
        formula="T_cell = T_ambient + dT_cell",
        variables={
            "T_ambient": temp_c,
            "dT_cell": temp_rise_cell
        },
        result=final_temp,
        result_name="T_cell",
        result_unit="C"
    )

    # ==========================================================================
    # SECTION 8: CURRENT LIMITS
    # ==========================================================================
    debugger.start_section("CURRENT LIMIT CALCULATIONS")

    # Rating limit
    i_rating = cell.max_continuous_discharge_a * parallel
    debugger.add_step(
        category="Limits",
        description="Maximum current from cell rating",
        formula="I_max_rating = I_max_cell * P",
        variables={
            "I_max_cell": cell.max_continuous_discharge_a,
            "P": parallel
        },
        result=i_rating,
        result_name="I_max_rating",
        result_unit="A",
        comment="Cell manufacturer's continuous discharge rating"
    )

    # Thermal limit calculation
    max_temp_rise = config.max_cell_temp_c - temp_c
    debugger.add_step(
        category="Limits",
        description="Maximum allowable temperature rise",
        formula="dT_max = T_max - T_ambient",
        variables={
            "T_max": config.max_cell_temp_c,
            "T_ambient": temp_c
        },
        result=max_temp_rise,
        result_name="dT_max",
        result_unit="C"
    )

    # Thermal limit formula derivation
    # P_heat = I_cell² * R_cell * k_entropic
    # dT = P_heat * R_th
    # dT_max = I_cell_max² * R_cell * k_entropic * R_th
    # I_cell_max = sqrt(dT_max / (R_cell * k_entropic * R_th))
    if max_temp_rise > 0:
        import math
        denominator = cell_ir_ohm * entropic_factor * thermal_r
        i_cell_max_thermal = math.sqrt(max_temp_rise / denominator) if denominator > 0 else float('inf')
        i_pack_max_thermal = i_cell_max_thermal * parallel

        debugger.add_step(
            category="Limits",
            description="Maximum cell current for thermal limit",
            formula="I_cell_max = sqrt(dT_max / (R_cell * k_entropic * R_th))",
            variables={
                "dT_max": max_temp_rise,
                "R_cell": cell_ir_ohm,
                "k_entropic": entropic_factor,
                "R_th": thermal_r
            },
            result=i_cell_max_thermal,
            result_name="I_cell_max_thermal",
            result_unit="A"
        )

        debugger.add_step(
            category="Limits",
            description="Maximum pack current for thermal limit",
            formula="I_pack_max_thermal = I_cell_max * P",
            variables={
                "I_cell_max": i_cell_max_thermal,
                "P": parallel
            },
            result=i_pack_max_thermal,
            result_name="I_max_thermal",
            result_unit="A"
        )
    else:
        i_pack_max_thermal = 0.0
        debugger.add_step(
            category="Limits",
            description="Thermal limit not applicable",
            formula="",
            variables={"dT_max": max_temp_rise},
            result=0.0,
            result_name="I_max_thermal",
            result_unit="A",
            comment="Ambient temperature already at or above max limit"
        )

    # Voltage limit
    cutoff_pack = cutoff_voltage_per_cell * series
    voltage_headroom = pack_ocv - cutoff_pack
    i_max_voltage = voltage_headroom / pack_ir_ohm if pack_ir_ohm > 0 else float('inf')

    debugger.add_step(
        category="Limits",
        description="Pack cutoff voltage",
        formula="V_cutoff_pack = V_cutoff_cell * S",
        variables={
            "V_cutoff_cell": cutoff_voltage_per_cell,
            "S": series
        },
        result=cutoff_pack,
        result_name="V_cutoff_pack",
        result_unit="V"
    )

    debugger.add_step(
        category="Limits",
        description="Voltage headroom above cutoff",
        formula="V_headroom = V_oc - V_cutoff",
        variables={
            "V_oc": pack_ocv,
            "V_cutoff": cutoff_pack
        },
        result=voltage_headroom,
        result_name="V_headroom",
        result_unit="V"
    )

    debugger.add_step(
        category="Limits",
        description="Maximum current for voltage limit",
        formula="I_max_voltage = V_headroom / R_pack",
        variables={
            "V_headroom": voltage_headroom,
            "R_pack": pack_ir_ohm
        },
        result=i_max_voltage,
        result_name="I_max_voltage",
        result_unit="A",
        comment="Current at which voltage drops to cutoff"
    )

    # Determine limiting factor
    limits = [
        (i_pack_max_thermal, "thermal"),
        (i_rating, "rating"),
        (i_max_voltage, "voltage")
    ]
    i_max, limiting_factor = min(limits, key=lambda x: x[0])

    debugger.add_step(
        category="Limits",
        description="Determine most restrictive limit",
        formula="I_max = min(I_thermal, I_rating, I_voltage)",
        variables={
            "I_thermal": i_pack_max_thermal,
            "I_rating": i_rating,
            "I_voltage": i_max_voltage
        },
        result=i_max,
        result_name="I_max_continuous",
        result_unit="A",
        comment=f"Limited by: {limiting_factor}"
    )

    # ==========================================================================
    # SECTION 9: CAPACITY AND ENERGY
    # ==========================================================================
    debugger.start_section("CAPACITY AND ENERGY CALCULATIONS")

    # Pack capacity
    pack_capacity = cell.capacity_mah * parallel
    debugger.add_step(
        category="Energy",
        description="Total pack capacity",
        formula="C_pack = C_cell * P",
        variables={
            "C_cell": cell.capacity_mah,
            "P": parallel
        },
        result=pack_capacity,
        result_name="C_pack",
        result_unit="mAh"
    )

    # Pack energy
    pack_energy = (pack_capacity / 1000.0) * (cell.nominal_voltage * series)
    debugger.add_step(
        category="Energy",
        description="Nominal pack energy",
        formula="E_pack = (C_pack/1000) * V_nom",
        variables={
            "C_pack": pack_capacity,
            "V_nom": cell.nominal_voltage * series
        },
        result=pack_energy,
        result_name="E_pack",
        result_unit="Wh"
    )

    # ==========================================================================
    # SECTION 10: RUNTIME CALCULATION
    # ==========================================================================
    debugger.start_section("RUNTIME CALCULATION")

    # Find end SOC (where voltage drops to cutoff)
    end_soc = calculate_end_soc(cell, series, parallel, test_current_a, cutoff_voltage_per_cell, temp_c)

    debugger.add_step(
        category="Runtime",
        description="End SOC (where loaded voltage reaches cutoff)",
        formula="Binary search: find SOC where V_loaded = V_cutoff",
        variables={
            "I": test_current_a,
            "V_cutoff": cutoff_pack
        },
        result=end_soc,
        result_name="SOC_end",
        result_unit="%",
        comment="Lowest SOC where voltage stays above cutoff under load"
    )

    # Usable SOC range
    usable_soc = soc_percent - end_soc
    debugger.add_step(
        category="Runtime",
        description="Usable SOC range",
        formula="SOC_usable = SOC_start - SOC_end",
        variables={
            "SOC_start": soc_percent,
            "SOC_end": end_soc
        },
        result=usable_soc,
        result_name="SOC_usable",
        result_unit="%"
    )

    # Usable capacity
    usable_capacity = pack_capacity * (usable_soc / 100.0)
    debugger.add_step(
        category="Runtime",
        description="Usable capacity",
        formula="C_usable = C_pack * (SOC_usable / 100)",
        variables={
            "C_pack": pack_capacity,
            "SOC_usable": usable_soc
        },
        result=usable_capacity,
        result_name="C_usable",
        result_unit="mAh"
    )

    # Runtime
    if test_current_a > 0:
        runtime_hours = (usable_capacity / 1000.0) / test_current_a
        runtime_minutes = runtime_hours * 60
    else:
        runtime_minutes = float('inf')

    debugger.add_step(
        category="Runtime",
        description="Estimated runtime",
        formula="t = (C_usable / 1000) / I * 60",
        variables={
            "C_usable": usable_capacity,
            "I": test_current_a
        },
        result=runtime_minutes,
        result_name="runtime",
        result_unit="min",
        comment="Simplified estimate assuming constant current"
    )

    # ==========================================================================
    # SECTION 11: MASS CALCULATIONS
    # ==========================================================================
    debugger.start_section("MASS CALCULATIONS")

    cell_mass_total = cell.mass_g * total_cells
    debugger.add_step(
        category="Mass",
        description="Total cell mass",
        formula="m_cells = m_cell * N_cells",
        variables={
            "m_cell": cell.mass_g,
            "N_cells": total_cells
        },
        result=cell_mass_total,
        result_name="m_cells",
        result_unit="g"
    )

    # Interconnect mass (estimated)
    interconnect_mass = 0.8 * total_cells * 2  # ~0.8g per connection, 2 per cell
    debugger.add_step(
        category="Mass",
        description="Interconnect mass estimate",
        formula="m_interconnect = 0.8 * N_cells * 2",
        variables={"N_cells": total_cells},
        result=interconnect_mass,
        result_name="m_interconnect",
        result_unit="g",
        comment="Estimated for nickel strips"
    )

    # Total mass
    total_mass = cell_mass_total + interconnect_mass
    debugger.add_step(
        category="Mass",
        description="Total pack mass",
        formula="m_total = m_cells + m_interconnect",
        variables={
            "m_cells": cell_mass_total,
            "m_interconnect": interconnect_mass
        },
        result=total_mass,
        result_name="m_total",
        result_unit="g"
    )

    # Energy density
    energy_density = pack_energy / (total_mass / 1000.0)
    debugger.add_step(
        category="Mass",
        description="Gravimetric energy density",
        formula="e_density = E_pack / (m_total / 1000)",
        variables={
            "E_pack": pack_energy,
            "m_total": total_mass
        },
        result=energy_density,
        result_name="e_density",
        result_unit="Wh/kg"
    )

    debugger.finish()
    return debugger
