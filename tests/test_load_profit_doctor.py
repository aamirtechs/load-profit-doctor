"""Tests for load_profit_doctor."""

import io
import json
import os
import sys
import tempfile
import unittest
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

import load_profit_doctor as lpd


def defaults(**overrides):
    """Default evaluation settings, with optional overrides."""
    base = {
        "cost_per_mile": Decimal("2.34"),
        "min_profit_per_mile": Decimal("0.50"),
        "dispatch_fee_percent": Decimal("0"),
        "factoring_percent": Decimal("0"),
    }
    base.update(overrides)
    return base


def good_load(**overrides):
    """A profitable load, with optional field overrides."""
    load = {"id": "L-1", "loaded_miles": 500, "deadhead_miles": 50,
            "gross_pay": 2000}
    load.update(overrides)
    return load


class TestEvaluateLoad(unittest.TestCase):
    def test_profitable_load_accept(self):
        record, error = lpd.evaluate_load(good_load(), 0, defaults())
        self.assertIsNone(error)
        self.assertEqual(record["verdict"], "ACCEPT")
        self.assertEqual(record["total_miles"], Decimal("550"))
        self.assertEqual(record["operating_cost"], Decimal("1287.00"))
        self.assertEqual(record["net_profit"], Decimal("713.00"))
        self.assertEqual(record["profit_per_total_mile"],
                         Decimal("1.30"))
        self.assertEqual(record["profit_per_loaded_mile"],
                         Decimal("1.43"))
        self.assertEqual(record["margin_percent"], Decimal("35.65"))

    def test_deadhead_kills_profit(self):
        record, error = lpd.evaluate_load(
            good_load(deadhead_miles=500, gross_pay=2100), 0,
            defaults())
        self.assertIsNone(error)
        self.assertEqual(record["verdict"], "REJECT")
        self.assertEqual(record["net_profit"], Decimal("-240.00"))
        self.assertEqual(record["deadhead_percent"], Decimal("50.00"))

    def test_marginal_between_zero_and_threshold(self):
        record, error = lpd.evaluate_load(
            good_load(gross_pay=1400), 0, defaults())
        self.assertIsNone(error)
        self.assertEqual(record["verdict"], "MARGINAL")
        self.assertEqual(record["net_profit"], Decimal("113.00"))

    def test_linehaul_plus_fuel_surcharge(self):
        record, error = lpd.evaluate_load(
            good_load(linehaul=1800, fuel_surcharge=200,
                      gross_pay=None), 0, defaults())
        self.assertIsNone(error)
        self.assertEqual(record["revenue"], Decimal("2000.00"))

    def test_accessorials_add_to_revenue(self):
        record, error = lpd.evaluate_load(
            good_load(linehaul=1800, fuel_surcharge=150,
                      accessorials=50, gross_pay=None), 0, defaults())
        self.assertIsNone(error)
        self.assertEqual(record["revenue"], Decimal("2000.00"))

    def test_gross_pay_wins_over_parts(self):
        record, error = lpd.evaluate_load(
            good_load(gross_pay=2000, linehaul=9999), 0, defaults())
        self.assertIsNone(error)
        self.assertEqual(record["revenue"], Decimal("2000.00"))

    def test_dispatch_and_factoring_fees(self):
        record, error = lpd.evaluate_load(
            good_load(dispatch_fee_percent=5, factoring_percent=3),
            0, defaults())
        self.assertIsNone(error)
        self.assertEqual(record["dispatch_fee"], Decimal("100.00"))
        self.assertEqual(record["factoring_fee"], Decimal("60.00"))
        self.assertEqual(record["net_profit"], Decimal("553.00"))

    def test_tolls_reduce_profit(self):
        record, error = lpd.evaluate_load(good_load(tolls=40), 0,
                                          defaults())
        self.assertIsNone(error)
        self.assertEqual(record["net_profit"], Decimal("673.00"))

    def test_break_even_loaded_rate(self):
        record, error = lpd.evaluate_load(good_load(), 0, defaults())
        self.assertIsNone(error)
        self.assertEqual(record["break_even_loaded_rate"],
                         Decimal("2.57"))

    def test_effective_hourly_rate(self):
        record, error = lpd.evaluate_load(good_load(hours=10), 0,
                                          defaults())
        self.assertIsNone(error)
        self.assertEqual(record["effective_hourly_rate"],
                         Decimal("71.30"))

    def test_no_hours_means_no_hourly_rate(self):
        record, error = lpd.evaluate_load(good_load(), 0, defaults())
        self.assertIsNone(error)
        self.assertNotIn("effective_hourly_rate", record)

    def test_custom_cost_per_mile(self):
        record, error = lpd.evaluate_load(good_load(), 0,
                                          defaults(
                                              cost_per_mile=Decimal("2.00")))
        self.assertIsNone(error)
        self.assertEqual(record["operating_cost"], Decimal("1100.00"))
        self.assertEqual(record["net_profit"], Decimal("900.00"))

    def test_per_load_cost_overrides_default(self):
        record, error = lpd.evaluate_load(
            good_load(cost_per_mile="1.50"), 0, defaults())
        self.assertIsNone(error)
        self.assertEqual(record["operating_cost"], Decimal("825.00"))

    def test_min_profit_threshold_from_defaults(self):
        record, error = lpd.evaluate_load(
            good_load(gross_pay=1400), 0,
            defaults(min_profit_per_mile=Decimal("0.10")))
        self.assertIsNone(error)
        self.assertEqual(record["verdict"], "ACCEPT")

    def test_missing_revenue_is_error(self):
        record, error = lpd.evaluate_load(
            {"id": "L-9", "loaded_miles": 100}, 0, defaults())
        self.assertIsNone(record)
        self.assertIn("needs gross_pay", error)

    def test_negative_miles_is_error(self):
        record, error = lpd.evaluate_load(
            good_load(loaded_miles=-10), 0, defaults())
        self.assertIsNone(record)
        self.assertIn("negative", error)

    def test_negative_deadhead_is_error(self):
        record, error = lpd.evaluate_load(
            good_load(deadhead_miles=-5), 0, defaults())
        self.assertIsNone(record)
        self.assertIn("negative", error)

    def test_zero_miles_is_error(self):
        record, error = lpd.evaluate_load(
            good_load(loaded_miles=0, deadhead_miles=0), 0, defaults())
        self.assertIsNone(record)
        self.assertIn("above zero", error)

    def test_zero_loaded_miles_is_error(self):
        record, error = lpd.evaluate_load(
            good_load(loaded_miles=0, deadhead_miles=10), 0, defaults())
        self.assertIsNone(record)
        self.assertIn("loaded_miles must be above zero", error)

    def test_fee_over_100_is_error(self):
        record, error = lpd.evaluate_load(
            good_load(dispatch_fee_percent=150), 0, defaults())
        self.assertIsNone(record)
        self.assertIn("0 to 100", error)

    def test_string_numbers_accepted(self):
        record, error = lpd.evaluate_load(
            good_load(gross_pay="$2,000"), 0, defaults())
        self.assertIsNone(error)
        self.assertEqual(record["revenue"], Decimal("2000.00"))

    def test_lane_and_equipment_kept(self):
        record, error = lpd.evaluate_load(
            good_load(lane="DAL to OKC", equipment="reefer"), 0,
            defaults())
        self.assertIsNone(error)
        self.assertEqual(record["lane"], "DAL to OKC")
        self.assertEqual(record["equipment"], "reefer")


