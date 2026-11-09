#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${RDG_CHROME_PATH:=/workspace/repo/.rdg-visual-browser/chrome-headless-shell/linux-155.0.8059.39/chrome-headless-shell-linux64/chrome-headless-shell}"
: "${RDG_SCREENSHOT_DIR:=/workspace/repo/rdg-visual-output}"
: "${RDG_FONTCONFIG:=/workspace/repo/.rdg-apt/fontconfig.xml}"
: "${RDG_SYSROOT:=/workspace/repo/.rdg-apt/sysroot}"
export RDG_CHROME_PATH RDG_SCREENSHOT_DIR
if [[ ! -x "$RDG_CHROME_PATH" ]]; then
  echo "Isolated headless Chromium not installed: $RDG_CHROME_PATH" >&2
  echo "Use a dedicated headless binary, not the user's Windows browser." >&2
  exit 2
fi
if [[ -f "$RDG_FONTCONFIG" ]]; then export FONTCONFIG_FILE="$RDG_FONTCONFIG"; fi
if [[ -d "$RDG_SYSROOT" ]]; then
  export LD_LIBRARY_PATH="$RDG_SYSROOT/usr/lib/x86_64-linux-gnu:$RDG_SYSROOT/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi
node "${RDG_VISUAL_TEST_FILE:-${1:-tests/visual/rdg-graph-scope.cjs}}"

