"""
Ollama model availability manager.

Decision tree when a job requests a model:
  1. Model installed?         → use it
  2. Not installed + auto_pull → pull it → use it
  3. Pull failed              → check fallback model
  4. Fallback installed?      → use fallback
  5. Fallback missing + auto_pull → pull fallback → use it
  6. Everything failed        → return None (job cannot run)
"""
import logging
import subprocess

import requests

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Querying installed models
# ------------------------------------------------------------------

def list_installed_models(ollama_host: str) -> list:
    """Return a list of installed model name strings."""
    try:
        r = requests.get(f"{ollama_host}/api/tags", timeout=5)
        r.raise_for_status()
        return [m["name"] for m in r.json().get("models", [])]
    except Exception as exc:
        logger.error("Could not list Ollama models: %s", exc)
        return []


def is_model_installed(ollama_host: str, model_name: str) -> bool:
    """
    Check whether a model is installed.
    Matches both  'qwen2.5-coder'  and  'qwen2.5-coder:latest'.
    """
    installed = list_installed_models(ollama_host)
    base = model_name.split(":")[0]
    return any(
        m == model_name or m.split(":")[0] == base
        for m in installed
    )


# ------------------------------------------------------------------
# Pulling models
# ------------------------------------------------------------------

def pull_model(model_name: str) -> bool:
    """
    Pull a model via the Ollama CLI.
    Progress is printed directly to the terminal so the user can see it.
    Returns True on success.
    """
    logger.info("Pulling model '%s' — this may take a while…", model_name)
    try:
        result = subprocess.run(
            ["ollama", "pull", model_name],
            check=True,
            capture_output=False,   # show download progress in terminal
        )
        return result.returncode == 0
    except subprocess.CalledProcessError as exc:
        logger.error("Pull failed for '%s': %s", model_name, exc)
        return False
    except FileNotFoundError:
        logger.error("'ollama' command not found.")
        return False


# ------------------------------------------------------------------
# Main entry — used by the poller before every job
# ------------------------------------------------------------------

def ensure_model(
    ollama_host: str,
    model_name: str,
    fallback_model: str = "llama3.2",
    auto_pull: bool = True,
) -> str | None:
    """
    Ensure the requested model (or its fallback) is available.

    Returns:
        The model name string to actually use, or None if nothing is available.
    """
    # --- Try primary model ---
    if is_model_installed(ollama_host, model_name):
        return model_name

    if auto_pull:
        logger.warning("Model '%s' not found locally. Pulling…", model_name)
        if pull_model(model_name):
            return model_name
        logger.error("Pull failed for '%s'. Trying fallback '%s'…", model_name, fallback_model)
    else:
        logger.warning(
            "Model '%s' not found. Auto-pull is disabled. "
            "Run: ollama pull %s",
            model_name, model_name,
        )

    # --- Try fallback model ---
    if model_name == fallback_model:
        # Already tried this — don't loop
        logger.error("Fallback model is the same as primary '%s'. Nothing to try.", model_name)
        return None

    if is_model_installed(ollama_host, fallback_model):
        logger.info("Using fallback model: %s", fallback_model)
        return fallback_model

    if auto_pull:
        logger.info("Fallback model '%s' not installed. Pulling…", fallback_model)
        if pull_model(fallback_model):
            logger.info("Using fallback model: %s", fallback_model)
            return fallback_model

    logger.error(
        "No usable model available. "
        "Tried '%s' and fallback '%s'. Run: ollama pull %s",
        model_name, fallback_model, fallback_model,
    )
    return None
