#!/usr/bin/env python3
"""Capture a selected calculation and safely replace it after evaluation."""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import selectors
import stat
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


MAX_SELECTION_LENGTH = 512
MAX_SELECTION_BYTES = MAX_SELECTION_LENGTH * 4
MAX_CLIPBOARD_TYPES_BYTES = 16_384
MAX_CLIPBOARD_SNAPSHOT_BYTES = 16 * 1024 * 1024
MAX_RESULT_LENGTH = 65_536
STATE_MAX_AGE_SECONDS = 60
PENDING_WAIT_SECONDS = 1.5
TOKEN_PATTERN = re.compile(r"^[a-f0-9]{32}$")
WINDOW_PATTERN = re.compile(r"^0x[0-9a-fA-F]+$")


@dataclass(frozen=True)
class ClipboardSnapshot:
    mime_type: str
    data: bytes


def runtime_directory() -> Path:
    configured = os.environ.get("XDG_RUNTIME_DIR")
    root = Path(configured) if configured else Path(f"/run/user/{os.getuid()}")
    if not root.is_absolute() or not root.is_dir() or root.is_symlink():
        raise RuntimeError("A private XDG runtime directory is required")
    directory = root / "omaquickcalc" / "transform"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory.chmod(0o700)
    if directory.is_symlink() or directory.stat().st_uid != os.getuid():
        raise RuntimeError("Unsafe transform runtime directory")
    return directory


def state_path(token: str) -> Path:
    if not TOKEN_PATTERN.fullmatch(token):
        raise ValueError("Invalid transform token")
    return runtime_directory() / f"{token}.json"


def cleanup_stale_state() -> None:
    cutoff = time.time() - STATE_MAX_AGE_SECONDS
    for path in runtime_directory().glob("*.json"):
        try:
            if not path.is_symlink() and path.stat().st_mtime < cutoff:
                path.unlink()
        except FileNotFoundError:
            pass


def active_window() -> dict[str, object]:
    process = subprocess.run(
        ["hyprctl", "-j", "activewindow"], capture_output=True, text=True,
        timeout=1, check=False,
    )
    if process.returncode != 0:
        return {}
    try:
        payload = json.loads(process.stdout or "{}")
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def is_terminal_window(window: dict[str, object]) -> bool:
    tags = window.get("tags", [])
    return isinstance(tags, list) and any(
        str(tag).rstrip("*") == "terminal" for tag in tags
    )


def send_shortcut(modifiers: str, key: str, window_address: str = "") -> bool:
    if (modifiers, key) not in {
        ("CTRL", "C"), ("CTRL", "INSERT"),
        ("CTRL", "V"), ("SHIFT", "INSERT"),
    }:
        raise ValueError("Unsupported synthetic shortcut")
    if window_address and not WINDOW_PATTERN.fullmatch(window_address):
        raise ValueError("Invalid shortcut target")
    for state in ("down", "up"):
        target = (f', window = hl.get_window("address:{window_address}")'
                  if window_address else "")
        code = (
            "hl.dispatch(hl.dsp.send_key_state({ mods = "
            f'"{modifiers}", key = "{key}", state = "{state}"{target} }}))'
        )
        process = subprocess.run(
            ["hyprctl", "eval", code], capture_output=True, timeout=1,
            check=False,
        )
        if process.returncode != 0:
            return False
        if state == "down":
            time.sleep(0.05)
    return True


def _read_bounded_output(command: list[str], byte_limit: int,
                         timeout: float) -> bytes | None:
    """Read a clipboard owner without allowing unbounded buffering."""
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if process.stdout is None:
        process.kill()
        process.wait()
        raise RuntimeError("Unable to read clipboard content safely")

    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    output = bytearray()
    deadline = time.monotonic() + timeout
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not selector.select(remaining):
                raise subprocess.TimeoutExpired(command, timeout)
            chunk = os.read(
                process.stdout.fileno(),
                min(65_536, byte_limit + 1 - len(output)),
            )
            if not chunk:
                break
            output.extend(chunk)
            if len(output) > byte_limit:
                raise RuntimeError("Clipboard content exceeds safe capture limit")

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(command, timeout)
        if process.wait(timeout=remaining) != 0:
            return None
        return bytes(output)
    finally:
        selector.close()
        process.stdout.close()
        if process.poll() is None:
            process.kill()
            process.wait()


