"""
Battery Calculator Validation Tests
====================================

Validates battery pack calculations against third-party test data.

Data Sources:
- Battery Mooch (https://www.e-cigarette-forum.com/blogs/mooch.256958/)
- Manufacturer datasheets

Test Methodology:
- Verify IR values match Battery Mooch measurements
- Verify voltage sag calculations are physically reasonable
- Verify SOC-OCV curves match published data
- Verify max current calculations are conservative
"""

import sys
from pathlib import Path
import unittest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.battery_calculator import (
    BatteryPack,
    CellSpec,
    CELL_DATABASE,
    get_cell,
    list_cells,
    BatteryCalculatorConfig,
    FormFactor,
    CellChemistry,
)
from src.battery_calculator.calculations.electrical import (
    soc_to_ocv,
    calculate_pack_ir,
    calculate_voltage_sag,
    calculate_loaded_voltage,
)


class TestCellDatabase(unittest.TestCase):
    """Test cell database contents and verified data."""

    def test_database_not_empty(self):
        """Verify cell database has entries."""
        self.assertGreater(len(CELL_DATABASE), 0)

    def test_verified_cells_exist(self):
        """Verify key cells with Battery Mooch data exist."""
        expected_cells = [
            "Molicel P45B",
            "Samsung 40T",
            "Samsung 30Q",
        ]
        for cell_name in expected_cells:
            self.assertIn(cell_name, CELL_DATABASE, f"Missing verified cell: {cell_name}")

    def test_molicel_p45b_specs(self):
        """Verify Molicel P45B matches Battery Mooch test data.

        Battery Mooch P45B test results:
        - DC IR: 11-13 mOhm at 50% SOC
        - Max continuous: 45A
        - Capacity: 4500mAh
        """
        cell = CELL_DATABASE["Molicel P45B"]

        # IR should be in Mooch's measured range
        self.assertGreaterEqual(cell.dc_ir_mohm, 10)
        self.assertLessEqual(cell.dc_ir_mohm, 15)

        # Max discharge should match datasheet
        self.assertEqual(cell.max_continuous_discharge_a, 45)

        # Capacity
        self.assertEqual(cell.capacity_mah, 4500)

        # Verified flag
        self.assertTrue(cell.verified)
        self.assertEqual(cell.data_source, "mooch")

    def test_samsung_40t_specs(self):
        """Verify Samsung 40T matches Battery Mooch test data.

        Battery Mooch 40T test results:
        - DC IR: 13.5-14.1 mOhm at 50% SOC
        - Max continuous: 25-35A (temperature dependent)
        - Capacity: 4000mAh
        """
        cell = CELL_DATABASE["Samsung 40T"]

        # IR should be in Mooch's measured range
        self.assertGreaterEqual(cell.dc_ir_mohm, 12)
        self.assertLessEqual(cell.dc_ir_mohm, 16)

        # Capacity
        self.assertEqual(cell.capacity_mah, 4000)

        # Verified
        self.assertTrue(cell.verified)

    def test_samsung_30q_specs(self):
        """Verify Samsung 30Q matches Battery Mooch test data.

        Battery Mooch 30Q test results:
        - DC IR: ~18 mOhm at 50% SOC
        - Max continuous: 15-20A
        - Capacity: 3000mAh
        """
        cell = CELL_DATABASE["Samsung 30Q"]

        # IR should be approximately 18 mOhm
        self.assertGreaterEqual(cell.dc_ir_mohm, 15)
        self.assertLessEqual(cell.dc_ir_mohm, 22)

        # Capacity
        self.assertEqual(cell.capacity_mah, 3000)


