#!/bin/bash
set -euo pipefail
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
build_dir=$(mktemp -d)
trap 'rm -rf -- "$build_dir"' EXIT
# These are development-only dependencies. Production input remains pure QML.
c++ -std=c++17 -fPIC "$repo/tests/guarded_input_test.cpp" -o "$build_dir/test" \
  $(pkg-config --cflags --libs Qt6Quick Qt6Qml Qt6Gui Qt6Test)
(
  ulimit -v 1048576
  export QT_QPA_PLATFORM=offscreen QT_QPA_PLATFORMTHEME= QT_QUICK_BACKEND=software
  export QT_LOGGING_RULES="*.info=true"
  export WAYLAND_DISPLAY= DISPLAY=
  timeout --kill-after=1s 15s "$build_dir/test" "$repo"
)
