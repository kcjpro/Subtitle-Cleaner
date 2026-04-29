#!/usr/bin/env bash
# Populate build/bin_mac/ with libmpv.2.dylib (+ its transitive dylibs,
# rpath-rewritten so they relocate cleanly inside the .app bundle's
# Frameworks/ folder) plus ffmpeg + ffprobe.
#
# Requires Homebrew with: mpv ffmpeg dylibbundler
# scripts/setup_mac.sh installs all of these.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT="$(cd "$HERE/.." && pwd)"

DEPS_DIR="$HERE/deps_mac"
BIN_DIR="$PROJECT/build/bin_mac"

# Wipe the staging area so stale dylibs from a previous build don't
# tag along into the bundle.
rm -rf "$BIN_DIR" "$DEPS_DIR/_stage"
mkdir -p "$DEPS_DIR" "$BIN_DIR" "$DEPS_DIR/_stage"

# ---------------------------------------------------------------
# Verify Homebrew + required formulas
# ---------------------------------------------------------------
if ! command -v brew >/dev/null 2>&1; then
    echo "ERROR: Homebrew not found. Run scripts/setup_mac.sh first."
    exit 1
fi

for formula in mpv ffmpeg dylibbundler; do
    if ! brew list --formula "$formula" >/dev/null 2>&1; then
        echo "Installing missing brew formula: $formula"
        brew install "$formula"
    fi
done

# ---------------------------------------------------------------
# ffmpeg + ffprobe
# ---------------------------------------------------------------
FFMPEG_BIN="$(brew --prefix ffmpeg)/bin/ffmpeg"
FFPROBE_BIN="$(brew --prefix ffmpeg)/bin/ffprobe"

if [ ! -x "$FFMPEG_BIN" ] || [ ! -x "$FFPROBE_BIN" ]; then
    echo "ERROR: ffmpeg/ffprobe not found at $(brew --prefix ffmpeg)/bin/"
    echo "       Try: brew reinstall ffmpeg"
    exit 1
fi

echo "Found ffmpeg/ffprobe under $(brew --prefix ffmpeg)/bin/"

# ---------------------------------------------------------------
# libmpv + transitive dylibs
# ---------------------------------------------------------------
MPV_PREFIX="$(brew --prefix mpv)"
LIBMPV_SRC=""
for candidate in \
    "$MPV_PREFIX/lib/libmpv.2.dylib" \
    "$MPV_PREFIX/lib/libmpv.dylib"; do
    if [ -e "$candidate" ]; then
        LIBMPV_SRC="$candidate"
        break
    fi
done
if [ -z "$LIBMPV_SRC" ]; then
    echo "ERROR: libmpv.2.dylib not found under $MPV_PREFIX/lib/."
    echo "       Try: brew reinstall mpv"
    exit 1
fi
echo "Found libmpv at: $LIBMPV_SRC"

# Stage libmpv + transitive dylibs into _stage/ first, then copy into
# build/bin_mac/ flat. dylibbundler rewrites their install names to
# @loader_path/<dylib> so they all sit next to each other.
STAGE="$DEPS_DIR/_stage"

# Resolve the real file (libmpv.2.dylib usually symlinks to libmpv.<full>.dylib).
LIBMPV_REAL="$(readlink -f "$LIBMPV_SRC" 2>/dev/null || true)"
if [ -z "$LIBMPV_REAL" ] || [ ! -e "$LIBMPV_REAL" ]; then
    LIBMPV_REAL="$LIBMPV_SRC"
fi
cp "$LIBMPV_REAL" "$STAGE/libmpv.2.dylib"
chmod +w "$STAGE/libmpv.2.dylib"

# dylibbundler:
#   -of      : overwrite existing files in the destination dir
#   -b       : actually do the bundling (default is dry-run)
#   -x       : extra binary to scan for dependencies (a dylib works too)
#   -d       : destination folder for bundled dylibs
#   -p       : install_name prefix to use (@loader_path/ so the bundle
#              can be relocated anywhere by the user)
#   -cd      : codesign each rewritten dylib (ad-hoc) so Gatekeeper
#              doesn't reject the bundle outright
echo "Running dylibbundler to gather libmpv's transitive deps..."
dylibbundler -of -b \
    -x "$STAGE/libmpv.2.dylib" \
    -d "$STAGE" \
    -p "@loader_path/" \
    -cd

# Copy dylibs flat into bin_mac/, then ffmpeg/ffprobe alongside.
cp "$STAGE"/*.dylib "$BIN_DIR/" 2>/dev/null || true
cp "$FFMPEG_BIN"  "$BIN_DIR/ffmpeg"
cp "$FFPROBE_BIN" "$BIN_DIR/ffprobe"
chmod +x "$BIN_DIR/ffmpeg" "$BIN_DIR/ffprobe"

# Verify libmpv.2.dylib is there (dylibbundler keeps the original name).
if [ ! -e "$BIN_DIR/libmpv.2.dylib" ]; then
    cp "$STAGE/libmpv.2.dylib" "$BIN_DIR/libmpv.2.dylib"
fi

echo
echo "build/bin_mac/ contents:"
ls -la "$BIN_DIR"
echo
echo "libmpv.2.dylib install_name dependencies (should all be"
echo "@loader_path/... or system /usr/lib/...):"
otool -L "$BIN_DIR/libmpv.2.dylib" | sed 's/^/  /'
