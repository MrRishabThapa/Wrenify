#!/usr/bin/env bash
# Build Wrenify AppImage for Linux distribution.
# Requires: appimagetool, python 3.11+
#
# Usage: ./build/build_appimage.sh [version]

set -euo pipefail

# Configuration
VERSION="${1:-0.1.0}"
APP_NAME="Wrenify"
BUILD_DIR="build/appdir"
DIST_DIR="dist"

echo "════════════════════════════════════════════"
echo "  Building Wrenify AppImage v${VERSION}"
echo "════════════════════════════════════════════"

# Clean previous builds
rm -rf "${BUILD_DIR}" "${DIST_DIR}"
mkdir -p "${BUILD_DIR}" "${DIST_DIR}"

# ─── 1. Create AppDir structure ───
echo ""
echo "[1/6] Creating AppDir structure..."
mkdir -p "${BUILD_DIR}/usr/bin"
mkdir -p "${BUILD_DIR}/usr/lib"
mkdir -p "${BUILD_DIR}/usr/share/applications"
mkdir -p "${BUILD_DIR}/usr/share/icons/hicolor/256x256/apps"

# ─── 2. Build wheel + install into AppDir ───
echo "[2/6] Building Python package..."
poetry build -f wheel
WHEEL=$(ls dist/wrenify-*.whl | head -1)

echo "[3/6] Installing into AppDir..."
python -m pip install \
    --target="${BUILD_DIR}/usr/lib/python3.11/site-packages" \
    --no-deps \
    "${WHEEL}"

# Install runtime dependencies
python -m pip install \
    --target="${BUILD_DIR}/usr/lib/python3.11/site-packages" \
    -r <(poetry export --without-hashes -f requirements.txt)

# ─── 3. Copy Python interpreter ───
echo "[4/6] Bundling Python interpreter..."
# Note: For truly portable AppImage, use python-appimage as base
# For simplicity, we assume system Python 3.11+ on target machines

cat > "${BUILD_DIR}/AppRun" << 'ENDOFAPPRUN'
#!/usr/bin/env bash
HERE="$(dirname "$(readlink -f "${0}")")"
export PYTHONPATH="${HERE}/usr/lib/python3.11/site-packages:${PYTHONPATH}"
export LD_LIBRARY_PATH="${HERE}/usr/lib:${LD_LIBRARY_PATH}"
exec python3 -m wrenify "$@"
ENDOFAPPRUN
chmod +x "${BUILD_DIR}/AppRun"

# ─── 4. Desktop file ───
echo "[5/6] Creating desktop entry..."
cat > "${BUILD_DIR}/wrenify.desktop" << EOF
[Desktop Entry]
Name=Wrenify
GenericName=Karaoke Studio
Comment=Local-first karaoke with auto-tune and recording
Exec=wrenify
Icon=wrenify
Type=Application
Categories=Audio;Music;
Terminal=false
StartupNotify=true
EOF

cp "${BUILD_DIR}/wrenify.desktop" "${BUILD_DIR}/usr/share/applications/"

# Icon
if [ -f "assets/wrenify.png" ]; then
    cp assets/wrenify.png "${BUILD_DIR}/wrenify.png"
    cp assets/wrenify.png "${BUILD_DIR}/usr/share/icons/hicolor/256x256/apps/wrenify.png"
else
    echo "  [warning] No wrenify.png found — using placeholder"
    touch "${BUILD_DIR}/wrenify.png"
fi

# ─── 5. Build AppImage ───
echo "[6/6] Building AppImage..."

if ! command -v appimagetool &> /dev/null; then
    echo ""
    echo "  [error] appimagetool not found."
    echo "  Install with:"
    echo "    wget https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
    echo "    chmod +x appimagetool-x86_64.AppImage"
    echo "    sudo mv appimagetool-x86_64.AppImage /usr/local/bin/appimagetool"
    exit 1
fi

ARCH=x86_64 appimagetool "${BUILD_DIR}" "${DIST_DIR}/${APP_NAME}-${VERSION}-x86_64.AppImage"

echo ""
echo "════════════════════════════════════════════"
echo "  ✓ Build complete!"
echo "════════════════════════════════════════════"
echo ""
echo "  Output: ${DIST_DIR}/${APP_NAME}-${VERSION}-x86_64.AppImage"
echo ""
echo "  To test:"
echo "    chmod +x ${DIST_DIR}/${APP_NAME}-${VERSION}-x86_64.AppImage"
echo "    ./${DIST_DIR}/${APP_NAME}-${VERSION}-x86_64.AppImage"
echo ""
