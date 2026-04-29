#!/usr/bin/env bash
# Wrap build/dist/SubtitleCleaner.app into a draggable .dmg.
#
# Output: installer/Output/SubtitleCleaner.dmg
#
# Requires brew install create-dmg (handled by scripts/setup_mac.sh).

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT="$(cd "$HERE/.." && pwd)"

APP="$PROJECT/build/dist/SubtitleCleaner.app"
OUT_DIR="$HERE/Output"
DMG_PATH="$OUT_DIR/SubtitleCleaner.dmg"

if [ ! -d "$APP" ]; then
    echo "ERROR: $APP does not exist. Run build/build_mac.sh first."
    exit 1
fi

mkdir -p "$OUT_DIR"
rm -f "$DMG_PATH"

if ! command -v create-dmg >/dev/null 2>&1; then
    echo "ERROR: create-dmg is not installed. Run: brew install create-dmg"
    exit 1
fi

# Stage a clean folder containing the .app + a README so the .dmg
# window has only what we want.
STAGE="$(mktemp -d -t scdmg)"
trap 'rm -rf "$STAGE"' EXIT
cp -R "$APP" "$STAGE/"

# Tiny README explaining how to bypass Gatekeeper for the unsigned bundle.
cat > "$STAGE/README.txt" <<'EOF'
Subtitle Cleaner
=================

This is an unsigned app. The first time you launch it, macOS will say
"can't be opened because it's from an unidentified developer."

Workaround (do this only once):

  1. Right-click SubtitleCleaner.app -> Open
  2. Click "Open" in the dialog that appears.

Or from Terminal:

  xattr -dr com.apple.quarantine /Applications/SubtitleCleaner.app

After that, the app launches normally from Spotlight or Launchpad.
EOF

create-dmg \
    --volname "Subtitle Cleaner" \
    --window-pos 200 120 \
    --window-size 640 400 \
    --icon-size 96 \
    --icon "SubtitleCleaner.app" 160 200 \
    --icon "README.txt" 320 200 \
    --hide-extension "SubtitleCleaner.app" \
    --app-drop-link 480 200 \
    --no-internet-enable \
    "$DMG_PATH" \
    "$STAGE"

echo
echo "============================================================"
echo "DMG ready: $DMG_PATH"
ls -lh "$DMG_PATH"
echo "============================================================"
