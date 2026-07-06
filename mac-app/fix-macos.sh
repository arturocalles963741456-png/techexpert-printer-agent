#!/bin/bash
# TechExpert Printer Agent — macOS Quick Fix
# Run this on your Mac after extracting the .app
# It ad-hoc signs the app so macOS Sonoma doesn't block it

APP_PATH="$1"
if [ -z "$APP_PATH" ]; then
    APP_PATH="/Applications/TechExpert TPV Printer.app"
fi

echo "🔧 Fixing $APP_PATH..."
echo ""

# Remove quarantine attribute
xattr -dr com.apple.quarantine "$APP_PATH" 2>/dev/null

# Ad-hoc sign the app bundle
codesign --force --deep --sign - "$APP_PATH" 2>&1

echo ""
echo "✅ Done! Try opening the app now."
echo "   If it still doesn't open, go to:"
echo "   System Settings → Privacy & Security → 'TechExpert was blocked...' → Allow Anyway"
