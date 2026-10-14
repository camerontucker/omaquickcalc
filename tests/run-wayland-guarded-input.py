#!/usr/bin/env python3
"""Exercise guarded input on a private offscreen Wayland compositor, never the desktop."""
import argparse
import os
from pathlib import Path
import re
import resource
import shlex
import subprocess
import tempfile
import time


def limited():
    resource.setrlimit(resource.RLIMIT_AS, (1024 ** 3, 1024 ** 3))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def flags(*modules):
    return shlex.split(subprocess.check_output(["pkg-config", "--cflags", "--libs", *modules], text=True))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    output = args.output_dir or Path(tempfile.mkdtemp(prefix="quickcalc-wayland-results-"))
    output.mkdir(parents=True, exist_ok=True)
    output = output.resolve()
    protocol = Path("/usr/share/wayland-protocols/staging/ext-data-control/ext-data-control-v1.xml")
    if not protocol.is_file():
        raise RuntimeError("ext-data-control-v1.xml is unavailable; install Wayland protocol development files to run this optional test")
    with tempfile.TemporaryDirectory(prefix="quickcalc-wayland-build-") as build_name, tempfile.TemporaryDirectory(prefix="quickcalc-wayland-private-") as runtime_name:
        build, runtime = Path(build_name), Path(runtime_name)
        runtime.chmod(0o700)
        (runtime / "mode").write_text("small")
        subprocess.run(["wayland-scanner", "server-header", str(protocol), str(build / "ext-server.h")], check=True)
        subprocess.run(["wayland-scanner", "private-code", str(protocol), str(build / "ext-code.c")], check=True)
        subprocess.run(["cc", "-c", str(build / "ext-code.c"), "-o", str(build / "ext-code.o")], check=True)
        subprocess.run(["c++", "-std=c++17", "-fPIC", "-pthread", "-I", str(build), str(repo / "tests/wayland/disposable_compositor.cpp"), str(build / "ext-code.o"), "-o", str(build / "compositor"), *flags("Qt6WaylandCompositor", "Qt6Gui", "wayland-server")], check=True)
        libexec = Path(subprocess.check_output(["pkg-config", "--variable=libexecdir", "Qt6Core"], text=True).strip())
        subprocess.run([str(libexec / "moc"), str(repo / "tests/wayland/client.cpp"), "-o", str(build / "client.moc")], check=True)
        subprocess.run(["c++", "-std=c++17", "-fPIC", "-I", str(build), str(repo / "tests/wayland/client.cpp"), "-o", str(build / "client"), *flags("Qt6Quick", "Qt6Qml", "Qt6Gui", "Qt6Test")], check=True)
        environment = dict(os.environ)
        for key in ("WAYLAND_DISPLAY", "DISPLAY", "HYPRLAND_INSTANCE_SIGNATURE", "DBUS_SESSION_BUS_ADDRESS", "WAYLAND_DEBUG", "WAYLAND_SOCKET"):
            environment.pop(key, None)
        environment.update(XDG_RUNTIME_DIR=runtime_name, XDG_CONFIG_HOME=runtime_name + "/config", XDG_DATA_HOME=runtime_name + "/data", QT_QPA_PLATFORMTHEME="", QT_QUICK_BACKEND="software", QT_WAYLAND_CLIENT_BUFFER_INTEGRATION="shm", QT_LOGGING_RULES="*.info=true")
        with (output / "compositor.log").open("w") as log:
            server = subprocess.Popen([str(build / "compositor"), runtime_name], env=dict(environment, QT_QPA_PLATFORM="offscreen"), stdout=log, stderr=subprocess.STDOUT, preexec_fn=limited)
            try:
                deadline = time.monotonic() + 3
                while not (runtime / "guarded-test").exists() and time.monotonic() < deadline and server.poll() is None:
                    time.sleep(0.02)
                if server.poll() is not None or not (runtime / "guarded-test").exists():
                    raise RuntimeError("Private Wayland compositor did not start; see compositor.log (Unix socket binding may be blocked by the sandbox)")
                with (output / "client.log").open("w") as client_log:
                    client = subprocess.run([str(build / "client"), str(repo), runtime_name, str(output / "candidate-wayland.png")], env=dict(environment, QT_QPA_PLATFORM="wayland", WAYLAND_DISPLAY="guarded-test", WAYLAND_DEBUG="1"), stdout=client_log, stderr=subprocess.STDOUT, preexec_fn=limited, timeout=12)
                if client.returncode:
                    raise RuntimeError(f"Wayland client failed with exit {client.returncode}; see client.log")
                text = (output / "client.log").read_text()
                before, after = text.split("BEGIN_POSITIVE_CONTROL", 1)
                receive = r"wl_data_offer[^\n]*\.receive\("
                assert not re.search(receive, before), "Unsolicited Qt clipboard payload read"
                assert re.search(receive, after), "Positive control did not exercise real clipboard retrieval"
                receives = (runtime / "receives.log").read_text()
                (output / "receives.log").write_text(receives)
                for expected in ("small clipboard", "small primary", "oversize clipboard", "capacity clipboard", "delayed clipboard", "stall clipboard", "drip clipboard"):
                    assert expected in receives, expected
                for line in text.splitlines():
                    if line.startswith("PASS "):
                        print(line)
                print("PASS zero unsolicited Qt Wayland receives; positive control produced a receive")
                print("Evidence:", output)
            finally:
                server.terminate()
                try:
                    server.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()


if __name__ == "__main__":
    main()
