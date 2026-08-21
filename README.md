# OmaQuickCalc

OmaQuickCalc is a Raycast-style calculation palette for Omarchy Quattro. It is
a single floating input powered by [Qalculate](https://qalculate.github.io/),
styled by the active Omarchy theme, and hosted inside `omarchy-shell`.

It complements the official [Omacalc](https://github.com/omacom-io/omacalc):
OmaQuickCalc is a keyboard-first expression and conversion overlay, while
Omacalc is a standalone traditional calculator with a keypad.

## Features

- Live arithmetic, percentages, units, constants, functions, currencies, and dates
- Natural phrases for percentages, discounts, tips, ratios, powers, and conversions
- Currency names, symbols, shorthand amounts, and either decimal convention
- Timezone questions, date arithmetic, timespans, workdays, REM/PX, and PPI
- HEX, RGB, HSL, OKLCH, and LAB color conversion with a live swatch
- Searchable 90-day history with pins and live time/date/currency updates
- Persistent calculation history with session-only and disabled privacy modes
- Result chaining, full multiline output, and detailed qalc errors
- Visible exchange-rate date, staleness warning, and manual/daily refresh
- Ctrl+K actions for answer, unformatted, equation, swap, refresh, numeric bases,
  fractions, and scientific/engineering notation
- Safe copy actions; expressions never pass through a shell
- Active Omarchy theme, typography, borders, and spacing
- Fast preview evaluation with a longer explicit-submit timeout
- Independent dependency health checks and automatic, user-authorized installation
- Discoverable Super + Space launcher entry and consent-based shortcut setup

Examples:

```text
240 * 15%
10ft in m
52% of 900
20% off 125
100 usd in cad
$1.500,25 in CAD
500 quid to EUR
$500
5pm ldn in sf
time in Tokyo
64px in rem
hsl(32, 100%, 50%)
```

## Install

The one-step local installer installs `libqalculate`, `wl-clipboard`, and Python through
Omarchy, links the plugin, rescans the shell, and enables it:

```bash
./install.sh
```

Omarchy intentionally does not execute lifecycle hooks from downloaded
plugins. OmaQuickCalc does not rely on `install.sh` for marketplace installs:
its enabled overlay creates its owned launcher entry on load, and its first-run
screen detects missing dependencies. Pressing Enter on the dependency prompt
opens Omarchy's package command in a visible terminal for sudo authentication:

```bash
omarchy plugin add https://github.com/camerontucker/omaquickcalc.git --enable
```

The manual dependency command is:

```bash
omarchy pkg add libqalculate wl-clipboard python
```

## Launch

Open the app launcher with `Super + Space`, search for **OmaQuickCalc**, and
press Enter. On first launch, choose one of three options:

- Replace Omacalc's `Super + Ctrl + Q` binding
- Choose another shortcut after checking it for conflicts
- Skip shortcut setup and continue using the launcher

OmaQuickCalc shows the exact replacement and asks for confirmation before it
touches `~/.config/hypr/bindings.lua`. It manages only a clearly marked block,
rolls back a binding rejected by Hyprland, and never overwrites an unrelated
desktop entry. Omacalc remains installed and available from the launcher.

Right-click OmaQuickCalc in a desktop-entry-aware launcher and choose
**Configure launch shortcut** to revisit the setup. You can also summon or
toggle the palette directly:

```bash
omarchy-shell shell summon io.github.camerontucker.omaquickcalc '{}'
omarchy-shell shell toggle io.github.camerontucker.omaquickcalc '{}'
```

To reopen launch setup directly:

```bash
omarchy-shell shell summon io.github.camerontucker.omaquickcalc '{"setup":true}'
```

## Upgrade and remove

Upgrade a marketplace/Git installation normally. The owned launcher entry is
updated automatically when the new plugin version loads:

```bash
omarchy plugin update io.github.camerontucker.omaquickcalc
```

Use the bundled removal command so the optional managed shortcut and owned
launcher entry are cleaned before Omarchy removes the plugin:

```bash
~/.config/omarchy/plugins/io.github.camerontucker.omaquickcalc/uninstall.sh --yes
```

Preferences and history are retained. The cleanup refuses to delete an
unmarked desktop entry and does not alter unrelated Hyprland bindings.

## Keyboard controls

| Key | Action |
| --- | --- |
| `Enter` | Run the configured default action (`copy-close` initially) |
| `Ctrl+Enter` | Copy the result and keep the palette open |
| `Shift+Enter` | Copy `expression = result` |
| `Tab` | Replace the expression with its result for chaining |
| `Alt+Enter` | Expand or collapse the full result/error |
| `Ctrl+K` | Open the contextual action menu |
| `Up` or `Ctrl+H` | Open calculation history |
| Type in history | Search expressions and results |
| `Up` / `Down` | Select a history entry |
| `Enter` in history | Recall the selected expression |
| `Ctrl+P` in history | Pin or unpin the selected entry |
| `Delete` in history | Remove the selected entry |
| `Ctrl+Shift+Delete` | Confirm and clear all history |
| `Escape` | Close detail/history, clear input, then close |

Enter, Ctrl+Enter, and clicking the displayed result copy the complete evaluated
result. Shift+Enter is the separate action that copies `expression = result`.

## Configuration

On first load, OmaQuickCalc creates
`~/.config/omaquickcalc/config.json`:

```json
{
  "version": 2,
  "historyMode": "persistent",
  "historyLimit": 100,
  "historyRetentionDays": 90,
  "saveOnClose": false,
  "defaultAction": "copy-close",
  "previewTimeoutMs": 250,
  "submitTimeoutMs": 2000,
  "qalcBinary": "qalc",
  "unicode": true,
  "digitGrouping": 0,
  "precision": 10,
  "clockFormat": "auto",
  "defaultFromCurrency": "USD",
  "defaultToCurrency": "CAD",
  "rateStaleDays": 7,
  "refreshExchangeRates": true,
  "backgroundOpacity": 0.92,
  "remPx": 16,
  "workdayHours": 8,
  "inputHint": "Type a calculation…"
}
```

`historyMode` accepts `persistent`, `session`, or `disabled`.
`defaultAction` accepts `copy-close`, `copy-stay`, or `reuse`.
`digitGrouping` follows qalc: `0` off, `1` standard, or `2` locale.
`precision` accepts 2–50 significant digits. `clockFormat` accepts `auto`,
`12`, or `24`. An amount with only a target currency uses
`defaultFromCurrency`; an amount with only a source converts to
`defaultToCurrency` (or back to the default source when they match).
`rateStaleDays` controls when the currency-rate date is shown as stale.
`backgroundOpacity` controls the floating card from `0` (fully transparent) to
`1` (fully opaque); text, results, and borders remain crisp.
Persistent history is stored in
`~/.local/share/omaquickcalc/history.json`, capped by `historyLimit`, and pruned
after `historyRetentionDays`; pinned entries are retained. `remPx` controls
REM/PX conversion and `workdayHours` controls workday calculations.

The overlay accepts an optional starting expression:

```bash
omarchy-shell shell summon io.github.camerontucker.omaquickcalc \
  '{"expression":"12 ft to m"}'
```

It also accepts `fontFamily`, matching the standard Omarchy overlay payload.

## Development

```bash
omarchy plugin validate .
qmllint -I /usr/share/omarchy/shell OmaQuickCalc.qml
```

OmaQuickCalc invokes its bundled standard-library Python evaluator and qalc with
argument arrays—never expression-bearing shell commands. Live evaluations are
debounced by 80 ms, and every request carries a generation number so a slower,
older result cannot replace a newer expression.

## License

MIT. See [LICENSE](LICENSE).
