#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UPSTREAM="$ROOT/upstream/tmc"

if [[ ! -d "$UPSTREAM/.git" && ! -f "$UPSTREAM/.git" ]]; then
  echo "Initializing Project Picori submodule..."
  git -C "$ROOT" submodule update --init --recursive
fi

echo "Resetting upstream working tree..."
git -C "$UPSTREAM" reset --hard
git -C "$UPSTREAM" clean -fd

echo "Applying Android phone patches..."
for patch in "$ROOT"/patches/*.patch; do
  [[ -e "$patch" ]] || continue
  echo "  -> $(basename "$patch")"
  git -C "$UPSTREAM" apply --whitespace=fix "$patch"
done

echo
echo "Android source prepared."
echo "Upstream commit: $(git -C "$UPSTREAM" rev-parse --short HEAD)"
echo "Next: build the native arm64-v8a target, then package with Gradle."
