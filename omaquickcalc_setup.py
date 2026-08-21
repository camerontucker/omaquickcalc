#!/usr/bin/env python3
"""Own OmaQuickCalc's launcher and optional Hyprland shortcut integration."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path


DESKTOP_MARKER = "X-OmaQuickCalc-Managed=true"
BINDING_START = "-- BEGIN OMAQUICKCALC MANAGED BINDING"
BINDING_END = "-- END OMAQUICKCALC MANAGED BINDING"
DEFAULT_PLUGIN_ID = "io.github.camerontucker.omaquickcalc"
ALLOWED_MODIFIERS = ("SUPER", "CTRL", "ALT", "SHIFT")
ALLOWED_KEYS = {
    *(chr(value) for value in range(ord("A"), ord("Z") + 1)),
    *(str(value) for value in range(10)),
    *(f"F{value}" for value in range(1, 13)),
    "SPACE",
    "RETURN",
    "TAB",
    "PERIOD",
    "COMMA",
    "SLASH",
    "SEMICOLON",
    "MINUS",
    "EQUAL",
}


def config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))


def data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))


def desktop_path(plugin_id: str = DEFAULT_PLUGIN_ID) -> Path:
    return data_home() / "applications" / f"{plugin_id}.desktop"


def bindings_path() -> Path:
    return config_home() / "hypr" / "bindings.lua"


def canonical_shortcut(value: str) -> str:
    raw = re.sub(r"\s+", " ", value.strip().upper())
    tokens = [token for token in re.split(r"\s*\+\s*|\s+", raw) if token]
    modifiers = [modifier for modifier in ALLOWED_MODIFIERS if modifier in tokens]
    keys = [token for token in tokens if token not in ALLOWED_MODIFIERS]
    if len(keys) != 1 or keys[0] not in ALLOWED_KEYS:
        raise ValueError("Shortcut must contain one supported key")
    if not any(modifier in modifiers for modifier in ("SUPER", "CTRL", "ALT")):
        raise ValueError("Shortcut must include Super, Ctrl, or Alt")
    return " + ".join(modifiers + keys)


def shortcut_identity(value: str) -> str:
    shortcut = canonical_shortcut(value)
    tokens = shortcut.split(" + ")
    return "+".join(sorted(tokens[:-1]) + [tokens[-1]])


def parse_keybindings(raw: str) -> dict[str, str]:
    bindings: dict[str, str] = {}
    for line in raw.splitlines():
        if "→" not in line:
            continue
        shortcut, description = line.split("→", 1)
        try:
            bindings[shortcut_identity(shortcut)] = description.strip()
        except ValueError:
            continue
    return bindings


def current_keybindings() -> dict[str, str]:
    completed = subprocess.run(
        ["omarchy", "menu", "keybindings", "--print"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            (completed.stderr or completed.stdout).strip()
            or "Could not inspect existing Omarchy keybindings"
        )
    return parse_keybindings(completed.stdout)


def shortcut_status(shortcuts: list[str]) -> list[dict[str, object]]:
    bindings = current_keybindings()
    result = []
    for value in shortcuts:
        shortcut = canonical_shortcut(value)
        description = bindings.get(shortcut_identity(shortcut), "")
        result.append({
            "shortcut": shortcut,
            "conflict": bool(description),
            "description": description,
        })
    return result


def desktop_contents(plugin_id: str, version: str) -> str:
    return f"""[Desktop Entry]
Type=Application
Name=OmaQuickCalc
GenericName=Calculator
Comment=Summon a fast calculation palette
Exec=omarchy-shell shell summon {plugin_id} {{}}
Icon=accessories-calculator
Terminal=false
Categories=Utility;Calculator;
Keywords=calculator;calc;math;currency;units;timezone;color;
StartupNotify=false
Actions=Setup;
{DESKTOP_MARKER}
X-OmaQuickCalc-Version={version}

