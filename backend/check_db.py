"""
Database Inspector
==================
Checks whether shopify_auth.db exists and shows all stored shop installations.

Usage (from the backend/ directory):
    python check_db.py
"""

import os
import sqlite3
from pathlib import Path

# ── Colour helpers ────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

DB_PATH = Path(__file__).parent / "shopify_auth.db"

print(f"\n{BOLD}{CYAN}═══════════════════════════════════════════{RESET}")
print(f"{BOLD}{CYAN}   Shopify Auth — Database Inspector       {RESET}")
print(f"{BOLD}{CYAN}═══════════════════════════════════════════{RESET}\n")

# ── 1. Does the file exist? ───────────────────────────────────────────────────
print(f"  DB path : {DB_PATH}")

if not DB_PATH.exists():
    print(f"\n  {RED}✗ Database file NOT found.{RESET}")
    print(f"    This means the server has never started successfully, or")
    print(f"    it was started from a different directory.\n")
    raise SystemExit(1)

size_kb = DB_PATH.stat().st_size / 1024
print(f"  {GREEN}✔ Database file exists{RESET}  ({size_kb:.1f} KB)\n")

# ── 2. Connect and list tables ────────────────────────────────────────────────
con = sqlite3.connect(DB_PATH)
cur = con.cursor()

cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [row[0] for row in cur.fetchall()]

if not tables:
    print(f"  {YELLOW}⚠ Database is empty — no tables found.{RESET}")
    print(f"    The server creates tables on first startup.\n")
    con.close()
    raise SystemExit(0)

print(f"  {BOLD}Tables found:{RESET} {', '.join(tables)}\n")

# ── 3. Show shop_installations rows ──────────────────────────────────────────
TABLE = "shop_installations"

if TABLE not in tables:
    print(f"  {YELLOW}⚠ Table '{TABLE}' does not exist yet.{RESET}\n")
    con.close()
    raise SystemExit(0)

cur.execute(f"SELECT COUNT(*) FROM {TABLE}")
total = cur.fetchone()[0]

print(f"{'─' * 45}")
print(f"  {BOLD}shop_installations{RESET}  ({total} row{'s' if total != 1 else ''})")
print(f"{'─' * 45}")

if total == 0:
    print(f"\n  {YELLOW}No installations recorded yet.{RESET}")
    print(f"  The OAuth callback has not run successfully, or")
    print(f"  the database was just created.\n")
else:
    cur.execute(f"""
        SELECT
            shop_domain,
            access_mode,
            scope,
            is_active,
            associated_user_id,
            installed_at,
            updated_at,
            length(access_token) AS token_length
        FROM {TABLE}
        ORDER BY installed_at DESC
    """)
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]

    for i, row in enumerate(rows, start=1):
        record = dict(zip(cols, row))
        active_label = f"{GREEN}active{RESET}" if record["is_active"] else f"{RED}inactive{RESET}"
        print(f"\n  {BOLD}#{i}  {record['shop_domain']}{RESET}")
        print(f"       access_mode      : {record['access_mode']}")
        print(f"       scope            : {record['scope'] or '(none)'}")
        print(f"       status           : {active_label}")
        print(f"       associated_user  : {record['associated_user_id'] or '(none — offline token)'}")
        print(f"       token stored     : {GREEN}YES{RESET} ({record['token_length']} chars)")
        print(f"       installed_at     : {record['installed_at']}")
        print(f"       updated_at       : {record['updated_at']}")

print(f"\n{'─' * 45}\n")
con.close()
