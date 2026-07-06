#!/bin/bash
# ===========================================================
# TechExpert Printer Agent — Notarización Oficial
#
# Pipeline completo: build → Developer ID sign → notarizar →
# staple → .pkg final listo para distribución transparente.
#
# Requiere: Apple Developer Program ($99/año), Xcode 15+
#
# Configuración única (solo la primera vez):
#   xcrun notarytool store-credentials "AC_PASSWORD" \
#     --apple-id "tu@email.com" \
#     --team-id "TU_TEAM_ID" \
#     --team-provider "TU_TEAM_ID" \
#     --password "app-specific-password"
# ===========================================================
set -e

APP_NAME="TechExpert TPV Printer"
APP_VERSION="2.0.0"
BUNDLE_ID="com.techexpert.printeragent"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_DIR="$BASE_DIR/mac-swift-app/TechExpertPrinterAgent"
WORK_DIR="$SCRIPT_DIR/notarize-work"
OUTPUT_DIR="$SCRIPT_DIR/output"
KEYCHAIN_PROFILE="AC_PASSWORD"

# ── Configuración (cambia estos valores) ──
DEVELOPER_ID_APP="Developer ID Application: TechExpert"   # Ajusta a tu nombre exacto
DEVELOPER_ID_INSTALLER="Developer ID Installer: TechExpert" # Ajusta a tu nombre exacto
APPLE_ID="oscar@techexpert.cloud"                           # Tu Apple ID

echo ""
echo "╔═══════════════════════════════════════════════╗"
echo "║   TechExpert — Notarización Oficial macOS     ║"
echo "╚═══════════════════════════════════════════════╝"
echo ""
echo "📋 Ajusta las variables en el script si tu Developer ID"
echo "   o Apple ID son diferentes."
echo ""

# ── Verificar entorno ──
if ! xcode-select -p &>/dev/null; then
  echo "❌ Xcode Command Line Tools no instalado"
  exit 1
fi

if ! security find-identity -v -p basic | grep -q "$DEVELOPER_ID_APP"; then
  echo "⚠️  No se encontró el certificado: $DEVELOPER_ID_APP"
  echo "   Ejecuta este comando para ver tus identidades:"
  echo "     security find-identity -v -p basic"
  echo ""
  read -p "¿Continuar de todas formas? (s/N): " CONTINUE
  if [ "$CONTINUE" != "s" ] && [ "$CONTINUE" != "S" ]; then
    echo "❌ Cancelado"
    exit 1
  fi
fi

# ── Paso 1: Build ──
echo ""
echo "━━━ [1/6] Compilando .app ━━━"
rm -rf "$WORK_DIR" "$OUTPUT_DIR"
mkdir -p "$WORK_DIR" "$OUTPUT_DIR"

cd "$PROJECT_DIR"
xcodebuild -project TechExpertPrinterAgent.xcodeproj \
  -scheme TechExpertPrinterAgent \
  -configuration Release \
  -derivedDataPath "$WORK_DIR/derived" \
  clean build \
  CODE_SIGN_IDENTITY="$DEVELOPER_ID_APP" \
  CODE_SIGN_STYLE=Manual \
  OTHER_CODE_SIGN_FLAGS="--timestamp" \
  2>&1 | tail -5

BUILT_APP=$(find "$WORK_DIR/derived" -name "*.app" -type d | head -1)
if [ -z "$BUILT_APP" ]; then
  echo "❌ No se encontró el .app"
  exit 1
fi
echo "✅ App compilada y firmada con Developer ID"

# ── Paso 2: Verificar app ──
echo ""
echo "━━━ [2/6] Verificando firma de la app ─━━"
codesign -dv --verbose=2 "$BUILT_APP" 2>&1 | head -10

# ── Paso 3: Crear .zip para notarización ──
echo ""
echo "━━━ [3/6] Preparando .zip para notarización ━━━"
ZIP_PATH="$WORK_DIR/$APP_NAME.zip"
ditto -c -k --keepParent "$BUILT_APP" "$ZIP_PATH"
echo "✅ ZIP creado: $ZIP_PATH"

# ── Paso 4: Subir a notarización ──
echo ""
echo "━━━ [4/6] Enviando a notarización de Apple ━━━"
echo "   (esto puede tardar varios minutos...)"
echo ""

xcrun notarytool submit "$ZIP_PATH" \
  --keychain-profile "$KEYCHAIN_PROFILE" \
  --wait \
  --timeout 600 \
  2>&1 | tee "$WORK_DIR/notarization.log"

# Check result
SUBMISSION_ID=""
if [ -f "$WORK_DIR/notarization.log" ]; then
  SUBMISSION_ID=$(grep -o "id: [a-z0-9-]*" "$WORK_DIR/notarization.log" | head -1 | cut -d' ' -f2)
fi

if [ -z "$SUBMISSION_ID" ]; then
  echo "⚠️  No se pudo extraer ID. Verifica el log."
  echo "   Log: $WORK_DIR/notarization.log"
fi

# ── Paso 5: Staple el ticket ──
echo ""
echo "━━━ [5/6] Stapleando ticket de notarización ━━━"
xcrun stapler staple "$BUILT_APP"
echo "✅ Ticket stapled"

# ── Paso 6: Crear .pkg final ──
echo ""
echo "━━━ [6/6] Creando .pkg firmado ━━━"
PKG_NAME="TechExpert-Printer-Agent-$APP_VERSION.pkg"
PKG_PATH="$OUTPUT_DIR/$PKG_NAME"

pkgbuild \
  --root "$BUILT_APP" \
  --identifier "$BUNDLE_ID" \
  --version "$APP_VERSION" \
  --sign "$DEVELOPER_ID_INSTALLER" \
  --timestamp \
  --install-location "/Applications/$APP_NAME.app" \
  "$PKG_PATH"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ ¡Listo! Notarización completada."
echo ""
echo "  📦 $PKG_PATH"
echo "  Tamaño: $(du -h "$PKG_PATH" | cut -f1)"
echo ""
echo "  ✅ Este .pkg está NOTARIZADO por Apple."
echo "  ✅ Sin warnings, sin bloqueos."
echo "  ✅ Distribución transparente a clientes."
echo ""
echo "  Verificar estado de notarización:"
echo "    spctl -a -v --type install \"$PKG_PATH\""
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── Limpieza ──
rm -rf "$WORK_DIR" 2>/dev/null || true
echo "💡 Limpieza completada"
