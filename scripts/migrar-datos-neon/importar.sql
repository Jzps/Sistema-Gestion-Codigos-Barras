-- ============================================================================
-- SGCBP - Importacion de los datos reales al destino (Neon).
--
-- Caracteristicas:
--   * Una sola transaccion: si algo falla, no se importa NADA.
--   * Idempotente: se puede reejecutar sin duplicar (ON CONFLICT DO NOTHING).
--   * Preflight: comprueba workspace, usuario y conflictos ANTES de insertar;
--     si el destino no es el esperado, aborta.
--   * Excluye los registros de prueba E2E (validacion explicita).
--   * Conserva las relaciones: se importan los id explicitos, de modo que
--     scans.product_id sigue apuntando al producto correcto.
--   * Reinicia las secuencias: sin esto, el siguiente INSERT del backend
--     usaria un id ya ocupado.
--
-- Ficheros que espera en el contenedor (rutas fijas):
--   /tmp/sgcbp_products.csv   /tmp/sgcbp_scans.csv
--
-- Uso (lo invoca importar.sh; no lo ejecutes a mano salvo que sepas lo que haces):
--   psql "$NEON_DATABASE_URL" -v ON_ERROR_STOP=1 -f /tmp/sgcbp_importar.sql
-- ============================================================================
\set ON_ERROR_STOP on

BEGIN;

-- Todo el intercambio de marcas de tiempo se hace en UTC.
SET LOCAL TIME ZONE 'UTC';

-- ---------------------------------------------------------------------------
-- 1. Tablas de staging (temporales: se descartan al terminar la transaccion)
-- ---------------------------------------------------------------------------
CREATE TEMP TABLE stg_products (LIKE products INCLUDING DEFAULTS) ON COMMIT DROP;
CREATE TEMP TABLE stg_scans   (LIKE scans   INCLUDING DEFAULTS) ON COMMIT DROP;

\copy stg_products FROM '/tmp/sgcbp_products.csv' WITH (FORMAT csv, HEADER true)
\copy stg_scans   FROM '/tmp/sgcbp_scans.csv'   WITH (FORMAT csv, HEADER true)

-- ---------------------------------------------------------------------------
-- 2. Validacion del CONTENIDO importado (origen)
-- ---------------------------------------------------------------------------
DO $$
DECLARE n int;
BEGIN
  SELECT count(*) INTO n FROM stg_products;
  IF n <> 3 THEN
    RAISE EXCEPTION 'El CSV de productos debe traer 3 filas y trae %', n;
  END IF;

  SELECT count(*) INTO n FROM stg_scans;
  IF n <> 5 THEN
    RAISE EXCEPTION 'El CSV de escaneos debe traer 5 filas y trae %', n;
  END IF;

  SELECT count(*) INTO n FROM stg_products WHERE barcode_raw LIKE 'E2E%';
  IF n > 0 THEN
    RAISE EXCEPTION 'El CSV contiene % producto(s) de prueba E2E: abortando', n;
  END IF;

  SELECT count(*) INTO n FROM stg_scans s
    JOIN stg_products p ON p.id = s.product_id
   WHERE p.barcode_raw LIKE 'E2E%';
  IF n > 0 THEN
    RAISE EXCEPTION 'El CSV contiene % escaneo(s) de prueba E2E: abortando', n;
  END IF;

  SELECT count(*) INTO n FROM stg_products WHERE workspace_id <> 1;
  IF n > 0 THEN
    RAISE EXCEPTION 'Hay % producto(s) con workspace_id distinto de 1', n;
  END IF;

  SELECT count(*) INTO n FROM stg_scans WHERE workspace_id <> 1 OR user_id <> 1;
  IF n > 0 THEN
    RAISE EXCEPTION 'Hay % escaneo(s) con workspace_id/user_id distinto de 1/1', n;
  END IF;

  SELECT count(*) INTO n FROM stg_scans s
   WHERE NOT EXISTS (SELECT 1 FROM stg_products p WHERE p.id = s.product_id);
  IF n > 0 THEN
    RAISE EXCEPTION 'Hay % escaneo(s) cuyo producto no esta en el CSV: se romperia la FK', n;
  END IF;
END
$$;

