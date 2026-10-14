import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import omaquickcalc_paste as paste


class BoundedPasteTests(unittest.TestCase):
    def read(self, code, limit=64, duration=0.3):
        return paste.read_bounded([sys.executable, "-c", code], time.monotonic() + duration, limit)

    def test_small_offer(self):
        self.assertEqual(self.read("import os;os.write(1,b'12+3')"), b"12+3")

    def test_reader_address_space_is_capped(self):
        value = self.read("import resource;print(resource.getrlimit(resource.RLIMIT_AS)[0])")
        self.assertLessEqual(int(value), paste.MAX_READER_MEMORY)

    def test_exact_byte_cap_is_allowed(self):
        self.assertEqual(self.read("import os;os.write(1,b'x'*64)"), b"x" * 64)

    def test_oversized_offer_is_rejected(self):
        with self.assertRaisesRegex(paste.PasteError, "too large"):
            self.read("import os;os.write(1,b'x'*65)")

    def test_stalled_offer_has_absolute_timeout(self):
        started = time.monotonic()
        with self.assertRaisesRegex(paste.PasteError, "timed out"):
            self.read("import time;time.sleep(2)", duration=0.15)
        self.assertLess(time.monotonic() - started, 0.8)

    def test_continuous_small_chunks_do_not_reset_deadline(self):
        with self.assertRaisesRegex(paste.PasteError, "timed out"):
            self.read("import os,time\nfor i in range(100):\n os.write(1,b'x');time.sleep(.02)", duration=0.15)

    def test_stderr_is_also_bounded(self):
        with self.assertRaisesRegex(paste.PasteError, "too large"):
            self.read("import os;os.write(2,b'x'*4097)")

    def test_timeout_reaps_reader(self):
        spawn = subprocess.Popen
        processes = []

        def record_process(*args, **kwargs):
            process = spawn(*args, **kwargs)
            processes.append(process)
            return process

        with patch.object(paste.subprocess, "Popen", side_effect=record_process):
            with self.assertRaises(paste.PasteError):
                self.read("import time;time.sleep(2)", duration=0.2)
        self.assertEqual(len(processes), 1)
        self.assertIsNotNone(processes[0].poll())
        with self.assertRaises(ProcessLookupError):
            os.kill(processes[0].pid, 0)

    def test_nonzero_reader_exit_does_not_insert_partial_text(self):
        with self.assertRaisesRegex(paste.PasteError, "unavailable"):
            self.read("import os;os.write(1,b'12');raise SystemExit(1)")

    def test_utf8_plain_text_and_single_line_normalization(self):
        with patch.object(paste, "read_bounded", side_effect=[b"text/plain;charset=utf-8\n", "é\n2\x00".encode()]):
            self.assertEqual(paste.read_paste(), "é 2")

    def test_utf16_capacity_counts_non_bmp_characters(self):
        with patch.object(paste, "read_bounded", side_effect=[b"text/plain\n", "😀".encode()]):
            with self.assertRaisesRegex(paste.PasteError, "does not fit"):
                paste.read_paste(maximum=1)

    def test_invalid_utf8_is_rejected(self):
        with patch.object(paste, "read_bounded", side_effect=[b"text/plain\n", b"\xff"]):
            with self.assertRaisesRegex(paste.PasteError, "valid UTF-8"):
                paste.read_paste()

    def test_unsupported_mime_is_not_fetched(self):
        with patch.object(paste, "read_bounded", return_value=b"text/html\n") as read:
            with self.assertRaisesRegex(paste.PasteError, "plain text"):
                paste.read_paste()
            self.assertEqual(read.call_count, 1)

    def test_primary_selection_requires_explicit_request_and_reuses_deadline(self):
        with patch.object(paste, "read_bounded", side_effect=[b"text/plain\n", b"12"]) as read:
            self.assertEqual(paste.read_paste(primary=True), "12")
            calls = read.call_args_list
            self.assertTrue(all("--primary" in call.args[0] for call in calls))
            self.assertEqual(calls[0].args[1], calls[1].args[1])

    def test_cli_with_fake_provider_never_contacts_live_clipboard(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "wl-paste"
            executable.write_text("#!/usr/bin/python3\nimport sys\nprint('text/plain' if '--list-types' in sys.argv else '12+3',end='\\n' if '--list-types' in sys.argv else '')\n")
            executable.chmod(0o700)
            environment = dict(os.environ, PATH=directory, WAYLAND_DISPLAY="", DISPLAY="")
            process = subprocess.run([sys.executable, str(Path(paste.__file__)), "--max-characters", "4"],
                                     env=environment, capture_output=True, text=True, timeout=3)
            self.assertEqual(process.returncode, 0)
            self.assertEqual(json.loads(process.stdout), {"ok": True, "text": "12+3"})


if __name__ == "__main__":
    unittest.main()
