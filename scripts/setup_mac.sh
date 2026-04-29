#!/usr/bin/env bash
# One-time idempotent setup for building Subtitle Cleaner on macOS.
#
# Detects what's already installed, only installs what's missing. Safe
# to re-run.
#
#   bash scripts/setup_mac.sh

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT="$(cd "$HERE/.." && pwd)"

echo "=== Subtitle Cleaner: macOS build setup ==="
echo

# ----------------------------------------------------------------
# Architecture
# ----------------------------------------------------------------
ARCH="$(uname -m)"
case "$ARCH" in
    arm64)  HOST_LABEL="Apple Silicon (arm64)" ;;
    x86_64) HOST_LABEL="Intel (x86_64)" ;;
    *)      HOST_LABEL="$ARCH" ;;
esac
echo "Host architecture: $HOST_LABEL"
echo

# ----------------------------------------------------------------
# 1. Xcode Command Line Tools (provides clang, git, install_name_tool, codesign)
# ----------------------------------------------------------------
if ! xcode-select -p >/dev/null 2>&1; then
    echo "Xcode Command Line Tools not found. Triggering installer..."
    echo "(A GUI prompt will appear. Click Install, wait for it to finish, then re-run this script.)"
    xcode-select --install || true
    exit 1
fi
echo "Xcode Command Line Tools: OK ($(xcode-select -p))"

# ----------------------------------------------------------------
# 2. Homebrew
# ----------------------------------------------------------------
if ! command -v brew >/dev/null 2>&1; then
    echo "Homebrew not found. Installing..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # Rehash brew into the current shell.
    if [ -x /opt/homebrew/bin/brew ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    elif [ -x /usr/local/bin/brew ]; then
        eval "$(/usr/local/bin/brew shellenv)"
    fi
fi
echo "Homebrew: OK ($(brew --prefix))"

# ----------------------------------------------------------------
# 3. Required brew formulas
# ----------------------------------------------------------------
NEEDED_FORMULAS=(python@3.12 mpv ffmpeg dylibbundler create-dmg)
MISSING_FORMULAS=()
for f in "${NEEDED_FORMULAS[@]}"; do
    if ! brew list --formula "$f" >/dev/null 2>&1; then
        MISSING_FORMULAS+=("$f")
    fi
done
if [ "${#MISSING_FORMULAS[@]}" -gt 0 ]; then
    echo "Installing missing formulas: ${MISSING_FORMULAS[*]}"
    brew install "${MISSING_FORMULAS[@]}"
else
    echo "All required brew formulas already installed."
fi

# ----------------------------------------------------------------
# 4. Pin Python 3.12 for the rest of the build
# ----------------------------------------------------------------
PY312="$(brew --prefix python@3.12)/bin/python3.12"
if [ ! -x "$PY312" ]; then
    echo "ERROR: brew installed python@3.12 but $PY312 is not executable."
    exit 1
fi
echo "Python: $PY312 ($($PY312 --version))"

# ----------------------------------------------------------------
# 5. Project venv at .build-env-mac/
# ----------------------------------------------------------------
VENV="$PROJECT/.build-env-mac"
if [ ! -d "$VENV" ]; then
    echo "Creating venv at $VENV ..."
    "$PY312" -m venv "$VENV"
fi

# Activate venv for the rest of this script.
# shellcheck disable=SC1090
source "$VENV/bin/activate"

# Make sure pip + the slim runtime deps are installed.
python -m pip install --upgrade pip >/dev/null
python -m pip install -r "$PROJECT/requirements.txt"
python -m pip install pyinstaller

echo
echo "Slim runtime deps installed in $VENV:"
python -m pip freeze | grep -E '^(PySide6|python-mpv|qtawesome|pyinstaller)' || true

# ----------------------------------------------------------------
# 6. Make build scripts executable. Git on Windows often loses the +x
#    bit, so we set it here even though it's a no-op on a clean clone.
# ----------------------------------------------------------------
for s in \
    "$PROJECT/MAKE_INSTALLER.command" \
    "$PROJECT/scripts/setup_mac.sh" \
    "$PROJECT/build/build_mac.sh" \
    "$PROJECT/installer/download_deps_mac.sh" \
    "$PROJECT/installer/build_dmg.sh"; do
    if [ -e "$s" ]; then
        chmod +x "$s"
    fi
done

# ----------------------------------------------------------------
# 7. Sanity probe
# ----------------------------------------------------------------
echo
echo "Probing python-mpv loadability..."
if python -c "import mpv; print('  python-mpv', mpv.__version__ if hasattr(mpv,'__version__') else 'OK')"; then
    :
else
    echo "  python-mpv loaded with an error. Check that libmpv is installed:"
    echo "  brew reinstall mpv"
    exit 1
fi

echo
echo "============================================================"
echo " macOS build environment ready."
echo
echo " Next steps:"
echo "   bash MAKE_INSTALLER.command       (one-click full build)"
echo
echo " Or step-by-step:"
echo "   bash installer/download_deps_mac.sh"
echo "   bash build/build_mac.sh"
echo "   bash installer/build_dmg.sh"
echo "============================================================"
