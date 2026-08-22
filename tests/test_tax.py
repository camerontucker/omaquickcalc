import json
import subprocess
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import omaquickcalc_backend as backend
import omaquickcalc_tax as tax


class TaxQueryTests(unittest.TestCase):
    def test_tax_is_a_suffix_over_the_complete_expression(self):
        query = tax.parse_tax_query("900 + 100 tax")
        self.assertEqual(query.amount_expression, "900 + 100")
        self.assertEqual(query.location, "")

        located = tax.parse_tax_query("(1200 - 200) tax in Ontario")
        self.assertEqual(located.amount_expression, "(1200 - 200)")
        self.assertEqual(located.location, "Ontario")

        custom = tax.parse_tax_query("900 + 100 tax at 8.25%")
        self.assertEqual(custom.amount_expression, "900 + 100")
        self.assertEqual(custom.custom_rate, "8.25")

    def test_unrelated_calculations_are_not_tax_queries(self):
        self.assertIsNone(tax.parse_tax_query("tax"))
        self.assertIsNone(tax.parse_tax_query("1000 taxable units"))
        self.assertIsNone(tax.parse_tax_query("1000 + 5%"))


class TaxCatalogTests(unittest.TestCase):
    def setUp(self):
        self.catalog = tax.load_catalog()
        self.jurisdictions, self.aliases = tax.jurisdiction_maps(self.catalog)

    def test_catalog_covers_every_canadian_province_and_territory(self):
        self.assertEqual(
            {identifier for identifier in self.jurisdictions if identifier.startswith("CA-")},
            {
                "CA-AB", "CA-BC", "CA-MB", "CA-NB", "CA-NL", "CA-NS", "CA-NT",
                "CA-NU", "CA-ON", "CA-PE", "CA-QC", "CA-SK", "CA-YT",
            },
        )
        self.assertEqual(self.jurisdictions["CA-NS"]["components"],
                         [{"code": "HST", "rate": "0.14"}])
        self.assertEqual(self.jurisdictions["CA-QC"]["components"][1]["rate"], "0.09975")

    def test_catalog_rates_are_sourced_and_reviewed(self):
        reviewed = date.fromisoformat(self.catalog["reviewedOn"])
        self.assertLessEqual((date.today() - reviewed).days, 366)
        for identifier, profile in self.jurisdictions.items():
            with self.subTest(identifier=identifier):
                self.assertTrue(profile["sources"])
                self.assertTrue(all(source.startswith("https://")
                                    for source in profile["sources"]))
                self.assertTrue(profile["components"])
                for component in profile["components"]:
                    rate = Decimal(component["rate"])
                    self.assertGreater(rate, 0)
                    self.assertLess(rate, 1)

    def test_catalog_locations_are_available_in_preferences(self):
        repository = Path(__file__).resolve().parents[1]
        model = (repository / "OmaQuickCalcModel.js").read_text(encoding="utf-8")
        qml = (repository / "OmaQuickCalc.qml").read_text(encoding="utf-8")
        for identifier in self.jurisdictions:
            with self.subTest(identifier=identifier):
                self.assertIn(f'"{identifier}"', model)
                self.assertIn(f'"{identifier}"', qml)

    def test_alias_and_timezone_resolution(self):
        profile, inferred = tax.resolve_jurisdiction("Québec", self.catalog)
        self.assertEqual(profile["id"], "CA-QC")
        self.assertFalse(inferred)

        profile, inferred = tax.resolve_jurisdiction(
            "auto", self.catalog, timezone_name="America/Winnipeg"
        )
        self.assertEqual(profile["id"], "CA-MB")
        self.assertTrue(inferred)

        profile, inferred = tax.resolve_jurisdiction(
            "auto", self.catalog, timezone_name="Europe/Berlin"
        )
        self.assertEqual(profile["id"], "DE")
        self.assertTrue(inferred)

    def test_every_report_reconciles_to_the_displayed_total(self):
        for identifier, profile in self.jurisdictions.items():
            with self.subTest(identifier=identifier):
                report = tax.build_report(Decimal("1000"), profile, self.catalog, False)
                self.assertEqual(len(report["sections"]),
                                 3 if identifier.startswith("CA-") else 2)
                self.assertEqual(report["sections"][0]["rows"][-1]["rawValue"],
                                 report["rawResult"])
                for section in report["sections"]:
                    values = [Decimal(row["rawValue"]) for row in section["rows"]]
                    self.assertEqual(sum(values[:-1]), values[-1])


