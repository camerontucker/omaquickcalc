# Security

OmaQuickCalc runs as unsandboxed user code inside `omarchy-shell`. Review the
repository before enabling it and report suspected vulnerabilities through
[GitHub private vulnerability reporting](https://github.com/camerontucker/omaquickcalc/security/advisories/new).
Please do not disclose a suspected vulnerability publicly before it has been
triaged.

## Supported versions

Security fixes are made against the latest release on the `main` branch. Older
releases are not maintained separately while the plugin is pre-1.0.

## System interactions

- Calculator expressions are passed to the bundled Python evaluator and
  `qalc` as argument arrays, never interpolated into shell commands.
- Results are passed to `wl-copy` as a single argument after `--`; they are not
  evaluated by a shell.
- Normal launcher opens never inspect selected or clipboard text. An approved
  keyboard shortcut explicitly captures only short text containing a number,
  restores the previous clipboard immediately, and transfers the selection
  through a mode-0600 single-use file under `$XDG_RUNTIME_DIR`.
- The shortcut summons the palette before targeted capture completes. Its
  pending handoff contains only the validated origin window, remains private,
  and is atomically completed or expires without enabling replacement.
- The previous clipboard representation exists only in the capture helper's
  memory until restoration. If its format cannot be restored safely, capture
  aborts without changing it.
- Transform sessions are never persisted to calculation history. A transformed
  result is pasted only after focus returns to the exact Hyprland window where
  capture began; focus is never forced to another window.
- Missing `libqalculate`, `wl-clipboard`, or Python support is installed only
  after the user presses Enter. The Omarchy package command opens in a visible
  terminal for normal authentication.
- The launcher entry is written beneath `$XDG_DATA_HOME/applications`. An
  existing unmarked file is never overwritten.
- A shortcut is written only after the first-run screen shows the exact change
  and the user confirms it. OmaQuickCalc manages one marked block in
  `$XDG_CONFIG_HOME/hypr/bindings.lua`, validates the result with Hyprland, and
  rolls back a rejected change.
- Removal deletes only marked OmaQuickCalc launch integrations. Calculator
  preferences and history are retained.
- Symlinked Hyprland binding files remain symlinks. A dangling binding symlink
  is rejected instead of being replaced or followed to a missing target.

## Local data and trust boundaries

Calculation history and preferences remain on the local machine beneath the
user's XDG data and configuration directories. Ephemeral transform state is
consumed once from the private XDG runtime directory and stale state is removed
after one minute. OmaQuickCalc stores no credentials and has no network client
of its own. Qalculate may refresh public exchange-rate data when the configured
refresh setting is enabled.

`qalcBinary` is an advanced local preference. Changing it selects an executable
that runs with the user's privileges, so it should point only to a trusted
calculator binary.

OmaQuickCalc does not install sudoers rules, request passwordless privileges,
download executable code, or store credentials.
