import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import omaquickcalc_transform as transform


PLUGIN_ID = "io.github.camerontucker.omaquickcalc"


class TransformStateTests(unittest.TestCase):
    def test_selection_is_numeric_bounded_and_single_line(self):
        self.assertEqual(transform.normalize_selection("  100 CAD\n"), "100 CAD")
        self.assertEqual(transform.normalize_selection("5 ft  11 in"), "5 ft 11 in")
        self.assertEqual(transform.normalize_selection("selected words"), "")
        self.assertEqual(transform.normalize_selection("1" * 513), "")

    def test_runtime_state_is_private_single_use(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"XDG_RUNTIME_DIR": directory}):
                token = transform.write_state(
                    "100 CAD", {"address": "0x123abc", "pid": 4242}, False
                )
                path = transform.state_path(token)
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                self.assertEqual(transform.consume_state(token), {
                    "selection": "100 CAD",
                    "windowAddress": "0x123abc",
                    "windowPid": 4242,
                    "terminal": False,
                })
                self.assertFalse(path.exists())

    def test_pending_state_waits_for_capture_without_blocking_summon(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"XDG_RUNTIME_DIR": directory}):
                token = transform.write_pending_state(
                    {"address": "0x123abc", "pid": 4242}, False
                )
                transform.complete_pending_state(token, "100 CAD")
                self.assertEqual(transform.consume_state(token)["selection"], "100 CAD")

    def test_invalid_token_cannot_escape_runtime_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"XDG_RUNTIME_DIR": directory}):
                with self.assertRaises(ValueError):
                    transform.state_path("../selection")

    def test_expired_state_is_rejected_and_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"XDG_RUNTIME_DIR": directory}):
                token = transform.write_state(
                    "100 CAD", {"address": "0x123abc", "pid": 4242}, False
                )
                path = transform.state_path(token)
                expired = transform.time.time() - transform.STATE_MAX_AGE_SECONDS - 1
                os.utime(path, (expired, expired))
                with self.assertRaisesRegex(RuntimeError, "expired"):
                    transform.consume_state(token)
                self.assertFalse(path.exists())

    def test_invalid_origin_cannot_create_state(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"XDG_RUNTIME_DIR": directory}):
                with self.assertRaises(ValueError):
                    transform.write_state("100 CAD", {"address": "", "pid": 0}, False)


class TransformWorkflowTests(unittest.TestCase):
    @patch("omaquickcalc_transform.subprocess.run")
    def test_capture_refuses_an_unrestorable_clipboard_format(self, run):
        run.return_value = subprocess.CompletedProcess(
            [], 0, "application/x-secret\n", ""
        )
        with self.assertRaisesRegex(RuntimeError, "cannot be restored"):
            transform.clipboard_snapshot()

    @patch("omaquickcalc_transform.restore_clipboard")
    @patch("omaquickcalc_transform.read_clipboard_text",
           side_effect=["omaquickcalc-sentinel", "100 CAD"])
    @patch("omaquickcalc_transform.send_shortcut", return_value=True)
    @patch("omaquickcalc_transform.clipboard_snapshot")
    @patch("omaquickcalc_transform.subprocess.run")
    @patch("omaquickcalc_transform.secrets.token_hex", return_value="sentinel")
    @patch("omaquickcalc_transform.time.sleep")
    def test_capture_restores_clipboard_and_returns_selection(
        self, _sleep, _token, run, snapshot, _send, _read, restore
    ):
        previous = transform.ClipboardSnapshot("text/plain", b"previous")
        snapshot.return_value = previous
        run.return_value = subprocess.CompletedProcess([], 0, b"", b"")

        self.assertEqual(transform.capture_selection(False), "100 CAD")
        restore.assert_called_once_with(previous)

    def test_capture_state_survives_until_overlay_consumes_it(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"XDG_RUNTIME_DIR": directory}):
                with patch("omaquickcalc_transform.active_window", return_value={
                    "address": "0xabc", "pid": 4242, "tags": []
                }):
                    events = []
                    with patch("omaquickcalc_transform.capture_selection",
                               side_effect=lambda *_args: events.append("capture") or "64px"):
                        with patch("omaquickcalc_transform.summon", return_value=0) as summon:
                            summon.side_effect = lambda *_args: events.append("summon") or 0
                            status = transform.capture_and_summon(PLUGIN_ID)
                self.assertEqual(status, 0)
                self.assertEqual(events, ["summon", "capture"])
                token = summon.call_args.args[1]
                self.assertTrue(transform.state_path(token).exists())
                self.assertEqual(transform.consume_state(token)["selection"], "64px")

    @patch("omaquickcalc_transform.send_shortcut", return_value=True)
    @patch("omaquickcalc_transform.active_window",
           return_value={"address": "0xabc", "pid": 4242})
    @patch("omaquickcalc_transform.subprocess.run")
    @patch("omaquickcalc_transform.time.sleep")
    def test_replace_pastes_only_into_origin_window(self, _sleep, run, active, send):
        run.return_value = subprocess.CompletedProcess([], 0, b"", b"")
        status = transform.replace_selection("$72.61", "0xabc", 4242, False)
        self.assertEqual(status, 0)
        active.assert_called_once()
        send.assert_called_once_with("CTRL", "V")
        self.assertEqual(run.call_args_list[0].args[0], ["wl-copy", "--", "$72.61"])

    @patch("omaquickcalc_transform.send_shortcut")
    @patch("omaquickcalc_transform.active_window",
           return_value={"address": "0xother", "pid": 9999})
    @patch("omaquickcalc_transform.subprocess.run")
    @patch("omaquickcalc_transform.time.sleep")
    @patch("omaquickcalc_transform.time.monotonic", side_effect=[0, 2])
    def test_replace_refuses_to_paste_into_another_window(
        self, _clock, _sleep, run, _active, send
    ):
        run.return_value = subprocess.CompletedProcess([], 0, b"", b"")
        self.assertEqual(transform.replace_selection("4 rem", "0xabc", 4242, False), 1)
        send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
