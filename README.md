# OllaBridge

> **Connect your local Ollama AI to any shared-hosting PHP website — no static IP, no relay, no cloud.**

[![Release](https://img.shields.io/github/v/release/issahakimu/ollabridge)](https://github.com/issahakimu/ollabridge/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Linux-lightgrey)](https://github.com/issahakimu/ollabridge)

**Developed by [Issa Hakimu](https://github.com/issahakimu)**

---

OllaBridge is a headless Python worker that runs on your local machine and bridges it to your web server using a simple polling queue. Your website submits AI jobs; the worker picks them up, runs them through [Ollama](https://ollama.ai) locally, and posts results back — all initiated from your side, so firewalls and NAT are never a problem.

The project ships with a **reference PHP server implementation** (in `server/`) to show you how the integration works. You are free to write your own integration in any language — the protocol is just HTTP + JSON.

---

## How it works

```
Browser → submit_job.php → MySQL queue
                                ↑
             OllaBridge polls ──┘
                    ↓
              Ollama (local)
                    ↓
         update_job.php → MySQL result
                                ↓
             Browser polls get_result.php
```

---

## Installation (Linux)

### Option A — From source (recommended for development)

```bash
git clone https://github.com/issahakimu/ollabridge.git
cd ollabridge
bash install.sh
```

### Option B — Standalone binary (no Python required)

Download the latest pre-built binary from [Releases](https://github.com/issahakimu/ollabridge/releases):

```bash
# Download
curl -L https://github.com/issahakimu/ollabridge/releases/latest/download/ollabridge-linux-x86_64 \
     -o ~/.local/bin/ollabridge
chmod +x ~/.local/bin/ollabridge

# First-time setup
ollabridge setup
```

**Requirements (source install only):** Python 3.10+, `python3-venv`, [Ollama](https://ollama.ai)

---

## Quick start

```bash
# First time — run the interactive setup wizard
ollabridge setup

# Start the worker
ollabridge run

# Check Ollama + server connectivity
ollabridge status
```

The worker auto-starts on login via **systemd** — you don't need to run it manually every time.

---

## Commands

```bash
ollabridge run                        # Start the AI worker
ollabridge run --site-url URL \       # Override config on the fly
               --secret-key KEY \
               --model gemma4:e2b

ollabridge setup                      # Interactive setup wizard (model picker, URL check)
ollabridge status                     # Check Ollama + server health
ollabridge update                     # Pull latest code and restart service
ollabridge uninstall                  # Remove OllaBridge from this system

ollabridge db stats                   # View job history in a rich table
ollabridge db stats --limit 100       # Show more records
ollabridge db clear                   # Delete all history (asks confirmation)
ollabridge db clear --yes             # Delete without asking
ollabridge db export                  # Export to a dated .sql file
ollabridge db export --output bak.sql # Export to a specific file
```

---

## Configuration

Config is stored at `~/.config/ollabridge/config.ini`:

```ini
[ollabridge]
site_url       = https://yoursite.com
secret_key     = your-secret-key-here
ollama_host    = http://localhost:11434
default_model  = gemma4:e2b
fallback_model = llama3.2
poll_interval  = 5
auto_start_ollama = true
auto_pull_model   = true
db_path        = local_jobs.db
log_level      = INFO
```

All settings can also be passed as CLI flags or environment variables:

| Env Variable | CLI Flag | Description |
|---|---|---|
| `OLLABRIDGE_SITE_URL` | `--site-url` | Your shared hosting URL |
| `OLLABRIDGE_SECRET_KEY` | `--secret-key` | Authentication key |
| `OLLABRIDGE_DEFAULT_MODEL` | `--model` | Primary Ollama model |
| `OLLABRIDGE_FALLBACK_MODEL` | `--fallback-model` | Fallback if primary missing |
| `OLLABRIDGE_OLLAMA_HOST` | `--ollama-host` | Ollama API address |
| `OLLABRIDGE_POLL_INTERVAL` | `--interval` | Seconds between polls |
| `OLLABRIDGE_LOG_LEVEL` | `--log-level` | DEBUG / INFO / WARNING |

---

## Server Integration (Reference Implementation)

The `server/` folder contains a **reference PHP implementation** to help you understand the integration protocol. It is intended as a starting point or example — not a production requirement.

**You can integrate OllaBridge with any web stack** (Node.js, Python/Django, Ruby, etc.) as long as you implement these three endpoints:

| Endpoint | Method | Description |
|---|---|---|
| `GET /get_jobs.php` | GET | Worker polls this for pending jobs |
| `POST /update_job.php` | POST | Worker posts AI result back |
| `POST /submit_job.php` | POST | Your frontend submits a new AI job |

All requests are authenticated using a shared `X-OllaBridge-Key` header.

### Quick deploy (PHP / shared hosting)

Upload everything from `server/` to `public_html/ollabridge/` on your host:

```
public_html/
└── ollabridge/
    ├── config.php       ← edit DB credentials + secret key
    ├── schema.sql       ← import via phpMyAdmin
    ├── demo.html        ← optional AI chat demo UI
    └── *.php
```

> **The `SECRET_KEY` in `config.php` must exactly match the one in your local `config.ini`.**

See [DEPLOY.md](DEPLOY.md) for the full deployment checklist.

---

## Service management

```bash
systemctl --user status  ollabridge    # Is it running?
systemctl --user start   ollabridge    # Start
systemctl --user stop    ollabridge    # Stop
systemctl --user restart ollabridge    # Restart (e.g. after config change)
journalctl --user -u ollabridge -f     # Live logs
```

---

## Building the standalone binary

```bash
cd worker
bash build.sh
# → dist/ollabridge  (single self-contained ELF binary)
```

No Python required on the target machine. Copy `dist/ollabridge` anywhere.

---

## Uninstall

```bash
# Interactive (recommended — lets you keep your config)
ollabridge uninstall

# Or full removal via script
bash uninstall.sh
```

---

## Project layout

```
ollabridge/
├── worker/                 Python worker (pip-installable)
│   ├── ollabridge.py       Entry point — all CLI commands
│   ├── pyproject.toml      Package definition
│   ├── build.sh            PyInstaller binary builder
│   ├── config/
│   │   ├── defaults.py     Default values
│   │   └── loader.py       Config merging (file + env + CLI)
│   └── modules/
│       ├── db.py           SQLite job deduplication + history
│       ├── executor.py     Runs jobs against Ollama
│       ├── media_handler.py Image handling + base64 encoding
│       ├── model_manager.py Auto-pull + fallback logic
│       ├── ollama_manager.py Health check + auto-start
│       └── poller.py       Main polling loop
├── server/                 Reference PHP integration example
│   ├── config.php          ← configure this
│   ├── schema.sql          MySQL schema
│   ├── demo.html           AI chat demo UI
│   └── *.php               Job queue endpoints
├── assets/
│   └── logo.png
├── install.sh              Linux installer
├── uninstall.sh            Uninstaller
├── DEPLOY.md               Shared hosting deployment checklist
└── README.md               This file
```

---

## Author

**Issa Hakimu** — [github.com/issahakimu](https://github.com/issahakimu)

---

## License

MIT — free to use, modify, and distribute.
