# SnowSheets

A minimal local SQL worksheet for Snowflake. Two files, no build step.

## Setup

1. Install the Snowflake Python connector:
   ```
   pip install snowflake-connector-python
   ```

2. Edit `app.py` — set your account and user at the top,
   or export environment variables:
   ```
   export SNOWFLAKE_ACCOUNT="myorg-myaccount"
   export SNOWFLAKE_USER="you@company.com"
   export SNOWFLAKE_WH="ANALYST_WH"     # optional
   export SNOWFLAKE_DB="PROD_DB"        # optional
   export SNOWFLAKE_SCHEMA="FRAUD"      # optional
   ```
   Your account identifier is in Snowflake URL: `https://<account>.snowflakecomputing.com`

3. Run:
   ```
   python app.py
   ```
   A browser tab opens automatically at http://localhost:8000.
   Your SSO login page will appear on first query.

## Features
- Tabbed worksheets (saved to browser localStorage)
- Schema browser with table click-to-insert
- Drag-to-resize results pane
- CSV export
- ⌘↵ / Ctrl+↵ to run
