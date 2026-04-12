#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# OllaBridge Linux Installer
# After running this you can use `ollabridge` from any terminal,
# exactly like `uvicorn`, `fastapi`, or `pip` itself.
#
# Usage:
#   bash install.sh
# ═══════════════════════════════════════════════════════════════

set -euo pipefail

# ── Paths ──────────────────────────────────────────────────────
BIN_DIR="$HOME/.local/bin"
CONFIG_DIR="$HOME/.config/ollabridge"
DATA_DIR="$HOME/.local/share/ollabridge"
VENV_DIR="$DATA_DIR/venv"
SERVICE_DIR="$HOME/.config/systemd/user"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/worker"

# ── Colors ─────────────────────────────────────────────────────
R='\033[0;31m'; G='\033[0;32m'; C='\033[0;36m'; Y='\033[1;33m'; B='\033[1m'; N='\033[0m'

banner() {
    echo -e "${C}"
    echo '  ___  _ _       ____       _     _  '
    echo ' / _ \| | | __ _| __ ) _ __(_) __| | __ _  ___ '
    echo '| | | | | |/ _` |  _ \| '"'"'__| |/ _` |/ _` |/ _ \'
    echo '| |_| | | | (_| | |_) | |  | | (_| | (_| |  __/'
    echo ' \___/|_|_|\__,_|____/|_|  |_|\__,_|\__, |\___|'
    echo '                                     |___/      '
    echo -e "${N}${B}Linux Installer — v1.0.0${N}\n"
}

step() { echo -e "${C}▸${N} $1"; }
ok()   { echo -e "${G}  ✅ $1${N}"; }
warn() { echo -e "${Y}  ⚠  $1${N}"; }
err()  { echo -e "${R}  ❌ $1${N}"; exit 1; }

banner

# ── Preflight ──────────────────────────────────────────────────
step "Checking system requirements…"
command -v python3 &>/dev/null    || err "python3 not found. Install: sudo apt install python3 python3-venv"
python3 -m venv --help &>/dev/null || err "python3-venv missing: sudo apt install python3-venv"
command -v ollama &>/dev/null     || warn "ollama not found — install from https://ollama.ai before running the worker"
ok "Python 3 found: $(python3 --version)"

# ── Detect existing installation ──────────────────────────────
EXISTING=false
if [ -L "$BIN_DIR/ollabridge" ] || systemctl --user is-active ollabridge.service &>/dev/null; then
    EXISTING=true
fi

if [ "$EXISTING" = true ]; then
    echo -e "${Y}  Existing installation detected — this will upgrade it.${N}"
    echo -e "  ${B}Tip:${N} to remove instead, run: ${C}ollabridge uninstall${N}\n"
    systemctl --user stop ollabridge.service 2>/dev/null || true
fi

# ── Create directories ─────────────────────────────────────────────
step "Creating directories…"
mkdir -p "$BIN_DIR" "$CONFIG_DIR" "$DATA_DIR" "$SERVICE_DIR"
ok "Directories ready"

# ── Virtual environment ────────────────────────────────────────
step "Creating Python virtual environment…"
if [ ! -f "$VENV_DIR/bin/activate" ]; then
    python3 -m venv "$VENV_DIR"
fi
ok "Virtual environment at $VENV_DIR"

# ── Install / upgrade via pip ─────────────────────────────────
if [ "$EXISTING" = true ]; then
    step "Upgrading OllaBridge package…"
    "$VENV_DIR/bin/pip" install -q --upgrade "$SRC_DIR"
    ok "Package upgraded"
else
    step "Installing OllaBridge via pip…"
    "$VENV_DIR/bin/pip" install -q --upgrade pip
    "$VENV_DIR/bin/pip" install -q "$SRC_DIR"
    ok "Package installed"
fi

# ── Expose the command system-wide via symlink ────────────────
step "Linking 'ollabridge' command to $BIN_DIR…"
ln -sf "$VENV_DIR/bin/ollabridge" "$BIN_DIR/ollabridge"
ok "Command ready: ollabridge"

# Remind about PATH
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    warn "$BIN_DIR is not in PATH. Add to ~/.bashrc:"
    echo -e "     ${C}export PATH=\"\$HOME/.local/bin:\$PATH\"${N}"
fi

# ── Config ────────────────────────────────────────────────────
step "Checking configuration…"
if [ ! -f "$CONFIG_DIR/config.ini" ]; then
    echo -e "${Y}  No config found — running setup wizard…${N}"
    "$VENV_DIR/bin/python" -m ollabridge setup --config "$CONFIG_DIR/config.ini" 2>/dev/null || \
    "$VENV_DIR/bin/ollabridge" setup --config "$CONFIG_DIR/config.ini"
else
    ok "Config already exists at $CONFIG_DIR/config.ini"
fi

# ── Systemd user service (auto-start on login) ────────────────
step "Installing systemd user service…"

cat > "$SERVICE_DIR/ollabridge.service" << SERVICE
[Unit]
Description=OllaBridge — Local AI Worker for Shared Hosting
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=$BIN_DIR/ollabridge run --config $CONFIG_DIR/config.ini
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
StartLimitIntervalSec=300
StartLimitBurst=5

[Install]
WantedBy=default.target
SERVICE

systemctl --user daemon-reload
systemctl --user enable ollabridge.service
systemctl --user start  ollabridge.service
ok "Service installed, enabled, and started"

# ── Enable linger (stay running after logout) ─────────────────
step "Enabling linger (run without active login session)…"
if loginctl enable-linger "$USER" 2>/dev/null; then
    ok "Linger enabled — worker survives logout"
else
    warn "Could not enable linger. Run manually: sudo loginctl enable-linger $USER"
fi

# ── Done ──────────────────────────────────────────────────────
echo ""
echo -e "${G}${B}🚀 OllaBridge is installed and running!${N}"
echo ""
echo -e "  ${B}Usage (from any terminal):${N}"
echo -e "    ${C}ollabridge run${N}       Start the worker"
echo -e "    ${C}ollabridge setup${N}     Reconfigure"
echo -e "    ${C}ollabridge status${N}    Check connectivity"
echo -e "    ${C}ollabridge db stats${N}  View job history"
echo ""
echo -e "  ${B}Service management:${N}"
echo -e "    ${C}systemctl --user status  ollabridge${N}"
echo -e "    ${C}systemctl --user restart ollabridge${N}"
echo -e "    ${C}journalctl --user -u ollabridge -f${N}   (live logs)"
echo -e "    ${C}bash uninstall.sh${N}   Remove everything"
echo ""
echo -e "  ${B}Config file:${N} ${C}$CONFIG_DIR/config.ini${N}"
echo ""
