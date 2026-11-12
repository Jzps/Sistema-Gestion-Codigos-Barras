#!/usr/bin/env bash
# ============================================================================
# SGCBP - Exportacion de los datos REALES de la base de datos local.
#
# Genera dos CSV (productos y escaneos) y un manifiesto con las sumas
# SHA-256. Solo exporta los registros indicados por PRODUCT_IDS / SCAN_IDS
# (por defecto: los 3 productos y los 5 escaneos reales). Los registros de
# prueba E2E quedan excluidos por validacion: si alguno se colara en la
# seleccion, el script aborta.
#
# Uso (desde la raiz del repo, en Git Bash):
#     scripts/migrar-datos-neon/exportar.sh
#
# Variables de entorno opcionales:
#     PG_CONTAINER  contenedor con el Postgres local (por defecto sgcbp_db)
#     PG_USER       usuario local (por defecto sgcbp)
#     PG_DB         base de datos local (por defecto sgcbp)
#     PRODUCT_IDS   ids de producto a exportar (por defecto "1,2,3")
#     SCAN_IDS      ids de escaneo a exportar (por defecto "1,2,3,4,24")
#     OUT_DIR       carpeta de salida (por defecto scripts/migrar-datos-neon/salida)
# ============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HERE="$ROOT/scripts/migrar-datos-neon"
OUT_DIR="${OUT_DIR:-$HERE/salida}"

PG_CONTAINER="${PG_CONTAINER:-sgcbp_db}"
PG_USER="${PG_USER:-sgcbp}"
PG_DB="${PG_DB:-sgcbp}"
PRODUCT_IDS="${PRODUCT_IDS:-1,2,3}"
SCAN_IDS="${SCAN_IDS:-1,2,3,4,24}"

EXPECTED_PRODUCTS=3
EXPECTED_SCANS=5
SOURCE_WORKSPACE_ID=1
SOURCE_USER_ID=1

log()  { echo "[migrar] $*"; }
fail() { echo "[migrar] ERROR: $*" >&2; exit 1; }

# --- 0. Comprobaciones previas -----------------------------------------------
docker inspect -f '{{.State.Running}}' "$PG_CONTAINER" 2>/dev/null | grep -qx true \
  || fail "El contenedor '$PG_CONTAINER' no esta en marcha. Levanta PostgreSQL con: docker compose up -d"

mkdir -p "$OUT_DIR"
PRODUCTS_CSV="$OUT_DIR/sgcbp_products.csv"
SCANS_CSV="$OUT_DIR/sgcbp_scans.csv"
MANIFEST="$OUT_DIR/manifiesto.txt"

log "Origen : contenedor=$PG_CONTAINER base=$PG_DB usuario=$PG_USER"
log "Productos a exportar: $PRODUCT_IDS   |   Escaneos a exportar: $SCAN_IDS"

# --- 1. Validacion de la seleccion (aborta si algo no cuadra) ----------------
# Se ejecuta DENTRO de la base de datos para no depender de herramientas
# externas. Cualquier EXCEPTION aborta el script (ON_ERROR_STOP).
docker exec -i "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -q -U "$PG_USER" -d "$PG_DB" <<SQL
DO \$\$
DECLARE n int;
BEGIN
  SELECT count(*) INTO n FROM products WHERE id IN ($PRODUCT_IDS);
  IF n <> $EXPECTED_PRODUCTS THEN
    RAISE EXCEPTION 'Se esperaban $EXPECTED_PRODUCTS productos y hay %', n;
  END IF;

  SELECT count(*) INTO n FROM scans WHERE id IN ($SCAN_IDS);
  IF n <> $EXPECTED_SCANS THEN
    RAISE EXCEPTION 'Se esperaban $EXPECTED_SCANS escaneos y hay %', n;
  END IF;

  SELECT count(*) INTO n FROM products WHERE id IN ($PRODUCT_IDS) AND barcode_raw LIKE 'E2E%';
  IF n > 0 THEN
    RAISE EXCEPTION 'La seleccion contiene % producto(s) de prueba E2E: abortando', n;
  END IF;

  SELECT count(*) INTO n FROM scans s
    JOIN products p ON p.id = s.product_id
   WHERE s.id IN ($SCAN_IDS) AND p.barcode_raw LIKE 'E2E%';
  IF n > 0 THEN
    RAISE EXCEPTION 'La seleccion contiene % escaneo(s) de prueba E2E: abortando', n;
  END IF;

  SELECT count(*) INTO n FROM products WHERE id IN ($PRODUCT_IDS) AND workspace_id <> $SOURCE_WORKSPACE_ID;
  IF n > 0 THEN
    RAISE EXCEPTION 'Hay % producto(s) con workspace_id distinto de $SOURCE_WORKSPACE_ID', n;
  END IF;

  SELECT count(*) INTO n FROM scans
   WHERE id IN ($SCAN_IDS) AND (workspace_id <> $SOURCE_WORKSPACE_ID OR user_id <> $SOURCE_USER_ID);
  IF n > 0 THEN
    RAISE EXCEPTION 'Hay % escaneo(s) con workspace_id/user_id distinto de $SOURCE_WORKSPACE_ID/$SOURCE_USER_ID', n;
  END IF;

  SELECT count(*) INTO n FROM scans s WHERE s.id IN ($SCAN_IDS)
    AND NOT EXISTS (SELECT 1 FROM products p WHERE p.id = s.product_id AND p.id IN ($PRODUCT_IDS));
  IF n > 0 THEN
    RAISE EXCEPTION 'Hay % escaneo(s) cuyo producto no esta entre los exportados', n;
  END IF;

  SELECT count(*) INTO n FROM scans s WHERE s.id IN ($SCAN_IDS) AND s.user_id NOT IN (SELECT id FROM users);
  IF n > 0 THEN
    RAISE EXCEPTION 'Hay % escaneo(s) cuyo user_id no existe en users', n;
  END IF;
