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
            "assets/omaquickcalc-demo.mp4",
            "manifest.json",
            "preview.png",
        ):
            with self.subTest(path=relative_path):
                self.assertTrue((REPOSITORY / relative_path).is_file())

        for relative_path in (
            "install.sh", "uninstall.sh", "omaquickcalc_setup.py",
            "omaquickcalc_transform.py",
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

        demo = REPOSITORY / "assets" / "omaquickcalc-demo.mp4"
        header = demo.read_bytes()[:32]
        self.assertIn(b"ftyp", header)
        self.assertLess(demo.stat().st_size, 100 * 1024 * 1024)

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
            "omaquickcalc_backend.py", "omaquickcalc_setup.py",
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
        self.assertIn("if (root.transformActive) return", qml)
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


if __name__ == "__main__":
    unittest.main()
