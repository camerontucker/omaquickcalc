# OmaQuickCalc configuration

OmaQuickCalc creates `$XDG_CONFIG_HOME/omaquickcalc/config.json`, falling back
to `~/.config/omaquickcalc/config.json`. Press `Ctrl+,` in OmaQuickCalc to
change card opacity, history mode, motion, time format, tax location, and common default currency pairs.
Edit the JSON file for advanced values or any other ISO currency; changes
reload live.

The generated defaults are:

```json
{
  "version": 4,
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
  "clockFormat": "12",
  "defaultFromCurrency": "USD",
  "defaultToCurrency": "CAD",
  "taxLocation": "auto",
  "taxCustomRate": 0,
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
| `version` | `4` | Current configuration schema. |
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
| `clockFormat` | `12`, `24`, `auto` | Display format for times and timezone answers; new installs default to 12-hour time. |
| `defaultFromCurrency` | three-letter code | Source used when an expression contains only a target currency. |
| `defaultToCurrency` | three-letter code | Target used when an expression contains only a source currency. |
| `taxLocation` | `auto` or a supported ISO country/subdivision code | Jurisdiction used by trailing `tax` queries. Auto uses only the system locale and timezone. Examples include `CA-MB`, `CA-ON`, `GB`, `DE`, `IN`, and `JP`. |
| `taxCustomRate` | `0`–`100` | Combined percentage used when `taxLocation` is `custom`; `0` requires a rate to be chosen before calculating. |
| `rateStaleDays` | `1`–`365` | Age after which cached exchange rates are marked stale. |
| `refreshExchangeRates` | `true`, `false` | Allow Qalculate's daily exchange-rate update behavior. |
| `backgroundOpacity` | `0`–`1` | Floating card opacity; text contrast follows the wallpaper beneath the card automatically. |
| `reducedMotion` | `true`, `false` | Disable decorative effects and card-resize animation while preserving all calculator feedback. |
| `remPx` | `1`–`512` | Pixel basis for REM/PX conversions. |
| `workdayHours` | `1`–`24` | Hours used for workday conversions. |
| `inputHint` | text | Placeholder shown in the empty input. |

Invalid or out-of-range values fall back to safe defaults or are clamped to
the supported range.

## Tax reports

`1000 tax` uses the configured location. `900 + 100 tax` first evaluates the
complete arithmetic expression, then produces the same report. A location in
the query, such as `1000 tax in Ontario` or `1000 tax in Germany`, overrides the
preference without changing it.

For address-dependent schemes such as US sales tax, select **Custom combined
rate** in preferences and set the local percentage, or write it inline as
`1000 tax at 8.25%`. Custom reports use the default source currency.

Canada includes every province and territory and reports the applicable
GST/PST/QST or HST components. Standard national VAT/GST profiles are also
bundled for Australia, New Zealand, the United Kingdom, selected large EU
countries, India, China, Japan, Mexico, Singapore, South Africa, Saudi Arabia,
and the United Arab Emirates. India and China display a more specific
assumption because their applicable rates depend strongly on the supply.

Reports assume a standard taxable purchase. Product exemptions, reduced or
zero rates, place-of-supply exceptions, registration thresholds, and special
local taxes can change the actual amount. Rates and official source URLs are
bundled locally; Auto location never performs an IP or geolocation lookup.

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
| Transform handoff | `$XDG_RUNTIME_DIR/omaquickcalc/transform` | Private single-use selection state; completed asynchronously after the palette appears and stale after one minute. |

To reopen shortcut setup without changing calculator preferences:

```bash
omarchy-shell shell summon io.github.camerontucker.omaquickcalc '{"setup":true}'
```

To erase retained preferences and history after uninstalling:

```bash
rm -rf ~/.config/omaquickcalc ~/.local/share/omaquickcalc
```
