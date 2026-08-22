import subprocess
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
HELPER = REPOSITORY / "omaquickcalc_contrast.py"


class ContrastHelperTests(unittest.TestCase):
    def run_helper(self, sample, card, card_opacity, scrim="#000000", scrim_opacity=0):
        return subprocess.run(
            [
                sys.executable, str(HELPER),
                "--sample", sample,
                "--scrim", scrim,
                "--scrim-opacity", str(scrim_opacity),
                "--card", card,
                "--card-opacity", str(card_opacity),
                "--light", "#FFFFFF",
                "--dark", "#000000",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_transparent_card_uses_wallpaper_contrast(self):
        dark = self.run_helper("#101010", "#FFFFFF", 0)
        light = self.run_helper("#F8F8F8", "#000000", 0)
        self.assertEqual(dark.returncode, 0)
        self.assertTrue(dark.stdout.startswith("#FFFFFF "))
        self.assertEqual(light.returncode, 0)
        self.assertTrue(light.stdout.startswith("#000000 "))

    def test_card_and_scrim_are_composited_before_choice(self):
        result = self.run_helper(
            "#FFFFFF", "#000000", 0.75,
            scrim="#000000", scrim_opacity=0.5,
        )
        self.assertEqual(result.returncode, 0)
        foreground, surface = result.stdout.strip().split()
        self.assertEqual(foreground, "#FFFFFF")
        self.assertEqual(surface, "#202020")

    def test_invalid_colors_fail_closed(self):
        result = self.run_helper("not-a-color", "#000000", 1)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
