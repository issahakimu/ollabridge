"""
OllaBridge Default Configuration Values

Priority order for config resolution:
  CLI Args  >  Environment Variables  >  config.ini  >  These Defaults
"""

DEFAULTS = {
    # --- Required (no default — must be set by user) ---
    "site_url":            None,
    "secret_key":          None,

    # --- Ollama ---
    "ollama_host":         "http://localhost:11434",
    "default_model":       "gemma4:e2b",
    "fallback_model":      "llama3.2",
    "auto_start_ollama":   True,   # Try to start ollama serve if not running
    "auto_pull_model":     True,   # Auto-pull model if not installed

    # --- Polling ---
    "poll_interval":       5,      # seconds between polls
    "long_poll_timeout":   20,     # seconds server waits before returning empty list
    "job_limit":           5,      # max jobs per poll response

    # --- Storage ---
    # Why SQLite? It's built into Python (zero extra install), persists history
    # across restarts (unlike in-memory dicts), handles single-worker perfectly,
    # and is far more reliable than a plain JSON file for concurrent reads.
    "db_path":             "local_jobs.db",

    # --- Logging ---
    "log_level":           "INFO",   # DEBUG | INFO | WARNING | ERROR
}

# Environment variable names (prefix: OLLABRIDGE_)
ENV_PREFIX = "OLLABRIDGE_"
ENV_MAP = {
    "site_url":           f"{ENV_PREFIX}SITE_URL",
    "secret_key":         f"{ENV_PREFIX}SECRET_KEY",
    "ollama_host":        f"{ENV_PREFIX}OLLAMA_HOST",
    "default_model":      f"{ENV_PREFIX}DEFAULT_MODEL",
    "fallback_model":     f"{ENV_PREFIX}FALLBACK_MODEL",
    "auto_start_ollama":  f"{ENV_PREFIX}AUTO_START_OLLAMA",
    "auto_pull_model":    f"{ENV_PREFIX}AUTO_PULL_MODEL",
    "poll_interval":      f"{ENV_PREFIX}POLL_INTERVAL",
    "job_limit":          f"{ENV_PREFIX}JOB_LIMIT",
    "db_path":            f"{ENV_PREFIX}DB_PATH",
    "log_level":          f"{ENV_PREFIX}LOG_LEVEL",
}
