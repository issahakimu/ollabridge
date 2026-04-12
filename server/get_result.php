<?php
/**
 * OllaBridge — Get Job Result
 * ─────────────────────────────────────────────────────────────────────
 * Your frontend polls this endpoint to check if a job is done
 * and retrieve the AI response.
 *
 * Method:  GET
 * Params:  ?job_id=<uuid>
 * Auth:    None required (job_id acts as the private token)
 *
 * Response:
 *   {
 *     "job_id":    "uuid",
 *     "status":    "pending|processing|completed|failed",
 *     "result":    "AI response text (null if not yet done)",
 *     "error_msg": "Error details (null unless failed)",
 *     "created_at": "2026-04-12 17:00:00",
 *     "updated_at": "2026-04-12 17:00:05"
 *   }
 *
 * Polling pattern (JavaScript example):
 *   async function waitForResult(jobId) {
 *     while (true) {
 *       const res = await fetch(`/ollabridge/get_result.php?job_id=${jobId}`);
 *       const data = await res.json();
 *       if (data.status === 'completed') return data.result;
 *       if (data.status === 'failed')    throw new Error(data.error_msg);
 *       await new Promise(r => setTimeout(r, 2000)); // wait 2s, then retry
 *     }
 *   }
 */

require_once __DIR__ . '/db.php';

if ($_SERVER['REQUEST_METHOD'] !== 'GET') {
    json_response(['error' => 'Method Not Allowed'], 405);
}

$job_id = trim($_GET['job_id'] ?? '');
if (empty($job_id)) {
    json_response(['error' => "Missing 'job_id' query parameter."], 400);
}

$stmt = $pdo->prepare("
    SELECT id AS job_id, status, result, error_msg, created_at, updated_at
    FROM   ollabridge_jobs
    WHERE  id = ?
");
$stmt->execute([$job_id]);
$job = $stmt->fetch();

if (!$job) {
    json_response(['error' => "Job '{$job_id}' not found."], 404);
}

json_response($job);
