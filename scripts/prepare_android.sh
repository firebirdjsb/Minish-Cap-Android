#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UPSTREAM="$ROOT/upstream/tmc"
OVERRIDES="$ROOT/overrides"

if ! git -C "$UPSTREAM" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Initializing pinned Project Picori source..."
  git -C "$ROOT" submodule sync -- upstream/tmc
  git -C "$ROOT" submodule update --init --depth 1 -- upstream/tmc
fi

# Only VirtuaAPU is required by the native Android game build. Two other
# upstream submodules are optional/private and must not make preparation fail.
git -C "$UPSTREAM" submodule sync -- libs/VirtuaAPU
git -C "$UPSTREAM" submodule update --init --depth 1 -- libs/VirtuaAPU

echo "Resetting upstream working tree..."
git -C "$UPSTREAM" reset --hard
git -C "$UPSTREAM" clean -fd

echo "Applying Android phone overrides..."
cp -a "$OVERRIDES/." "$UPSTREAM/"
python3 "$ROOT/scripts/add_android_save_transfer_api.py"
python3 "$ROOT/scripts/add_android_touch_config.py"
python3 "$ROOT/scripts/tune_s24_touch.py"
python3 "$ROOT/scripts/android_gpu_touch_overlay.py"
python3 "$ROOT/scripts/android_touch_menu_toggle.py"
python3 "$ROOT/scripts/android_controller_menu.py"
python3 "$ROOT/scripts/android_controller_stick_nav.py"
python3 "$ROOT/scripts/android_menu_layout_v2.py"
python3 "$ROOT/scripts/android_ui_fit_v3.py"
python3 "$ROOT/scripts/fix_android_single_screen_present.py"
python3 "$ROOT/scripts/android_native_aspect_modes.py"
python3 "$ROOT/scripts/android_gpu_raster_sync.py"

echo
echo "Android source prepared."
echo "Upstream commit: $(git -C "$UPSTREAM" rev-parse --short HEAD)"
echo "Target: arm64-v8a single-screen phone APK"
