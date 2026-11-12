#!/usr/bin/env bash
# ============================================================================
# SGCBP - ENSAYO de la migracion sobre una base de datos desechable local.
#
# Ejecuta TODO el procedimiento (exportar -> backup -> importar -> verificar ->
# reimportar (idempotencia) -> revertir) contra una base de datos temporal
# que se crea y se destruye aqui mismo. NO toca Neon ni la base de datos
# local de trabajo.
#
# Uso (desde la raiz del repo, en Git Bash):
#     scripts/migrar-datos-neon/rehearsal.sh
#
# Sirve para comprobar que el procedimiento funciona antes de apuntarlo a
# Neon. Es exactamente el mismo codigo que se ejecutara contra el destino.
# ============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HERE="$ROOT/scripts/migrar-datos-neon"
PG_CONTAINER="${PG_CONTAINER:-sgcbp_db}"
PG_USER="${PG_USER:-sgcbp}"
REHEARSAL_DB="sgcbp_rehearsal"

log()  { echo ""; echo "[ensayo] $*"; }
fail() { echo "[ensayo] ERROR: $*" >&2; exit 1; }

cleanup() {
  docker exec "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -q -U "$PG_USER" -d postgres \
    -c "DROP DATABASE IF EXISTS $REHEARSAL_DB;" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker inspect -f '{{.State.Running}}' "$PG_CONTAINER" 2>/dev/null | grep -qx true \
  || fail "El contenedor '$PG_CONTAINER' no esta en marcha"

# --- 1. Base de datos de ensayo (vacia, como la de Neon tras el seed) --------
log "1/6 Creando la base de datos de ensayo '$REHEARSAL_DB'"
docker exec "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -q -U "$PG_USER" -d postgres \
  -c "DROP DATABASE IF EXISTS $REHEARSAL_DB;" \
  -c "CREATE DATABASE $REHEARSAL_DB OWNER $PG_USER;"
REHEARSAL_URL="postgresql+psycopg://$PG_USER:$PG_USER@localhost:5432/$REHEARSAL_DB"

# Mismo esquema y mismo seed que en Neon.
(cd "$ROOT/backend" && DATABASE_URL="$REHEARSAL_URL" .venv/Scripts/python.exe -m alembic upgrade head >/dev/null)
(cd "$ROOT/backend" && DATABASE_URL="$REHEARSAL_URL" SEED_ADMIN_PASSWORD=admin123 \
  .venv/Scripts/python.exe -m app.seed >/dev/null)
log "   Esquema aplicado y seed ejecutado (workspace 1 + usuario 1)"

# --- 2. Exportacion desde la base local --------------------------------------
log "2/6 Exportando desde la base de datos local"
"$HERE/exportar.sh" > /dev/null
log "   CSV exportados"

# --- 3. Importacion (con backup previo) --------------------------------------
log "3/6 Importando en la base de datos de ensayo"
NEON_DATABASE_URL="$REHEARSAL_URL" "$HERE/importar.sh" > /tmp/sgcbp_rehearsal_import.log 2>&1 \
  || { cat /tmp/sgcbp_rehearsal_import.log; fail "La importacion ha fallado"; }
grep -E "productos_importados|escaneos_importados|^ +[0-9]+$" /tmp/sgcbp_rehearsal_import.log | head -6 || true
log "   Importacion correcta"

# --- 4. Comprobacion del contenido -------------------------------------------
log "4/6 Comprobando el contenido importado"
COUNTS=$(docker exec "$PG_CONTAINER" psql -t -A -U "$PG_USER" -d "$REHEARSAL_DB" -c \
  "SELECT (SELECT count(*) FROM products WHERE id IN (1,2,3)) || ',' || (SELECT count(*) FROM scans WHERE id IN (1,2,3,4,24));")
[ "$COUNTS" = "3,5" ] || fail "Se esperaban 3 productos y 5 escaneos; hay '$COUNTS'"
ORPHANS=$(docker exec "$PG_CONTAINER" psql -t -A -U "$PG_USER" -d "$REHEARSAL_DB" -c \
  "SELECT count(*) FROM scans s LEFT JOIN products p ON p.id = s.product_id WHERE p.id IS NULL;")
[ "$ORPHANS" = "0" ] || fail "Hay escaneos huerfanos: $ORPHANS"
E2E=$(docker exec "$PG_CONTAINER" psql -t -A -U "$PG_USER" -d "$REHEARSAL_DB" -c \
  "SELECT count(*) FROM products WHERE barcode_raw LIKE 'E2E%';")
[ "$E2E" = "0" ] || fail "Han entrado $E2E productos E2E"
log "   3 productos, 5 escaneos, 0 huerfanos, 0 residuos E2E"

# --- 5. Idempotencia: reimportar no debe duplicar ---------------------------
log "5/6 Reimportando (debe ser idempotente: 3 productos y 5 escaneos)"
NEON_DATABASE_URL="$REHEARSAL_URL" "$HERE/importar.sh" > /tmp/sgcbp_rehearsal_reimport.log 2>&1 \
  || { tail -20 /tmp/sgcbp_rehearsal_reimport.log; fail "La reimportacion ha fallado"; }
COUNTS2=$(docker exec "$PG_CONTAINER" psql -t -A -U "$PG_USER" -d "$REHEARSAL_DB" -c \
  "SELECT (SELECT count(*) FROM products WHERE id IN (1,2,3)) || ',' || (SELECT count(*) FROM scans WHERE id IN (1,2,3,4,24)) || ',' || (SELECT count(*) FROM products);")
[ "$COUNTS2" = "3,5,3" ] || fail "La reimportacion no es idempotente: '$COUNTS2'"
log "   Idempotente: sigue habiendo 3 productos y 5 escaneos"

# --- 6. Reversion -------------------------------------------------------------
log "6/6 Revirtiendo"
printf 'BORRAR\n' | NEON_DATABASE_URL="$REHEARSAL_URL" "$HERE/revertir.sh" > /tmp/sgcbp_rehearsal_revert.log 2>&1 \
  || { tail -20 /tmp/sgcbp_rehearsal_revert.log; fail "La reversion ha fallado"; }
COUNTS3=$(docker exec "$PG_CONTAINER" psql -t -A -U "$PG_USER" -d "$REHEARSAL_DB" -c \
  "SELECT (SELECT count(*) FROM products) || ',' || (SELECT count(*) FROM scans);")
[ "$COUNTS3" = "0,0" ] || fail "La reversion no ha borrado todo: '$COUNTS3'"
log "   Reversion correcta: la base de datos de ensayo queda vacia"

echo ""
echo "================================================================"
echo " ENSAYO COMPLETO CORRECTO"
echo "   export -> backup -> import -> verificar -> reimport -> revertir"
echo " La base de datos de ensayo se destruye al salir."
echo "================================================================"
