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
- Prevent the managed launcher from being recreated while the plugin unloads
  during removal.
- Replace the competing inline first-run dependency prompt with a dedicated,
  consent-based calculator-engine step that continues automatically.
- Rewrite shortcut onboarding in plain language without exposing binding-file
  implementation details.
- Return to onboarding automatically after the visible dependency terminal
  closes instead of losing the setup flow when focus moves to the terminal.
- Adopt the permanent marketplace ID
  `io.github.camerontucker.omaquickcalc`.
- Expand natural-language calculations, history, actions, formats, transparency,
  dependency recovery, and copy-result behavior.
- Promote valid answers to an expanding, left-aligned result row with stronger
  typography, full-width conversion space, metadata, and a visible copy hint.
- Round displayed and normally copied currency answers to two decimal places
  while retaining full precision for swap and unformatted actions.
- Convert shorthand times such as `1pm pacific`, `1pm vancouver`, and `1pm pdt`
  to the current local timezone, showing a date only when the day changes.
- Add Transform in Place: explicitly capture a selected numeric value from the
  approved shortcut, transform it in the palette, and use Shift+Enter to replace
  it only in the originating window without persisting the selection.
- Keep incomplete and out-of-range live expressions from crashing the bundled
  evaluator while the user types.
- Add automated release-contract, lifecycle, evaluator, shell, Python, and QML
  checks for every push and pull request.
- Add instant `Ctrl+?` shortcut help and `Ctrl+,` preferences for opacity,
  history mode, and default currencies without leaving the palette.
- Adapt text contrast to the active theme, wallpaper, card position, and chosen
  opacity so transparent cards stay readable as the desktop changes.
- Add QML model tests, a representative-input latency budget, and stricter
  storefront asset contracts to the release gate.
- Replace the marketplace preview with the normal calculator experience and
  remove the obsolete demo video.
- Add a tiny set of name-based Easter eggs with copyable results, a subtle
  keyboard-help clue, distinct theme-aware micro-interactions, and static
  reduced-motion variants.
