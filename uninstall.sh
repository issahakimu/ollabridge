#!/usr/bin/env bash
# OllaBridge Uninstaller — removes everything install.sh put in place

set -euo pipefail

G='\033[0;32m'; R='\033[0;31m'; C='\033[0;36m'; N='\033[0m'
echo -e "${C}▸${N} Stopping and removing OllaBridge…\n"

# Stop and disable service
if systemctl --user is-active ollabridge.service &>/dev/null; then
    systemctl --user stop    ollabridge.service && echo -e "${G}✅ Service stopped${N}"
fi
if systemctl --user is-enabled ollabridge.service &>/dev/null; then
    systemctl --user disable ollabridge.service && echo -e "${G}✅ Service disabled${N}"
fi

# Remove files
rm -f  "$HOME/.config/systemd/user/ollabridge.service"
rm -f  "$HOME/.local/bin/ollabridge"
rm -rf "$HOME/.local/share/ollabridge"
systemctl --user daemon-reload

echo -e "${G}✅ OllaBridge uninstalled.${N}"
echo -e "  Config kept at: ${C}$HOME/.config/ollabridge/config.ini${N}"
echo -e "  Remove it too:  ${R}rm -rf \$HOME/.config/ollabridge${N}"
