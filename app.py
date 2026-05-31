"""
SnowSheets - Local Snowflake Worksheet
Run: python app.py
Open: http://localhost:8000
"""

import os
import json
import threading
import webbrowser
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import snowflake.connector

# ── CONFIG ─────────────────────────────────────────────────────────────────────
ACCOUNT      = os.environ.get("SNOWFLAKE_ACCOUNT", "your-account-identifier")
USER         = os.environ.get("SNOWFLAKE_USER",    "your@email.com")
WAREHOUSE    = os.environ.get("SNOWFLAKE_WH",      "")
DATABASE     = os.environ.get("SNOWFLAKE_DB",      "")
SCHEMA       = os.environ.get("SNOWFLAKE_SCHEMA",  "")
PORT         = 8000

# Point this at your shared Google Drive folder.
# Everyone on the team sets the same path on their machine.
# Example: "/Users/jhuey/Google Drive/Shared drives/Team/SnowSheets Queries"
QUERIES_DIR  = os.environ.get(
    "SNOWSHEETS_QUERIES_DIR",
    str(Path.home() / "Google Drive" / "SnowSheets Queries")
)
# ───────────────────────────────────────────────────────────────────────────────

_conn = None

def get_conn():
    global _conn
    if _conn is None:
        print("\n🔐  Opening browser for SSO login…\n")
        kwargs = dict(
            account=ACCOUNT,
            user=USER,
            authenticator="externalbrowser",
        )
        if WAREHOUSE: kwargs["warehouse"] = WAREHOUSE
        if DATABASE:  kwargs["database"]  = DATABASE
        if SCHEMA:    kwargs["schema"]    = SCHEMA
        _conn = snowflake.connector.connect(**kwargs)
        print("✅  Connected to Snowflake.\n")
    return _conn


def run_query(sql: str, limit: int = 2000):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute(sql)
    cols = [d[0] for d in cur.description] if cur.description else []
    rows = cur.fetchmany(limit)
    cur.close()
    return {
        "columns": cols,
        "rows":    [list(r) for r in rows],
        "rowcount": cur.rowcount,
    }


def get_databases():
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("SHOW DATABASES")
    dbs = [r[1] for r in cur.fetchall()]
    cur.close()
    return dbs


def get_db_tree(db: str):
    conn = get_conn()
    cur  = conn.cursor()
    tree = {}
    try:
        cur.execute(f'SHOW SCHEMAS IN DATABASE "{db}"')
        schemas = [r[1] for r in cur.fetchall()]
        for sc in schemas:
            try:
                cur.execute(f'SHOW TABLES IN "{db}"."{sc}"')
                tables = [r[1] for r in cur.fetchall()]
                tree[sc] = tables
            except Exception:
                tree[sc] = []
    except Exception as e:
        cur.close()
        raise e
    cur.close()
    return tree


# ── QUERY LIBRARY (shared folder) ─────────────────────────────────────────────

def queries_dir() -> Path:
    p = Path(QUERIES_DIR)
    p.mkdir(parents=True, exist_ok=True)
    return p

def list_queries():
    d = queries_dir()
    files = sorted(d.glob("*.sql"), key=lambda f: f.stat().st_mtime, reverse=True)
    return [{"name": f.stem, "filename": f.name,
             "modified": f.stat().st_mtime} for f in files]

def read_query(filename: str) -> str:
    p = queries_dir() / Path(filename).name   # prevent path traversal
    if not p.exists():
        raise FileNotFoundError(f"{filename} not found")
    return p.read_text(encoding="utf-8")

def save_query_file(name: str, sql: str):
    safe = "".join(c if c.isalnum() or c in " _-" else "_" for c in name).strip()
    if not safe:
        safe = "query"
    p = queries_dir() / f"{safe}.sql"
    p.write_text(sql, encoding="utf-8")
    return p.name