class TestEvaluate(unittest.TestCase):
    def test_ranking_by_profit_per_total_mile(self):
        report = lpd.evaluate(
            [good_load(id="A", gross_pay=1400),
             good_load(id="B", gross_pay=2000),
             good_load(id="C", gross_pay=1000)], defaults())
        self.assertEqual([r["id"] for r in report["loads"]],
                         ["B", "A", "C"])
        self.assertEqual([r["rank"] for r in report["loads"]],
                         [1, 2, 3])

    def test_totals(self):
        report = lpd.evaluate(
            [good_load(id="A", gross_pay=2000),
             good_load(id="B", gross_pay=1000)], defaults())
        totals = report["totals"]
        self.assertEqual(totals["loads"], 2)
        self.assertEqual(totals["total_revenue"], Decimal("3000.00"))
        self.assertEqual(totals["total_net_profit"],
                         Decimal("426.00"))
        self.assertEqual(totals["accept"], 1)
        self.assertEqual(totals["reject"], 1)
        self.assertEqual(totals["best_load"], "A")
        self.assertEqual(totals["worst_load"], "B")

    def test_errors_do_not_stop_report(self):
        report = lpd.evaluate(
            [good_load(), {"id": "BAD", "loaded_miles": 100}],
            defaults())
        self.assertEqual(len(report["loads"]), 1)
        self.assertEqual(len(report["errors"]), 1)

    def test_object_with_loads_list(self):
        report = lpd.evaluate({"loads": [good_load()]}, defaults())
        self.assertEqual(len(report["loads"]), 1)

    def test_bad_document_shape(self):
        with self.assertRaises(lpd.LoadError):
            lpd.evaluate("not a list", defaults())
        with self.assertRaises(lpd.LoadError):
            lpd.evaluate({"nope": []}, defaults())

    def test_empty_list(self):
        report = lpd.evaluate([], defaults())
        self.assertEqual(report["totals"]["loads"], 0)
        self.assertEqual(report["totals"]["total_net_profit"],
                         Decimal("0.00"))


