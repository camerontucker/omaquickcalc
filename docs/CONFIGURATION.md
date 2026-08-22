# OmaQuickCalc configuration

OmaQuickCalc creates `$XDG_CONFIG_HOME/omaquickcalc/config.json`, falling back
to `~/.config/omaquickcalc/config.json`. Press `Ctrl+,` in OmaQuickCalc to
change card opacity, history mode, motion, and common default currency pairs.
Edit the JSON file for advanced values or any other ISO currency; changes
reload live.

The generated defaults are:

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
  "reducedMotion": false,
  "remPx": 16,
  "workdayHours": 8,
  "inputHint": "Type a calculation…"
}
```

## Reference

| Setting | Accepted values | Effect |
| --- | --- | --- |
| `version` | `2` | Current configuration schema. |
| `historyMode` | `persistent`, `session`, `disabled` | Save history across launches, keep it only for this shell session, or record nothing. |
| `historyLimit` | `1`–`1000` | Maximum number of retained entries. |
| `historyRetentionDays` | `1`–`3650` | Age limit for unpinned persistent entries. |
| `saveOnClose` | `true`, `false` | Add the current result to history when the palette closes. |
| `defaultAction` | `copy-close`, `copy-stay`, `reuse` | What Enter does with a successful result. |
| `previewTimeoutMs` | `50`–`10000` | Timeout for live preview evaluation. |
| `submitTimeoutMs` | `100`–`60000` | Timeout for an explicit Enter submission. |
| `qalcBinary` | executable name or path | Qalculate command used by the evaluator. |
| `unicode` | `true`, `false` | Allow Qalculate's Unicode result formatting. |
| `digitGrouping` | `0`, `1`, `2` | Qalculate grouping: off, standard, or locale. |
| `precision` | `2`–`50` | Significant digits requested from Qalculate. |
| `clockFormat` | `auto`, `12`, `24` | Display format for times and timezone answers. |
| `defaultFromCurrency` | three-letter code | Source used when an expression contains only a target currency. |
| `defaultToCurrency` | three-letter code | Target used when an expression contains only a source currency. |
| `rateStaleDays` | `1`–`365` | Age after which cached exchange rates are marked stale. |
| `refreshExchangeRates` | `true`, `false` | Allow Qalculate's daily exchange-rate update behavior. |
| `backgroundOpacity` | `0`–`1` | Floating card opacity; text contrast follows the wallpaper beneath the card automatically. |
| `reducedMotion` | `true`, `false` | Disable decorative effects and card-resize animation while preserving all calculator feedback. |
| `remPx` | `1`–`512` | Pixel basis for REM/PX conversions. |
| `workdayHours` | `1`–`24` | Hours used for workday conversions. |
| `inputHint` | text | Placeholder shown in the empty input. |

Invalid or out-of-range values fall back to safe defaults or are clamped to
the supported range.

Currency answers are displayed and normally copied with two decimal places.
The **Copy Unformatted** action and conversion swapping retain Qalculate's full
numeric precision.

## Data locations

OmaQuickCalc respects XDG base directories:

| Data | Default location | Removal behavior |
| --- | --- | --- |
| Preferences | `~/.config/omaquickcalc/config.json` | Retained by normal plugin removal. |
| Launch choice | `~/.config/omaquickcalc/launch.json` | Retained by normal plugin removal. |
| Persistent history | `~/.local/share/omaquickcalc/history.json` | Retained by normal plugin removal. |
| Launcher entry | `~/.local/share/applications/io.github.camerontucker.omaquickcalc.desktop` | Removed by `uninstall.sh` only when marked as OmaQuickCalc-managed. |
| Optional shortcut | marked block in `~/.config/hypr/bindings.lua` | Removed by `uninstall.sh`; unrelated content is preserved. |
| Transform handoff | `$XDG_RUNTIME_DIR/omaquickcalc/transform` | Private single-use selection state; consumed immediately and stale after one minute. |

To reopen shortcut setup without changing calculator preferences:

```bash
omarchy-shell shell summon io.github.camerontucker.omaquickcalc '{"setup":true}'
```

To erase retained preferences and history after uninstalling:

```bash
rm -rf ~/.config/omaquickcalc ~/.local/share/omaquickcalc
```
