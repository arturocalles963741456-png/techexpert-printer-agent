#!/bin/bash
# TechExpert Printer Agent — macOS Installer Helper
# Run after extracting the app: bash install-macos.sh

APP_NAME="TechExpert Printer Agent.app"
LAUNCH_AGENT_DIR="$HOME/Library/LaunchAgents"
PLIST_FILE="$LAUNCH_AGENT_DIR/com.techexpert.printer-agent.plist"

echo ""
echo "╔══════════════════════════════════════╗"
echo "║  TechExpert Printer Agent           ║"
echo "║  Instalación para macOS             ║"
echo "╚══════════════════════════════════════╝"
echo ""

# Check for .app
if [ ! -d "$APP_NAME" ]; then
    echo "❌ No se encuentra '$APP_NAME' en este directorio."
    echo "   Extrae el ZIP primero y ejecuta este script desde la carpeta."
    exit 1
fi

# Move to Applications
if [ -d "/Applications/$APP_NAME" ]; then
    echo "⚠️  Ya existe una instalación previa. Sobrescribiendo..."
    rm -rf "/Applications/$APP_NAME"
fi

echo "📦 Copiando a /Applications/..."
cp -R "$APP_NAME" "/Applications/$APP_NAME"
echo "✅ Instalado en /Applications/$APP_NAME"

# Create LaunchAgent for autostart
echo ""
echo "🔧 Configurando inicio automático..."
mkdir -p "$LAUNCH_AGENT_DIR"

cat > "$PLIST_FILE" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.techexpert.printer-agent</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Applications/$APP_NAME/Contents/MacOS/tray-launcher</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardOutPath</key>
    <string>$HOME/Library/Logs/techexpert-agent.log</string>
    <key>StandardErrorPath</key>
    <string>$HOME/Library/Logs/techexpert-agent.log</string>
</dict>
</plist>
EOF

launchctl load "$PLIST_FILE" 2>/dev/null || true
echo "✅ Auto-arranque configurado (LaunchAgent)"

# Open the app
echo ""
echo "🚀 Abriendo TechExpert Printer Agent..."
open "/Applications/$APP_NAME"

echo ""
echo "╔══════════════════════════════════════╗"
echo "║  ✅ Instalación completada           ║"
echo "║                                     ║"
echo "║  1. Abre el panel de Administración  ║"
echo "║     → Impresora                      ║"
echo "║  2. Copia el TOKEN                   ║"
echo "║  3. Pégalo en el config.json del app ║"
echo "║  4. El icono aparecerá en la barra   ║"
echo "╚══════════════════════════════════════╝"
echo ""
