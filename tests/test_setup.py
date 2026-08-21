import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import omaquickcalc_setup as setup

PLUGIN_ID = "io.github.camerontucker.omaquickcalc"


class ShortcutTests(unittest.TestCase):
    def test_shortcut_normalization_and_validation(self):
        self.assertEqual(setup.canonical_shortcut("ctrl + super + q"), "SUPER + CTRL + Q")
        with self.assertRaises(ValueError):
            setup.canonical_shortcut("Q")
        with self.assertRaises(ValueError):
            setup.canonical_shortcut('SUPER + Q\"')

    def test_keybinding_output_reports_conflicts(self):
        parsed = setup.parse_keybindings(
            "SUPER CTRL + Q                      → Calculator\n"
            "SUPER ALT + Q                       → Another action\n"
        )
        self.assertEqual(parsed[setup.shortcut_identity("SUPER + CTRL + Q")], "Calculator")
        self.assertEqual(parsed[setup.shortcut_identity("SUPER + ALT + Q")], "Another action")

    def test_apply_preserves_user_content_and_replaces_only_owned_block(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bindings.lua"
            path.write_text('-- personal\no.bind("SUPER + X", "Mine", "thing")\n', encoding="utf-8")
            first = setup.apply_shortcut(path, "SUPER + ALT + Q", PLUGIN_ID, False)
            second = setup.apply_shortcut(path, "SUPER + SHIFT + Q", PLUGIN_ID, False)
            content = path.read_text(encoding="utf-8")
        self.assertTrue(first["ok"] and second["ok"])
        self.assertIn('o.bind("SUPER + X", "Mine", "thing")', content)
        self.assertIn('hl.unbind("SUPER + SHIFT + Q")', content)
        self.assertNotIn('hl.unbind("SUPER + ALT + Q")', content)
        self.assertEqual(content.count(setup.BINDING_START), 1)

    def test_failed_hyprland_validation_rolls_back(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bindings.lua"
            original = "-- untouched\n"
            path.write_text(original, encoding="utf-8")
            with patch("omaquickcalc_setup.hyprland_reload", return_value=(False, "bad config")):
                result = setup.apply_shortcut(path, "SUPER + ALT + Q", PLUGIN_ID)
            self.assertFalse(result["ok"])
            self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_failed_cleanup_validation_restores_owned_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bindings.lua"
            setup.apply_shortcut(path, "SUPER + ALT + Q", PLUGIN_ID, False)
            original = path.read_text(encoding="utf-8")
            with patch("omaquickcalc_setup.hyprland_reload", return_value=(False, "bad config")):
                with patch("omaquickcalc_setup.subprocess.run"):
                    result = setup.cleanup(Path(directory) / "missing.desktop", path)
            self.assertFalse(result["ok"])
            self.assertEqual(path.read_text(encoding="utf-8"), original)


class LifecycleTests(unittest.TestCase):
    def test_default_cleanup_removes_owned_legacy_launcher(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            current = root / f"{PLUGIN_ID}.desktop"
            legacy = root / "omaquickcalc.desktop"
            bindings = root / "bindings.lua"
            setup.ensure_launcher(current, PLUGIN_ID, "0.5.0")
            setup.ensure_launcher(legacy, "omaquickcalc", "0.4.0")
            result = setup.cleanup(current, bindings, False, (legacy,))
            self.assertTrue(result["ok"])
            self.assertFalse(current.exists())
            self.assertFalse(legacy.exists())

    def test_launcher_create_upgrade_conflict_and_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            desktop = root / "applications" / f"{PLUGIN_ID}.desktop"
            bindings = root / "hypr" / "bindings.lua"

            created = setup.ensure_launcher(desktop, PLUGIN_ID, "0.5.0")
            upgraded = setup.ensure_launcher(desktop, PLUGIN_ID, "0.5.1")
            self.assertEqual(created["action"], "created")
            self.assertEqual(upgraded["action"], "updated")
            self.assertIn("X-OmaQuickCalc-Version=0.5.1", desktop.read_text(encoding="utf-8"))

            setup.apply_shortcut(bindings, "SUPER + ALT + Q", PLUGIN_ID, False)
            removed = setup.cleanup(desktop, bindings, False)
            self.assertTrue(removed["ok"])
            self.assertFalse(desktop.exists())
            self.assertNotIn(setup.BINDING_START, bindings.read_text(encoding="utf-8"))

            desktop.write_text("[Desktop Entry]\nName=User file\n", encoding="utf-8")
            conflict = setup.ensure_launcher(desktop, PLUGIN_ID, "0.5.2")
            self.assertFalse(conflict["ok"])
            self.assertEqual(desktop.read_text(encoding="utf-8"), "[Desktop Entry]\nName=User file\n")

    def test_cli_install_launch_upgrade_and_remove(self):
        helper = Path(__file__).resolve().parents[1] / "omaquickcalc_setup.py"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "config"
            data = root / "data"
            binaries = root / "bin"
            launch_log = root / "launched.txt"
            binaries.mkdir()
            fake_shell = binaries / "omarchy-shell"
            fake_shell.write_text(
                "#!/bin/sh\nprintf '%s\\n' \"$*\" > \"$OMAQUICKCALC_LAUNCH_LOG\"\n",
                encoding="utf-8",
            )
            fake_shell.chmod(0o755)
            environment = os.environ.copy()
            environment.update({
                "XDG_CONFIG_HOME": str(config),
                "XDG_DATA_HOME": str(data),
                "PATH": f"{binaries}:{environment['PATH']}",
                "OMAQUICKCALC_LAUNCH_LOG": str(launch_log),
            })

            installed = subprocess.run(
                [str(helper), "ensure-launcher", "--version", "0.5.0"],
                check=True, capture_output=True, text=True, env=environment,
            )
            self.assertEqual(json.loads(installed.stdout)["action"], "created")
            desktop = data / "applications" / f"{PLUGIN_ID}.desktop"
            if shutil.which("desktop-file-validate"):
                subprocess.run(["desktop-file-validate", str(desktop)], check=True)

            if shutil.which("gtk-launch"):
                subprocess.run(["gtk-launch", PLUGIN_ID], check=True, env=environment)
                for _ in range(20):
                    if launch_log.exists():
                        break
                    time.sleep(0.05)
                self.assertEqual(
                    launch_log.read_text(encoding="utf-8").strip(),
                    f"shell summon {PLUGIN_ID} {{}}",
                )

            subprocess.run(
                [str(helper), "apply-shortcut", "SUPER + ALT + Q", "--no-reload"],
                check=True, capture_output=True, text=True, env=environment,
            )
            bindings = config / "hypr" / "bindings.lua"
            self.assertIn(setup.BINDING_START, bindings.read_text(encoding="utf-8"))

            upgraded = subprocess.run(
                [str(helper), "ensure-launcher", "--version", "0.5.1"],
                check=True, capture_output=True, text=True, env=environment,
            )
            self.assertEqual(json.loads(upgraded.stdout)["action"], "updated")

            subprocess.run(
                [str(helper), "cleanup", "--no-reload"],
                check=True, capture_output=True, text=True, env=environment,
            )
            self.assertFalse(desktop.exists())
            self.assertNotIn(setup.BINDING_START, bindings.read_text(encoding="utf-8"))

    def test_uninstall_script_cleans_integrations_before_plugin_removal(self):
        repository = Path(__file__).resolve().parents[1]
        helper = repository / "omaquickcalc_setup.py"
        uninstall = repository / "uninstall.sh"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binaries = root / "bin"
            binaries.mkdir()
            removal_log = root / "removed.txt"
            (binaries / "hyprctl").write_text(
                "#!/bin/sh\n[ \"$1\" = configerrors ] || printf 'ok\\n'\n",
                encoding="utf-8",
            )
            (binaries / "omarchy").write_text(
                "#!/bin/sh\nprintf '%s\\n' \"$*\" > \"$OMAQUICKCALC_REMOVE_LOG\"\n",
                encoding="utf-8",
            )
            (binaries / "hyprctl").chmod(0o755)
            (binaries / "omarchy").chmod(0o755)
            environment = os.environ.copy()
            environment.update({
                "XDG_CONFIG_HOME": str(root / "config"),
                "XDG_DATA_HOME": str(root / "data"),
                "PATH": f"{binaries}:{environment['PATH']}",
                "OMAQUICKCALC_REMOVE_LOG": str(removal_log),
            })
            subprocess.run(
                [str(helper), "ensure-launcher", "--version", "0.5.0"],
                check=True, capture_output=True, text=True, env=environment,
            )
            subprocess.run(
                [str(helper), "apply-shortcut", "SUPER + ALT + Q", "--no-reload"],
                check=True, capture_output=True, text=True, env=environment,
            )

            subprocess.run(
                [str(uninstall), "--yes"], check=True, capture_output=True,
                text=True, env=environment,
            )
            self.assertEqual(removal_log.read_text(encoding="utf-8").strip(),
                f"plugin remove {PLUGIN_ID} --yes")
            self.assertFalse((root / f"data/applications/{PLUGIN_ID}.desktop").exists())
            bindings = (root / "config/hypr/bindings.lua").read_text(encoding="utf-8")
            self.assertNotIn(setup.BINDING_START, bindings)


if __name__ == "__main__":
    unittest.main()
