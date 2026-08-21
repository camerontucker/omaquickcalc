# Omarchy marketplace submission draft

This draft follows the marketplace's current
[submission guide](https://github.com/HANCORE-linux/omarchy-plugin-marketplace/blob/main/SUBMISSION.md).
Do not create the issue until the owner reviews the repository at its final
commit, confirms all five checklist statements (especially ownership of
`preview.png` and the demo), and explicitly approves this title and body.

Contest timing: submit and trigger marketplace validation before **Monday,
August 24, 2026 at 09:00 CEST**. Leave time to correct automated compatibility
or security-baseline feedback before the deadline.

## Issue title

```text
[Plugin]: OmaQuickCalc
```

## Issue body

```markdown
### Repository URL

https://github.com/camerontucker/omaquickcalc

### Category

Productivity

### Tags

launcher, quickshell, hyprland

### Suggest a missing tag

calculator

### Maintainer notes

OmaQuickCalc is a keyboard-first, Raycast-style calculator for Omarchy Quattro: summon one floating input, type a calculation or conversion, and press Enter to copy the result. It combines live arithmetic with natural-language percentages, units, currencies, dates, timezones, design conversions, color formats, searchable history, and contextual copy/format actions while following the active Omarchy theme.

The launch experience is complete for normal marketplace installation even though lifecycle hooks are not executed. The enabled overlay creates its owned Super + Space launcher entry on load and presents optional first-run shortcut setup. A user can replace Omacalc's Super+Ctrl+Q binding, choose a conflict-checked alternative, or skip. No user configuration is changed without an explicit confirmation; the plugin manages only its marked block, validates Hyprland, and rolls back rejected changes. Removal cleans only managed launch integrations and retains calculator data by design.

Runtime dependencies (`python`, `libqalculate`, and `wl-clipboard`) are documented and checked independently. Missing packages are offered only after user action through a visible `omarchy pkg add` terminal. Calculations run locally, there is no account or telemetry, and Qalculate's optional exchange-rate refresh is the only calculation-related network access. The repository includes tests for evaluator behavior and safe install, launch, upgrade, shortcut rollback, and removal lifecycles.

Submitted for the August 2026 Omarchy plugin contest. The idea is intentionally simple—make calculation feel native to the launcher—and the implementation is designed to cover the less-visible details that make that interaction dependable.

### Submission checklist

- [x] The repository is public and contains installation and removal instructions.
- [x] I have documented the plugin license and any external dependencies.
- [x] I confirm that I own or have permission to submit this plugin and its preview assets.
- [x] The plugin does not overwrite user configuration without explicit consent.
- [x] I understand that approval is for listing and is not a security review.
```

After final approval, create the issue with:

```bash
gh issue create \
  --repo HANCORE-linux/omarchy-plugin-marketplace \
  --title "[Plugin]: OmaQuickCalc" \
  --body-file /tmp/omarchy-plugin-submission.md
```

Copy only the contents of the **Issue body** code block to
`/tmp/omarchy-plugin-submission.md`. Keep the six headings in that exact order.

## Final storefront preflight

- [ ] `preview.png` is an authentic capture of the released interface, under
  50 MB and 40 megapixels, and readable at marketplace-card size.
- [ ] `assets/omaquickcalc-demo.mp4` shows the same released interface and the
  README demo link opens from GitHub.
- [ ] README install, launch, update, and removal commands match the final ID.
- [ ] `manifest.json`, `CHANGELOG.md`, installer arguments, and launcher identity
  carry the same version and plugin ID.
- [ ] The complete repository checks pass from a fresh clone of the final commit.
- [ ] The public repository contains a root README, license, manifest, and one
  plugin only; the permanent ID is absent from the current marketplace registry.
- [ ] The owner confirms every submission checkbox and approves the exact title
  and body above before the issue is created.
