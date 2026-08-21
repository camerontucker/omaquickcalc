# Changelog

## 0.5.0 — 2026-08-21

- Add a discoverable Super + Space launcher entry that does not depend on
  lifecycle hooks.
- Add consent-based first-run shortcut setup with Omacalc replacement,
  conflict-aware alternatives, and a skip option.
- Validate Hyprland changes and roll back rejected bindings.
- Preserve symlinked dotfile-managed Hyprland bindings and reject dangling
  binding symlinks.
- Add safe launcher upgrades and managed integration removal.
- Adopt the permanent marketplace ID
  `io.github.camerontucker.omaquickcalc`.
- Expand Raycast-style calculations, history, actions, formats, transparency,
  dependency recovery, and copy-result behavior.
- Promote valid answers to an expanding, left-aligned result row with stronger
  typography, full-width conversion space, metadata, and a visible copy hint.
- Round displayed and normally copied currency answers to two decimal places
  while retaining full precision for swap and unformatted actions.
- Keep incomplete and out-of-range live expressions from crashing the bundled
  evaluator while the user types.
- Add automated release-contract, lifecycle, evaluator, shell, Python, and QML
  checks for every push and pull request.
