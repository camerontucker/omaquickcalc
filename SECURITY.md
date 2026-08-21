# Security

OmaQuickCalc runs as unsandboxed user code inside `omarchy-shell`. Review the
repository before enabling it and report suspected vulnerabilities through
[GitHub private vulnerability reporting](https://github.com/camerontucker/omaquickcalc/security/advisories/new).

## System interactions

- Calculator expressions are passed to the bundled Python evaluator and
  `qalc` as argument arrays, never interpolated into shell commands.
- Results are sent to `wl-copy` through standard input.
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

OmaQuickCalc does not install sudoers rules, request passwordless privileges,
download executable code, or store credentials.
