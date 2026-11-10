#!/usr/bin/env bash
# Build a source release zip for download (no secrets, no caches, no .git).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT_DIR="${1:-$ROOT/dist}"
NAME="skillcorpus-0.1.1-src"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

mkdir -p "$OUT_DIR" "$STAGE/$NAME"

# Copy tree without .git / caches / build artifacts.
shopt -s dotglob nullglob
for item in "$ROOT"/* "$ROOT"/.[!.]* "$ROOT"/..?*; do
  base="$(basename "$item")"
  case "$base" in
    .|..|.git|.venv|venv|dist|__pycache__|.pytest_cache|.ruff_cache|.skillcorpus-cache|.eval-work) continue ;;
  esac
  if [[ "$base" == *.egg-info ]]; then
    continue
  fi
  cp -a "$item" "$STAGE/$NAME/"
done

# Drop nested caches if copied.
find "$STAGE/$NAME" -type d \( -name '__pycache__' -o -name '.pytest_cache' -o -name '.ruff_cache' -o -name '*.egg-info' \) -prune -exec rm -rf {} +
find "$STAGE/$NAME" -type f -name '*.pyc' -delete

# Sensitivity grep before zipping (exclude this script so pattern literals do not self-match)
if grep -RInE \
  --exclude-dir=.git \
  --exclude-dir=dist \
  --exclude='*.pdf' \
  --exclude='make_release_zip.sh' \
  -e 'AKIA[0-9A-Z]{16}' \
  -e 'BEGIN RSA PRIVATE KEY' \
  -e 'xox[baprs]-' \
  -e 'sk-[a-zA-Z0-9]{20,}' \
  "$STAGE/$NAME"; then
  echo "Refusing release: possible secret pattern detected" >&2
  exit 1
fi

# License files must be present
test -f "$STAGE/$NAME/LICENSE"
test -f "$STAGE/$NAME/NOTICE"

ZIP="$OUT_DIR/${NAME}.zip"
rm -f "$ZIP"
(cd "$STAGE" && zip -qr "$ZIP" "$NAME")
echo "Wrote $ZIP"
sha256sum "$ZIP"
