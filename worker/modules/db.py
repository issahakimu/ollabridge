"""
SQLite-based local job tracking database.

Why SQLite and not something else?
- Built into Python (zero pip installs needed)
- Persists job history across restarts unlike an in-memory dict
- Fully reliable for single-worker use (one writer at a time)
- Indexed deduplication lookups are extremely fast
- No server process to manage (unlike Redis / PostgreSQL)
- A plain JSON file would lose data on crash; SQLite won't
"""
import sqlite3
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class JobDatabase:
    def __init__(self, db_path: str = "local_jobs.db"):
        self.db_path = db_path
        self._init_db()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Create tables and indexes on first run."""
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS processed_jobs (
                    job_id       TEXT PRIMARY KEY,
                    status       TEXT NOT NULL,          -- 'done' | 'failed'
                    model_used   TEXT,
                    duration_ms  INTEGER,
                    error_msg    TEXT,
                    completed_at TEXT DEFAULT (datetime('now'))
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_pj_status ON processed_jobs(status)"
            )
            conn.commit()
        logger.debug("SQLite DB ready: %s", self.db_path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_processed(self, job_id: str) -> bool:
        """Return True if this job was already completed (deduplication guard)."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM processed_jobs WHERE job_id = ? AND status = 'done'",
                (job_id,),
            ).fetchone()
            return row is not None

    def mark_done(self, job_id: str, model: str = None, duration_ms: int = None):
        """Record a successfully completed job."""
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO processed_jobs
                    (job_id, status, model_used, duration_ms)
                VALUES (?, 'done', ?, ?)
                """,
                (job_id, model, duration_ms),
            )
            conn.commit()

    def mark_failed(self, job_id: str, error_msg: str = None):
        """Record a failed job so we don't retry it endlessly."""
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO processed_jobs
                    (job_id, status, error_msg)
                VALUES (?, 'failed', ?)
                """,
                (job_id, error_msg),
            )
            conn.commit()

    def get_stats(self) -> dict:
        """Return total / done / failed counts for the startup status line."""
        with self._get_conn() as conn:
            total  = conn.execute("SELECT COUNT(*) FROM processed_jobs").fetchone()[0]
            done   = conn.execute("SELECT COUNT(*) FROM processed_jobs WHERE status='done'").fetchone()[0]
            failed = conn.execute("SELECT COUNT(*) FROM processed_jobs WHERE status='failed'").fetchone()[0]
        return {"total": total, "done": done, "failed": failed}

    def get_recent(self, limit: int = 50) -> list:
        """Return recent job records as a list of dicts (newest first)."""
        with self._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT job_id, status, model_used, duration_ms, error_msg, completed_at
                FROM   processed_jobs
                ORDER  BY completed_at DESC
                LIMIT  ?
                """,
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def clear_all(self) -> int:
        """Delete every record. Returns the number of rows deleted."""
        with self._get_conn() as conn:
            count = conn.execute("SELECT COUNT(*) FROM processed_jobs").fetchone()[0]
            conn.execute("DELETE FROM processed_jobs")
            conn.commit()
        logger.info("Cleared %d records from %s", count, self.db_path)
        return count

    def export_sql(self, output_path: str) -> int:
        """
        Write all records as SQL INSERT statements to a file.
        Returns the number of records exported.
        """
        rows = self.get_recent(limit=999_999)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("-- OllaBridge Job History Export\n")
            f.write(f"-- Generated : {datetime.now().isoformat()}\n")
            f.write(f"-- Source DB : {self.db_path}\n")
            f.write(f"-- Records   : {len(rows)}\n\n")
            f.write(
                "CREATE TABLE IF NOT EXISTS processed_jobs (\n"
                "    job_id       TEXT PRIMARY KEY,\n"
                "    status       TEXT NOT NULL,\n"
                "    model_used   TEXT,\n"
                "    duration_ms  INTEGER,\n"
                "    error_msg    TEXT,\n"
                "    completed_at TEXT DEFAULT (datetime('now'))\n"
                ");\n\n"
            )
            for row in rows:
                esc = lambda s: (s or "").replace("'", "''")
                dur = row["duration_ms"] if row["duration_ms"] is not None else "NULL"
                f.write(
                    f"INSERT OR REPLACE INTO processed_jobs "
                    f"(job_id, status, model_used, duration_ms, error_msg, completed_at) VALUES ("
                    f"'{esc(row['job_id'])}', "
                    f"'{esc(row['status'])}', "
                    f"'{esc(row['model_used'])}', "
                    f"{dur}, "
                    f"'{esc(row['error_msg'])}', "
                    f"'{esc(row['completed_at'])}'"
                    f");\n"
                )
        return len(rows)
