#!/bin/bash
# ===========================================================
# TechExpert Printer Agent — .pkg Installer (Free Option)
# Crea un instalador .pkg firmado ad-hoc con postinstall
# para distribución cero-terminal a clientes.
#
# Requiere: macOS con Xcode 15+ y Command Line Tools
# ===========================================================
set -e

APP_NAME="TechExpert TPV Printer"
APP_VERSION="2.0.0"
BUNDLE_ID="com.techexpert.printeragent"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_DIR="$BASE_DIR/mac-swift-app/TechExpertPrinterAgent"
PKG_DIR="$SCRIPT_DIR/pkg-work"
OUTPUT_DIR="$SCRIPT_DIR/output"
POSTINSTALL_SRC="$SCRIPT_DIR/scripts/postinstall"

echo ""
echo "╔═══════════════════════════════════════════════╗"
echo "║  TechExpert Printer Agent — .pkg Installer   ║"
echo "║  Versión $APP_VERSION                              ║"
echo "╚═══════════════════════════════════════════════╝"
echo ""

# ── 1. Limpiar ──
rm -rf "$PKG_DIR" "$OUTPUT_DIR"
mkdir -p "$PKG_DIR" "$OUTPUT_DIR"

# ── 2. Compilar .app desde Xcode ──
echo "📦 [1/4] Compilando .app con xcodebuild..."
cd "$PROJECT_DIR"

xcodebuild -project TechExpertPrinterAgent.xcodeproj \
  -scheme TechExpertPrinterAgent \
  -configuration Release \
  -derivedDataPath "$PKG_DIR/derived" \
  clean build \
  CODE_SIGN_IDENTITY="-" \
  CODE_SIGN_STYLE=Manual \
  CODE_SIGN_ALLOW_ENTITLEMENTS_MODIFICATION=NO \
  2>&1 | tail -5

# Find the built .app
BUILT_APP=$(find "$PKG_DIR/derived" -name "*.app" -type d 2>/dev/null | head -1)
if [ -z "$BUILT_APP" ]; then
  echo "❌ No se encontró el .app compilado"
  exit 1
fi
echo "   ✅ App compilada: $BUILT_APP"

# ── 3. Preparar payload ──
echo "📦 [2/4] Preparando payload para .pkg..."
PAYLOAD_DIR="$PKG_DIR/payload/Applications"
mkdir -p "$PAYLOAD_DIR"
cp -R "$BUILT_APP" "$PAYLOAD_DIR/$APP_NAME.app"
echo "   ✅ App copiada a $PAYLOAD_DIR/$APP_NAME.app"

# ── 4. Firmado ad-hoc + scripts ──
echo "📦 [3/4] Preparando scripts de postinstall..."

# Ad-hoc sign the app inside the payload
codesign --force --deep -s - "$PAYLOAD_DIR/$APP_NAME.app" 2>/dev/null || true
echo "   ✅ App firmada ad-hoc"

# Copy postinstall to scripts dir
mkdir -p "$PKG_DIR/scripts"
if [ -f "$POSTINSTALL_SRC" ]; then
  cp "$POSTINSTALL_SRC" "$PKG_DIR/scripts/postinstall"
  chmod +x "$PKG_DIR/scripts/postinstall"
  echo "   ✅ Script postinstall copiado"
else
  echo "⚠️  No se encontró postinstall — generando uno por defecto"
  cat > "$PKG_DIR/scripts/postinstall" << 'POSTINSTALL'
#!/bin/bash
APP="/Applications/TechExpert Printer Agent.app"
xattr -dr com.apple.quarantine "$APP" 2>/dev/null || true
xattr -cr "$APP" 2>/dev/null || true
codesign --force --deep -s - "$APP" 2>/dev/null || true
exit 0
POSTINSTALL
  chmod +x "$PKG_DIR/scripts/postinstall"
fi

# ── 5. Crear .pkg ──
echo "📦 [4/4] Creando .pkg..."
PKG_NAME="$APP_NAME-Installer.pkg"
PKG_PATH="$OUTPUT_DIR/$PKG_NAME"

pkgbuild \
  --root "$PKG_DIR/payload" \
  --identifier "$BUNDLE_ID" \
  --version "$APP_VERSION" \
  --install-location "/" \
  --scripts "$PKG_DIR/scripts" \
  "$PKG_PATH"

# ── 6. Resultados ──
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ ¡Listo!"
echo ""
echo "  📦 $PKG_PATH"
echo "  Tamaño: $(du -h "$PKG_PATH" | cut -f1)"
echo ""
echo "  📋 Distribuye este .pkg a tus clientes."
echo ""
echo "  ⚠️  Al ser firma ad-hoc, el primer cliente"
echo "     necesitará: Botón derecho > Abrir"
echo "     (solo la primera vez)."
echo ""
echo "  💡 Para evitar ese paso completamente,"
echo "     usa la opción oficial con Developer ID"
echo "     + notarización (./notarize-macos.sh)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── Limpieza ──
rm -rf "$PKG_DIR/payload" "$PKG_DIR/scripts" 2>/dev/null || true
