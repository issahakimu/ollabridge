<?php
/**
 * OllaBridge — Update Job Status / Deliver Result
 * ─────────────────────────────────────────────────────────────────────
 * Called by the Python worker to:
 *   1. Mark a job as 'processing' (prevents double-pickup)
 *   2. Deliver the completed AI result (status = 'completed')
 *   3. Report a failure              (status = 'failed')
 *
 * Method:  POST
 * Header:  X-OllaBridge-Key: <secret_key>
 * Body:    JSON
 *   { "job_id": "uuid",  "status": "processing" }
 *   { "job_id": "uuid",  "status": "completed",  "result": "..." }
 *   { "job_id": "uuid",  "status": "failed",     "error":  "..." }
 *
 * Response: { "success": true, "status": "<new_status>" }
 */

require_once __DIR__ . '/db.php';

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    json_response(['error' => 'Method Not Allowed'], 405);
}

auth_check();

$body = json_decode(file_get_contents('php://input'), true);
if (!$body || empty($body['job_id']) || empty($body['status'])) {
    json_response(['error' => 'Missing job_id or status in request body.'], 400);
}

$allowed = ['processing', 'completed', 'failed'];
if (!in_array($body['status'], $allowed, true)) {
    json_response(['error' => "Invalid status '{$body['status']}'. Allowed: " . implode(', ', $allowed)], 400);
}

$stmt = $pdo->prepare("
    UPDATE ollabridge_jobs
    SET    status    = :status,
           result    = :result,
           error_msg = :error,
           updated_at = NOW()
    WHERE  id = :job_id
");

$stmt->execute([
    ':status'  => $body['status'],
    ':result'  => $body['result'] ?? null,
    ':error'   => $body['error']  ?? null,
    ':job_id'  => $body['job_id'],
]);

if ($stmt->rowCount() === 0) {
    json_response(['error' => "Job '{$body['job_id']}' not found."], 404);
}

json_response(['success' => true, 'status' => $body['status']]);
