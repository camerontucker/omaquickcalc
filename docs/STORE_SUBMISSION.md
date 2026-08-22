# Omarchy marketplace submission draft

This draft follows the marketplace's current
[submission guide](https://github.com/HANCORE-linux/omarchy-plugin-marketplace/blob/main/SUBMISSION.md).
Do not create the issue until the owner reviews the repository at its final
commit, confirms all five checklist statements (especially ownership of
`preview.png`), and explicitly approves this title and body.

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

OmaQuickCalc is a keyboard-first modal calculator for Omarchy Quattro with Transform in Place: highlight `100 CAD` in any application, summon one floating input, type `in USD`, and press Shift+Enter to replace the selection with `$72.61`. Enter still copies normally. The same universal workflow handles percentages, units, design values, and local-time shorthand while preserving the dead-simple single-input interface and active Omarchy theme.

The launch experience is complete for normal marketplace installation even though lifecycle hooks are not executed. The enabled overlay creates its owned Super + Space launcher entry on load and presents optional first-run shortcut setup. A user can replace Omacalc's Super+Ctrl+Q binding, choose a conflict-checked alternative, or skip. The approved shortcut explicitly enables numeric selection capture; normal launcher opens never read the clipboard. No user configuration is changed without confirmation, and the plugin manages only its marked block, validates Hyprland, and rolls back rejected changes.

Runtime dependencies (`python`, `libqalculate`, and `wl-clipboard`) are documented and checked independently. Transform selections use a private single-use runtime handoff, never enter history, restore the previous clipboard after capture, and paste only when focus returns to the originating window. Missing packages are offered only after user action through a visible `omarchy pkg add` terminal. Calculations run locally, there is no account or telemetry, and Qalculate's optional exchange-rate refresh is the only calculation-related network access.

Submitted for the August 2026 Omarchy plugin contest. The memorable five-second workflow is intentionally simple: select a value, transform it in a native shell surface, and put the answer straight back. The implementation covers the less-visible privacy, focus, clipboard, launch, and rollback details that make that interaction dependable.

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
- [ ] README install, launch, update, and removal commands match the final ID.
- [ ] `manifest.json`, `CHANGELOG.md`, installer arguments, and launcher identity
  carry the same version and plugin ID.
- [ ] The complete repository checks pass from a fresh clone of the final commit.
- [ ] The public repository contains a root README, license, manifest, and one
  plugin only; the permanent ID is absent from the current marketplace registry.
- [ ] The owner confirms every submission checkbox and approves the exact title
  and body above before the issue is created.
