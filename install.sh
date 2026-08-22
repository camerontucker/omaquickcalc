#!/bin/bash

set -euo pipefail

plugin_source="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
plugin_parent="${XDG_CONFIG_HOME:-$HOME/.config}/omarchy/plugins"
plugin_target="$plugin_parent/io.github.camerontucker.omaquickcalc"

omarchy pkg add libqalculate wl-clipboard python
mkdir -p "$plugin_parent"

if [[ -L "$plugin_target" && "$(readlink -f -- "$plugin_target")" == "$plugin_source" ]]; then
  :
elif [[ -e "$plugin_target" || -L "$plugin_target" ]]; then
  printf 'Refusing to replace existing plugin path: %s\n' "$plugin_target" >&2
  exit 1
else
  ln -s "$plugin_source" "$plugin_target"
fi

omarchy-shell shell rescanPlugins
omarchy plugin enable io.github.camerontucker.omaquickcalc
python3 "$plugin_source/omaquickcalc_setup.py" ensure-launcher \
  --plugin-id io.github.camerontucker.omaquickcalc --version 0.6.0

printf 'OmaQuickCalc is installed and enabled.\n'
printf 'Open Super + Space and search for OmaQuickCalc to finish launch setup.\n'
