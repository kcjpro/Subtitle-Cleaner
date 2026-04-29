#!/usr/bin/env bash
# Subtitle Cleaner - one-click installer + portable build for macOS.
#
# Double-click in Finder, or run from Terminal:
#     bash MAKE_INSTALLER.command
#
# Outputs in installer/Output/:
#   SubtitleCleaner.dmg          drag-to-Applications installer
#   SubtitleCleaner-mac.zip      portable .app bundle (unzip + double-click)

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

echo "============================================================"
echo " Subtitle Cleaner - macOS one-click installer build"
echo "============================================================"
echo

# ----- Step 1/6: dependency setup -----
echo "Step 1/6 - Verifying / installing prerequisites..."
bash scripts/setup_mac.sh
echo

# ----- Step 2/6: clean previous build -----
echo "Step 2/6 - Cleaning previous build output..."
rm -rf build/dist build/build installer/Output

# ----- Step 3/6: download deps into build/bin_mac/ -----
echo "Step 3/6 - Bundling libmpv + ffmpeg into build/bin_mac/..."
bash installer/download_deps_mac.sh
echo

# ----- Step 4/6: PyInstaller -----
echo "Step 4/6 - Running PyInstaller..."
bash build/build_mac.sh
echo

APP_PATH="build/dist/SubtitleCleaner.app"
if [ ! -d "$APP_PATH" ]; then
    echo "ERROR: $APP_PATH was not produced. Aborting."
    exit 1
fi

# ----- Step 5/6: dmg + zip -----
echo "Step 5/6 - Building .dmg and portable .zip..."
bash installer/build_dmg.sh

mkdir -p installer/Output
ZIP_OUT="installer/Output/SubtitleCleaner-mac.zip"
rm -f "$ZIP_OUT"
# Use ditto to preserve resource forks / Finder metadata in the zip.
ditto -c -k --sequesterRsrc --keepParent "$APP_PATH" "$ZIP_OUT"
echo "Portable zip written to $ZIP_OUT"
echo

# ----- Step 6/6: report -----
echo "Step 6/6 - Done."
echo
echo "============================================================"
echo " SUCCESS"
echo " DMG:      installer/Output/SubtitleCleaner.dmg"
echo " Portable: installer/Output/SubtitleCleaner-mac.zip"
echo
echo " Both bundle libmpv + ffmpeg, so end users do not need"
echo " to brew install anything."
echo
echo " First-launch tip: macOS will block the unsigned .app once."
echo " Right-click SubtitleCleaner.app -> Open, click Open in"
echo " the dialog. After that it launches normally."
echo "============================================================"
echo

# Keep the Terminal window open when double-clicked from Finder.
if [ -t 0 ]; then
    read -r -p "Press return to close..." _
fi
