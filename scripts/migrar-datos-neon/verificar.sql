-- ============================================================================
-- SGCBP - Verificacion de la importacion en el destino.
--
-- Se puede ejecutar:
--   * con psql contra Neon:
--       psql "$NEON_DATABASE_URL" -v ON_ERROR_STOP=1 -f verificar.sql
--   * copiando el contenido en el SQL Editor de Neon (consola web).
--
-- Todos los contadores esperados deben coincidir. Si alguno no lo hace, la
-- importacion NO ha ido bien.
-- ============================================================================
\pset pager off
\echo ''
\echo '================ 1. CONTADORES ESPERADOS ================'
SELECT count(*) AS productos_esperados, 3 AS ok
  FROM products WHERE id IN (1, 2, 3);
SELECT count(*) AS escaneos_esperados, 5 AS ok
  FROM scans WHERE id IN (1, 2, 3, 4, 24);

\echo ''
\echo '================ 2. RELACIONES (producto de cada escaneo) ================'
SELECT s.id AS scan_id, s.scanned_at, s.product_id, p.barcode_raw,
       p.product_name, p.weight_value, p.weight_unit, p.weight_kg,
       s.user_id, s.workspace_id
  FROM scans s
  JOIN products p ON p.id = s.product_id
 WHERE s.id IN (1, 2, 3, 4, 24)
 ORDER BY s.id;

\echo ''
\echo '================ 3. INTEGRIDAD ================'
-- Escaneos sin producto (debe ser 0)
SELECT count(*) AS escaneos_huerfanos FROM scans s
  LEFT JOIN products p ON p.id = s.product_id
 WHERE p.id IS NULL AND s.id IN (1, 2, 3, 4, 24);
-- Escaneos cuyo usuario no existe (debe ser 0)
SELECT count(*) AS escaneos_con_usuario_inexistente FROM scans s
  LEFT JOIN users u ON u.id = s.user_id
 WHERE u.id IS NULL AND s.id IN (1, 2, 3, 4, 24);
-- Productos con unidad de peso invalida (debe ser 0)
SELECT count(*) AS unidades_invalidas FROM products
 WHERE id IN (1, 2, 3) AND weight_unit NOT IN ('KG', 'LB');
-- Codigos duplicados en el workspace (debe ser 0)
SELECT count(*) AS codigos_duplicados FROM (
  SELECT workspace_id, barcode_raw FROM products GROUP BY 1, 2 HAVING count(*) > 1
) d;

\echo ''
\echo '================ 4. AUSENCIA DE RESIDUOS DE PRUEBA ================'
SELECT count(*) AS productos_e2e FROM products WHERE barcode_raw LIKE 'E2E%';
SELECT count(*) AS escaneos_e2e FROM scans s
  JOIN products p ON p.id = s.product_id
 WHERE p.barcode_raw LIKE 'E2E%';

\echo ''
\echo '================ 5. SECUENCIAS (el proximo id debe estar libre) ================'
SELECT sequencename, last_value FROM pg_sequences
 WHERE schemaname = 'public' AND sequencename IN ('products_id_seq', 'scans_id_seq')
 ORDER BY sequencename;
SELECT GREATEST((SELECT COALESCE(max(id), 1) FROM products), 1) AS max_product_id,
       GREATEST((SELECT COALESCE(max(id), 1) FROM scans), 1)    AS max_scan_id;

\echo ''
\echo '================ 6. USUARIO ADMIN (no se ha de tocar) ================'
SELECT id, username, role, is_active, workspace_id FROM users ORDER BY id;
