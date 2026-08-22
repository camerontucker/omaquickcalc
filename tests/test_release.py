import ast
import json
import re
import stat
import struct
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]


class ReleaseContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((REPOSITORY / "manifest.json").read_text(encoding="utf-8"))

    def test_marketplace_manifest_contract(self):
        manifest = self.manifest
        self.assertEqual(manifest["schemaVersion"], 1)
        self.assertEqual(manifest["id"], "io.github.camerontucker.omaquickcalc")
        self.assertRegex(manifest["version"], r"^\d+\.\d+\.\d+$")
        self.assertEqual(manifest["kinds"], ["overlay"])
        self.assertTrue(manifest["keepLoaded"], "launcher setup requires the enabled overlay to load")
        entry_point = manifest["entryPoints"]["overlay"]
        self.assertEqual(Path(entry_point).name, entry_point)
        self.assertTrue((REPOSITORY / entry_point).is_file())

    def test_release_version_is_synchronized(self):
        version = self.manifest["version"]
        changelog = (REPOSITORY / "CHANGELOG.md").read_text(encoding="utf-8")
        installer = (REPOSITORY / "install.sh").read_text(encoding="utf-8")
        self.assertRegex(changelog, rf"(?m)^## {re.escape(version)}\b")
        self.assertIn(f"--version {version}", installer)

    def test_required_release_files_and_modes(self):
        for relative_path in (
            "AGENTS.md",
            "CHANGELOG.md",
            "LICENSE",
            "README.md",
            "SECURITY.md",
            "manifest.json",
            "preview.png",
        ):
            with self.subTest(path=relative_path):
                self.assertTrue((REPOSITORY / relative_path).is_file())

        for relative_path in (
            "install.sh", "uninstall.sh", "omaquickcalc_contrast.py", "omaquickcalc_setup.py",
            "omaquickcalc_transform.py", "tests/run-qml.sh",
        ):
            mode = (REPOSITORY / relative_path).stat().st_mode
            self.assertTrue(mode & stat.S_IXUSR, f"{relative_path} must be executable")

    def test_store_assets_are_valid_and_within_host_limits(self):
        preview = REPOSITORY / "preview.png"
        data = preview.read_bytes()
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(data[12:16], b"IHDR")
        width, height = struct.unpack(">II", data[16:24])
        self.assertGreaterEqual(width, 1280)
        self.assertGreaterEqual(height, 720)
        self.assertLessEqual(width * height, 40_000_000)
        self.assertLess(preview.stat().st_size, 50 * 1024 * 1024)
        self.assertEqual(
            preview.read_bytes(),
            (REPOSITORY / "assets/readme-currency-conversion.png").read_bytes(),
            "the marketplace preview must stay on the cropped primary calculator story",
        )
        self.assertEqual(list(REPOSITORY.rglob("*.mp4")), [], "video assets were intentionally removed")

    def test_readme_local_links_resolve(self):
        readme = (REPOSITORY / "README.md").read_text(encoding="utf-8")
        targets = re.findall(r"!?\[[^]]*\]\(([^)]+)\)", readme)
        targets.extend(
            re.findall(
                r'<(?:a|img)\b[^>]*\b(?:href|src)="([^"]+)"',
                readme,
                re.IGNORECASE,
            )
        )
        local_targets = [
            target.split("#", 1)[0]
            for target in targets
            if target and not target.startswith(("#", "http://", "https://"))
        ]
        self.assertTrue(local_targets)
        for target in local_targets:
            with self.subTest(target=target):
                self.assertTrue((REPOSITORY / target).is_file())

    def test_python_runtime_has_no_third_party_imports(self):
        standard_library = {
            "argparse", "calendar", "colorsys", "dataclasses", "datetime", "decimal",
            "fractions", "json", "locale", "math", "os", "pathlib", "re",
            "secrets", "shlex", "stat", "subprocess", "sys", "tempfile",
            "time", "unicodedata", "zoneinfo", "__future__",
        }
        for relative_path in (
            "omaquickcalc_backend.py", "omaquickcalc_contrast.py", "omaquickcalc_setup.py",
            "omaquickcalc_transform.py",
        ):
            tree = ast.parse((REPOSITORY / relative_path).read_text(encoding="utf-8"))
            imported = {
                node.names[0].name.split(".")[0]
                for node in ast.walk(tree)
                if isinstance(node, ast.Import)
            }
            imported.update(
                node.module.split(".")[0]
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and node.module
            )
            self.assertEqual(imported - standard_library, set())

    def test_marketplace_install_does_not_depend_on_install_hook(self):
        qml = (REPOSITORY / "OmaQuickCalc.qml").read_text(encoding="utf-8")
        self.assertIn("Component.onCompleted: initStorage.running = true", qml)
        self.assertIn("id: launcherFile", qml)
        self.assertIn("X-OmaQuickCalc-Managed=true", qml)
        self.assertNotIn("install.sh", qml)

        launcher_view = qml.split("id: launcherFile", 1)[1].split("\n  }", 1)[0]
        self.assertNotIn(
            "watchChanges:", launcher_view,
            "deleting the owned launcher during uninstall must not recreate it",
        )
        self.assertNotIn("onFileChanged:", launcher_view)

    def test_missing_dependencies_use_a_dedicated_first_run_step(self):
        qml = (REPOSITORY / "OmaQuickCalc.qml").read_text(encoding="utf-8")
        self.assertIn('if (setupPage === "dependencies") return [', qml)
        self.assertIn('label: "Install calculator engine"', qml)
        self.assertIn('"Missing: " + (missingDependencyPackages', qml)
        self.assertIn('root.setupPage = "installing-dependencies"', qml)
        self.assertIn('root.continueAfterDependencies()', qml)
        self.assertIn("visible: !root.setupOpen", qml)

    def test_user_values_are_not_interpolated_into_shell_commands(self):
        qml = (REPOSITORY / "OmaQuickCalc.qml").read_text(encoding="utf-8")
        self.assertIn('copyProcess.command = ["wl-copy", "--", String(value)]', qml)
        self.assertIn('"--expression", root.activeExpression', qml)
        self.assertNotRegex(qml, r"bash.*(?:expression|evaluatedResult|activeExpression|result)")

        transform = (REPOSITORY / "omaquickcalc_transform.py").read_text(encoding="utf-8")
        self.assertNotIn("shell=True", transform)
        self.assertIn('["wl-copy", "--", result]', transform)

    def test_transform_in_place_contract(self):
        qml = (REPOSITORY / "OmaQuickCalc.qml").read_text(encoding="utf-8")
        setup = (REPOSITORY / "omaquickcalc_setup.py").read_text(encoding="utf-8")
        self.assertIn('root.submit("replace-selection")', qml)
        self.assertIn('if (root.transformActive || root.resultKind === "easter-egg") return', qml)
        self.assertIn('"consume", "--token"', qml)
        self.assertIn('return query + " " + operand', qml)
        self.assertIn('return operand + " to " + query.replace', qml)
        self.assertIn("state.version === 2", qml)
        self.assertIn("capture-and-summon", setup)

    def test_valid_result_uses_a_distinct_copyable_second_row(self):
        qml = (REPOSITORY / "OmaQuickCalc.qml").read_text(encoding="utf-8")
        self.assertIn(
            "readonly property int resultRowHeight: result.length > 0",
            qml,
        )
        self.assertIn("id: resultRow", qml)
        self.assertIn('root.transformActive ? "⇧↵ Replace" : "↵ Copy"', qml)
        self.assertIn("Math.round(Style.font.heading * 1.5)", qml)
        self.assertIn('onClicked: root.submit("copy-close")', qml)

    def test_translucent_card_tracks_wallpaper_contrast(self):
        qml = (REPOSITORY / "OmaQuickCalc.qml").read_text(encoding="utf-8")
        self.assertIn('root.contrastHelperPath', qml)
        self.assertIn('onBackgroundChanged: root.scheduleContrastRefresh()', qml)
        self.assertIn('onFileChanged: root.scheduleContrastRefresh()', qml)
        self.assertIn('readonly property color foreground: contrastForeground', qml)
        self.assertIn('readonly property color accent: readableTextColor(themeAccent)', qml)

    def test_help_and_preferences_are_discoverable_without_a_result(self):
        qml = (REPOSITORY / "OmaQuickCalc.qml").read_text(encoding="utf-8")
        self.assertIn('return statusText || (!expression && !transformActive ? "Ctrl+? Help" : "")', qml)
        self.assertIn('event.key === Qt.Key_Comma', qml)
        self.assertIn('event.key === Qt.Key_Question', qml)
        self.assertIn('id: preferencesPane', qml)
        self.assertIn('id: shortcutHelpPane', qml)
        self.assertIn('items.push({ id: "preferences"', qml)
        self.assertNotIn('if (!root.result) return\n    root.historyOpen', qml)

    def test_quattro_easter_egg_stays_subtle_and_copyable(self):
        qml = (REPOSITORY / "OmaQuickCalc.qml").read_text(encoding="utf-8")
        self.assertIn('readonly property string easterEggName:', qml)
        self.assertIn('readonly property bool quattroEasterEggActive:', qml)
        self.assertIn('text: root.resultNote || root.rateSummary', qml)
        for motif in (
            'id: quattroMotif', 'id: eulerOrbit', 'id: fibonacciMotif',
            'id: gaussMotif', 'id: ramanujanMotif', 'id: dhhMotif',
        ):
            self.assertIn(motif, qml)
        self.assertIn('!root.settings.reducedMotion', qml)
        self.assertIn('Behavior on height {\n        enabled: !root.settings.reducedMotion', qml)
        self.assertIn('root.resultKind === "easter-egg"', qml)
        self.assertIn('root.queueCopy(evaluatedResult, keepOpen)', qml)
        self.assertIn('Some names calculate too', qml)


if __name__ == "__main__":
    unittest.main()
