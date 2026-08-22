import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
BACKEND = REPOSITORY / "omaquickcalc_backend.py"


@unittest.skipUnless(shutil.which("qalc"), "qalc is required for the release latency budget")
class EvaluationLatencyTests(unittest.TestCase):
    def test_warm_backend_stays_inside_modal_ui_budget(self):
        expressions = ("1000 + 123", "64px in rem", "100 CAD in USD", "1pm pst",
                       "900 + 100 tax in Manitoba")
        with tempfile.TemporaryDirectory() as directory:
            environment = os.environ.copy()
            environment.update({
                "HOME": directory,
                "XDG_CACHE_HOME": str(Path(directory) / ".cache"),
                "XDG_CONFIG_HOME": str(Path(directory) / ".config"),
                "XDG_DATA_HOME": str(Path(directory) / ".local/share"),
            })
            for expression in expressions:
                command = [
                    sys.executable, str(BACKEND), "--expression", expression,
                    "--timeout-ms", "2000",
                ]
                subprocess.run(command, check=True, capture_output=True,
                               text=True, timeout=3, env=environment)
                durations = []
                for _ in range(5):
                    started = time.perf_counter()
                    subprocess.run(command, check=True, capture_output=True,
                                   text=True, timeout=3, env=environment)
                    durations.append(time.perf_counter() - started)
                median = statistics.median(durations)
                self.assertLess(
                    median, 0.25,
                    f"{expression!r} backend median {median * 1000:.1f}ms exceeds "
                    "the 250ms release budget before the 200ms UI debounce",
                )


if __name__ == "__main__":
    unittest.main()
