# OmaQuickCalc

<p align="center">
  <strong>Calculate anything without leaving your flow.</strong><br>
  A fast modal calculator for Omarchy Quattro, with Transform in Place.
</p>

![OmaQuickCalc converting 100 CAD to 72.61 USD over the Omarchy wallpaper](assets/readme-currency-conversion.png)

<p align="center">
  <a href="#install"><strong>Install</strong></a>
  ·
  <a href="docs/CONFIGURATION.md"><strong>Configure</strong></a>
  ·
  <a href="SECURITY.md"><strong>Security</strong></a>
</p>

OmaQuickCalc is the calculator you summon, not switch to. Type math or
plain-language conversions into a focused floating palette and get a live,
copy-ready answer. When the result belongs in the app you came from, Transform
in Place can put it there.

[![Play the OmaQuickCalc demo](assets/omaquickcalc-demo-poster.png)](https://raw.githubusercontent.com/camerontucker/omaquickcalc/main/assets/omaquickcalc-demo.gif)

## Examples

**Design units**

![64 pixels converted to 4 rem in OmaQuickCalc](assets/readme-discount-math.png)

**Mixed units**

![5 feet 11 inches converted to 180.34 centimetres in OmaQuickCalc](assets/readme-unit-conversion.png)

**Currency conversion**

![100 Canadian dollars converted to 72.61 US dollars with the current rate date](assets/readme-currency-conversion.png)

**Calculation history**

![1000 plus 123 equals 1123 with calculation history open](assets/readme-calculation-history.png)

Also try `20% off 125`, `square root of 625`, `18% tip on 80`, or
`1pm pacific` to convert directly to your local time.

## Transform in Place

Highlight `100 CAD`, summon OmaQuickCalc, and type `in USD`. Press `Enter` to
copy `$72.61`, or `Shift+Enter` to replace the original selection.

**1. Select the value**

![100 CAD selected in an Omawrite client invoice](assets/readme-transform-selected.png)

**2. Type `in USD`**

![OmaQuickCalc converting the selected 100 CAD to 72.61 USD](assets/readme-transform-converted.png)

**3. Put the answer back**

![The selected invoice value replaced with 72.61 dollars in Omawrite](assets/readme-transform-replaced.png)

Selection capture runs only from a shortcut you explicitly approve. Normal
launcher opens remain clipboard-blind. See [Security](SECURITY.md) for details.

## Install

OmaQuickCalc requires **Omarchy Quattro**. Install and enable it with the native
plugin command:

```bash
omarchy plugin add https://github.com/camerontucker/omaquickcalc.git --enable
```

The plugin checks for `python`, `libqalculate`, and `wl-clipboard`, then offers
to install anything missing in a visible terminal. To install them yourself:

```bash
omarchy pkg add python libqalculate wl-clipboard
```

Launch from `Super + Space`. On first use, choose whether to replace Omacalc's
shortcut, set another, or skip. Nothing changes without confirmation.

Omarchy plugins run as unsandboxed user code. Review the
[security notes](SECURITY.md) before enabling any community plugin.

## Configuration

Set history, precision, currencies, clock format, rate freshness, REM and
workday bases, and background transparency in
`~/.config/omaquickcalc/config.json`. See the
[configuration reference](docs/CONFIGURATION.md).

## Privacy and security

Calculations are local, with no account, telemetry, ads, or API key. Qalculate
may access the network only to refresh exchange rates. History can be
persistent, session-only, or disabled.

Transform selections are private, single-use, excluded from history, and
replaced only in the originating window. The plugin never overwrites unmarked
desktop or Hyprland configuration. Read the full [security model](SECURITY.md).

## Update

```bash
omarchy plugin update io.github.camerontucker.omaquickcalc
```

Omarchy shows the incoming update for review before applying it.

## Remove

Use the bundled removal script to remove the managed shortcut and launcher:

```bash
~/.config/omarchy/plugins/io.github.camerontucker.omaquickcalc/uninstall.sh --yes
```

Preferences and history are retained. To erase those too:

```bash
rm -rf ~/.config/omaquickcalc ~/.local/share/omaquickcalc
```

<details>
<summary>Development</summary>

From a source checkout, run `./install.sh`. Before a release:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
bash -n install.sh uninstall.sh
omarchy plugin validate .
/usr/lib/qt6/bin/qmllint -I /usr/share/omarchy/shell OmaQuickCalc.qml
git diff --check
```

Architecture and contributor invariants live in [AGENTS.md](AGENTS.md).
Release history lives in [CHANGELOG.md](CHANGELOG.md).

</details>

## License

[MIT](LICENSE) © 2026 OmaQuickCalc contributors.