class TestTextAndJson(unittest.TestCase):
    def test_text_output_contains_verdicts(self):
        report = lpd.evaluate([good_load()], defaults())
        text = lpd.format_text(report)
        self.assertIn("L-1", text)
        self.assertIn("ACCEPT", text)
        self.assertIn("Loads: 1", text)

    def test_json_round_trip(self):
        report = lpd.evaluate([good_load()], defaults())
        text = json.dumps(report, default=lpd.decimal_default)
        parsed = json.loads(text)
        self.assertEqual(parsed["loads"][0]["net_profit"], "713.00")


class TestCli(unittest.TestCase):
    def run_cli(self, args, content):
        """Run main() against a temp JSON file, capturing stdout."""
        with tempfile.NamedTemporaryFile("w", suffix=".json",
                                        delete=False) as handle:
            handle.write(content)
            path = handle.name
        try:
            saved = sys.stdout
            sys.stdout = io.StringIO()
            try:
                code = lpd.main([path] + args)
                output = sys.stdout.getvalue()
            finally:
                sys.stdout = saved
            return code, output
        finally:
            os.unlink(path)

    def test_cli_text_exit_zero(self):
        code, output = self.run_cli(
            [], json.dumps([good_load()]))
        self.assertEqual(code, 0)
        self.assertIn("ACCEPT", output)

    def test_cli_check_fails_on_reject(self):
        code, output = self.run_cli(
            ["--check"], json.dumps([good_load(gross_pay=1000)]))
        self.assertEqual(code, 1)

    def test_cli_check_passes_on_accept(self):
        code, output = self.run_cli(["--check"],
                                    json.dumps([good_load()]))
        self.assertEqual(code, 0)

    def test_cli_json_flag(self):
        code, output = self.run_cli(["--json"],
                                    json.dumps([good_load()]))
        self.assertEqual(code, 0)
        parsed = json.loads(output)
        self.assertEqual(parsed["loads"][0]["verdict"], "ACCEPT")

    def test_cli_missing_file(self):
        code = lpd.main(["/nonexistent/loads.json"])
        self.assertEqual(code, 2)

    def test_cli_bad_json(self):
        code, output = self.run_cli([], "{not json")
        self.assertEqual(code, 2)

    def test_cli_cost_override(self):
        code, output = self.run_cli(
            ["--cost-per-mile", "1.00"], json.dumps([good_load()]))
        self.assertEqual(code, 0)
        self.assertIn("$1450.00", output)


if __name__ == "__main__":
    unittest.main()
