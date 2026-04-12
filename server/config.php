<?php
/**
 * OllaBridge Server Configuration
 * ─────────────────────────────────────────────────────────────────────
 * Edit the values below and save this file as config.php.
 *
 * SECURITY TIP: Move this file ABOVE your public_html directory so it
 * cannot be accessed via a browser URL. Then update the require_once
 * path in db.php to point to the new location.
 */

// ── Authentication ────────────────────────────────────────────────────
// Must EXACTLY match the --secret-key used by the Python worker.
define('OLLABRIDGE_SECRET_KEY', 'CHANGE_THIS_TO_A_STRONG_RANDOM_SECRET');

// ── Database ──────────────────────────────────────────────────────────
define('DB_HOST', 'localhost');
define('DB_NAME', 'your_database_name');
define('DB_USER', 'your_database_user');
define('DB_PASS', 'your_database_password');

// ── Behaviour ─────────────────────────────────────────────────────────
// How many seconds get_jobs.php waits before returning an empty list
// (long-polling — reduces hammering while staying responsive)
define('LONG_POLL_SECONDS', 20);

// Maximum jobs the worker can fetch in a single request
define('MAX_JOBS_PER_REQUEST', 10);

// Safety: stop accepting new jobs when the queue has this many pending
define('MAX_PENDING_JOBS', 200);
