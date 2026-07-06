#!/bin/bash
# ============================================================
# TechExpert Printer Agent — macOS App Bundle Builder
# Creates a proper .app bundle with native macOS experience
# ============================================================

set -e

APP_NAME="TechExpert TPV Printer"
APP_VERSION="2.0.0"
BUNDLE_ID="com.techexpert.printer-agent"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$BASE_DIR/builds"
APP_BUNDLE="$BUILD_DIR/$APP_NAME.app"
CONTENTS="$APP_BUNDLE/Contents"
MACOS="$CONTENTS/MacOS"
RESOURCES="$CONTENTS/Resources"

echo "📦 Building $APP_NAME v$APP_VERSION"
echo ""

# Clean previous
rm -rf "$APP_BUNDLE"

# Create bundle structure
mkdir -p "$MACOS" "$RESOURCES"

# ── Info.plist ──
cat > "$CONTENTS/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>$APP_NAME</string>
    <key>CFBundleDisplayName</key>
    <string>$APP_NAME</string>
    <key>CFBundleIdentifier</key>
    <string>$BUNDLE_ID</string>
    <key>CFBundleVersion</key>
    <string>$APP_VERSION</string>
    <key>CFBundleShortVersionString</key>
    <string>$APP_VERSION</string>
    <key>CFBundleExecutable</key>
    <string>TechExpert-App</string>
    <key>CFBundleIconFile</key>
    <string>icon</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSUIElement</key>
    <string>1</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSAppTransportSecurity</key>
    <dict>
        <key>NSAllowsArbitraryLoads</key>
        <true/>
    </dict>
</dict>
</plist>
EOF

# ── Launcher script ──
cat > "$MACOS/TechExpert-App" << 'LAUNCHER'
#!/bin/bash
# TechExpert Printer Agent — macOS Launcher
DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(dirname "$(dirname "$DIR")")"

# Path to the real agent binary
AGENT="$DIR/agent"
APP_PY="$DIR/app.py"

# Check for Python3
PYTHON=""
for cmd in python3 python; do
    if command -v $cmd &>/dev/null; then
        PYTHON="$cmd"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    osascript -e 'display dialog "Python 3 no está instalado.\n\nInstálalo con: brew install python" buttons {"OK"} default button 1 with icon stop'
    exit 1
fi

# Run the app
cd "$APP_DIR"
exec "$PYTHON" "$APP_PY"
LAUNCHER
chmod +x "$MACOS/TechExpert-App"

# ── Copy agent binary ──
if [ -f "$BUILD_DIR/agent-macos-arm64" ]; then
    cp "$BUILD_DIR/agent-macos-arm64" "$MACOS/agent"
elif [ -f "$BUILD_DIR/agent-macos-x64" ]; then
    cp "$BUILD_DIR/agent-macos-x64" "$MACOS/agent"
elif [ -f "$BASE_DIR/agent.js" ]; then
    cp "$BASE_DIR/agent.js" "$MACOS/agent.js"
fi
chmod +x "$MACOS/agent" 2>/dev/null || true

# ── Copy app.py and resources ──
cp "$SCRIPT_DIR/app.py" "$MACOS/app.py"
cp "$SCRIPT_DIR/icon.png" "$RESOURCES/icon.png" 2>/dev/null || true
cp "$SCRIPT_DIR/icon.svg" "$RESOURCES/icon.svg" 2>/dev/null || true
cp "$BASE_DIR/config.json" "$RESOURCES/config.json" 2>/dev/null || true

# ── Generate .icns icon (macOS format) ──
if [ -f "$SCRIPT_DIR/icon.png" ]; then
    ICONSET="$BUILD_DIR/icon.iconset"
    mkdir -p "$ICONSET"
    sips -z 16 16 "$SCRIPT_DIR/icon.png" --out "$ICONSET/icon_16x16.png" 2>/dev/null || true
    sips -z 32 32 "$SCRIPT_DIR/icon.png" --out "$ICONSET/icon_16x16@2x.png" 2>/dev/null || true
    sips -z 32 32 "$SCRIPT_DIR/icon.png" --out "$ICONSET/icon_32x32.png" 2>/dev/null || true
    sips -z 64 64 "$SCRIPT_DIR/icon.png" --out "$ICONSET/icon_32x32@2x.png" 2>/dev/null || true
    sips -z 128 128 "$SCRIPT_DIR/icon.png" --out "$ICONSET/icon_128x128.png" 2>/dev/null || true
    sips -z 256 256 "$SCRIPT_DIR/icon.png" --out "$ICONSET/icon_128x128@2x.png" 2>/dev/null || true
    sips -z 256 256 "$SCRIPT_DIR/icon.png" --out "$ICONSET/icon_256x256.png" 2>/dev/null || true
    sips -z 512 512 "$SCRIPT_DIR/icon.png" --out "$ICONSET/icon_256x256@2x.png" 2>/dev/null || true
    iconutil -c icns "$ICONSET" -o "$RESOURCES/icon.icns" 2>/dev/null || true
    rm -rf "$ICONSET"
fi

# ── Create PkgInfo ──
echo "APPL????" > "$CONTENTS/PkgInfo"

# ── Codesign (ad-hoc) ──
if command -v codesign &>/dev/null; then
    codesign --force --deep --sign - "$APP_BUNDLE" 2>/dev/null || true
    echo "🔏 Ad-hoc code signature applied"
fi

# ── Package into DMG ──
DMG_PATH="$BUILD_DIR/$APP_NAME.dmg"
rm -f "$DMG_PATH"

if command -v create-dmg &>/dev/null; then
    create-dmg --volname "$APP_NAME" --window-pos 200 120 --window-size 600 400 \
        --icon-size 100 --app-drop-link 400 120 \
        "$DMG_PATH" "$APP_BUNDLE" 2>/dev/null || true
elif command -v hdiutil &>/dev/null; then
    # Create temp dir with Applications symlink
    DMG_TMP="$BUILD_DIR/.dmg-tmp"
    mkdir -p "$DMG_TMP"
    cp -R "$APP_BUNDLE" "$DMG_TMP/"
    ln -s /Applications "$DMG_TMP/Applications"
    hdiutil create -volname "$APP_NAME" -srcfolder "$DMG_TMP" \
        -ov -format UDZO "$DMG_PATH" 2>/dev/null || true
    rm -rf "$DMG_TMP"
fi

# ── Also create ZIP (more universal) ──
ZIP_PATH="$BUILD_DIR/TechExpert-Printer-Agent-macOS-Native.zip"
cd "$BUILD_DIR"
rm -f "TechExpert-Printer-Agent-macOS-Native.zip"
zip -r "$ZIP_PATH" "$APP_NAME.app" 2>/dev/null

echo ""
echo "✅ macOS App Bundle: $APP_BUNDLE"
if [ -f "$DMG_PATH" ]; then
    echo "📀 DMG: $DMG_PATH ($(du -h "$DMG_PATH" | cut -f1))"
fi
echo "📦 ZIP: $ZIP_PATH ($(du -h "$ZIP_PATH" | cut -f1))"
echo ""
echo "🚀 Done! User can open the .app or install from the .dmg"
