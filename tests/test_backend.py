import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
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
            "500 * 0.5 in usd": "(500 * 0.5) USD to USD",
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

    @patch("omaquickcalc_backend._run_qalc_bounded")
    def test_unit_conversion_returns_a_swappable_expression(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, "3.048 m\n", "")
        result = backend.evaluate("10ft in m")
        self.assertTrue(result.ok)
        self.assertEqual(result.kind, "unit")
        self.assertEqual(result.swapExpression, "3.048 m to ft")

    @patch("omaquickcalc_backend._run_qalc_bounded")
    def test_currency_has_numeric_unformatted_result(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, "£74.9475\n", "")
        result = backend.evaluate("100 usd in gbp")
        self.assertEqual(result.kind, "currency")
        self.assertTrue(result.dynamic)
        self.assertEqual(result.result, "£74.95")
        self.assertEqual(result.rawResult, "74.9475")
        self.assertEqual(result.swapExpression, "74.9475 GBP to USD")

    @patch("omaquickcalc_backend._run_qalc_bounded")
    def test_currency_rounds_half_up_and_preserves_grouping(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, "$1,234.565\n", "")
        result = backend.evaluate("1700 cad in usd")
        self.assertEqual(result.result, "$1,234.57")
        self.assertEqual(result.rawResult, "1234.565")

    @patch("omaquickcalc_backend._run_qalc_bounded")
    def test_symbol_led_dollar_conversion_keeps_symbol_and_target_code(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, "CAD 142.195\n", "")
        result = backend.evaluate("$100 in CAD")
        self.assertEqual(result.result, "CAD $142.20")
        self.assertEqual(result.rawResult, "142.195")

    @patch("omaquickcalc_backend._run_qalc_bounded")
    def test_arithmetic_is_evaluated_before_currency_formatting(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, "$250\n", "")
        result = backend.evaluate("500 * 0.5 in usd")
        self.assertTrue(result.ok)
        self.assertEqual(result.result, "$250.00")
        self.assertEqual(result.rawResult, "250")
        self.assertEqual(result.normalizedExpression, "(500 * 0.5) USD to USD")
        self.assertFalse(result.dynamic)
        self.assertEqual(result.swapExpression, "")
        self.assertEqual(result.rateDate, "")