def clipboard_snapshot() -> ClipboardSnapshot | None:
    types = _read_bounded_output(
        ["wl-paste", "--list-types"], MAX_CLIPBOARD_TYPES_BYTES, 1,
    )
    if types is None:
        return None
    offered = [
        line.strip()
        for line in types.decode("utf-8", errors="replace").splitlines()
        if line.strip()
    ]
    priorities = (
        "text/plain;charset=utf-8", "text/plain", "UTF8_STRING",
        "image/png", "text/uri-list",
    )
    mime_type = next((item for item in priorities if item in offered), "")
    if not mime_type:
        if offered:
            raise RuntimeError("The current clipboard format cannot be restored safely")
        return None
    content = _read_bounded_output(
        ["wl-paste", "--type", mime_type], MAX_CLIPBOARD_SNAPSHOT_BYTES, 2,
    )
    if content is None:
        return None
    return ClipboardSnapshot(mime_type, content)


def restore_clipboard(snapshot: ClipboardSnapshot | None) -> None:
    if snapshot is None:
        subprocess.run(
            ["wl-copy", "--clear"], stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, timeout=1,
            check=False,
        )
        return
    subprocess.run(
        ["wl-copy", "--type", snapshot.mime_type], input=snapshot.data,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        timeout=2, check=False,
    )


def read_clipboard_text() -> str:
    content = _read_bounded_output(
        ["wl-paste", "--no-newline", "--type", "text/plain"],
        MAX_SELECTION_BYTES, 1,
    )
    if content is None:
        return ""
    return content.decode("utf-8", errors="replace")


def normalize_selection(value: str) -> str:
    normalized = " ".join(value.strip().split())
    if not normalized or len(normalized) > MAX_SELECTION_LENGTH:
        return ""
    if not any(character.isdigit() for character in normalized):
        return ""
    if any(ord(character) < 32 for character in normalized):
        return ""
    return normalized


def capture_selection(terminal: bool, window_address: str = "") -> str:
    snapshot = clipboard_snapshot()
    sentinel = f"omaquickcalc-{secrets.token_hex(24)}"
    try:
        seeded = subprocess.run(
            ["wl-copy", "--type", "text/plain;charset=utf-8"],
            input=sentinel.encode(), stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, timeout=2,
            check=False,
        )
        if seeded.returncode != 0:
            return ""
        # Let the physical launch chord release before injecting a copy chord.
        time.sleep(0.2)
        modifiers, key = (("CTRL", "INSERT") if terminal else ("CTRL", "C"))
        if not send_shortcut(modifiers, key, window_address):
            return ""
        deadline = time.monotonic() + 0.6
        while time.monotonic() < deadline:
            selected = read_clipboard_text()
            if selected and selected != sentinel:
                return normalize_selection(selected)
            time.sleep(0.03)
        return ""
    finally:
        restore_clipboard(snapshot)


def write_state(selection: str, window: dict[str, object], terminal: bool) -> str:
    cleanup_stale_state()
    selection = normalize_selection(selection)
    window_address = str(window.get("address", ""))
    window_pid = int(window.get("pid", 0) or 0)
    if not selection or not WINDOW_PATTERN.fullmatch(window_address) or window_pid <= 0:
        raise ValueError("Invalid transform selection or origin window")
    token = secrets.token_hex(16)
    path = state_path(token)
    descriptor = os.open(
        path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600
    )
    payload = {
        "selection": selection,
        "windowAddress": window_address,
        "windowPid": window_pid,
        "terminal": terminal,
    }
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)
    return token


