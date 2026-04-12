# OllaBridge

**Connect your local Ollama AI to any shared-hosting PHP website — no static IP, no relay, no cloud.**

**Developer:** Issa Hakimu

OllaBridge is a headless Python worker that runs on your local machine and bridges it to your web server using a simple polling queue. Your website submits AI jobs; the worker picks them up, runs them through Ollama locally, and posts results back — all initiated from your side, so firewalls and NAT are never a problem.

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

```bash
git clone https://github.com/you/ollabridge.git
cd ollabridge
bash install.sh
```

That's it. `ollabridge` is now a system command — just like `uvicorn` or `pip`.

**Requirements:** Python 3.10+, `python3-venv`, [Ollama](https://ollama.ai)

---

## Quick start

```bash
# First time — run the setup wizard
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

ollabridge setup                      # Interactive setup wizard
ollabridge status                     # Check Ollama + server health

ollabridge db stats                   # View job history table
ollabridge db stats --limit 100       # Show more records
ollabridge db clear                   # Delete all history (asks confirmation)
ollabridge db clear --yes             # Delete without asking
ollabridge db export                  # Export to dated .sql file
ollabridge db export --output bak.sql # Export to specific file
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

## Server setup (Example Integration)

The `server/` folder provides a reference PHP implementation. It is intended as an **example** to show you how to integrate OllaBridge into your existing project. You can adapt these scripts to any language (Node.js, Python, Ruby, etc.) as long as the API endpoints match.

Upload everything from the `server/` folder to `public_html/ollabridge/` on your host:

```
public_html/
└── ollabridge/
    ├── config.php       ← edit DB credentials + secret key
    ├── db.php
    ├── demo.html        ← optional AI chat UI
    ├── get_jobs.php
    ├── get_result.php
    ├── submit_job.php
    └── update_job.php
    └── assets/
        └── logo.png
```

1. Create a MySQL database via cPanel
2. Import `server/schema.sql` via phpMyAdmin
3. Edit `config.php` with your DB credentials and `SECRET_KEY`
4. Upload the files
5. Run `ollabridge setup` locally — point `site_url` at your domain
6. Run `ollabridge run` — jobs submitted via `demo.html` will now work

> **The `SECRET_KEY` in `config.php` must exactly match the one in your local `config.ini`.**

See [DEPLOY.md](DEPLOY.md) for the full step-by-step checklist.

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

## Uninstall

```bash
bash uninstall.sh
```

---

## Project layout

```
ollabridge/
├── worker/                 Python worker (installed via pip)
│   ├── ollabridge.py       CLI entry point
│   ├── pyproject.toml      Package definition
│   ├── config/
│   │   ├── defaults.py     Default values
│   │   └── loader.py       Config file + env + CLI merging
│   └── modules/
│       ├── db.py           SQLite job deduplication + history
│       ├── executor.py     Runs jobs against Ollama
│       ├── media_handler.py Image download + base64 encoding
│       ├── model_manager.py Auto-pull + fallback logic
│       ├── ollama_manager.py Ollama health check + auto-start
│       └── poller.py       Main polling loop
├── server/                 PHP files → upload to shared hosting
│   ├── config.php
│   ├── db.php
│   ├── schema.sql
│   ├── submit_job.php
│   ├── get_jobs.php
│   ├── update_job.php
│   ├── get_result.php
│   ├── demo.html
│   └── assets/logo.png
├── assets/                 Brand assets
│   └── logo.png
├── install.sh              Linux installer
├── uninstall.sh            Uninstaller
├── DEPLOY.md               Shared hosting deployment checklist
└── README.md               This file
```

---

## Building a standalone binary

To distribute OllaBridge as a single binary (no Python required on the target machine):

```bash
pip install pyinstaller
cd worker
bash build.sh           # → dist/ollabridge
```

Copy `dist/ollabridge` to any Linux machine — no Python, no pip, no venv needed.
