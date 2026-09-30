import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from microgrid_portfolio.billing import BillingRates, cash_bill
from microgrid_portfolio.controller import Battery, rollout, step
from microgrid_portfolio.demo import run_demo


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.battery = Battery(10, 100, 20, 20, 0.9, 0.9)

    def test_deficit_discharge_and_balance(self):
        result = step(60, load=40, pv=5, contract=20, charge_target=0, battery=self.battery)
        self.assertAlmostEqual(result["discharge"], 15)
        self.assertAlmostEqual(result["emergency"], 0)
        self.assertAlmostEqual(result["balance_residual"], 0)

    def test_low_soc_forces_emergency_purchase(self):
        result = step(10, load=40, pv=0, contract=20, charge_target=0, battery=self.battery)
        self.assertAlmostEqual(result["emergency"], 20)

    def test_rollout_rejects_mismatched_lengths(self):
        with self.assertRaises(ValueError):
            rollout(60, [1, 2], [0], [1, 2], [0, 0], self.battery)


class BillingTests(unittest.TestCase):
    def test_cash_bill_components(self):
        bill = cash_bill([1], [100], [80], [2], BillingRates())
        self.assertAlmostEqual(bill["normal_contract"], 80)
        self.assertAlmostEqual(bill["cancellation_penalty"], 10)
        self.assertAlmostEqual(bill["emergency_purchase"], 10)
        self.assertAlmostEqual(bill["total"], 100)


class DemoTests(unittest.TestCase):
    def test_demo_is_deterministic_and_feasible(self):
        first, _ = run_demo()
        second, _ = run_demo()
        self.assertEqual(first, second)
        self.assertEqual(first["intervals"], 144)
        self.assertTrue(first["soc_bounds_satisfied"])
        self.assertTrue(first["charge_discharge_mutually_exclusive"])
        self.assertLessEqual(first["max_balance_residual_kwh"], 1e-7)
        self.assertTrue(math.isfinite(first["cash_bill_with_storage"]))


if __name__ == "__main__":
    unittest.main()
