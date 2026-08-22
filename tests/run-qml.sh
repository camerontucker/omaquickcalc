#!/bin/bash

set -euo pipefail

runner=$(command -v qmltestrunner6 2>/dev/null \
  || command -v qmltestrunner 2>/dev/null \
  || true)
if [[ -z $runner && -x /usr/lib/qt6/bin/qmltestrunner ]]; then
  runner=/usr/lib/qt6/bin/qmltestrunner
fi
if [[ -z $runner ]]; then
  printf '%s\n' "qmltestrunner not found; install Qt 6 QML test tooling" >&2
  exit 1
fi

QT_QPA_PLATFORM=offscreen "$runner" -input tests/qml
