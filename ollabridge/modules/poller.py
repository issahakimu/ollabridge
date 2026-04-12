"""
Main polling loop — the heart of OllaBridge.

Flow per cycle:
  GET  /ollabridge/get_jobs.php  → list of pending jobs
  For each job:
    1. Deduplication check (SQLite)
    2. Mark 'processing' on server
    3. Resolve model (auto-pull / fallback)
    4. Process images → Base64
    5. Execute job via Ollama
    6. POST result back to server
    7. Record in SQLite
"""
import logging
import time

import requests

from .db             import JobDatabase
from .executor       import execute_job, JobExecutionError
from .media_handler  import process_images
from .model_manager  import ensure_model

logger = logging.getLogger(__name__)

HTTP_TIMEOUT = 30   # seconds for calls to the shared server


class Poller:
    def __init__(self, config: dict, db: JobDatabase):
        self.config        = config
        self.db            = db
        self.site_url      = config["site_url"].rstrip("/")
        self.secret_key    = config["secret_key"]
        self.ollama_host   = config["ollama_host"]
        self.poll_interval = int(config["poll_interval"])
        self.job_limit     = int(config.get("job_limit", 5))
        self.default_model = config["default_model"]
        self.fallback_model= config["fallback_model"]
        self.auto_pull     = bool(config.get("auto_pull_model", True))

        self._headers = {"X-OllaBridge-Key": self.secret_key}

        # Counters for the shutdown summary
        self.jobs_processed = 0
        self.jobs_failed    = 0

    # ------------------------------------------------------------------
    # Server communication helpers
    # ------------------------------------------------------------------

    def _fetch_jobs(self) -> list:
        """GET pending jobs from the shared server. Returns list (may be empty)."""
        url = f"{self.site_url}/ollabridge/get_jobs.php"
        try:
            r = requests.get(
                url,
                headers=self._headers,
                params={"limit": self.job_limit},
                timeout=HTTP_TIMEOUT,
            )
            r.raise_for_status()
            data = r.json()
            return data if isinstance(data, list) else []
        except requests.exceptions.ConnectionError:
            logger.error("Cannot reach server: %s", self.site_url)
        except requests.exceptions.HTTPError as exc:
            code = exc.response.status_code
            if code == 403:
                logger.error("Authentication failed — check your --secret-key.")
            else:
                logger.error("Server returned HTTP %d", code)
        except Exception as exc:
            logger.error("Fetch failed: %s", exc)
        return []

    def _mark_processing(self, job_id: str):
        """Tell the server we are working on this job (prevents double-pickup)."""
        try:
            requests.post(
                f"{self.site_url}/ollabridge/update_job.php",
                json={"job_id": job_id, "status": "processing"},
                headers=self._headers,
                timeout=HTTP_TIMEOUT,
            )
        except Exception as exc:
            logger.warning("Could not mark job %s as processing: %s", job_id, exc)

    def _deliver_result(self, job_id: str, result: str) -> bool:
        """POST the completed AI response back to the shared server."""
        try:
            r = requests.post(
                f"{self.site_url}/ollabridge/update_job.php",
                json={"job_id": job_id, "status": "completed", "result": result},
                headers=self._headers,
                timeout=HTTP_TIMEOUT,
            )
            return r.status_code == 200
        except Exception as exc:
            logger.error("Delivery failed for job %s: %s", job_id, exc)
            return False

    def _deliver_failure(self, job_id: str, error: str):
        """Report an unrecoverable job error back to the shared server."""
        try:
            requests.post(
                f"{self.site_url}/ollabridge/update_job.php",
                json={"job_id": job_id, "status": "failed", "error": error},
                headers=self._headers,
                timeout=HTTP_TIMEOUT,
            )
        except Exception:
            pass   # Best-effort; we already logged the error locally

    # ------------------------------------------------------------------
    # Single job processor
    # ------------------------------------------------------------------

    def _process_job(self, job: dict):
        job_id = job.get("job_id") or job.get("id")
        if not job_id:
            logger.warning("Job has no 'job_id' field — skipping: %s", job)
            return

        # Deduplication
        if self.db.is_processed(job_id):
            logger.debug("Job %s already processed — skipping.", job_id)
            return

        job_type = job.get("type", "generate")
        model_req = job.get("model", self.default_model)
        logger.info("📥  Job %-36s  type=%-8s  model=%s", job_id, job_type, model_req)

        # Mark processing on server immediately
        self._mark_processing(job_id)

        # Resolve model (auto-pull + fallback)
        model = ensure_model(
            self.ollama_host, model_req, self.fallback_model, self.auto_pull
        )
        if model is None:
            err = (
                f"No model available. Tried '{model_req}' "
                f"and fallback '{self.fallback_model}'."
            )
            logger.error(err)
            self._deliver_failure(job_id, err)
            self.db.mark_failed(job_id, err)
            self.jobs_failed += 1
            return

        if model != model_req:
            logger.warning("⚠  Using fallback model '%s' instead of '%s'", model, model_req)

        # Process images
        raw_images = job.get("images") or []
        if raw_images:
            logger.info("   📷 Processing %d image(s)…", len(raw_images))
            job["_images_b64"] = process_images(raw_images)
        else:
            job["_images_b64"] = []

        # Execute
        try:
            result_text, duration_ms = execute_job(job, self.ollama_host, model)
            logger.info(
                "✅  Job %s done in %dms (model=%s)", job_id, duration_ms, model
            )

            if self._deliver_result(job_id, result_text):
                self.db.mark_done(job_id, model, duration_ms)
                self.jobs_processed += 1
            else:
                err = "Result delivered but server did not confirm."
                self.db.mark_failed(job_id, err)
                self.jobs_failed += 1

        except JobExecutionError as exc:
            err = str(exc)
            logger.error("❌  Job %s failed: %s", job_id, err)
            self._deliver_failure(job_id, err)
            self.db.mark_failed(job_id, err)
            self.jobs_failed += 1

    # ------------------------------------------------------------------
    # Main loop (runs until Ctrl+C)
    # ------------------------------------------------------------------

    def run(self):
        """Start the infinite poll → process → sleep loop."""
        while True:
            try:
                jobs = self._fetch_jobs()
                if jobs:
                    logger.info("📦  %d job(s) received", len(jobs))
                    for job in jobs:
                        self._process_job(job)
                else:
                    logger.debug("No jobs. Sleeping %ds…", self.poll_interval)

                time.sleep(self.poll_interval)

            except KeyboardInterrupt:
                raise   # let the caller (ollabridge.py) handle the summary
            except Exception as exc:
                logger.error("Unexpected loop error: %s", exc)
                time.sleep(self.poll_interval)
