#!/usr/bin/env bash
# ============================================================================
# SGCBP - Reversion de la importacion de datos en el destino.
#
# Borra SOLO los registros importados por esta migracion (ids 1, 2 y 3 de
# products; ids 1, 2, 3, 4 y 24 de scans) y reinicia las secuencias.
# Es transaccional: si algo falla, no borra nada.
#
# No toca workspaces ni users (la contrasena del admin no se ve afectada).
# Los productos y escaneos creados DESPUES de la importacion tienen ids
# distintos (las secuencias se reiniciaron) y NO se tocan.
#
# Uso (desde la raiz del repo, en Git Bash):
#     read -rs -p "URL de Neon: " NEON_DATABASE_URL; export NEON_DATABASE_URL; echo
#     scripts/migrar-datos-neon/revertir.sh
#
# Si la base de datos esta muy danada, la alternativa nuclear es restaurar la
# copia de seguridad:
#     scripts/migrar-datos-neon/restaurar.sh <fichero.dump>
# ============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HERE="$ROOT/scripts/migrar-datos-neon"
PG_CONTAINER="${PG_CONTAINER:-sgcbp_db}"
PRODUCT_IDS="${PRODUCT_IDS:-1,2,3}"
SCAN_IDS="${SCAN_IDS:-1,2,3,4,24}"

log()  { echo "[revertir] $*"; }
fail() { echo "[revertir] ERROR: $*" >&2; exit 1; }

[ -n "${NEON_DATABASE_URL:-}" ] || fail "Falta NEON_DATABASE_URL"

docker exec -i "$PG_CONTAINER" sh -c 'cat > /tmp/sgcbp_neon.env' <<< "NEON_DATABASE_URL='$NEON_DATABASE_URL'"

echo
log "Se va a BORRAR del destino:"
log "  products con id IN ($PRODUCT_IDS)"
log "  scans    con id IN ($SCAN_IDS)"
echo
read -r -p "  Escribe BORRAR en mayusculas para confirmar: " CONFIRM
[ "$CONFIRM" = "BORRAR" ] || { log "Cancelado: no se ha modificado nada."; docker exec "$PG_CONTAINER" rm -f /tmp/sgcbp_neon.env; exit 1; }

docker exec -i "$PG_CONTAINER" sh -c \
  'set -a; . /tmp/sgcbp_neon.env; set +a;
   URL="${NEON_DATABASE_URL/postgresql+psycopg:/postgresql:}";
   psql "$URL" -v ON_ERROR_STOP=1 -f -' <<SQL
BEGIN;
SET LOCAL TIME ZONE 'UTC';

DELETE FROM scans    WHERE id IN ($SCAN_IDS);
DELETE FROM products WHERE id IN ($PRODUCT_IDS);

SELECT setval(pg_get_serial_sequence('products', 'id'),
              GREATEST((SELECT COALESCE(max(id), 1) FROM products), 1), true);
SELECT setval(pg_get_serial_sequence('scans', 'id'),
              GREATEST((SELECT COALESCE(max(id), 1) FROM scans), 1), true);

COMMIT;

\echo '--- Reversion aplicada ---'
SELECT count(*) AS productos_restantes FROM products WHERE id IN ($PRODUCT_IDS);
SELECT count(*) AS escaneos_restantes  FROM scans    WHERE id IN ($SCAN_IDS);
SQL

docker exec "$PG_CONTAINER" rm -f /tmp/sgcbp_neon.env
log "Hecho. Comprueba el destino con: scripts/migrar-datos-neon/verificar.sql"
