"""
SnowSheet - Local Snowflake Worksheet
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
ACCOUNT   = os.environ.get("SNOWFLAKE_ACCOUNT", "your-account-identifier")
USER      = os.environ.get("SNOWFLAKE_USER",    "your@email.com")
WAREHOUSE = os.environ.get("SNOWFLAKE_WH",      "")   # optional default
DATABASE  = os.environ.get("SNOWFLAKE_DB",       "")   # optional default
SCHEMA    = os.environ.get("SNOWFLAKE_SCHEMA",   "")   # optional default
PORT      = 8000
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


def get_schemas():
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("SHOW DATABASES")
    dbs = [r[1] for r in cur.fetchall()]
    tree = {}
    for db in dbs[:20]:      # cap at 20 dbs for speed
        try:
            cur.execute(f'SHOW SCHEMAS IN DATABASE "{db}"')
            schemas = [r[1] for r in cur.fetchall()]
            tree[db] = {}
            for sc in schemas[:30]:
                try:
                    cur.execute(f'SHOW TABLES IN "{db}"."{sc}"')
                    tables = [r[1] for r in cur.fetchall()]
                    tree[db][sc] = tables[:100]
                except Exception:
                    tree[db][sc] = []
        except Exception:
            tree[db] = {}
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

        if parsed.path in ("/", "/index.html"):
            html = Path(__file__).parent / "index.html"
            body = html.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/api/schemas":
            try:
                self.send_json(get_schemas())
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
    # validate config
    if ACCOUNT == "your-account-identifier":
        print("⚠️  Edit SNOWFLAKE_ACCOUNT / SNOWFLAKE_USER in app.py (or set env vars) before running.\n")

    server = HTTPServer(("localhost", PORT), Handler)
    url    = f"http://localhost:{PORT}"
    print(f"🚀  SnowSheet running at {url}")
    print("    Press Ctrl+C to stop.\n")

    threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋  Stopped.")
        if _conn:
            _conn.close()
