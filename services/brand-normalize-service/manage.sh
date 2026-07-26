#!/usr/bin/env bash
# ============================================================================
#  brand-normalize-service  container manager (bash / Git-Bash on Windows)
#  usage:  bash manage.sh <start|stop|restart|status|logs|reload|update|health|build>
#  actions:
#    start    docker compose up -d --build  (+ wait healthy)
#    stop     docker compose down
#    restart  docker compose restart        (+ wait healthy)
#    status   container ps + /health summary
#    logs     follow logs
#    reload   hot-reload brand DB (no restart) via /api/brand/reload
#    update   refresh SCS token (best-effort) then hot-reload brand DB
#    health   raw /health JSON
#    build    build image only
#  NOTE: kept ASCII-only to avoid any encoding issues under Windows.
# ============================================================================
set -euo pipefail

# cd into the script's folder so docker compose resolves docker-compose.yml / .env
# relative to cwd (avoids MSYS double-converting a POSIX absolute path for docker.exe).
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="docker-compose.yml"
ENV_FILE=".env"
SERVICE="ofs-brand-normalize"
HEALTH_URL="http://localhost:8000/health"
RELOAD_URL="http://localhost:8000/api/brand/reload"
PORT=8000
TOKEN=""
SCS_SECRET_DIR=""
SCS_TOKEN_FILE=""

action="${1:-status}"

info()  { printf '[*] %s\n' "$1"; }
ok()    { printf '[+] %s\n' "$1"; }
warn()  { printf '[!] %s\n' "$1"; }
err()   { printf '[x] %s\n' "$1"; }

assert_docker() {
  if ! docker version >/dev/null 2>&1; then
    err "Docker is not running or not found in PATH. Start Docker Desktop first."
    exit 1
  fi
}

read_config() {
  if [ -f "$ENV_FILE" ]; then
    TOKEN="$(grep -m1 '^BRAND_API_TOKEN=' "$ENV_FILE" | cut -d= -f2- | tr -d '"')"
    SCS_SECRET_DIR="$(grep -m1 '^SCS_SECRET_DIR=' "$ENV_FILE" | cut -d= -f2- | tr -d '"')"
  fi
  [ -z "$SCS_SECRET_DIR" ] && SCS_SECRET_DIR="$HOME/.workbuddy/secrets"
  SCS_TOKEN_FILE="$SCS_SECRET_DIR/scs-token.json"
}

wait_healthy() {
  info "waiting for /health (max 30s)..."
  for i in $(seq 1 30); do
    resp="$(curl -s -m 2 "$HEALTH_URL" 2>/dev/null || true)"
    if printf '%s' "$resp" | grep -q '"status"[[:space:]]*:[[:space:]]*"ok"'; then
      brand="$(printf '%s' "$resp" | sed -n 's/.*"brand_count"[[:space:]]*:[[:space:]]*\([0-9]*\).*/\1/p')"
      scs="$(printf '%s' "$resp" | sed -n 's/.*"scs_enabled"[[:space:]]*:[[:space:]]*\([a-z]*\).*/\1/p')"
      ok "healthy after ${i}s: brand_count=$brand scs_enabled=$scs"
      return 0
    fi
    sleep 1
  done
  warn "service did not report healthy within 30s. Check 'bash manage.sh logs'."
  return 0
}

do_reload() {
  if [ -z "$TOKEN" ]; then
    err "BRAND_API_TOKEN missing in .env ; cannot call reload."
    exit 1
  fi
  info "hot-reloading brand DB (no container restart)..."
  resp="$(curl -s -m 10 -X POST "$RELOAD_URL" \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -d '{}' 2>/dev/null || true)"
  if [ -n "$resp" ]; then
    echo "$resp"
    ok "reload done."
  else
    err "reload failed (no response)."
    exit 1
  fi
}

case "$action" in
  start)
    assert_docker
    info "starting $SERVICE (detached)..."
    docker compose -f "$COMPOSE_FILE" up -d --build
    wait_healthy
    ;;
  stop)
    assert_docker
    info "stopping $SERVICE..."
    docker compose -f "$COMPOSE_FILE" down
    ok "stopped."
    ;;
  restart)
    assert_docker
    info "restarting $SERVICE..."
    docker compose -f "$COMPOSE_FILE" restart
    wait_healthy
    ;;
  status)
    assert_docker
    docker compose -f "$COMPOSE_FILE" ps
    echo
    resp="$(curl -s -m 3 "$HEALTH_URL" 2>/dev/null || true)"
    if [ -n "$resp" ]; then
      ok "health: $resp"
    else
      warn "service not reachable on port $PORT (is it started?)."
    fi
    ;;
  logs)
    assert_docker
    docker compose -f "$COMPOSE_FILE" logs -f --tail=200
    ;;
  health)
    resp="$(curl -s -m 3 "$HEALTH_URL" 2>/dev/null || true)"
    if [ -n "$resp" ]; then
      echo "$resp"
      ok "health check ok"
    else
      err "health check failed (no response)"
      exit 1
    fi
    ;;
  reload)
    assert_docker
    read_config
    do_reload
    ;;
  update)
    assert_docker
    read_config
    info "step 1/2: refreshing SCS token (needs Kimi WebBridge + SCS login)..."
    set +e
    python scripts/refresh_scs_token.py --out "$SCS_TOKEN_FILE" 2>&1
    rc=$?
    set -e
    if [ "$rc" -eq 0 ]; then
      ok "SCS token refreshed -> service hot-loads it on next request (mtime)."
    else
      warn "SCS token refresh failed (rc=$rc). WebBridge/browser not available or SCS login expired. Service keeps using the previous token until file updates."
    fi
    info "step 2/2: hot-reloading brand DB..."
    do_reload
    ;;
  build)
    assert_docker
    info "building image (no start)..."
    docker compose -f "$COMPOSE_FILE" build
    ok "build done."
    ;;
  *)
    warn "unknown action. use one of: start | stop | restart | status | logs | reload | update | health | build"
    exit 1
    ;;
esac
