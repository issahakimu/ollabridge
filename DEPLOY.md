# 🚀 Shared Hosting Deployment Checklist

## Step 1 — Create the MySQL Database on Shared Hosting

Log into your **cPanel → MySQL Databases** and:

1. Create a new database (e.g., `yourusername_ollabridge`)
2. Create a database user with a strong password
3. Add the user to the database with **All Privileges**
4. Note down: DB host, DB name, DB user, DB password

---

## Step 2 — Import the Schema

Go to **cPanel → phpMyAdmin**:

1. Select your new database
2. Click **Import** tab
3. Upload `server/schema.sql`
4. Click **Go**

You should see the `ollabridge_jobs` table created.

---

## Step 3 — Configure `config.php`

Open `server/config.php` and fill in your real values:

```php
define('OLLABRIDGE_SECRET_KEY', 'make-this-very-hard-to-guess-abc123xyz');

define('DB_HOST', 'localhost');                    // usually 'localhost' on shared hosting
define('DB_NAME', 'yourusername_ollabridge');      // your DB name from Step 1
define('DB_USER', 'yourusername_dbuser');          // your DB user from Step 1
define('DB_PASS', 'your-strong-password');         // your DB password from Step 1
```

> ⚠️ The `OLLABRIDGE_SECRET_KEY` MUST match exactly what you set in your worker's `config.ini`

---

## Step 4 — Upload Files to Shared Hosting

Using **File Manager** or **FTP (FileZilla)**:

1. Go to your `public_html` folder
2. Create a new folder called `ollabridge`
3. Upload ALL files from the `server/` folder into it:

```
public_html/
└── ollabridge/
    ├── config.php        ← Edit this BEFORE uploading (Step 3)
    ├── db.php
    ├── demo.html
    ├── get_jobs.php
    ├── get_result.php
    ├── submit_job.php
    └── update_job.php
    (do NOT upload schema.sql — it's already imported)
```

---

## Step 5 — Test the Server Side

Open your browser and test these URLs:

| Test | URL | Expected |
|------|-----|----------|
| Wrong key → 403 | `https://yoursite.com/ollabridge/get_jobs.php` | `{"error":"Unauthorized..."}` |
| Submit a test job | POST to `submit_job.php` | `{"job_id":"uuid","status":"pending"}` |
| Demo page loads | `https://yoursite.com/ollabridge/demo.html` | AI chat UI appears |

**Quick browser test (just visit this URL):**
```
https://yoursite.com/ollabridge/submit_job.php
```
You should see `{"error":"Invalid or empty JSON body."}` — that means PHP and MySQL are connected ✅

---

## Step 6 — Update Your Worker Config

On your **local Ubuntu machine**, open the worker config:

```bash
nano /home/anonymous/Desktop/ProjectA/worker/config.ini
```

Change `site_url` and `secret_key` to match your real hosting:

```ini
[ollabridge]
site_url   = https://yoursite.com        ← ✏️ change this
secret_key = make-this-very-hard-to-guess-abc123xyz  ← ✏️ must match config.php
default_model  = gemma4:e2b
fallback_model = llama3.2
poll_interval  = 5
```

---

## Step 7 — Run the Worker Against Live Server

```bash
cd /home/anonymous/Desktop/ProjectA/worker
/home/anonymous/Desktop/ProjectA/.venv/bin/python ollabridge.py status
```

You should see both Ollama ✅ and Shared Server ✅.

Then start it:
```bash
/home/anonymous/Desktop/ProjectA/.venv/bin/python ollabridge.py run
```

---

## Step 8 — Live Test!

1. Open `https://yoursite.com/ollabridge/demo.html` in your browser
2. Type a prompt and press Enter
3. Watch the worker terminal — it should say `📥 Job received`
4. The browser page shows `pending → processing → completed`
5. The AI response appears on the page

---

## 🔧 Troubleshooting

| Problem | Fix |
|---------|-----|
| `403 Unauthorized` on all requests | Secret key mismatch — check `config.php` vs `config.ini` |
| `500 Server Error` | DB credentials wrong in `config.php` — check phpMyAdmin |
| Job stays `pending` forever | Worker is not running — start it with the command above |
| Job goes `processing` but never completes | Ollama is slow — be patient, or try a smaller model |
| `Cannot reach server` in worker | Wrong `site_url` in `config.ini`, or folder name is not `ollabridge` |

---

## 📁 Files NOT to Upload
- `schema.sql` — already imported via phpMyAdmin
- `demo.html` is optional — only if you want the chat UI on live server
