#!/usr/bin/env bash
# Build Subtitle Cleaner.app via PyInstaller on macOS.
#
# Run from anywhere:
#     bash build/build_mac.sh
#
# Output: build/dist/SubtitleCleaner.app
#
# Prerequisites: Python 3.12 + the slim runtime deps (PySide6, python-mpv,
# qtawesome) + PyInstaller. The setup_mac.sh helper installs all of these.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT="$(cd "$HERE/.." && pwd)"

cd "$HERE"

echo "=== Subtitle Cleaner build (macOS, slim portable, mpv playback) ==="
echo

# ----- Python detection ---------------------------------------------
if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 is not on PATH. Install Python 3.12 from"
    echo "       https://www.python.org/ or run scripts/setup_mac.sh first."
    exit 1
fi

PYVER=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
echo "Build Python: $(python3 --version) ($PYVER)"

case "$PYVER" in
    3.10|3.11|3.12) ;;
    *)
        echo "WARNING: Python $PYVER is not in the tested range (3.10-3.12)."
        echo "         Wheels may fail. If this build fails, install Python 3.12"
        echo "         and rerun (scripts/setup_mac.sh handles this for you)."
        ;;
esac

# ----- Pre-flight checks --------------------------------------------
ARCH="$(uname -m)"
echo "Build architecture: $ARCH"
echo

MISSING=0
if [ ! -e "$HERE/bin_mac/libmpv.2.dylib" ] && [ ! -e "$HERE/bin_mac/libmpv.dylib" ]; then
    echo "NOTE: build/bin_mac/libmpv.2.dylib not found."
    echo "      Without it, video playback will not work."
    echo "      installer/download_deps_mac.sh handles this for you."
    MISSING=1
fi
if [ ! -e "$HERE/bin_mac/ffmpeg" ]; then
    echo "NOTE: build/bin_mac/ffmpeg not found."
    echo "      Drop ffmpeg + ffprobe in there to bundle them."
    MISSING=1
fi
if [ "$MISSING" = "1" ]; then
    echo
    echo "Run 'bash installer/download_deps_mac.sh' first to populate build/bin_mac/."
    echo "Continuing anyway in case you wired the binaries manually..."
    echo
fi

# ----- Install build deps -------------------------------------------
echo "Installing/updating build + runtime dependencies..."
python3 -m pip install --upgrade pip >/dev/null
python3 -m pip install -r "$PROJECT/requirements.txt"
python3 -m pip install pyinstaller

# ----- Run PyInstaller ----------------------------------------------
echo
echo "Running PyInstaller (full log: build/pyinstaller.log)..."
PYI_RC=0
python3 -m PyInstaller --noconfirm --clean --log-level=WARN \
    SubtitleCleanerMac.spec > pyinstaller.log 2>&1 || PYI_RC=$?

echo "PyInstaller exit code: $PYI_RC"
echo
echo "--- last 60 lines of build/pyinstaller.log ---"
tail -n 60 pyinstaller.log
echo "--- end of log tail ---"
echo

if [ "$PYI_RC" != "0" ]; then
    echo "Build failed. See build/pyinstaller.log for details."
    exit 1
fi

# Make sure the empty profiles folder ships with the bundle.
APP="$HERE/dist/SubtitleCleaner.app"
if [ -d "$APP" ]; then
    mkdir -p "$APP/Contents/Resources/data/profiles"
fi

if [ ! -d "$APP" ]; then
    echo "ERROR: PyInstaller exited 0 but did not produce $APP"
    echo "Folder contents of build/dist/:"
    ls -la "$HERE/dist" 2>/dev/null || echo "  (dist folder does not exist)"
    exit 1
fi

# Strip Apple's quarantine attribute that gets attached when the bundle
# is unpacked from a downloaded zip. Only matters for the developer
# building locally; end users download a fresh copy.
xattr -dr com.apple.quarantine "$APP" 2>/dev/null || true

echo
echo "============================================================"
echo "Build complete."
echo "Open: $APP"
echo "============================================================"