class TaxEvaluationTests(unittest.TestCase):
    def test_manitoba_report_has_add_reverse_and_gst_only_sections(self):
        result = backend.evaluate("1000 tax", tax_location="CA-MB")
        self.assertTrue(result.ok)
        self.assertEqual(result.kind, "tax")
        self.assertEqual(result.result, "$1,120.00")
        self.assertEqual(result.rawResult, "1120")
        self.assertTrue(result.dynamic)
        self.assertEqual([section["title"] for section in result.report["sections"]],
                         ["Add tax", "Tax included", "GST only included"])
        self.assertEqual(
            [(row["label"], row["value"])
             for row in result.report["sections"][1]["rows"]],
            [
                ("Before tax", "$892.86"),
                ("GST (5%)", "$44.64"),
                ("PST (7%)", "$62.50"),
                ("Total", "$1,000.00"),
            ],
        )

    @patch("omaquickcalc_backend._run_qalc_bounded")
    def test_currency_symbols_are_accepted_as_amount_notation(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, "1000\n", "")
        direct = backend.evaluate("$1000 tax", tax_location="CA-MB")
        self.assertEqual(direct.result, "$1,120.00")

        arithmetic = backend.evaluate("$900 + $100 tax", tax_location="CA-MB")
        self.assertEqual(arithmetic.result, "$1,120.00")
        self.assertEqual(run.call_args.args[0][-1], "900 + 100")

    @patch("omaquickcalc_backend._run_qalc_bounded")
    def test_arithmetic_prefix_is_evaluated_before_tax(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, "1000\n", "")
        result = backend.evaluate("900 + 100 tax", tax_location="CA-MB")
        self.assertTrue(result.ok)
        self.assertEqual(result.result, "$1,120.00")
        command = run.call_args.args[0]
        self.assertEqual(command[-1], "900 + 100")
        self.assertNotIn("tax", command[-1])

    def test_inline_location_overrides_preference(self):
        result = backend.evaluate("1000 tax in Ontario", tax_location="CA-MB")
        self.assertEqual(result.result, "$1,130.00")
        self.assertEqual(result.report["location"], "CA-ON")
        self.assertEqual(result.report["sections"][0]["rows"][1]["label"], "HST (13%)")

    def test_major_national_vat_and_gst_profiles_use_two_sections(self):
        cases = {
            "Germany": ("€1,190.00", "VAT (19%)"),
            "Australia": ("$1,100.00", "GST (10%)"),
            "Japan": ("¥1,100", "Consumption tax (10%)"),
            "Mexico": ("$1,160.00", "IVA (16%)"),
        }
        for location, (expected, component) in cases.items():
            with self.subTest(location=location):
                result = backend.evaluate(f"1000 tax in {location}", tax_location="CA-MB")
                self.assertEqual(result.result, expected)
                self.assertEqual(len(result.report["sections"]), 2)
                self.assertEqual(result.report["sections"][0]["rows"][1]["label"], component)

    @patch("omaquickcalc_backend._run_qalc_bounded")
    def test_inline_and_preference_custom_rates_cover_local_combined_schemes(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, "1000\n", "")
        inline = backend.evaluate("1000 tax at 8.25%", tax_location="auto")
        self.assertEqual(inline.result, "$1,082.50")
        self.assertEqual(inline.report["location"], "CUSTOM")
        self.assertEqual(len(inline.report["sections"]), 2)

        saved = backend.evaluate("900 + 100 tax", tax_location="custom",
                                 tax_custom_rate=8.25)
        self.assertEqual(saved.result, "$1,082.50")

        missing = backend.evaluate("1000 tax", tax_location="custom")
        self.assertFalse(missing.ok)
        self.assertEqual(missing.error, "Set a custom tax rate in Preferences")

    def test_auto_location_uses_system_timezone_without_network(self):
        with patch("omaquickcalc_tax.system_timezone", return_value="America/Winnipeg"):
            result = backend.evaluate("1000 tax", tax_location="auto")
        self.assertTrue(result.ok)
        self.assertEqual(result.report["location"], "CA-MB")
        self.assertTrue(result.report["locationInferred"])
        self.assertIn("Auto", result.note)

    def test_unknown_or_ambiguous_location_is_an_actionable_error(self):
        unknown = backend.evaluate("1000 tax in Atlantis", tax_location="CA-MB")
        self.assertFalse(unknown.ok)
        self.assertEqual(unknown.error, "Unsupported tax location: Atlantis")

        with patch("omaquickcalc_tax.system_timezone", return_value="Etc/UTC"), \
                patch.dict(backend.os.environ, {"LC_ADDRESS": "C", "LC_ALL": "C", "LANG": "C"}, clear=False):
            ambiguous = backend.evaluate("1000 tax", tax_location="auto")
        self.assertFalse(ambiguous.ok)
        self.assertEqual(ambiguous.error, "Choose a tax location in Preferences")

    def test_incomplete_and_non_numeric_tax_inputs_do_not_leak_qalculate_results(self):
        incomplete = backend.evaluate("900 + tax", tax_location="CA-MB")
        self.assertFalse(incomplete.ok)
        self.assertTrue(incomplete.pending)

        unit = backend.evaluate("10 metres tax", tax_location="CA-MB")
        self.assertFalse(unit.ok)
        self.assertEqual(unit.error, "Tax requires a unitless numeric amount")

    def test_cli_json_contains_the_structured_report(self):
        with patch("sys.argv", ["omaquickcalc_backend.py", "--expression", "1000 tax",
                                "--tax-location", "CA-MB"]), \
                patch("builtins.print") as output:
            self.assertEqual(backend.main(), 0)
        payload = json.loads(output.call_args.args[0])
        self.assertEqual(payload["kind"], "tax")
        self.assertEqual(len(payload["report"]["sections"]), 3)


if __name__ == "__main__":
    unittest.main()
