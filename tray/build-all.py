#!/usr/bin/env python3
"""
TechExpert TPV — Printer Agent Builder
Builds platform-specific packages with pkg and bundles the tray app.
"""

import os
import sys
import subprocess
import shutil
import json
import zipfile
import tarfile
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # printer-agent/
AGENT_JS = BASE_DIR / 'agent.js'
CONFIG_JSON = BASE_DIR / 'config.json'
README = BASE_DIR / 'README.md'
TRAY_DIR = BASE_DIR / 'tray'
ICON_SVG = TRAY_DIR / 'icon.svg'
ICON_PNG = TRAY_DIR / 'icon.png'
BUILDS_DIR = BASE_DIR / 'builds'

# Platform targets for pkg
TARGETS = {
    'linux-x64': {'pkg': 'node18-linux-x64', 'ext': '', 'name': 'TechExpert-Printer-Agent-Linux'},
    'win-x64':   {'pkg': 'node18-win-x64',   'ext': '.exe', 'name': 'TechExpert-Printer-Agent-Windows'},
    'macos-x64': {'pkg': 'node18-macos-x64',  'ext': '', 'name': 'TechExpert-Printer-Agent-macOS'},
    'macos-arm': {'pkg': 'node18-macos-arm64','ext': '', 'name': 'TechExpert-Printer-Agent-macOS-ARM'},
}

def ensure_dir(d):
    os.makedirs(d, exist_ok=True)

def build_pkg(target):
    """Build binary with pkg for given target"""
    pkg_target = TARGETS[target]['pkg']
    print(f"\n🔨 Building {target} ({pkg_target})...")

    result = subprocess.run(
        ['npx', 'pkg', str(AGENT_JS), '--targets', pkg_target, '--output',
         str(BUILDS_DIR / f'agent-{target}'), '--public'],
        cwd=str(BASE_DIR),
        capture_output=True, text=True, timeout=120
    )

    if result.returncode != 0:
        print(f"❌ Build failed: {result.stderr}")
        return False

    binary_name = f'agent-{target}'
    binary_path = BUILDS_DIR / binary_name
    if not binary_path.exists():
        binary_path = BUILDS_DIR / (binary_name + TARGETS[target]['ext'])

    print(f"✅ Built: {binary_path}")
    return binary_path

def build_app_bundle(binary_path, target):
    """Create macOS .app bundle"""
    if not target.startswith('macos'):
        return binary_path

    app_name = f"TechExpert Printer Agent.app"
    app_dir = BUILDS_DIR / app_name
    contents_dir = app_dir / "Contents"
    macos_dir = contents_dir / "MacOS"
    resources_dir = contents_dir / "Resources"

    ensure_dir(macos_dir)
    ensure_dir(resources_dir)

    # Info.plist
    plist = {
        "CFBundleName": "TechExpert Printer Agent",
        "CFBundleDisplayName": "TechExpert Printer Agent",
        "CFBundleIdentifier": "com.techexpert.printer-agent",
        "CFBundleVersion": "2.0.0",
        "CFBundleShortVersionString": "2.0.0",
        "CFBundleExecutable": "agent-launcher",
        "CFBundleIconFile": "icon",
        "CFBundlePackageType": "APPL",
        "LSUIElement": "1",
        "NSHighResolutionCapable": "True",
    }

    with open(contents_dir / 'Info.plist', 'w') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n')
        f.write('<plist version="1.0">\n<dict>\n')
        for k, v in plist.items():
            f.write(f'    <key>{k}</key>\n')
            if isinstance(v, bool):
                f.write(f'    <{"true" if v else "false"}/>\n')
            elif isinstance(v, str):
                f.write(f'    <string>{v}</string>\n')
            elif isinstance(v, int):
                f.write(f'    <integer>{v}</integer>\n')
        f.write('</dict>\n</plist>\n')

    # Create launcher script
    launcher = macos_dir / 'agent-launcher'
    with open(launcher, 'w') as f:
        f.write('#!/bin/bash\n')
        f.write('DIR="$(cd "$(dirname "$0")/.." && pwd)"\n')
        f.write(f'exec "$DIR/MacOS/agent" --no-tunnel 2>&1\n')
    os.chmod(launcher, 0o755)

    # Copy binary
    agent_bin = macos_dir / 'agent'
    shutil.copy2(binary_path, agent_bin)
    os.chmod(agent_bin, 0o755)

    # Copy config
    if CONFIG_JSON.exists():
        shutil.copy2(CONFIG_JSON, resources_dir / 'config.json')

    # Create tray launcher
    tray_script = macos_dir / 'tray-launcher'
    shutil.copy2(TRAY_DIR / 'tray-launcher.py', macos_dir / 'tray-launcher.py')
    with open(tray_script, 'w') as f:
        f.write('#!/bin/bash\n')
        f.write(f'DIR="$(cd "$(dirname "$0")/.." && pwd)"\n')
        f.write(f'exec /usr/bin/python3 "$DIR/MacOS/tray-launcher.py" --tray 2>&1\n')
    os.chmod(tray_script, 0o755)

    # Generate icon (.icns for macOS)
    try:
        icns_path = resources_dir / 'icon.icns'
        # Convert PNG to ICNS using Python
        img_path = str(ICON_PNG) if ICON_PNG.exists() else None
        if img_path:
            import struct
            import zlib
            # Read PNG
            with open(img_path, 'rb') as f:
                png_data = f.read()
            # Create iconset folder first (Apple way)
            iconset_dir = BUILDS_DIR / 'icon.iconset'
            ensure_dir(iconset_dir)
            sizes = [(16, 'icon_16x16'), (32, 'icon_16x16@2x'), (32, 'icon_32x32'),
                     (64, 'icon_32x32@2x'), (128, 'icon_128x128'), (256, 'icon_128x128@2x'),
                     (256, 'icon_256x256'), (512, 'icon_256x256@2x'), (512, 'icon_512x512')]

            for w, name in sizes:
                dst = iconset_dir / f'{name}.png'
                # For now, copy original (assumes PNG is 256x256 minimum)
                if w <= 256:
                    shutil.copy2(img_path, dst)

            # Try iconutil (macOS only)
            subprocess.run(['iconutil', '-c', 'icns', str(iconset_dir), '-o', str(icns_path)],
                           capture_output=True, timeout=30)

            if icns_path.exists():
                print(f"✅ Icon: {icns_path}")
    except Exception as e:
        print(f"⚠️ Icon generation skipped: {e}")

    print(f"✅ App bundle: {app_dir}")
    return app_dir