class StructuredEvaluatorTests(unittest.TestCase):
    @patch("omaquickcalc_backend._run_qalc_bounded")
    def test_name_easter_eggs_are_local_and_copyable(self, run):
        expected = {
            "  QuAtTrO  ": ("4", "Fast by design."),
            "Euler": ("2.718281828459045", "eⁱπ + 1 = 0"),
            "Fibonacci": ("1, 1, 2, 3, 5, 8, 13, 21", "The pattern continues."),
            "Gauss": ("5050", "Pair the ends."),
            "Ramanujan": ("1729", "1³ + 12³ = 9³ + 10³"),
            "DHH": ("37", "Convention over configuration."),
        }
        for expression, (value, note) in expected.items():
            with self.subTest(expression=expression):
                result = backend.evaluate(expression)
                self.assertTrue(result.ok)
                self.assertEqual(result.result, value)
                self.assertEqual(result.rawResult, value)
                self.assertEqual(result.kind, "easter-egg")
                self.assertEqual(result.note, note)
        run.assert_not_called()

    def test_design_and_duration_calculations(self):
        self.assertEqual(backend.evaluate("64px in rem").result, "4 rem")
        self.assertEqual(backend.evaluate("50rem").result, "800 px")
        self.assertEqual(backend.evaluate("1000px").result, "62.5 rem")
        self.assertEqual(backend.evaluate("10cm").result, "3.937007874 in")
        self.assertEqual(backend.evaluate("10in").result, "25.4 cm")
        self.assertEqual(backend.evaluate("90 mins to timespan").result, "1 hour 30 minutes")
        self.assertEqual(backend.evaluate("16 h in workdays").result, "2 workdays")

    @patch("omaquickcalc_backend._run_qalc_bounded")
    def test_incomplete_or_arbitrary_text_does_not_leak_qalculate_constants(self, run):
        for expression in ("50r", "50re", "10c", "10i", "quatt", "hello world"):
            with self.subTest(expression=expression):
                result = backend.evaluate(expression)
                self.assertFalse(result.ok)
                self.assertTrue(result.pending)
                self.assertEqual(result.error, "")
        run.assert_not_called()

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

    def test_numeric_formats_do_not_expand_huge_scientific_results(self):
        formats = backend.numeric_formats("9.900656229e301029", 10)
        self.assertNotIn("Fraction", {item["label"] for item in formats})
        self.assertNotIn("Binary", {item["label"] for item in formats})
        self.assertNotIn("Octal", {item["label"] for item in formats})
        self.assertNotIn("Hexadecimal", {item["label"] for item in formats})
        self.assertTrue(all(len(item["value"]) <= backend.MAX_FORMAT_VALUE_CHARS
                            for item in formats))

    def test_expression_length_is_bounded_before_evaluation(self):
        result = backend.evaluate("1" * (backend.MAX_EXPRESSION_LENGTH + 1))
        self.assertFalse(result.ok)
        self.assertEqual(result.error, "Expression is too long")

    def test_clock_format_is_configurable(self):
        value = backend.datetime(2030, 1, 2, 17, 5, tzinfo=backend.timezone.utc)
        self.assertEqual(backend.format_clock(value, "12"), "5:05 PM")
        self.assertEqual(backend.format_clock(value, "24"), "17:05")
        self.assertEqual(backend.format_clock(value, "12"),
                         backend.format_clock(value, backend.DEFAULT_CLOCK_FORMAT))

    def test_timezone_shorthand_converts_to_local_time(self):
        target = backend.ZoneInfo("America/Winnipeg")
        with patch("omaquickcalc_backend.local_zone", return_value=target):
            for phrase in ("1pm pacific", "1pm vancouver", "1pm pdt", "1pm pt", "1pm pst"):
                with self.subTest(phrase=phrase):
                    result = backend.evaluate(phrase, clock_format="12")
                    self.assertTrue(result.ok)
                    self.assertEqual(result.kind, "timezone")
                    source = backend.resolve_zone(phrase.split(maxsplit=1)[1])
                    source_value = backend.datetime.combine(
                        backend.datetime.now(source).date(), backend.time(13), source)
                    expected = backend.format_timezone_conversion(
                        source_value, source_value.astimezone(target), "12")
                    self.assertEqual(result.result, expected)
        self.assertEqual(backend.resolve_zone("pdt").utcoffset(None), backend.timedelta(hours=-7))
        self.assertEqual(backend.resolve_zone("pst").utcoffset(None), backend.timedelta(hours=-8))

    def test_timezone_conversion_only_includes_date_across_day_boundary(self):
        same_day = backend.evaluate("1pm Vancouver in Winnipeg", clock_format="12")
        self.assertRegex(same_day.result, r"^3:00 PM C[DS]T$")

        next_day = backend.evaluate("5pm London in Tokyo", clock_format="12")
        self.assertRegex(next_day.result, r"^[12]:00 AM · .+ · JST$")

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

    def test_rate_cache_reader_rejects_oversized_sparse_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rates.json"
            with path.open("wb") as stream:
                stream.truncate(1024 * 1024 * 1024)
            with self.assertRaises(backend.RateCacheTooLarge):
                backend._read_rate_cache(path)

    def test_rate_cache_reader_preserves_ordinary_utf8(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rates.json"
            content = '{"date":"2026-08-20","label":"café"}'
            path.write_text(content, encoding="utf-8")
            self.assertEqual(backend._read_rate_cache(path), content)

    def test_ambiguous_three_letter_text_is_not_a_hex_color(self):
        self.assertIsNone(backend.color_evaluation("abc"))
        self.assertTrue(backend.color_evaluation("#abc").ok)

    def test_unknown_timezone_is_an_error_not_unit_math(self):
        result = backend.evaluate("time in definitely-not-a-timezone")
        self.assertFalse(result.ok)
        self.assertEqual(result.kind, "timezone")

    def test_incomplete_or_out_of_range_live_input_never_crashes(self):
        expressions = (
            "rgb(.., 0, 0)",
            "10 px in inches at 0 ppi",
            "workhours in 0000",
            "March 4 + 999999999999999999999 days",
            "time in " + "9" * 400 + " hours",
        )
        for expression in expressions:
            with self.subTest(expression=expression[:40]):
                result = backend.evaluate(expression)
                self.assertFalse(result.ok)
                self.assertEqual(result.error, "Calculation is out of range")


class BoundedQalcProcessTests(unittest.TestCase):
    def test_ordinary_process_output_is_collected(self):
        process = backend._run_qalc_bounded(
            [sys.executable, "-c", "print('4')"], 2.0
        )
        self.assertEqual(process.returncode, 0)
        self.assertEqual(process.stdout, "4\n")
        self.assertEqual(process.stderr, "")

    def test_stdout_over_limit_terminates_the_process(self):
        command = [
            sys.executable,
            "-c",
            f"import sys; sys.stdout.buffer.write(b'x' * {backend.MAX_QALC_STDOUT_BYTES + 1})",
        ]
        with self.assertRaises(backend.QalcOutputLimitError):
            backend._run_qalc_bounded(command, 2.0)

    def test_stderr_over_limit_terminates_the_process(self):
        command = [
            sys.executable,
            "-c",
            f"import sys; sys.stderr.buffer.write(b'x' * {backend.MAX_QALC_STDERR_BYTES + 1})",
        ]
        with self.assertRaises(backend.QalcOutputLimitError):
            backend._run_qalc_bounded(command, 2.0)

    def test_child_address_space_is_limited(self):
        command = [
            sys.executable,
            "-c",
            "import resource; print(resource.getrlimit(resource.RLIMIT_AS)[0])",
        ]
        process = backend._run_qalc_bounded(command, 2.0)
        self.assertEqual(process.returncode, 0)
        self.assertLessEqual(int(process.stdout), backend.MAX_QALC_MEMORY_BYTES)

    @patch("omaquickcalc_backend._run_qalc_bounded")
    def test_large_qalc_result_is_rejected_before_parsing(self, run):
        run.return_value = subprocess.CompletedProcess(
            [], 0, "1" * (backend.MAX_RESULT_TEXT_BYTES + 1), ""
        )
        result = backend.evaluate("2^100")
        self.assertFalse(result.ok)
        self.assertEqual(result.error, "Calculation result is too large")

    def test_json_payload_size_is_bounded(self):
        self.assertIsNone(
            backend.encode_json_payload({"result": "x" * 100}, byte_limit=16)
        )


if __name__ == "__main__":
    unittest.main()
