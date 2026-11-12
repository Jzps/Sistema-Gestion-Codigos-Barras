#!/usr/bin/env bash
# ============================================================================
# SGCBP - Restauracion de la copia de seguridad del destino.
#
# Alternativa nuclear a revertir.sh: restaura el dump completo (esquema +
# datos) del destino, TAL COMO ESTABA antes de la importacion.
#
# ADVERTENCIA: borra el contenido actual del destino (DROP/CREATE de los
# objetos). USAR CON CUIDADO, solo si la reversion logica no basta.
#
# Uso (desde la raiz del repo, en Git Bash):
#     read -rs -p "URL de Neon: " NEON_DATABASE_URL; export NEON_DATABASE_URL; echo
#     scripts/migrar-datos-neon/restaurar.sh scripts/migrar-datos-neon/salida/backups/neon_antes_XXXX.dump
# ============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PG_CONTAINER="${PG_CONTAINER:-sgcbp_db}"
DUMP_FILE="${1:-}"

log()  { echo "[restaurar] $*"; }
fail() { echo "[restaurar] ERROR: $*" >&2; exit 1; }

[ -n "${NEON_DATABASE_URL:-}" ] || fail "Falta NEON_DATABASE_URL"
[ -n "$DUMP_FILE" ] || fail "Uso: restaurar.sh <fichero.dump>"
[ -f "$DUMP_FILE" ] || fail "No existe el fichero '$DUMP_FILE'"

docker inspect -f '{{.State.Running}}' "$PG_CONTAINER" 2>/dev/null | grep -qx true \
  || fail "El contenedor '$PG_CONTAINER' no esta en marcha"

echo
log "Se va a RESTAURAR el destino completo desde:"
log "  $DUMP_FILE"
echo
read -r -p "  Escribe RESTAURAR en mayusculas para confirmar: " CONFIRM
[ "$CONFIRM" = "RESTAURAR" ] || { log "Cancelado: no se ha modificado nada."; exit 1; }

docker cp "$DUMP_FILE" "$PG_CONTAINER":/tmp/sgcbp_restore.dump >/dev/null
docker exec -i "$PG_CONTAINER" sh -c 'cat > /tmp/sgcbp_neon.env' <<< "NEON_DATABASE_URL='$NEON_DATABASE_URL'"

docker exec "$PG_CONTAINER" sh -c \
  'set -a; . /tmp/sgcbp_neon.env; set +a;
   URL="${NEON_DATABASE_URL/postgresql+psycopg:/postgresql:}";
   pg_restore --clean --if-exists --no-owner --no-privileges --dbname="$URL" /tmp/sgcbp_restore.dump' \
  || fail "Fallo pg_restore. Revisa el estado del destino."

docker exec "$PG_CONTAINER" rm -f /tmp/sgcbp_neon.env /tmp/sgcbp_restore.dump
log "Restauracion completada. Comprueba el destino con: scripts/migrar-datos-neon/verificar.sql"
