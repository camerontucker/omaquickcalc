# Changelog

## Unreleased

## 0.6.0 — 2026-08-22

- Show compact example calculations in the reserved result row after three
  idle seconds, then hand the same space to the first successful calculation.
- Add local, province-aware Canadian tax reports with add-tax, reverse-all-tax,
  and GST-only reverse calculations.
- Treat trailing `tax` as a modifier over the complete preceding expression, so
  `900 + 100 tax` produces the same report as `1000 tax`.
- Infer a default tax jurisdiction from the system locale and timezone, allow a
  saved Tax location preference, and support inline overrides such as
  `1000 tax in Ontario`.
- Add sourced standard VAT/GST profiles for major national schemes, structured
  report copy actions, and explicit standard-taxable-purchase assumptions.
- Support saved and inline custom combined rates for address-dependent schemes.

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
- Hide onboarding and focus Omarchy's standard centered floating terminal
  during dependency installation instead of tiling it behind the calculator.
- Adopt the permanent marketplace ID
  `io.github.camerontucker.omaquickcalc`.
- Expand natural-language calculations, history, actions, formats, transparency,
  dependency recovery, and copy-result behavior.
- Promote valid answers to an expanding, left-aligned result row with stronger
  typography, full-width conversion space, metadata, and a visible copy hint.
- Reserve that result row from the first keystroke and debounce live evaluation
  for 200ms so the palette stays still while someone types.
- Show the shortcut palette immediately, then complete numeric selection capture
  silently and asynchronously instead of delaying or labelling a normal
  no-selection launch.
- Treat bare `rem`, `px`, `cm`, and `in` as practical design and length shorthands,
  while silently waiting on partial unit fragments that Qalculate maps to constants.
- Keep arbitrary word-only input in that same quiet pending state so partial
  names such as `quatt` cannot leak Qalculate's unrelated scientific symbols.
- Round displayed and normally copied currency answers to two decimal places
  while retaining full precision for swap and unformatted actions.
- Preserve `$` in symbol-led transforms between dollar currencies and prefix
  the target code, for example `$100 in CAD` → `CAD $142.20`.
- Evaluate complete arithmetic before a trailing currency format, so
  `500 * 0.5 in USD` produces `$250.00` instead of converting only `500`.
- Convert shorthand times such as `1pm pacific`, `1pm vancouver`, and `1pm pdt`
  to the current local timezone, using compact `4:00 PM CDT` output and showing
  a separated date only when the day changes.
- Add Transform in Place: explicitly capture a selected numeric value from the
  approved shortcut, transform it in the palette, and use Enter to replace it
  only in the originating window without persisting the selection.
- Keep incomplete and out-of-range live expressions from crashing the bundled
  evaluator while the user types.
- Add automated release-contract, lifecycle, evaluator, shell, Python, and QML
  checks for every push and pull request.
- Add instant `Ctrl+?` shortcut help and `Ctrl+,` preferences for opacity,
  history mode, 12/24-hour time, and default currencies without leaving the palette.
- Open calculation history from the input with either Up or Down, then use the
  same arrows to navigate its entries.
- Adapt text contrast to the active theme, wallpaper, card position, and chosen
  opacity so transparent cards stay readable as the desktop changes.
- Add QML model tests, a representative-input latency budget, and stricter
  storefront asset contracts to the release gate.
- Replace the marketplace preview with the normal calculator experience and
  remove the obsolete demo video.
- Add a tiny set of name-based Easter eggs with copyable results, a subtle
  keyboard-help clue, distinct theme-aware micro-interactions, and static
  reduced-motion variants.