class TestSOCtoOCV(unittest.TestCase):
    """Test SOC to OCV conversion accuracy."""

    def test_full_charge_voltage(self):
        """100% SOC should give 4.2V for NMC chemistry."""
        ocv = soc_to_ocv(100.0, CellChemistry.NMC)
        self.assertAlmostEqual(ocv, 4.20, places=2)

    def test_empty_voltage(self):
        """0% SOC should give ~3.0V for NMC chemistry."""
        ocv = soc_to_ocv(0.0, CellChemistry.NMC)
        self.assertAlmostEqual(ocv, 3.0, places=1)

    def test_nominal_voltage(self):
        """50% SOC should give ~3.7-3.8V for NMC chemistry."""
        ocv = soc_to_ocv(50.0, CellChemistry.NMC)
        self.assertGreaterEqual(ocv, 3.70)
        self.assertLessEqual(ocv, 3.85)

    def test_monotonic_decrease(self):
        """OCV should decrease monotonically with SOC."""
        prev_ocv = 5.0
        for soc in range(100, -1, -10):
            ocv = soc_to_ocv(float(soc), CellChemistry.NMC)
            self.assertLess(ocv, prev_ocv, f"OCV not decreasing at SOC={soc}")
            prev_ocv = ocv

    def test_lfp_voltage_range(self):
        """LFP chemistry should have flatter voltage curve."""
        ocv_100 = soc_to_ocv(100.0, CellChemistry.LFP)
        ocv_50 = soc_to_ocv(50.0, CellChemistry.LFP)
        ocv_0 = soc_to_ocv(0.0, CellChemistry.LFP)

        # LFP full charge is ~3.6V
        self.assertAlmostEqual(ocv_100, 3.60, places=1)

        # LFP is flatter than NMC in the middle range
        self.assertLess(ocv_100 - ocv_50, 0.4)


class TestVoltageCalculations(unittest.TestCase):
    """Test voltage sag and loaded voltage calculations."""

    def setUp(self):
        """Set up test cell and pack."""
        self.cell = CELL_DATABASE["Molicel P45B"]
        self.series = 6
        self.parallel = 2

    def test_pack_ir_calculation(self):
        """Verify pack IR calculation is correct.

        Pack IR = (Cell IR × Series) / Parallel
        For 6S2P P45B: (12 × 6) / 2 = 36 mOhm
        """
        pack_ir = calculate_pack_ir(
            self.cell, self.series, self.parallel,
            soc_percent=50.0, temp_c=25.0
        )

        # Should be approximately 36 mOhm
        self.assertGreaterEqual(pack_ir, 30)
        self.assertLessEqual(pack_ir, 45)

    def test_voltage_sag_at_current(self):
        """Verify voltage sag calculation.

        V_sag = I × R_pack
        At 30A with 36 mOhm pack: 30 × 0.036 = 1.08V
        """
        v_sag = calculate_voltage_sag(
            self.cell, self.series, self.parallel,
            current_a=30.0, soc_percent=50.0, temp_c=25.0
        )

        # Should be approximately 1V
        self.assertGreaterEqual(v_sag, 0.8)
        self.assertLessEqual(v_sag, 1.5)

    def test_loaded_voltage(self):
        """Verify loaded voltage calculation.

        At 50% SOC, 6S pack OCV ~22.8V
        Minus 1V sag at 30A = ~21.8V loaded
        """
        v_loaded = calculate_loaded_voltage(
            self.cell, self.series, self.parallel,
            current_a=30.0, soc_percent=50.0, temp_c=25.0
        )

        # Should be in reasonable range
        self.assertGreaterEqual(v_loaded, 20.0)
        self.assertLessEqual(v_loaded, 23.0)

    def test_voltage_sag_increases_with_current(self):
        """Voltage sag should increase linearly with current."""
        sag_10a = calculate_voltage_sag(
            self.cell, self.series, self.parallel,
            current_a=10.0, soc_percent=50.0, temp_c=25.0
        )
        sag_30a = calculate_voltage_sag(
            self.cell, self.series, self.parallel,
            current_a=30.0, soc_percent=50.0, temp_c=25.0
        )

        # 30A should have 3x the sag of 10A
        ratio = sag_30a / sag_10a
        self.assertAlmostEqual(ratio, 3.0, places=1)


