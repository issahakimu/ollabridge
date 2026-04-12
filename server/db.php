<?php
/**
 * Shared database connection and authentication helper.
 * Required by all OllaBridge server endpoints.
 */

require_once __DIR__ . '/config.php';

// PDO connection — shared across all files that include db.php
try {
    $pdo = new PDO(
        'mysql:host=' . DB_HOST . ';dbname=' . DB_NAME . ';charset=utf8mb4',
        DB_USER,
        DB_PASS,
        [
            PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            PDO::ATTR_EMULATE_PREPARES   => false,
        ]
    );
} catch (PDOException $e) {
    http_response_code(500);
    header('Content-Type: application/json');
    echo json_encode(['error' => 'Database connection failed.']);
    exit;
}

/**
 * Verify the X-OllaBridge-Key header matches the configured secret.
 * Terminates with 403 if authentication fails.
 */
function auth_check(): void
{
    $provided = $_SERVER['HTTP_X_OLLABRIDGE_KEY'] ?? '';
    if (empty($provided) || $provided !== OLLABRIDGE_SECRET_KEY) {
        http_response_code(403);
        header('Content-Type: application/json');
        echo json_encode(['error' => 'Unauthorized. Invalid or missing X-OllaBridge-Key header.']);
        exit;
    }
}

/**
 * Send a JSON response and terminate.
 */
function json_response(mixed $data, int $code = 200): void
{
    http_response_code($code);
    header('Content-Type: application/json');
    echo json_encode($data);
    exit;
}

/**
 * Generate a v4 UUID.
 */
function generate_uuid(): string
{
    return sprintf(
        '%04x%04x-%04x-%04x-%04x-%04x%04x%04x',
        mt_rand(0, 0xffff), mt_rand(0, 0xffff),
        mt_rand(0, 0xffff),
        mt_rand(0, 0x0fff) | 0x4000,
        mt_rand(0, 0x3fff) | 0x8000,
        mt_rand(0, 0xffff), mt_rand(0, 0xffff), mt_rand(0, 0xffff)
    );
}
