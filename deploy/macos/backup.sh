#!/usr/bin/env bash
# Nightly SQLite backup of the live DB into backups/, keeping 30 days. Run by com.oscout.backup (16:00 Mon–Fri).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
url="$(grep -E '^DATABASE_URL=' "$ROOT/backend/.env" 2>/dev/null | cut -d= -f2- || true)"
db="${url#sqlite:///}"; db="${db:-./oscout_v2_live.db}"
case "$db" in /*) ;; *) db="$ROOT/backend/${db#./}" ;; esac
[ -f "$db" ] || { echo "$(date '+%F %T') no DB at $db" >&2; exit 1; }
mkdir -p "$ROOT/backups"
out="$ROOT/backups/$(basename "${db%.db}")_$(date +%F).db"
/usr/bin/sqlite3 "$db" ".backup '$out'"
find "$ROOT/backups" -name '*.db' -mtime +30 -delete
echo "$(date '+%F %T') backed up $db -> $out"