-- ---------------------------------------------------------------------------
-- 3. Preflight del DESTINO: aborta si no es la base de datos esperada
-- ---------------------------------------------------------------------------
DO $$
DECLARE n int; detalle text;
BEGIN
  SELECT count(*) INTO n FROM workspaces WHERE id = 1;
  IF n <> 1 THEN
    RAISE EXCEPTION 'El destino no tiene el workspace id=1 (lo crea el seed). ¿Es la base de datos correcta?';
  END IF;

  SELECT count(*) INTO n FROM users WHERE id = 1 AND workspace_id = 1 AND is_active;
  IF n <> 1 THEN
    RAISE EXCEPTION 'El destino no tiene el usuario id=1 activo dentro del workspace 1';
  END IF;

  -- Conflicto real: mismo id pero distinto codigo de barras.
  SELECT count(*) INTO n FROM products p
    JOIN stg_products s ON p.id = s.id
   WHERE p.barcode_raw <> s.barcode_raw;
  IF n > 0 THEN
    RAISE EXCEPTION 'El destino tiene % producto(s) con el mismo id pero otro codigo de barras: importacion abortada', n;
  END IF;

  -- Conflicto real: mismo codigo de barras (UNIQUE workspace_id+barcode_raw)
  -- pero distinto id -> importarlo crearia un duplicado.
  SELECT count(*) INTO n FROM products p
    JOIN stg_products s ON p.barcode_raw = s.barcode_raw AND p.workspace_id = s.workspace_id
   WHERE p.id <> s.id;
  IF n > 0 THEN
    SELECT string_agg(s.barcode_raw, ', ') INTO detalle
      FROM products p JOIN stg_products s
        ON p.barcode_raw = s.barcode_raw AND p.workspace_id = s.workspace_id
     WHERE p.id <> s.id;
    RAISE EXCEPTION 'El destino ya tiene estos codigos con otro id (%), lo crearia duplicado: importacion abortada', detalle;
  END IF;

  -- Escaneos con el mismo id pero otro producto/usuario.
  SELECT count(*) INTO n FROM scans s
    JOIN stg_scans t ON s.id = t.id
   WHERE s.product_id <> t.product_id OR s.user_id <> t.user_id;
  IF n > 0 THEN
    RAISE EXCEPTION 'El destino tiene % escaneo(s) con el mismo id pero otras referencias: importacion abortada', n;
  END IF;
END
$$;

-- ---------------------------------------------------------------------------
-- 4. Importacion (idempotente: reejecutarla no duplica nada)
-- ---------------------------------------------------------------------------
INSERT INTO products (
    id, workspace_id, barcode_raw, barcode_type, product_identifier, product_name,
    weight_value, weight_unit, weight_kg, created_at, updated_at
)
SELECT id, workspace_id, barcode_raw, barcode_type, product_identifier, product_name,
       weight_value, weight_unit, weight_kg, created_at, updated_at
  FROM stg_products
ON CONFLICT DO NOTHING;

INSERT INTO scans (id, workspace_id, product_id, user_id, scanned_at)
SELECT id, workspace_id, product_id, user_id, scanned_at
  FROM stg_scans
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------------------
-- 5. Comprobacion posterior (si falla, la transaccion se deshace entera)
-- ---------------------------------------------------------------------------
DO $$
DECLARE n int;
BEGIN
  SELECT count(*) INTO n FROM products p
    JOIN stg_products s ON p.id = s.id
   WHERE p.barcode_raw = s.barcode_raw
     AND p.workspace_id = s.workspace_id
     AND p.weight_kg = s.weight_kg;
  IF n <> 3 THEN
    RAISE EXCEPTION 'Tras importar hay % de 3 productos coincidentes', n;
  END IF;

  SELECT count(*) INTO n FROM scans s
    JOIN stg_scans t ON s.id = t.id
   WHERE s.product_id = t.product_id
     AND s.user_id = t.user_id
     AND s.workspace_id = t.workspace_id
     AND s.scanned_at = t.scanned_at;
  IF n <> 5 THEN
    RAISE EXCEPTION 'Tras importar hay % de 5 escaneos coincidentes', n;
  END IF;

  SELECT count(*) INTO n FROM scans s
    LEFT JOIN products p ON p.id = s.product_id
   WHERE p.id IS NULL;
  IF n > 0 THEN
    RAISE EXCEPTION 'Hay % escaneo(s) con producto huerfano', n;
  END IF;

  SELECT count(*) INTO n FROM products WHERE barcode_raw LIKE 'E2E%';
  IF n > 0 THEN
    RAISE EXCEPTION 'Ha entrado % producto(s) E2E: abortando', n;
  END IF;
END
$$;

-- ---------------------------------------------------------------------------
-- 6. Secuencias: el siguiente id del backend no debe chocar con lo importado
--    setval(seq, max, true) -> el siguiente nextval sera max + 1
-- ---------------------------------------------------------------------------
SELECT setval(pg_get_serial_sequence('products', 'id'),
              GREATEST((SELECT COALESCE(max(id), 1) FROM products), 1), true);
SELECT setval(pg_get_serial_sequence('scans', 'id'),
              GREATEST((SELECT COALESCE(max(id), 1) FROM scans), 1), true);

COMMIT;

\echo '--- Importacion confirmada ---'
SELECT count(*) AS productos_importados FROM products WHERE id IN (1, 2, 3);
SELECT count(*) AS escaneos_importados  FROM scans    WHERE id IN (1, 2, 3, 4, 24);