class TestBatteryPackIntegration(unittest.TestCase):
    """Test BatteryPack class integration."""

    def setUp(self):
        """Set up test pack."""
        self.cell = CELL_DATABASE["Molicel P45B"]
        self.pack = BatteryPack(
            self.cell,
            series=6,
            parallel=2,
            config=BatteryCalculatorConfig()
        )

    def test_pack_configuration(self):
        """Test basic pack configuration."""
        self.assertEqual(self.pack.configuration_string, "6S2P")
        self.assertEqual(self.pack.total_cells, 12)

    def test_nominal_voltage(self):
        """Test nominal voltage calculation."""
        # 6S × 3.6V = 21.6V (P45B uses 3.6V nominal)
        self.assertAlmostEqual(self.pack.nominal_voltage, 21.6, places=1)

    def test_capacity(self):
        """Test capacity calculation."""
        # 4500mAh × 2P = 9000mAh
        self.assertEqual(self.pack.capacity_mah, 9000)

    def test_energy(self):
        """Test energy calculation."""
        # 9Ah × 22.2V = 199.8 Wh
        self.assertGreaterEqual(self.pack.energy_wh, 190)
        self.assertLessEqual(self.pack.energy_wh, 210)

    def test_mass(self):
        """Test mass calculation."""
        # 12 cells × ~70g = ~840g cells only
        mass_g = self.pack.get_total_mass_g()
        self.assertGreaterEqual(mass_g, 800)
        self.assertLessEqual(mass_g, 1000)

    def test_max_continuous_current(self):
        """Test max continuous current calculation.

        Default is now drone_in_flight (4 C/W per cell) which is appropriate for drones.
        Test that different thermal environments affect max current appropriately.
        """
        max_i, limiting_factor = self.pack.get_max_continuous_current()

        # With default drone_in_flight, should get reasonable current for 6S2P
        # 30A should be easily within limits (cells only at 15A each vs 45A rating)
        self.assertGreater(max_i, 30)
        self.assertIn(limiting_factor, ["thermal", "rating", "voltage"])

        # Test with still air (worse cooling)
        config_still = BatteryCalculatorConfig(thermal_environment="still_air")
        pack_still = BatteryPack(self.cell, series=6, parallel=2, config=config_still)
        max_i_still, limit_still = pack_still.get_max_continuous_current()

        # Still air should have LOWER max current than drone_in_flight
        self.assertLess(max_i_still, max_i)

        # Test with active cooling (better)
        config_active = BatteryCalculatorConfig(thermal_environment="active_cooling")
        pack_active = BatteryPack(self.cell, series=6, parallel=2, config=config_active)
        max_i_active, limit_active = pack_active.get_max_continuous_current()

        # Active cooling should be better than drone_in_flight
        self.assertGreater(max_i_active, max_i)
        self.assertLessEqual(max_i_active, 90)  # Can't exceed cell rating

    def test_voltage_at_current(self):
        """Test voltage under load."""
        # At 30A, 80% SOC
        v = self.pack.get_voltage_at_current(30.0, soc=80.0, temp_c=25.0)

        # Should be reasonable voltage
        self.assertGreater(v, 20.0)
        self.assertLess(v, 26.0)

    def test_heat_generation(self):
        """Test heat generation calculation."""
        # At 30A
        heat_w = self.pack.get_heat_generation_w(30.0, soc=50.0, temp_c=25.0)

        # P = I²R = 30² × 0.036 × 1.1 ≈ 36W
        self.assertGreater(heat_w, 25)
        self.assertLess(heat_w, 50)


class TestPhysicalLayoutOptional(unittest.TestCase):
    """Test that physical layout is properly optional."""

    def test_geometry_disabled_by_default(self):
        """Geometry should be disabled by default."""
        config = BatteryCalculatorConfig()
        self.assertFalse(config.enable_geometry)

    def test_geometry_raises_when_disabled(self):
        """Geometry methods should raise when disabled."""
        cell = CELL_DATABASE["Molicel P45B"]
        pack = BatteryPack(cell, series=6, parallel=2)

        with self.assertRaises(RuntimeError):
            pack.get_dimensions_mm()

        with self.assertRaises(RuntimeError):
            pack.get_cog_mm()

    def test_geometry_works_when_enabled(self):
        """Geometry methods should work when enabled."""
        cell = CELL_DATABASE["Molicel P45B"]
        config = BatteryCalculatorConfig(enable_geometry=True)
        pack = BatteryPack(cell, series=6, parallel=2, config=config)

        dims = pack.get_dimensions_mm()
        self.assertEqual(len(dims), 3)
        self.assertTrue(all(d > 0 for d in dims))

        cog = pack.get_cog_mm()
        self.assertEqual(len(cog), 3)