def delete_query_file(filename: str):
    p = queries_dir() / Path(filename).name
    if p.exists():
        p.unlink()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def send_json(self, data, status=200):
        body = json.dumps(data, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        qs     = parse_qs(parsed.query)

        if parsed.path in ("/", "/index.html"):
            html = Path(__file__).parent / "index.html"
            body = html.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/api/databases":
            try:
                self.send_json(get_databases())
            except Exception as e:
                self.send_json({"error": str(e)}, 500)
            return

        if parsed.path == "/api/expand":
            db = qs.get("db", [None])[0]
            if not db:
                self.send_json({"error": "missing db param"}, 400)
                return
            try:
                self.send_json(get_db_tree(db))
            except Exception as e:
                self.send_json({"error": str(e)}, 500)
            return

        if parsed.path == "/api/library":
            self.send_json(list_queries())
            return

        if parsed.path == "/api/library/read":
            filename = qs.get("file", [None])[0]
            if not filename:
                self.send_json({"error": "missing file param"}, 400)
                return
            try:
                self.send_json({"sql": read_query(filename)})
            except FileNotFoundError as e:
                self.send_json({"error": str(e)}, 404)
            return

        if parsed.path == "/api/library/dir":
            self.send_json({"path": str(queries_dir())})
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body   = json.loads(self.rfile.read(length)) if length else {}

        if self.path == "/api/query":
            sql = body.get("sql", "").strip()
            if not sql:
                self.send_json({"error": "No SQL provided"}, 400)
                return
            try:
                self.send_json(run_query(sql))
            except Exception as e:
                self.send_json({"error": str(e)}, 500)
            return

        if self.path == "/api/library/save":
            name = body.get("name", "").strip()
            sql  = body.get("sql", "").strip()
            if not name or not sql:
                self.send_json({"error": "name and sql required"}, 400)
                return
            try:
                filename = save_query_file(name, sql)
                self.send_json({"ok": True, "filename": filename})
            except Exception as e:
                self.send_json({"error": str(e)}, 500)
            return

        self.send_response(404)
        self.end_headers()

    def do_DELETE(self):
        parsed   = urlparse(self.path)
        qs       = parse_qs(parsed.query)
        if parsed.path == "/api/library/delete":
            filename = qs.get("file", [None])[0]
            if not filename:
                self.send_json({"error": "missing file param"}, 400)
                return
            delete_query_file(filename)
            self.send_json({"ok": True})
            return
        self.send_response(404)
        self.end_headers()


if __name__ == "__main__":
    if ACCOUNT == "your-account-identifier":
        print("⚠️  Edit SNOWFLAKE_ACCOUNT / SNOWFLAKE_USER in app.py (or set env vars) before running.\n")

    print(f"📂  Query library: {queries_dir()}")

    server = HTTPServer(("localhost", PORT), Handler)
    url    = f"http://localhost:{PORT}"
    print(f"🚀  SnowSheets running at {url}")
    print("    Press Ctrl+C to stop.\n")

    threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋  Stopped.")
        if _conn:
            _conn.close()


_conn = None

def get_conn():
    global _conn
    if _conn is None:
        print("\n🔐  Opening browser for SSO login…\n")
        kwargs = dict(
            account=ACCOUNT,
            user=USER,
            authenticator="externalbrowser",
        )
        if WAREHOUSE: kwargs["warehouse"] = WAREHOUSE
        if DATABASE:  kwargs["database"]  = DATABASE
        if SCHEMA:    kwargs["schema"]    = SCHEMA
        _conn = snowflake.connector.connect(**kwargs)
        print("✅  Connected to Snowflake.\n")
    return _conn


def run_query(sql: str, limit: int = 2000):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute(sql)
    cols = [d[0] for d in cur.description] if cur.description else []
    rows = cur.fetchmany(limit)
    cur.close()
    return {
        "columns": cols,
        "rows":    [list(r) for r in rows],
        "rowcount": cur.rowcount,
    }


def get_databases():
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("SHOW DATABASES")
    dbs = [r[1] for r in cur.fetchall()]
    cur.close()
    return dbs


def get_db_tree(db: str):
    conn = get_conn()
    cur  = conn.cursor()
    tree = {}
    try:
        cur.execute(f'SHOW SCHEMAS IN DATABASE "{db}"')
        schemas = [r[1] for r in cur.fetchall()]
        for sc in schemas:
            try:
                cur.execute(f'SHOW TABLES IN "{db}"."{sc}"')
                tables = [r[1] for r in cur.fetchall()]
                tree[sc] = tables
            except Exception:
                tree[sc] = []
    except Exception as e:
        cur.close()
        raise e
    cur.close()
    return tree


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass   # suppress default access log noise

    def send_json(self, data, status=200):
        body = json.dumps(data, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        qs     = parse_qs(parsed.query)

        if parsed.path in ("/", "/index.html"):
            html = Path(__file__).parent / "index.html"
            body = html.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/api/databases":
            try:
                self.send_json(get_databases())
            except Exception as e:
                self.send_json({"error": str(e)}, 500)
            return

        if parsed.path == "/api/expand":
            db = qs.get("db", [None])[0]
            if not db:
                self.send_json({"error": "missing db param"}, 400)
                return
            try:
                self.send_json(get_db_tree(db))
            except Exception as e:
                self.send_json({"error": str(e)}, 500)
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        if self.path == "/api/query":
            length = int(self.headers.get("Content-Length", 0))
            body   = json.loads(self.rfile.read(length))
            sql    = body.get("sql", "").strip()
            if not sql:
                self.send_json({"error": "No SQL provided"}, 400)
                return
            try:
                result = run_query(sql)
                self.send_json(result)
            except Exception as e:
                self.send_json({"error": str(e)}, 500)
            return

        self.send_response(404)
        self.end_headers()


if __name__ == "__main__":
    if ACCOUNT == "your-account-identifier":
        print("⚠️  Edit SNOWFLAKE_ACCOUNT / SNOWFLAKE_USER in app.py (or set env vars) before running.\n")

    server = HTTPServer(("localhost", PORT), Handler)
    url    = f"http://localhost:{PORT}"
    print(f"🚀  SnowSheets running at {url}")
    print("    Press Ctrl+C to stop.\n")

    threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋  Stopped.")
        if _conn:
            _conn.close()
