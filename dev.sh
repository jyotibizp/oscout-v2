#!/usr/bin/env bash
# Run the oscout dev servers detached in the background.
#
#   ./dev.sh start|stop|restart|status [backend|frontend|all]
#   ./dev.sh logs [backend|frontend|all] [-n LINES]   (follows; Ctrl-C to quit)
#
# PIDs and logs live in .run/ (gitignored). Env overrides:
#   BACKEND_PORT (8000)  FRONTEND_PORT (5173)  BACKEND_RELOAD (1 = uvicorn --reload)
set -u

ROOT="$(cd "$(dirname "$0")" && pwd)"
RUN_DIR="$ROOT/.run"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
BACKEND_RELOAD="${BACKEND_RELOAD:-1}"

mkdir -p "$RUN_DIR"

pid_file() { echo "$RUN_DIR/$1.pid"; }
# Port the running instance was started on (env may differ now).
live_port() { cat "$RUN_DIR/$1.port" 2>/dev/null || port_of "$1"; }
log_file() { echo "$RUN_DIR/$1.log"; }
port_of()  { if [ "$1" = backend ]; then echo "$BACKEND_PORT"; else echo "$FRONTEND_PORT"; fi; }

# PID from the pid file, if that process is still alive.
running_pid() {
  local f; f="$(pid_file "$1")"
  [ -f "$f" ] || return 1
  local pid; pid="$(cat "$f")"
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then echo "$pid"; return 0; fi
  rm -f "$f" "$RUN_DIR/$1.port"; return 1
}

port_owner() { lsof -nP -iTCP:"$1" -sTCP:LISTEN -t 2>/dev/null | head -1; }

# pid plus all descendants (uvicorn --reload and vite spawn children).
tree() {
  local pid="$1" child
  for child in $(pgrep -P "$pid" 2>/dev/null); do tree "$child"; done
  echo "$pid"
}

start_one() {
  local svc="$1" port pid owner
  port="$(port_of "$svc")"
  if pid="$(running_pid "$svc")"; then
    echo "$svc: already running (pid $pid, port $(live_port "$svc"))"; return 0
  fi
  owner="$(port_owner "$port")"
  if [ -n "$owner" ]; then
    echo "$svc: port $port is in use by pid $owner ($(ps -o comm= -p "$owner")), not started" >&2
    return 1
  fi

  case "$svc" in
    backend)
      [ -x "$ROOT/backend/.venv/bin/uvicorn" ] || { echo "backend: backend/.venv missing, see README" >&2; return 1; }
      local reload=""; [ "$BACKEND_RELOAD" = 1 ] && reload="--reload"
      (cd "$ROOT/backend" && exec nohup .venv/bin/uvicorn app.main:app --port "$port" $reload) \
        >>"$(log_file backend)" 2>&1 </dev/null &
      ;;
    frontend)
      [ -x "$ROOT/frontend/node_modules/.bin/vite" ] || { echo "frontend: run npm install in frontend/" >&2; return 1; }
      (cd "$ROOT/frontend" && exec nohup node_modules/.bin/vite --port "$port" --strictPort) \
        >>"$(log_file frontend)" 2>&1 </dev/null &
      ;;
  esac
  pid=$!
  echo "$pid" >"$(pid_file "$svc")"
  echo "$port" >"$RUN_DIR/$svc.port"

  # Wait up to 20s for the port to come up.
  local i
  for i in $(seq 1 40); do
    if ! kill -0 "$pid" 2>/dev/null; then
      rm -f "$(pid_file "$svc")" "$RUN_DIR/$svc.port"
      echo "$svc: exited during startup, last log lines:" >&2
      tail -n 20 "$(log_file "$svc")" >&2
      return 1
    fi
    [ -n "$(port_owner "$port")" ] && { echo "$svc: started (pid $pid) http://localhost:$port"; return 0; }
    sleep 0.5
  done
  echo "$svc: pid $pid running but port $port not listening yet, check ./dev.sh logs $svc" >&2
}

stop_one() {
  local svc="$1" pid pids i
  if ! pid="$(running_pid "$svc")"; then echo "$svc: not running"; return 0; fi
  pids="$(tree "$pid")"
  kill $pids 2>/dev/null
  for i in $(seq 1 20); do
    kill -0 $pids 2>/dev/null || break
    sleep 0.5
  done
  if kill -0 $pids 2>/dev/null; then kill -9 $pids 2>/dev/null; echo "$svc: force-killed"; fi
  rm -f "$(pid_file "$svc")" "$RUN_DIR/$svc.port"
  echo "$svc: stopped"
}

status_one() {
  local svc="$1" port pid owner
  port="$(port_of "$svc")"
  if pid="$(running_pid "$svc")"; then
    echo "$svc: running (pid $pid) http://localhost:$(live_port "$svc")  log: .run/$svc.log"
  else
    owner="$(port_owner "$port")"
    if [ -n "$owner" ]; then
      echo "$svc: not managed by dev.sh, but port $port is held by pid $owner"
    else
      echo "$svc: stopped"
    fi
  fi
}

cmd="${1:-}"; shift || true
target="all"
case "${1:-}" in backend|frontend|all) target="$1"; shift ;; esac
case "$target" in all) svcs="backend frontend" ;; *) svcs="$target" ;; esac

rc=0
case "$cmd" in
  start)   for s in $svcs; do start_one "$s" || rc=1; done ;;
  stop)    for s in $svcs; do stop_one "$s" || rc=1; done ;;
  restart) for s in $svcs; do stop_one "$s"; start_one "$s" || rc=1; done ;;
  status)  for s in $svcs; do status_one "$s"; done ;;
  logs)
    files=""; for s in $svcs; do touch "$(log_file "$s")"; files="$files $(log_file "$s")"; done
    exec tail -n "${2:-50}" -F $files ;;
  *)
    sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'
    exit 2 ;;
esac
exit $rc
