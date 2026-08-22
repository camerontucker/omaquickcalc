#!/bin/bash

set -euo pipefail

plugin_source="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
plugin_id="io.github.camerontucker.omaquickcalc"

# Unload first so the overlay cannot recreate its managed launcher while it is
# being removed. Calculator preferences and history are intentionally retained.
omarchy plugin disable "$plugin_id"
python3 "$plugin_source/omaquickcalc_setup.py" cleanup \
  --plugin-id "$plugin_id"
omarchy plugin remove "$plugin_id" "$@"

printf 'OmaQuickCalc and its managed launch integrations were removed.\n'