END
\$\$;
SQL
log "Validacion de origen OK ($EXPECTED_PRODUCTS productos, $EXPECTED_SCANS escaneos, sin E2E)"

# --- 2. Exportacion a CSV ----------------------------------------------------
# SET TIME ZONE UTC para que las marcas de tiempo se exporten siempre en UTC
# (el destino puede tener otra zona configurada).
docker exec "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -q -U "$PG_USER" -d "$PG_DB" -c \
  "SET TIME ZONE 'UTC';" -c \
  "\copy (SELECT id, workspace_id, barcode_raw, barcode_type, product_identifier, product_name, weight_value, weight_unit, weight_kg, created_at, updated_at FROM products WHERE id IN ($PRODUCT_IDS) ORDER BY id) TO stdout WITH (FORMAT csv, HEADER true)" \
  > "$PRODUCTS_CSV"

docker exec "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -q -U "$PG_USER" -d "$PG_DB" -c \
  "SET TIME ZONE 'UTC';" -c \
  "\copy (SELECT id, workspace_id, product_id, user_id, scanned_at FROM scans WHERE id IN ($SCAN_IDS) ORDER BY id) TO stdout WITH (FORMAT csv, HEADER true)" \
  > "$SCANS_CSV"

PRODUCT_ROWS=$(( $(wc -l < "$PRODUCTS_CSV") - 1 ))   # -1 = cabecera
SCAN_ROWS=$(( $(wc -l < "$SCANS_CSV") - 1 ))
[ "$PRODUCT_ROWS" -eq "$EXPECTED_PRODUCTS" ] || fail "El CSV de productos tiene $PRODUCT_ROWS filas (se esperaban $EXPECTED_PRODUCTS)"
[ "$SCAN_ROWS" -eq "$EXPECTED_SCANS" ] || fail "El CSV de escaneos tiene $SCAN_ROWS filas (se esperaban $EXPECTED_SCANS)"

# --- 3. Manifiesto -----------------------------------------------------------
{
  echo "# Manifiesto de exportacion SGCBP"
  echo "generado=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "origen=contenedor:$PG_CONTAINER base:$PG_DB usuario:$PG_USER"
  echo "product_ids=$PRODUCT_IDS"
  echo "scan_ids=$SCAN_IDS"
  echo "workspace_id_origen=$SOURCE_WORKSPACE_ID"
  echo "user_id_origen=$SOURCE_USER_ID"
  echo "productos=$PRODUCT_ROWS"
  echo "escaneos=$SCAN_ROWS"
  echo "productos_sha256=$(sha256sum "$PRODUCTS_CSV" | cut -d' ' -f1)"
  echo "escaneos_sha256=$(sha256sum "$SCANS_CSV" | cut -d' ' -f1)"
} > "$MANIFEST"

log "Exportado: $PRODUCTS_CSV ($PRODUCT_ROWS productos)"
log "Exportado: $SCANS_CSV ($SCAN_ROWS escaneos)"
log "Manifiesto: $MANIFEST"
echo
cat "$MANIFEST"