class TestCalculationAccuracy(unittest.TestCase):
    """Test calculation accuracy against known reference values.

    Reference values from Battery Mooch tests and physics.
    """

    def test_voltage_sag_physics(self):
        """Verify voltage sag follows Ohm's law: V = IR."""
        cell = CELL_DATABASE["Molicel P45B"]

        # Single cell at 30A
        pack_ir = calculate_pack_ir(cell, 1, 1, 50.0, 25.0)  # mOhm
        v_sag = calculate_voltage_sag(cell, 1, 1, 30.0, 50.0, 25.0)

        # V = I × R
        expected_sag = 30.0 * (pack_ir / 1000.0)
        self.assertAlmostEqual(v_sag, expected_sag, places=3)

    def test_ir_temperature_coefficient(self):
        """Verify IR increases at low temperature.

        Standard coefficient: ~0.7% per degree C from 25C reference.
        At 0C, IR should be ~17.5% higher than at 25C.
        """
        cell = CELL_DATABASE["Molicel P45B"]

        ir_25c = calculate_pack_ir(cell, 1, 1, 50.0, 25.0)
        ir_0c = calculate_pack_ir(cell, 1, 1, 50.0, 0.0)

        # IR at 0C should be higher
        self.assertGreater(ir_0c, ir_25c)

        # Should be approximately 17.5% higher
        ratio = ir_0c / ir_25c
        self.assertGreater(ratio, 1.10)
        self.assertLess(ratio, 1.30)

    def test_ir_soc_variation(self):
        """Verify IR is lowest around 50% SOC (U-shaped curve)."""
        cell = CELL_DATABASE["Molicel P45B"]

        ir_100 = calculate_pack_ir(cell, 1, 1, 100.0, 25.0)
        ir_50 = calculate_pack_ir(cell, 1, 1, 50.0, 25.0)
        ir_20 = calculate_pack_ir(cell, 1, 1, 20.0, 25.0)

        # IR at 50% should be lowest
        self.assertLess(ir_50, ir_100)
        self.assertLess(ir_50, ir_20)


