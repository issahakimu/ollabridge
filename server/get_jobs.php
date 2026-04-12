<?php
/**
 * OllaBridge — Get Pending Jobs
 * ─────────────────────────────────────────────────────────────────────
 * Called by the Python worker to fetch pending AI jobs.
 *
 * Method:  GET
 * Header:  X-OllaBridge-Key: <secret_key>
 * Params:  ?limit=5  (optional, max MAX_JOBS_PER_REQUEST)
 *
 * Response: JSON array of job objects, or [] if no jobs are pending.
 *
 * Long-polling behaviour:
 *   If there are no pending jobs, this script waits up to
 *   LONG_POLL_SECONDS before returning an empty array.
 *   This reduces the number of HTTP calls from the worker
 *   without sacrificing responsiveness.
 *
 * Shared hosting safety:
 *   - set_time_limit(90): allows the long-poll to run without PHP killing it
 *   - ignore_user_abort(true): keeps running even if the worker disconnects
 */

// Must be called BEFORE output and BEFORE any blocking code
@set_time_limit(90);
@ignore_user_abort(true);

require_once __DIR__ . '/db.php';

// Only allow GET
if ($_SERVER['REQUEST_METHOD'] !== 'GET') {
    json_response(['error' => 'Method Not Allowed'], 405);
}

auth_check();

$limit = max(1, min((int)($_GET['limit'] ?? 5), MAX_JOBS_PER_REQUEST));

// Long-poll loop: wait up to LONG_POLL_SECONDS for at least one job
$deadline = time() + LONG_POLL_SECONDS;

while (true) {
    $jobs = fetch_pending_jobs($pdo, $limit);

    if (!empty($jobs)) {
        json_response($jobs, 200);
    }

    if (time() >= $deadline) {
        json_response([], 200);
    }

    sleep(2);   // wait before checking again
}

// ── Helper ────────────────────────────────────────────────────────────

function fetch_pending_jobs(PDO $pdo, int $limit): array
{
    $stmt = $pdo->prepare("
        SELECT id AS job_id, type, model, payload, images
        FROM ollabridge_jobs
        WHERE status = 'pending'
        ORDER BY created_at ASC
        LIMIT :limit
    ");
    $stmt->bindValue(':limit', $limit, PDO::PARAM_INT);
    $stmt->execute();
    $rows = $stmt->fetchAll();

    $jobs = [];
    foreach ($rows as $row) {
        // Unpack the payload JSON into the job object
        $payload = json_decode($row['payload'], true) ?? [];
        $job = array_merge($row, $payload);
        $job['images'] = $row['images'] ? json_decode($row['images'], true) : [];
        unset($job['payload']);
        $jobs[] = $job;
    }

    return $jobs;
}
