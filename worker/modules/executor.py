"""
Ollama job executor.

Handles two job types:
  - 'generate': single prompt → single response  (/api/generate)
  - 'chat':     message history → next reply     (/api/chat)

Critical rule (from spec): stream is ALWAYS forced to False.
This ensures the worker deals with one complete JSON response, not a stream.
"""
import logging
import time

import requests

logger = logging.getLogger(__name__)

OLLAMA_TIMEOUT = 300   # 5 minutes — large models can be slow


class JobExecutionError(Exception):
    """Raised when a job cannot be completed."""


# ------------------------------------------------------------------
# Public entry point
# ------------------------------------------------------------------

def execute_job(job: dict, ollama_host: str, model_override: str = None) -> tuple:
    """
    Execute a single AI job against the local Ollama instance.

    Args:
        job:            Job dict from the shared server (already validated).
        ollama_host:    Base URL of Ollama (e.g. http://localhost:11434).
        model_override: If set, use this model name instead of job['model'].

    Returns:
        (response_text: str, duration_ms: int)

    Raises:
        JobExecutionError on failure.
    """
    job_type = job.get("type", "generate")
    model    = model_override or job.get("model", "qwen2.5-coder")
    images   = job.get("_images_b64", [])   # pre-processed by media_handler

    t0 = time.time()

    if job_type == "generate":
        text = _run_generate(job, model, ollama_host, images)
    elif job_type == "chat":
        text = _run_chat(job, model, ollama_host, images)
    else:
        raise JobExecutionError(
            f"Unknown job type '{job_type}'. Supported: 'generate', 'chat'."
        )

    duration_ms = int((time.time() - t0) * 1000)
    return text, duration_ms


# ------------------------------------------------------------------
# Job type handlers
# ------------------------------------------------------------------

def _run_generate(job: dict, model: str, host: str, images: list) -> str:
    prompt = job.get("prompt", "").strip()
    if not prompt:
        raise JobExecutionError("Job type 'generate' requires a non-empty 'prompt' field.")

    payload = {
        "model":  model,
        "prompt": prompt,
        "stream": False,          # ALWAYS False — enforced here, not trusted from server
    }
    if images:
        payload["images"] = images

    logger.debug("▶ /api/generate | model=%s | prompt_len=%d", model, len(prompt))
    resp = _post(f"{host}/api/generate", payload)
    return resp.get("response", "")


def _run_chat(job: dict, model: str, host: str, images: list) -> str:
    messages = job.get("messages", [])
    if not messages:
        raise JobExecutionError("Job type 'chat' requires a non-empty 'messages' array.")

    # Attach images to the last user message (Ollama vision format)
    if images:
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].get("role") == "user":
                messages[i]["images"] = images
                break

    payload = {
        "model":    model,
        "messages": messages,
        "stream":   False,        # ALWAYS False
    }

    logger.debug("▶ /api/chat | model=%s | messages=%d", model, len(messages))
    resp = _post(f"{host}/api/chat", payload)
    return resp.get("message", {}).get("content", "")


# ------------------------------------------------------------------
# Low-level HTTP helper
# ------------------------------------------------------------------

def _post(url: str, payload: dict) -> dict:
    """POST JSON to Ollama and return parsed response dict."""
    try:
        r = requests.post(url, json=payload, timeout=OLLAMA_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.Timeout:
        raise JobExecutionError(
            f"Ollama timed out after {OLLAMA_TIMEOUT}s. "
            "The model may need more RAM or the prompt is too long."
        )
    except requests.exceptions.ConnectionError:
        raise JobExecutionError(
            "Cannot reach Ollama. Did it crash? Try restarting with: ollama serve"
        )
    except requests.exceptions.HTTPError as exc:
        raise JobExecutionError(
            f"Ollama error {exc.response.status_code}: {exc.response.text[:300]}"
        )
    except Exception as exc:
        raise JobExecutionError(f"Unexpected Ollama error: {exc}")