def create_archive(source_path, target):
    """Create zip/tar.gz archive"""
    info = TARGETS[target]
    archive_stem = info['name']
    build_dir = BUILDS_DIR / '_archive'
    dest_dir = build_dir / info['name']

    # Clean and prepare
    if build_dir.exists():
        shutil.rmtree(build_dir)
    ensure_dir(dest_dir)

    if isinstance(source_path, Path) and source_path.is_dir():
        # .app bundle
        shutil.copytree(source_path, dest_dir / source_path.name)
    else:
        # Binary file
        if source_path:
            shutil.copy2(source_path, dest_dir / (source_path.name))
        # Copy tray launcher
        if TRAY_DIR.exists():
            tray_dest = dest_dir / 'tray'
            ensure_dir(tray_dest)
            for f in ['tray-launcher.py', 'icon.svg', 'icon.png']:
                src = TRAY_DIR / f
                if src.exists():
                    shutil.copy2(src, tray_dest / f)

    # Copy README
    if README.exists():
        shutil.copy2(README, dest_dir / 'README.md')

    # Copy default config
    if CONFIG_JSON.exists():
        shutil.copy2(CONFIG_JSON, dest_dir / 'config.json')

    # Create installer instructions
    instructions = dest_dir / 'INSTRUCCIONES.txt'
    with open(instructions, 'w') as f:
        f.write("""
╔══════════════════════════════════════════╗
║  TechExpert TPV — Printer Agent          ║
║  Manual de instalación rápida            ║
╚══════════════════════════════════════════╝

1. Copia el TOKEN desde el panel de Administración → Impresora
2. Abre config.json y pega el token:
   { "token": "tu-token-aquí", "tunnel_url": "wss://sattpv.techexpert.cloud/tunnel/agent" }
3. Ejecuta el agente:
   - Linux:   ./agent  (o ./TechExpert-Printer-Agent)
   - Windows: haz doble clic en agent.exe
   - macOS:   abre "TechExpert Printer Agent.app"

Para bandeja del sistema (tray):
   - Linux:   python3 tray/tray-launcher.py --tray
   - macOS:   ejecuta el script tray-launcher dentro del .app
   - Windows: python tray/tray-launcher.py --tray

Auto-arranque:
   - Desde el menú del tray: "Iniciar con el sistema"
   - O manual: ejecuta el agente con --headless

Más info: README.md
""")

    # Create archive
    archive_name = f'{archive_stem}.zip'
    archive_path = BUILDS_DIR / archive_name

    if archive_path.exists():
        os.remove(archive_path)

    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(build_dir):
            for f in files:
                file_path = os.path.join(root, f)
                arcname = os.path.relpath(file_path, build_dir)
                zf.write(file_path, arcname)

    # Cleanup
    shutil.rmtree(build_dir)

    print(f"📦 Package: {archive_path} ({os.path.getsize(archive_path) / 1024 / 1024:.1f} MB)")
    return archive_path

def build_all():
    ensure_dir(BUILDS_DIR)

    # Generate PNG icon first
    print("\n🎨 Generating icon...")
    subprocess.run([sys.executable, 'tray-launcher.py', '--gen-icon'],
                   cwd=str(TRAY_DIR), capture_output=True)

    archives = []

    for target in TARGETS:
        print(f"\n{'='*60}")
        print(f"Building {target}...")
        print('='*60)

        binary = build_pkg(target)
        if not binary:
            print(f"⚠️ Skipping {target}")
            continue

        if target.startswith('macos'):
            bundle = build_app_bundle(binary, target)
            archive = create_archive(bundle, target)
        else:
            archive = create_archive(binary, target)

        if archive:
            archives.append(archive)

    # Also create source package
    source_zip = BUILDS_DIR / 'TechExpert-Printer-Agent-source.zip'
    with zipfile.ZipFile(source_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(BASE_DIR):
            # Skip node_modules, builds, pkg
            if 'node_modules' in root or 'builds' in root or 'pkg' in root or '__pycache__' in root:
                continue
            for f in files:
                file_path = os.path.join(root, f)
                arcname = os.path.relpath(file_path, BASE_DIR)
                zf.write(file_path, arcname)
    print(f"\n📦 Source: {source_zip} ({os.path.getsize(source_zip)/1024:.1f} KB)")

    print(f"\n{'='*60}")
    print("✅ BUILD COMPLETE")
    print('='*60)
    for a in archives:
        size_mb = os.path.getsize(a) / 1024 / 1024
        print(f"  {a.name}: {size_mb:.1f} MB")

if __name__ == '__main__':
    build_all()
