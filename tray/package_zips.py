#!/usr/bin/env python3
"""Package printer agent builds into ZIPs"""
import os, zipfile, shutil

BASE = '/home/battle/sattpv-clone/printer-agent/builds'
SRC = '/home/battle/sattpv-clone/printer-agent'

# Clean old zips
for f in os.listdir(BASE):
    if f.endswith('.zip'):
        os.remove(os.path.join(BASE, f))

def package(name, binary, extra=[]):
    tmp = os.path.join(BASE, '_tmp')
    if os.path.exists(tmp):
        shutil.rmtree(tmp)
    os.makedirs(tmp)
    
    # Copy binary
    src = os.path.join(BASE, binary)
    if binary.endswith('.exe'):
        dst = os.path.join(tmp, 'TechExpert-Printer-Agent.exe')
    else:
        dst = os.path.join(tmp, 'TechExpert-Printer-Agent')
    shutil.copy2(src, dst)
    os.chmod(dst, 0o755)
    
    # Copy support files
    for f in ['config.json', 'README.md']:
        s = os.path.join(SRC, f)
        if os.path.exists(s):
            shutil.copy2(s, tmp)
    
    # Copy tray files
    td = os.path.join(tmp, 'tray')
    os.makedirs(td, exist_ok=True)
    for f in ['tray-launcher.py', 'icon.svg', 'icon.png']:
        s = os.path.join(SRC, 'tray', f)
        if os.path.exists(s):
            shutil.copy2(s, td)
    
    # Extra files
    for f in extra:
        s = os.path.join(SRC, 'tray', f)
        if os.path.exists(s):
            shutil.copy2(s, tmp)
    
    # Create zip
    zpath = os.path.join(BASE, f'{name}.zip')
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(tmp):
            for f in files:
                fp = os.path.join(root, f)
                arcname = os.path.relpath(fp, tmp)
                zf.write(fp, arcname)
    
    shutil.rmtree(tmp)
    size_mb = os.path.getsize(zpath) / 1024 / 1024
    print(f'{name}.zip: {size_mb:.1f} MB')
    return zpath

package('TechExpert-Printer-Agent-Linux', 'agent-linux-x64', ['install-macos.sh'])
package('TechExpert-Printer-Agent-Windows', 'agent-win-x64.exe')
package('TechExpert-Printer-Agent-macOS', 'agent-macos-x64', ['install-macos.sh'])
package('TechExpert-Printer-Agent-macOS-ARM', 'agent-macos-arm64', ['install-macos.sh'])

# Also source zip
sz = os.path.join(BASE, 'TechExpert-Printer-Agent-source.zip')
with zipfile.ZipFile(sz, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(SRC):
        skip_dirs = {'node_modules', 'builds', 'pkg', '__pycache__'}
        parts = root.replace(SRC, '').lstrip('/').split('/')
        if any(d in skip_dirs for d in parts):
            continue
        for f in files:
            fp = os.path.join(root, f)
            arcname = os.path.relpath(fp, SRC)
            zf.write(fp, arcname)
print(f'Source: {os.path.getsize(sz)/1024:.1f} KB')

# List all
print('\nAll packages:')
for f in sorted(os.listdir(BASE)):
    if f.endswith('.zip'):
        print(f'  {f}: {os.path.getsize(os.path.join(BASE, f))/1024/1024:.1f} MB')
