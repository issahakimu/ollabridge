"""
Ollama service lifecycle manager.

Startup behaviour:
  1. Ping localhost:11434 — if it responds, we are done.
  2. If not running and auto_start=True → run `ollama serve` in background.
  3. Wait up to STARTUP_TIMEOUT seconds for it to come up.
  4. If still not up → return False (caller will exit with a clear error).
"""
import logging
import subprocess
import time

import requests

logger = logging.getLogger(__name__)

STARTUP_TIMEOUT = 20   # seconds to wait for `ollama serve` to become ready
PING_INTERVAL   = 1    # seconds between readiness checks


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def is_running(ollama_host: str) -> bool:
    """Return True if the Ollama API is reachable and healthy."""
    try:
        r = requests.get(f"{ollama_host}/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def start_ollama() -> bool:
    """
    Attempt to launch `ollama serve` as a detached background process.
    Returns True if the command launched (not necessarily ready yet).
    """
    logger.info("Starting Ollama service in background…")
    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,   # detach so it survives the parent
        )
        return True
    except FileNotFoundError:
        logger.error("'ollama' binary not found. Install Ollama: https://ollama.ai")
        return False
    except Exception as exc:
        logger.error("Failed to start Ollama: %s", exc)
        return False


def ensure_running(ollama_host: str, auto_start: bool = True) -> bool:
    """
    Guarantee Ollama is running before the worker loop begins.

    Args:
        ollama_host:  Base URL of the Ollama API.
        auto_start:   If True, try to launch `ollama serve` automatically.

    Returns:
        True  — Ollama is ready.
        False — Ollama is not reachable and could not be started.
    """
    if is_running(ollama_host):
        return True

    if not auto_start:
        logger.error(
            "Ollama is not running. Start it manually with: ollama serve\n"
            "Or allow auto-start by omitting --no-auto-start."
        )
        return False

    logger.warning("Ollama not running — attempting automatic start…")
    if not start_ollama():
        return False

    logger.info("Waiting up to %ds for Ollama to become ready…", STARTUP_TIMEOUT)
    for elapsed in range(STARTUP_TIMEOUT):
        time.sleep(PING_INTERVAL)
        if is_running(ollama_host):
            logger.info("Ollama is ready (took %ds).", elapsed + 1)
            return True
        logger.debug("  Still waiting… (%ds)", elapsed + 1)

    logger.error(
        "Ollama did not respond within %ds. "
        "Check that it is installed correctly.",
        STARTUP_TIMEOUT,
    )
    return False
