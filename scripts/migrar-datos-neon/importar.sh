#!/usr/bin/env bash
# ============================================================================
# SGCBP - Importacion de los datos locales en el destino (Neon).
#
# Secuencia: copia de seguridad -> preflight -> importacion transaccional ->
# verificacion. Si cualquier paso falla, no se importa nada.
#
# Uso (desde la raiz del repo, en Git Bash):
#
#     # 1) Exportar desde la base local
#     scripts/migrar-datos-neon/exportar.sh
#
#     # 2) Indicar la URL de Neon SIN dejarla en el historial ni en el repo
#     read -rs -p "URL de Neon: " NEON_DATABASE_URL; export NEON_DATABASE_URL; echo
#
#     # 3) Importar (hace backup, importa y verifica)
#     scripts/migrar-datos-neon/importar.sh
#
# Variables de entorno opcionales:
#     NEON_DATABASE_URL  cadena de conexion del destino (OBLIGATORIA)
#     PG_CONTAINER       contenedor con psql (por defecto sgcbp_db)
#     OUT_DIR            carpeta con los CSV exportados
#                       (por defecto scripts/migrar-datos-neon/salida)
#     BACKUP_DIR         carpeta de las copias de seguridad
#                       (por defecto scripts/migrar-datos-neon/salida/backups)
#
# La URL NUNCA se escribe en el repositorio ni se imprime: se pasa al
# contenedor por stdin y se borra al terminar.
# ============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HERE="$ROOT/scripts/migrar-datos-neon"
OUT_DIR="${OUT_DIR:-$HERE/salida}"
BACKUP_DIR="${BACKUP_DIR:-$OUT_DIR/backups}"
PG_CONTAINER="${PG_CONTAINER:-sgcbp_db}"

PRODUCTS_CSV="$OUT_DIR/sgcbp_products.csv"
SCANS_CSV="$OUT_DIR/sgcbp_scans.csv"
STAMP="$(date -u +%Y%m%d_%H%M%S)"

log()  { echo "[migrar] $*"; }
fail() { echo "[migrar] ERROR: $*" >&2; exit 1; }

[ -n "${NEON_DATABASE_URL:-}" ] || fail "Falta la variable NEON_DATABASE_URL. Ejemplo:
    read -rs -p \"URL de Neon: \" NEON_DATABASE_URL; export NEON_DATABASE_URL; echo"
[ -f "$PRODUCTS_CSV" ] || fail "No existe '$PRODUCTS_CSV'. Ejecuta antes: scripts/migrar-datos-neon/exportar.sh"
[ -f "$SCANS_CSV" ]   || fail "No existe '$SCANS_CSV'. Ejecuta antes: scripts/migrar-datos-neon/exportar.sh"

docker inspect -f '{{.State.Running}}' "$PG_CONTAINER" 2>/dev/null | grep -qx true \
  || fail "El contenedor '$PG_CONTAINER' no esta en marcha"

mkdir -p "$BACKUP_DIR"

# --- 1. Copia de seguridad del DESTINO (antes de tocar nada) ----------------
log "1/4 Copia de seguridad del destino..."
docker exec -i "$PG_CONTAINER" sh -c 'cat > /tmp/sgcbp_neon.env' <<< "NEON_DATABASE_URL='$NEON_DATABASE_URL'"
# psql y pg_dump son clientes libpq: no entienden el sufijo "+psycopg" de
# SQLAlchemy, asi que se quita para la conexion.
docker exec "$PG_CONTAINER" sh -c \
  'set -a; . /tmp/sgcbp_neon.env; set +a;
   URL="${NEON_DATABASE_URL/postgresql+psycopg:/postgresql:}";
   pg_dump "$URL" --format=custom --file=/tmp/sgcbp_neon_backup.dump' \
  || fail "Fallo el pg_dump del destino. Abortado SIN tocar nada."
docker cp "$PG_CONTAINER":/tmp/sgcbp_neon_backup.dump "$BACKUP_DIR/neon_antes_${STAMP}.dump" >/dev/null
BACKUP_FILE="$BACKUP_DIR/neon_antes_${STAMP}.dump"
log "   Copia de seguridad: $BACKUP_FILE ($(du -h "$BACKUP_FILE" | cut -f1))"

# --- 2. Copiar los ficheros al contenedor ------------------------------------
docker cp "$PRODUCTS_CSV" "$PG_CONTAINER":/tmp/sgcbp_products.csv >/dev/null
docker cp "$SCANS_CSV"   "$PG_CONTAINER":/tmp/sgcbp_scans.csv   >/dev/null
docker cp "$HERE/importar.sql" "$PG_CONTAINER":/tmp/sgcbp_importar.sql >/dev/null

# --- 3. Importacion transaccional -------------------------------------------
log "2/4 Importacion (transaccion)..."
IMPORT_OK=0
docker exec "$PG_CONTAINER" sh -c \
  'set -a; . /tmp/sgcbp_neon.env; set +a;
   URL="${NEON_DATABASE_URL/postgresql+psycopg:/postgresql:}";
   psql "$URL" -v ON_ERROR_STOP=1 -f /tmp/sgcbp_importar.sql' \
  && IMPORT_OK=1 || IMPORT_OK=0

if [ "$IMPORT_OK" -ne 1 ]; then
  echo
  log "La importacion ha fallado y se ha DESHECIDO (transaccion): no se ha modificado nada."
  log "La copia de seguridad previo sigue en: $BACKUP_FILE"
  docker exec "$PG_CONTAINER" rm -f /tmp/sgcbp_neon.env /tmp/sgcbp_products.csv /tmp/sgcbp_scans.csv /tmp/sgcbp_importar.sql
  exit 1
fi

# --- 4. Verificacion posterior ------------------------------------------------
log "3/4 Verificacion posterior..."
docker exec -i "$PG_CONTAINER" sh -c \
  'set -a; . /tmp/sgcbp_neon.env; set +a;
   URL="${NEON_DATABASE_URL/postgresql+psycopg:/postgresql:}";
   psql "$URL" -v ON_ERROR_STOP=1 -f -' < "$HERE/verificar.sql"

# --- 5. Limpieza --------------------------------------------------------------
docker exec "$PG_CONTAINER" rm -f /tmp/sgcbp_neon.env /tmp/sgcbp_products.csv /tmp/sgcbp_scans.csv /tmp/sgcbp_importar.sql

log "4/4 Importacion finalizada."
log "   Copia de seguridad previa: $BACKUP_FILE"
log "   Reversion: scripts/migrar-datos-neon/revertir.sh"
