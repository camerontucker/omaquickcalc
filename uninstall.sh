#!/bin/bash

set -euo pipefail

plugin_source="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

# Remove only the desktop entry and marked binding block that OmaQuickCalc owns.
# Calculator preferences and history are intentionally retained.
python3 "$plugin_source/omaquickcalc_setup.py" cleanup \
  --plugin-id io.github.camerontucker.omaquickcalc
omarchy plugin remove io.github.camerontucker.omaquickcalc "$@"

printf 'OmaQuickCalc and its managed launch integrations were removed.\n'