[Desktop Action Setup]
Name=Configure launch shortcut
Exec=omarchy-shell shell summon {plugin_id} {{\"setup\":true}}
"""


def atomic_write(path: Path, content: str, mode: int | None = None) -> None:
    if path.is_symlink() and not path.exists():
        raise OSError(f"Refusing to write through dangling symlink: {path}")
    write_path = path.resolve() if path.is_symlink() else path
    write_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{write_path.name}.", dir=write_path.parent
    )
    temp_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if mode is not None:
            temp_path.chmod(mode)
        os.replace(temp_path, write_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def ensure_launcher(path: Path, plugin_id: str, version: str) -> dict[str, object]:
    action = "created"
    if path.exists():
        current = path.read_text(encoding="utf-8")
        if DESKTOP_MARKER not in current:
            return {"ok": False, "action": "conflict", "path": str(path)}
        action = "unchanged" if current == desktop_contents(plugin_id, version) else "updated"
    content = desktop_contents(plugin_id, version)
    if action != "unchanged":
        atomic_write(path, content, 0o644)
    return {"ok": True, "action": action, "path": str(path)}


def managed_block(shortcut: str, plugin_id: str) -> str:
    return (
        f"{BINDING_START}\n"
        "-- Added with explicit consent in OmaQuickCalc's launch setup.\n"
        f'hl.unbind("{shortcut}")\n'
        f'o.bind("{shortcut}", "OmaQuickCalc", '
        f'"omarchy-shell shell toggle {plugin_id} \'{{}}\'")\n'
        f"{BINDING_END}\n"
    )


def without_managed_block(content: str) -> str:
    pattern = re.compile(
        rf"(?:^|\n){re.escape(BINDING_START)}\n.*?{re.escape(BINDING_END)}(?:\n|$)",
        re.DOTALL,
    )
    cleaned = pattern.sub("\n", content)
    return cleaned.rstrip() + ("\n" if cleaned.strip() else "")


def render_bindings(content: str, shortcut: str, plugin_id: str) -> str:
    base = without_managed_block(content)
    separator = "\n" if base else ""
    return base + separator + managed_block(canonical_shortcut(shortcut), plugin_id)


def hyprland_reload() -> tuple[bool, str]:
    reload_result = subprocess.run(
        ["hyprctl", "reload"], check=False, capture_output=True, text=True, timeout=10
    )
    if reload_result.returncode != 0:
        return False, (reload_result.stderr or reload_result.stdout).strip()
    errors = subprocess.run(
        ["hyprctl", "configerrors"], check=False, capture_output=True, text=True, timeout=10
    )
    error_text = (errors.stdout or errors.stderr).strip()
    return errors.returncode == 0 and not error_text, error_text


def apply_shortcut(
    path: Path, shortcut: str, plugin_id: str, reload_hyprland: bool = True
) -> dict[str, object]:
    shortcut = canonical_shortcut(shortcut)
    existed = path.exists()
    previous = path.read_text(encoding="utf-8") if existed else ""
    previous_mode = path.stat().st_mode & 0o777 if existed else 0o644
    updated = render_bindings(previous, shortcut, plugin_id)
    atomic_write(path, updated, previous_mode)
    if reload_hyprland:
        valid, detail = hyprland_reload()
        if not valid:
            if existed:
                atomic_write(path, previous, previous_mode)
            elif path.exists():
                path.unlink()
            subprocess.run(
                ["hyprctl", "reload"], check=False, capture_output=True, text=True, timeout=10
            )
            return {"ok": False, "error": detail or "Hyprland rejected the binding"}
    return {"ok": True, "shortcut": shortcut, "path": str(path)}


def cleanup(
    desktop: Path,
    bindings: Path,
    reload_hyprland: bool = True,
    legacy_desktops: tuple[Path, ...] = (),
) -> dict[str, object]:
    removed: list[str] = []
    binding_changed = False
    previous_binding = ""
    previous_mode = 0o644
    if bindings.exists():
        current = bindings.read_text(encoding="utf-8")
        updated = without_managed_block(current)
        if updated != current:
            previous_binding = current
            previous_mode = bindings.stat().st_mode & 0o777
            atomic_write(bindings, updated, previous_mode)
            removed.append("managed shortcut")
            binding_changed = True

    if binding_changed and reload_hyprland:
        valid, detail = hyprland_reload()
        if not valid:
            atomic_write(bindings, previous_binding, previous_mode)
            subprocess.run(
                ["hyprctl", "reload"], check=False, capture_output=True, text=True, timeout=10
            )
            return {
                "ok": False,
                "error": detail or "Hyprland reload failed",
                "removed": [],
            }

    for owned_desktop in (desktop, *legacy_desktops):
        if (owned_desktop.exists()
                and DESKTOP_MARKER in owned_desktop.read_text(encoding="utf-8")):
            owned_desktop.unlink()
            removed.append(str(owned_desktop))
    return {"ok": True, "removed": removed}


def output(payload: dict[str, object]) -> int:
    print(json.dumps(payload, separators=(",", ":")))
    return 0 if payload.get("ok", True) else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    launcher = subparsers.add_parser("ensure-launcher")
    launcher.add_argument("--plugin-id", default=DEFAULT_PLUGIN_ID)
    launcher.add_argument("--version", default="0")

    status = subparsers.add_parser("shortcut-status")
    status.add_argument("shortcut", nargs="+")

    apply = subparsers.add_parser("apply-shortcut")
    apply.add_argument("shortcut")
    apply.add_argument("--plugin-id", default=DEFAULT_PLUGIN_ID)
    apply.add_argument("--no-reload", action="store_true")

    remove = subparsers.add_parser("cleanup")
    remove.add_argument("--plugin-id", default=DEFAULT_PLUGIN_ID)
    remove.add_argument("--no-reload", action="store_true")

    args = parser.parse_args()
    try:
        if args.command == "ensure-launcher":
            return output(ensure_launcher(
                desktop_path(args.plugin_id), args.plugin_id, args.version
            ))
        if args.command == "shortcut-status":
            return output({"ok": True, "shortcuts": shortcut_status(args.shortcut)})
        if args.command == "apply-shortcut":
            return output(apply_shortcut(
                bindings_path(), args.shortcut, args.plugin_id, not args.no_reload
            ))
        legacy = ()
        if args.plugin_id == DEFAULT_PLUGIN_ID:
            legacy = (desktop_path("omaquickcalc"),)
        return output(cleanup(
            desktop_path(args.plugin_id), bindings_path(), not args.no_reload, legacy
        ))
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        return output({"ok": False, "error": str(error)})


if __name__ == "__main__":
    raise SystemExit(main())
