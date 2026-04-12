#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# OllaBridge Build Script — Linux & macOS
# Creates a single self-contained binary using PyInstaller.
#
# Requirements:
#   pip install pyinstaller
#
# Output:
#   Linux : dist/ollabridge          (ELF binary)
#   macOS : dist/ollabridge          (Mach-O binary)
# ═══════════════════════════════════════════════════════════════

set -euo pipefail
cd "$(dirname "$0")"   # always run from worker/ directory

G='\033[0;32m'; C='\033[0;36m'; R='\033[0;31m'; N='\033[0m'

echo -e "${C}▸${N} Installing build deps…"
pip install -q pyinstaller pyinstaller-hooks-contrib requests rich ollama

echo -e "${C}▸${N} Building binary…"
pyinstaller ollabridge.spec --distpath ../dist --workpath ../build_tmp --clean

BINARY="../dist/ollabridge"
if [ -f "$BINARY" ]; then
    SIZE=$(du -sh "$BINARY" | cut -f1)
    echo -e "${G}✅ Build complete: dist/ollabridge (${SIZE})${N}"
    echo ""
    echo "  Run directly:  ./dist/ollabridge run --site-url https://yoursite.com --secret-key KEY"
    echo "  Install:       bash install.sh"
else
    echo -e "${R}❌ Build failed — check output above.${N}"
    exit 1
fi

# Cleanup temp build files
rm -rf ../build_tmp
