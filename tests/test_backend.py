import subprocess
import unittest
from unittest.mock import patch

import omaquickcalc_backend as backend


class NaturalLanguageTests(unittest.TestCase):
    def test_common_raycast_phrases_are_normalized(self):
        cases = {
            "10ft in m": "10 ft to m",
            "52% of 900": "52% * (900)",
            "square root of 625": "sqrt(625)",
            "2 power 10": "(2) ^ (10)",
            "20% off 125": "(125) * (1 - 20%)",
            "18% tip on 80": "(80) * (1 + 18%)",
            "10k usd in gbp": "10000 USD to GBP",
            "$2.5m in cad": "2500000 USD to CAD",
        }
        for phrase, expected in cases.items():
            with self.subTest(phrase=phrase):
                self.assertEqual(backend.normalize_natural_language(phrase), expected)

    def test_currency_aliases_locale_and_defaults(self):
        cases = {
            "$1.500,25 in CAD": "1500.25 USD to CAD",
            "1,500.25 euros to pounds": "1500.25 EUR to GBP",
            "500 quid to eur": "500 GBP to EUR",
            "usd 420 to dkk": "420 USD to DKK",
            "500 to euros": "500 USD to EUR",
            "$500": "500 USD to CAD",
        }
        for phrase, expected in cases.items():
            with self.subTest(phrase=phrase):
                self.assertEqual(backend.normalize_natural_language(phrase), expected)

    def test_default_currency_pair_is_configurable(self):
        self.assertEqual(backend.normalize_natural_language("500 eur", "GBP", "USD"),
                         "500 EUR to USD")
        self.assertEqual(backend.normalize_natural_language("500 to cad", "GBP", "USD"),
                         "500 GBP to CAD")

    @patch("omaquickcalc_backend.subprocess.run")
    def test_unit_conversion_returns_a_swappable_expression(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, "3.048 m\n", "")
        result = backend.evaluate("10ft in m")
        self.assertTrue(result.ok)
        self.assertEqual(result.kind, "unit")
        self.assertEqual(result.swapExpression, "3.048 m to ft")

    @patch("omaquickcalc_backend.subprocess.run")
    def test_currency_has_numeric_unformatted_result(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, "£74.9475\n", "")
        result = backend.evaluate("100 usd in gbp")
        self.assertEqual(result.kind, "currency")
        self.assertTrue(result.dynamic)
        self.assertEqual(result.rawResult, "74.9475")
        self.assertEqual(result.swapExpression, "74.9475 GBP to USD")


class StructuredEvaluatorTests(unittest.TestCase):
    def test_design_and_duration_calculations(self):
        self.assertEqual(backend.evaluate("64px in rem").result, "4 rem")
        self.assertEqual(backend.evaluate("90 mins to timespan").result, "1 hour 30 minutes")
        self.assertEqual(backend.evaluate("16 h in workdays").result, "2 workdays")

    def test_natural_date_addition(self):
        result = backend.evaluate("March 4, 2030 + 45 days")
        self.assertTrue(result.ok)
        self.assertEqual(result.rawResult, "2030-04-18")

    def test_color_exposes_all_copy_formats(self):
        result = backend.evaluate("hsl(32, 100%, 50%)")
        self.assertEqual(result.result, "#FF8800")
        self.assertEqual(result.colorHex, "#FF8800")
        self.assertEqual([item["label"] for item in result.formats],
                         ["HEX", "RGB", "HSL", "OKLCH", "LAB"])

    def test_numeric_formats_include_bases_and_fraction(self):
        integer = backend.numeric_formats("1024", 10)
        self.assertIn({"label": "Binary", "value": "0b10000000000"}, integer)
        self.assertIn({"label": "Hexadecimal", "value": "0x400"}, integer)
        fraction = backend.numeric_formats("0.3333333333", 10)
        self.assertIn({"label": "Fraction", "value": "1/3"}, fraction)

    def test_clock_format_is_configurable(self):
        value = backend.datetime(2030, 1, 2, 17, 5, tzinfo=backend.timezone.utc)
        self.assertEqual(backend.format_clock(value, "12"), "5:05 PM")
        self.assertEqual(backend.format_clock(value, "24"), "17:05")

    def test_rate_metadata_reports_freshness(self):
        with patch.dict("omaquickcalc_backend.os.environ", {
            "OMAQUICKCALC_QALCULATE_DATA_DIR": "tests/fixtures"
        }, clear=False):
            rate_date, source, age, stale = backend.rate_metadata(7)
        self.assertEqual(rate_date, "2026-08-20")
        self.assertEqual(source, "Qalculate cache")
        expected_age = max(0, (backend.date.today() - backend.date.fromisoformat(rate_date)).days)
        self.assertEqual(age, expected_age)
        self.assertEqual(stale, expected_age > 7)

    def test_ambiguous_three_letter_text_is_not_a_hex_color(self):
        self.assertIsNone(backend.color_evaluation("abc"))
        self.assertTrue(backend.color_evaluation("#abc").ok)

    def test_unknown_timezone_is_an_error_not_unit_math(self):
        result = backend.evaluate("time in definitely-not-a-timezone")
        self.assertFalse(result.ok)
        self.assertEqual(result.kind, "timezone")


if __name__ == "__main__":
    unittest.main()
