import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import omaquickcalc_state as state


REPOSITORY = Path(__file__).resolve().parents[1]
STATE_HELPER = REPOSITORY / "omaquickcalc_state.py"


class BoundedStateReaderTests(unittest.TestCase):
    def test_ordinary_utf8_state_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            content = '{"inputHint":"2 × 2"}\n'
            path.write_text(content, encoding="utf-8")
            self.assertEqual(state.read_state(path, 1024), content)

    def test_symlinked_state_remains_supported(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "tracked-config.json"
            link = Path(directory) / "config.json"
            target.write_text('{"historyMode":"session"}\n', encoding="utf-8")
            link.symlink_to(target)
            self.assertEqual(state.read_state(link, 1024), target.read_text(encoding="utf-8"))

    def test_oversized_state_is_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.json"
            path.write_bytes(b"x" * 33)
            with self.assertRaises(state.StateFileTooLarge):
                state.read_state(path, 32)

    def test_invalid_utf8_and_non_regular_files_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            invalid = Path(directory) / "invalid.json"
            invalid.write_bytes(b"\xff")
            with self.assertRaises(state.StateFileInvalid):
                state.read_state(invalid, 32)
            with self.assertRaises(state.StateFileInvalid):
                state.read_state(Path(directory), 32)

    def test_cli_emits_no_content_for_oversized_state(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_bytes(b"x" * (state.STATE_LIMITS["config"] + 1))
            process = subprocess.run(
                [sys.executable, str(STATE_HELPER), "read", "--kind", "config",
                 "--path", str(path)],
                capture_output=True,
                check=False,
                timeout=2,
            )
        self.assertEqual(process.returncode, state.EXIT_TOO_LARGE)
        self.assertEqual(process.stdout, b"")
        self.assertEqual(process.stderr, b"")

    def test_cli_distinguishes_a_missing_file(self):
        process = subprocess.run(
            [sys.executable, str(STATE_HELPER), "read", "--kind", "launch",
             "--path", "/definitely/missing/omaquickcalc-state"],
            capture_output=True,
            check=False,
            timeout=2,
        )
        self.assertEqual(process.returncode, state.EXIT_MISSING)
        self.assertEqual(process.stdout, b"")


if __name__ == "__main__":
    unittest.main()
