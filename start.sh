#!/usr/bin/env bash
# ============================================================================
# SGCBP - Arranque del entorno de desarrollo local con un solo comando.
#
#   ./start.sh
#
# Levanta PostgreSQL (Docker Compose), aplica migraciones, carga el seed y
# arranca backend (FastAPI) y frontend (Angular) a la vez.
# CTRL+C detiene ambos procesos correctamente.
#
# Requisito: Git Bash en Windows, con Docker Desktop en ejecucion.
# ============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT/backend"
FRONTEND_DIR="$ROOT/frontend"
ENV_FILE="$ROOT/.env"

log()  { echo "[sgcbp] $*"; }
fail() { echo "[sgcbp] ERROR: $*" >&2; exit 1; }

# Lee una variable de .env (si existe) con valor por defecto.
read_env() {
  local key="$1" default="${2:-}" value=""
  if [[ -f "$ENV_FILE" ]]; then
    value="$(grep -E "^${key}=" "$ENV_FILE" | tail -n1 | cut -d= -f2- | tr -d '\r' | xargs || true)"
  fi
  printf '%s' "${value:-$default}"
}

# --- 1. PostgreSQL -----------------------------------------------------------
log "1/6 Comprobando PostgreSQL (Docker Compose)..."
if (cd "$ROOT" && docker compose ps --services --filter status=running 2>/dev/null | grep -qx db); then
  log "PostgreSQL ya esta en ejecucion."
else
  log "PostgreSQL no esta activo; levantandolo..."
  (cd "$ROOT" && docker compose up -d)
fi

PG_USER="$(read_env POSTGRES_USER sgcbp)"
PG_DB="$(read_env POSTGRES_DB sgcbp)"
log "Esperando a que PostgreSQL acepte conexiones..."
ready=0
for _ in $(seq 1 30); do
  if (cd "$ROOT" && docker compose exec -T db pg_isready -U "$PG_USER" -d "$PG_DB" >/dev/null 2>&1); then
    ready=1
    break
  fi
  sleep 1
done
[[ "$ready" == "1" ]] || fail "PostgreSQL no respondio a tiempo."

# --- 2. Entorno virtual ------------------------------------------------------
log "2/6 Verificando el entorno virtual del backend..."
VENV_ACTIVATE="$BACKEND_DIR/.venv/Scripts/activate"
[[ -f "$VENV_ACTIVATE" ]] || fail "No existe backend/.venv
  Crealo una vez con:
    cd backend && python -m venv .venv
    .venv/Scripts/python -m pip install -r requirements.txt"

# --- 3. Activar venv ---------------------------------------------------------
log "3/6 Activando el entorno virtual..."
# shellcheck disable=SC1090
source "$VENV_ACTIVATE"

# --- 4. Migraciones + seed (idempotentes) ------------------------------------
log "4/6 Aplicando migraciones y seed..."
cd "$BACKEND_DIR"
python -m alembic upgrade head
python -m app.seed

# --- 5. Dependencias del frontend --------------------------------------------
log "5/6 Verificando dependencias del frontend..."
[[ -d "$FRONTEND_DIR/node_modules" ]] || fail "No existe frontend/node_modules
  Instalalas una vez con: cd frontend && npm install"

# --- 6. Arranque de backend y frontend ---------------------------------------
log "6/6 Arrancando backend y frontend..."

# Sin puertos ocupados previamente: un ng serve que pregunta "(Y/n)" de forma
# interactiva colgaria el script.
busy_ports="$(powershell -NoProfile -Command '$r = @(); foreach ($p in 8000,4200) { if (Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue) { $r += $p } }; $r -join ", "')"
[[ -z "$busy_ports" ]] || fail "Puertos en uso: $busy_ports
  Cierra el proceso que los ocupa (¿otra instancia de start.sh?) y reintenta."

# Nota: uvicorn SIN --reload a proposito. El proceso "reloader" rearranca al
# servidor cuando muere por causas externas y rompe el apagado limpio con
# CTRL+C. Para recarga automatica, ejecuta uvicorn a mano (ver docs/setup.md).
(cd "$BACKEND_DIR" && exec python -m uvicorn app.main:app) &
BACKEND_PID=$!
(cd "$FRONTEND_DIR" && exec npm start) &
FRONTEND_PID=$!

cleanup() {
  trap - INT TERM EXIT
  echo
  log "Deteniendo backend y frontend..."
  for pid in "$BACKEND_PID" "$FRONTEND_PID"; do
    # taskkill /T elimina el arbol completo (hijos de uvicorn/npm) en Windows.
    taskkill //PID "$pid" //T //F >/dev/null 2>&1 || true
    kill "$pid" 2>/dev/null || true
  done
  # Barrido final por puerto por si algun hijo quedara huerfano.
  powershell -NoProfile -Command 'foreach ($p in 8000,4200) { Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue } }' >/dev/null 2>&1 || true
  log "Entorno detenido."
}
trap cleanup INT TERM EXIT

log "Esperando a que la API responda en /api/health..."
api_up=0
for _ in $(seq 1 30); do
  if curl -s -o /dev/null http://localhost:8000/api/health; then
    api_up=1
    break
  fi
  sleep 1
done
[[ "$api_up" == "1" ]] || fail "La API no respondio en /api/health."

log "Esperando a que Angular sirva en :4200..."
web_up=0
for _ in $(seq 1 60); do
  if curl -s -o /dev/null http://localhost:4200; then
    web_up=1
    break
  fi
  sleep 2
done
[[ "$web_up" == "1" ]] || fail "Angular no respondio en http://localhost:4200."

echo
log "Entorno listo:"
log "  Backend:  http://localhost:8000  (docs: http://localhost:8000/docs)"
log "  Frontend: http://localhost:4200"
log "Pulsa CTRL+C para detener ambos."

# Espera a que termine cualquiera de los dos; el trap limpia el resto.
wait -n "$BACKEND_PID" "$FRONTEND_PID" || true