def write_pending_state(window: dict[str, object], terminal: bool) -> str:
    """Create a private handoff before the overlay is summoned."""
    cleanup_stale_state()
    window_address = str(window.get("address", ""))
    window_pid = int(window.get("pid", 0) or 0)
    if not WINDOW_PATTERN.fullmatch(window_address) or window_pid <= 0:
        raise ValueError("Invalid transform origin window")
    token = secrets.token_hex(16)
    path = state_path(token)
    descriptor = os.open(
        path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600
    )
    payload = {
        "pending": True,
        "selection": "",
        "windowAddress": window_address,
        "windowPid": window_pid,
        "terminal": terminal,
    }
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)
    return token


def complete_pending_state(token: str, selection: str) -> None:
    """Atomically publish selection capture to the waiting overlay."""
    path = state_path(token)
    metadata = path.lstat()
    if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid()
            or metadata.st_mode & 0o077):
        raise RuntimeError("Unsafe transform state")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["pending"] = False
    payload["selection"] = normalize_selection(selection)
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}")
    descriptor = os.open(
        temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def consume_state(token: str) -> dict[str, object]:
    path = state_path(token)
    deadline = time.monotonic() + PENDING_WAIT_SECONDS
    try:
        while True:
            metadata = path.lstat()
            if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid()
                    or metadata.st_mode & 0o077):
                raise RuntimeError("Unsafe transform state")
            if metadata.st_mtime < time.time() - STATE_MAX_AGE_SECONDS:
                raise RuntimeError("Transform state expired")
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Invalid transform state")
            if not payload.get("pending"):
                return payload
            if time.monotonic() >= deadline:
                payload["pending"] = False
                return payload
            time.sleep(0.02)
    finally:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def summon(plugin_id: str, token: str = "") -> int:
    payload = {"transformToken": token} if token else {}
    process = subprocess.run(
        ["omarchy-shell", "shell", "summon", plugin_id, json.dumps(payload)],
        timeout=5, check=False,
    )
    return process.returncode


def capture_and_summon(plugin_id: str) -> int:
    window = active_window()
    terminal = is_terminal_window(window)
    window_address = str(window.get("address", ""))
    token = write_pending_state(window, terminal)
    status = summon(plugin_id, token)
    if status != 0:
        try:
            state_path(token).unlink()
        except FileNotFoundError:
            pass
        return status
    selection = capture_selection(terminal, window_address)
    try:
        complete_pending_state(token, selection)
    except FileNotFoundError:
        # The overlay may have timed out or been dismissed while capture was
        # still in flight; there is no longer any private state to publish.
        pass
    return status


def replace_selection(result: str, window_address: str,
                      window_pid: int, terminal: bool) -> int:
    if not result or len(result) > MAX_RESULT_LENGTH:
        return 2
    if not WINDOW_PATTERN.fullmatch(window_address) or window_pid <= 0:
        return 2
    copied = subprocess.run(
        ["wl-copy", "--", result], stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, timeout=2,
        check=False,
    )
    if copied.returncode != 0:
        return copied.returncode or 1

    deadline = time.monotonic() + 1.5
    while time.monotonic() < deadline:
        window = active_window()
        if (str(window.get("address", "")) == window_address
                and int(window.get("pid", 0) or 0) == window_pid):
            modifiers, key = (("SHIFT", "INSERT") if terminal else ("CTRL", "V"))
            return 0 if send_shortcut(modifiers, key, window_address) else 1
        time.sleep(0.05)
    return 1


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)

    capture = commands.add_parser("capture-and-summon")
    capture.add_argument("--plugin-id", required=True)

    consume = commands.add_parser("consume")
    consume.add_argument("--token", required=True)

    replace = commands.add_parser("replace")
    replace.add_argument("--result", required=True)
    replace.add_argument("--window-address", required=True)
    replace.add_argument("--window-pid", required=True, type=int)
    replace.add_argument("--terminal", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()
    try:
        if args.command == "capture-and-summon":
            return capture_and_summon(args.plugin_id)
        if args.command == "consume":
            print(json.dumps(consume_state(args.token), ensure_ascii=False))
            return 0
        return replace_selection(
            args.result, args.window_address, args.window_pid, args.terminal
        )
    except (OSError, RuntimeError, subprocess.SubprocessError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
