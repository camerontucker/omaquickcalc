# OmaQuickCalc contributor guide

These instructions apply to the entire repository. OmaQuickCalc is an Omarchy
Quattro overlay plugin, not a standalone desktop application. Preserve its
keyboard-first, single-floating-input experience and keep changes scoped.

## Start here

1. Read `manifest.json`, `README.md`, and the files relevant to the change.
2. Run `git status --short` and preserve unrelated work.
3. Prefer `rg` and `rg --files` for discovery and `apply_patch` for edits.
4. Never edit `/usr/share/omarchy` or overwrite user configuration.

## Architecture

- `OmaQuickCalc.qml` owns the overlay UI, process lifecycles, history,
  first-run launch setup, desktop entry, dependency recovery, and clipboard
  actions.
- `OmaQuickCalcModel.js` contains QML-compatible settings and history helpers.
  Keep it free of Node-only APIs.
- `omaquickcalc_backend.py` normalizes natural-language calculator phrases and returns
  structured results from Qalculate.
- `omaquickcalc_setup.py` owns the optional, consent-based Hyprland binding and
  reversible launcher lifecycle operations.
- `omaquickcalc_transform.py` owns explicit numeric-selection capture, private
  runtime handoff, origin-window validation, and replace-in-place paste.
- `install.sh` is for local development. Marketplace installation does not run
  lifecycle hooks, so normal installation must remain functional without it.
- `tests/` covers evaluator behavior and install/launch/upgrade/removal safety.

Persistent calculator preferences and launch state live under
`$XDG_CONFIG_HOME/omaquickcalc`; history lives under
`$XDG_DATA_HOME/omaquickcalc`. Those stable data paths deliberately do not
change with the permanent plugin ID `io.github.camerontucker.omaquickcalc`.

## Correctness and safety invariants

- Pass expressions and user-controlled values through argument arrays or
  standard input. Never interpolate them into shell commands. Clipboard text
  is passed literally after `wl-copy --`; do not switch that path to stdin
  unless the QML process can also close the write channel reliably.
- Enter, Ctrl+Enter, and clicking a result copy the evaluated result. Shift+Enter
  replaces the originating selection only in an explicit transform session; it
  remains the separate equation-copy action during normal launches.
- Normal launcher opens must not inspect clipboard or selected text. Transform
  selections must be short and numeric, single-use, private to XDG runtime,
  excluded from history, and pasted only into the verified originating window.
- A marketplace install must create a discoverable launcher even when
  `install.sh` is never executed and optional calculator dependencies are
  missing.
- Never modify `~/.config/hypr/bindings.lua` before the user sees the exact
  shortcut change and explicitly confirms it.
- Manage only the marked OmaQuickCalc binding block and desktop entry. Preserve
  unrelated user content and refuse to overwrite an unmarked desktop file.
- Validate Hyprland after a managed binding change and restore the previous
  file if validation fails.
- Keep Omacalc installed. Replacing `Super+Ctrl+Q` changes only the binding.
- Missing packages may be offered through `omarchy pkg add` in a visible
  terminal after user action. Do not add passwordless sudo, remote executable
  downloads, or hidden package-manager operations.
- Preserve active Omarchy theme tokens and configurable card transparency.
- Old evaluation processes must never replace newer input; retain generation
  checks when changing evaluation flow.

## Verification

Run the smallest relevant check first, then the complete local suite before a
release or broad handoff:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
bash -n install.sh uninstall.sh
omarchy plugin validate .
/usr/lib/qt6/bin/qmllint -I /usr/share/omarchy/shell OmaQuickCalc.qml
git diff --check
```

QML lint may report unresolved Omarchy singleton warnings outside the live
shell import layout; syntax errors and new actionable warnings must still be
resolved. Use isolated `XDG_CONFIG_HOME` and `XDG_DATA_HOME` directories for
lifecycle tests. Do not run `install.sh`, `uninstall.sh`, plugin rescans, or
live shortcut changes as generic verification.

## Releases and marketplace

- Keep `manifest.json`, `CHANGELOG.md`, installer version arguments, README
  commands, launcher identity, and tests synchronized when the version or
  plugin ID changes.
- A release candidate needs a root `preview.png`, accurate install/update/remove
  instructions, documented dependencies, a clean fresh-clone test, and an
  authentic demo of the current UI.
- Keep preview and demo imagery truthful to the shipped interface; do not use a
  synthetic UI mockup as evidence of functionality.
- Marketplace submission uses category `Productivity`, tags `launcher` and
  `quickshell`, and may suggest the reusable tag `calculator`.
- Do not commit, push, tag, create a release, or submit the marketplace issue
  without explicit authorization. Show the exact submission body before
  creating the issue.
