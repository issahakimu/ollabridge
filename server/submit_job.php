<?php
/**
 * OllaBridge — Submit a New AI Job
 * ─────────────────────────────────────────────────────────────────────
 * Your website/app calls this endpoint to queue a new AI task.
 * The Python worker will pick it up, run it through Ollama, and
 * write the result back to the database.
 *
 * Method:  POST
 * Header:  X-OllaBridge-Key: <secret_key>   (optional — set REQUIRE_AUTH below)
 *
 * Body JSON examples:
 *   Text generation:
 *     { "type": "generate", "model": "qwen2.5-coder",
 *       "prompt": "Write a PHP function to validate email" }
 *
 *   Conversation:
 *     { "type": "chat", "model": "qwen2.5-coder",
 *       "messages": [
 *         {"role": "system", "content": "You are a helpful assistant."},
 *         {"role": "user",   "content": "How do I sort an array in PHP?"}
 *       ] }
 *
 *   Vision (image understanding):
 *     { "type": "chat", "model": "llava",
 *       "messages": [{"role": "user", "content": "Describe this image"}],
 *       "images": ["https://yoursite.com/uploads/photo.jpg"] }
 *
 * Response:
 *   { "job_id": "uuid", "status": "pending" }
 *
 * Use get_result.php to poll for the result using the returned job_id.
 */

require_once __DIR__ . '/db.php';

// Set to true if you want to require the secret key for job submission too.
// Useful if submit_job.php is called from your backend (not from a browser).
define('REQUIRE_AUTH_FOR_SUBMIT', false);

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    json_response(['error' => 'Method Not Allowed'], 405);
}

if (REQUIRE_AUTH_FOR_SUBMIT) {
    auth_check();
}

$data = json_decode(file_get_contents('php://input'), true);
if (!$data) {
    json_response(['error' => 'Invalid or empty JSON body.'], 400);
}

// Validate type
$type = $data['type'] ?? 'generate';
if (!in_array($type, ['generate', 'chat'], true)) {
    json_response(['error' => "Invalid type '{$type}'. Use 'generate' or 'chat'."], 400);
}

// Validate required fields per type
if ($type === 'generate' && empty($data['prompt'])) {
    json_response(['error' => "Missing 'prompt' for type 'generate'."], 400);
}
if ($type === 'chat' && empty($data['messages'])) {
    json_response(['error' => "Missing 'messages' for type 'chat'."], 400);
}

// Check queue capacity
$pending_count = (int) $pdo->query(
    "SELECT COUNT(*) FROM ollabridge_jobs WHERE status = 'pending'"
)->fetchColumn();

if ($pending_count >= MAX_PENDING_JOBS) {
    json_response(['error' => 'Job queue is full. Please try again later.'], 429);
}

// Build the payload stored in the database
$model   = $data['model'] ?? 'qwen2.5-coder';
$payload = ($type === 'generate')
    ? ['prompt'   => $data['prompt']]
    : ['messages' => $data['messages']];

$images   = !empty($data['images']) ? json_encode($data['images']) : null;
$job_id   = generate_uuid();

$stmt = $pdo->prepare("
    INSERT INTO ollabridge_jobs (id, type, model, payload, images, status)
    VALUES (:id, :type, :model, :payload, :images, 'pending')
");
$stmt->execute([
    ':id'      => $job_id,
    ':type'    => $type,
    ':model'   => $model,
    ':payload' => json_encode($payload),
    ':images'  => $images,
]);

json_response(['job_id' => $job_id, 'status' => 'pending'], 201);
