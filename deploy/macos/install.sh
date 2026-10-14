#!/usr/bin/env bash
# Run oscout as a macOS service (Tailscale sharing, backlog #13).
#
#   deploy/macos/install.sh            build the UI, install/reload the launchd agents
#   deploy/macos/install.sh uninstall  remove them (then ./dev.sh works again)
#   deploy/macos/install.sh status
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
AGENTS="$HOME/Library/LaunchAgents"
LABELS="com.oscout.backend com.oscout.backup com.oscout.awake"
DOMAIN="gui/$(id -u)"

unload() { launchctl bootout "$DOMAIN/$1" 2>/dev/null || true; }

case "${1:-install}" in
  install)
    [ -x "$ROOT/backend/.venv/bin/uvicorn" ] || { echo "backend/.venv missing, see README" >&2; exit 1; }
    (cd "$ROOT/frontend" && npm run build)
    "$ROOT/dev.sh" stop backend   # same port; dev.sh is for development only
    mkdir -p "$AGENTS" "$ROOT/.run"
    chmod +x "$ROOT/deploy/macos/backup.sh"
    for l in $LABELS; do
      unload "$l"
      sed "s#__ROOT__#$ROOT#g" "$ROOT/deploy/macos/$l.plist" >"$AGENTS/$l.plist"
      launchctl bootstrap "$DOMAIN" "$AGENTS/$l.plist"
      echo "loaded $l"
    done
    for i in $(seq 1 30); do curl -fs http://127.0.0.1:8000/health >/dev/null && break; sleep 1; done
    curl -fs http://127.0.0.1:8000/health >/dev/null && echo "backend up: http://127.0.0.1:8000" \
      || echo "backend not answering yet, see .run/service.log" >&2
    ;;
  uninstall)
    for l in $LABELS; do unload "$l"; rm -f "$AGENTS/$l.plist"; echo "removed $l"; done ;;
  status)
    for l in $LABELS; do launchctl print "$DOMAIN/$l" 2>/dev/null | grep -E '^\s*(state|pid|last exit code)' | sed "s/^/$l: /" || echo "$l: not loaded"; done ;;
  *) sed -n '2,7p' "$0" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
