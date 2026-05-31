# SnowSheets

A minimal local SQL worksheet for Snowflake. No build step, no framework — just two files and a Python server.

## Setup

**1. Install the Snowflake connector (one-time):**
```
pip install snowflake-connector-python
```

**2. Edit `app.py` — set your account and user at the top:**
```python
ACCOUNT = "myorg-myaccount"   # from your Snowflake URL: https://<account>.snowflakecomputing.com
USER    = "you@company.com"
```

Or use environment variables:
```bash
export SNOWFLAKE_ACCOUNT="myorg-myaccount"
export SNOWFLAKE_USER="you@company.com"
export SNOWFLAKE_WH="ANALYST_WH"      # optional default warehouse
export SNOWFLAKE_DB="PROD_DB"         # optional default database
export SNOWFLAKE_SCHEMA="FRAUD"       # optional default schema
```

**3. Run:**
```
python app.py
```

A browser tab opens automatically at http://localhost:8000. Your SSO login page will appear on your first query — after that the session is held until you stop the server.

---

## Features

- **Tabbed worksheets** — multiple queries open at once, saved to browser localStorage between sessions
- **Schema browser** — lazy-loads databases, schemas, and tables on demand; click a table to insert its full name into the editor
- **Charts** — bar, line, scatter, pie, doughnut with axis selectors; appears after every query run
- **AI analyst** — Claude-powered side panel that analyzes your results, spots anomalies, suggests follow-up queries, and can run them directly. Requires an Anthropic API key (get one at console.anthropic.com)
- **Shared query library** — save and load `.sql` files from a shared Google Drive folder; the whole team sees the same library
- **CSV export** — one click from the results pane
- **⌘↵ / Ctrl+↵** to run

---

## Shared Query Library (Google Drive)

All saved queries are stored as `.sql` files in a local folder that syncs via Google Drive.

**Default path:** `~/Google Drive/SnowSheets Queries`

To use a shared team folder, point everyone at the same Drive path:
```python
# in app.py
QUERIES_DIR = "/Users/you/Google Drive/Shared drives/Analytics/SnowSheets Queries"
```

Or via env var:
```bash
export SNOWSHEETS_QUERIES_DIR="/path/to/shared/folder"
```

The current folder path is printed to the terminal on startup and shown at the top of the library panel.

Queries are plain `.sql` files — they can also be edited directly in Finder or any text editor.

---

## AI Analyst

Click **✦ AI** in the topbar to open the analyst panel. Paste your Anthropic API key into the field — it's held in memory only, never stored or sent anywhere except the Anthropic API.

After running a query, ask anything:
- *"what's driving the high risk scores?"*
- *"are there any anomalies in this data?"*
- *"summarize this by merchant"*
- *"write a follow-up query for this"*

When the AI writes SQL you get three options: **copy**, **use in editor**, or **▶ run it** which executes immediately.

---

## Files

| File | Purpose |
|------|---------|
| `app.py` | Python server — Snowflake connection, query execution, library file I/O |
| `index.html` | Full UI — editor, results, charts, schema browser, AI panel |
| `.gitignore` | Excludes secrets, cache, key files |