class TestThermalCalculations(unittest.TestCase):
    """Test thermal calculations for physical correctness.

    These tests verify that thermal modeling produces realistic results
    and that thermal limits are consistent with steady-state temperatures.
    """

    def setUp(self):
        """Set up test pack."""
        self.cell = CELL_DATABASE["Molicel P45B"]
        self.pack = BatteryPack(
            self.cell,
            series=6,
            parallel=2,
            config=BatteryCalculatorConfig(thermal_environment="drone_in_flight")
        )

    def test_steady_state_temp_realistic(self):
        """Verify steady-state temperatures are physically realistic.

        At 30A on 6S2P P45B pack (drone_in_flight cooling):
        - Heat generation ~35W
        - Temperature rise should be 10-20C above ambient
        """
        steady_temp = self.pack.get_steady_state_temp(30.0, soc=50.0)

        # Should be above ambient but not extreme
        self.assertGreater(steady_temp, 25.0)  # Above ambient
        self.assertLess(steady_temp, 60.0)     # Below max rated

        # Reasonable range for 35W heat
        self.assertGreater(steady_temp, 30.0)
        self.assertLess(steady_temp, 50.0)

    def test_steady_state_temp_not_extreme(self):
        """Verify no physically impossible temperatures (the old bug)."""
        # At 50A, should still be well below 100C
        steady_temp = self.pack.get_steady_state_temp(50.0, soc=50.0)
        self.assertLess(steady_temp, 100.0)

        # At 30A, should definitely be < 50C in flight
        steady_temp_30a = self.pack.get_steady_state_temp(30.0, soc=50.0)
        self.assertLess(steady_temp_30a, 50.0)

    def test_thermal_limit_consistency(self):
        """Verify thermal limit current produces max allowed temperature.

        Critical consistency check: if max current is X amps and thermal limited,
        then steady-state temp at X amps should equal max_temp.
        """
        max_current, limiting_factor = self.pack.get_max_continuous_current(50.0)

        if limiting_factor == "thermal":
            steady_at_limit = self.pack.get_steady_state_temp(max_current, 50.0)
            max_temp = self.pack.config.max_cell_temp_c

            # Should be within 1C of max allowed temp
            self.assertAlmostEqual(steady_at_limit, max_temp, delta=1.0)

    def test_heat_generation_proportional_to_current_squared(self):
        """Verify heat generation follows I²R relationship."""
        heat_10a = self.pack.get_heat_generation_w(10.0, 50.0)
        heat_20a = self.pack.get_heat_generation_w(20.0, 50.0)
        heat_30a = self.pack.get_heat_generation_w(30.0, 50.0)

        # Heat should scale with I²
        ratio_20_10 = heat_20a / heat_10a
        ratio_30_10 = heat_30a / heat_10a

        self.assertAlmostEqual(ratio_20_10, 4.0, delta=0.2)  # (20/10)² = 4
        self.assertAlmostEqual(ratio_30_10, 9.0, delta=0.5)  # (30/10)² = 9

    def test_thermal_environment_affects_temperature(self):
        """Verify different thermal environments produce different temperatures."""
        cell = CELL_DATABASE["Molicel P45B"]

        # Still air (worst cooling)
        pack_still = BatteryPack(
            cell, series=6, parallel=2,
            config=BatteryCalculatorConfig(thermal_environment="still_air")
        )

        # Drone in flight (good cooling)
        pack_flight = BatteryPack(
            cell, series=6, parallel=2,
            config=BatteryCalculatorConfig(thermal_environment="drone_in_flight")
        )

        # Active cooling (best)
        pack_active = BatteryPack(
            cell, series=6, parallel=2,
            config=BatteryCalculatorConfig(thermal_environment="active_cooling")
        )

        temp_still = pack_still.get_steady_state_temp(30.0, 50.0)
        temp_flight = pack_flight.get_steady_state_temp(30.0, 50.0)
        temp_active = pack_active.get_steady_state_temp(30.0, 50.0)

        # Better cooling = lower temperature
        self.assertGreater(temp_still, temp_flight)
        self.assertGreater(temp_flight, temp_active)

    def test_thermal_time_constant_reasonable(self):
        """Verify thermal time constant is physically reasonable."""
        # For a ~850g pack with Cp=1.0 J/g·K and R_th=4/12 C/W
        # tau = m * Cp * R_th = 871 * 1.0 * (4/12) = 290 seconds ~ 5 minutes
        tau = self.pack._thermal_model.thermal_time_constant_s

        # Should be in reasonable range for battery pack
        self.assertGreater(tau, 100)   # At least 1-2 minutes
        self.assertLess(tau, 1000)     # Less than 15 minutes

    def test_zero_current_no_temperature_rise(self):
        """At zero current, steady-state should equal ambient."""
        steady_temp = self.pack.get_steady_state_temp(0.0, 50.0)
        self.assertAlmostEqual(steady_temp, self.pack.config.ambient_temp_c, delta=0.1)


def run_validation():
    """Run validation tests and print summary."""
    print("=" * 60)
    print("Battery Calculator Validation")
    print("=" * 60)
    print()

    # Run tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestCellDatabase))
    suite.addTests(loader.loadTestsFromTestCase(TestSOCtoOCV))
    suite.addTests(loader.loadTestsFromTestCase(TestVoltageCalculations))
    suite.addTests(loader.loadTestsFromTestCase(TestBatteryPackIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestPhysicalLayoutOptional))
    suite.addTests(loader.loadTestsFromTestCase(TestCalculationAccuracy))
    suite.addTests(loader.loadTestsFromTestCase(TestThermalCalculations))

    # Run with verbosity
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print()
    print("=" * 60)
    if result.wasSuccessful():
        print("All validation tests PASSED")
    else:
        print(f"FAILED: {len(result.failures)} failures, {len(result.errors)} errors")
    print("=" * 60)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_validation()
    sys.exit(0 if success else 1)
