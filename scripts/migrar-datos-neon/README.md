# Migración de datos locales → Neon

Kit para llevar los datos reales de la base de datos local de desarrollo a la
base de datos de producción (Neon), de forma **transaccional, reproducible,
idempotente y reversible**.

> ⚠️ **Estos scripts son la única forma de migrar datos en el proyecto.**
> `alembic` solo gestiona el **esquema**, nunca los datos.

---

## Qué se migra

De la base de datos local hay **11 productos y 14 escaneos**, pero solo una
parte son datos reales: el resto son **residuos de las pruebas E2E** (`E2E-*`),
que no se migran.

| Origen (local) | | Destino (Neon) | |
| --- | --- | --- | --- |
| `products.id` | 1, 2, 3 | `products.id` | 1, 2, 3 (mismos ids) |
| `scans.id` | 1, 2, 3, 4, 24 | `scans.id` | 1, 2, 3, 4, 24 (mismos ids) |
| `workspace_id` | 1 | `workspace_id` | 1 (ya existe por el seed) |
| `user_id` | 1 | `user_id` | 1 (el usuario `admin` del seed) |

Los 3 productos reales:

| id | `barcode_raw` | Nombre | Peso |
| --- | --- | --- | --- |
| 1 | `7501234567890` | Caja demo | 44.09 LB (19.998888 kg) |
| 2 | `SNPK91365` | Prueba | 32.00 LB (14.514956 kg) |
| 3 | `LIVE-1` | Producto live | 10.00 KG (10.000000 kg) |

Los 5 escaneos: ids 1 y 2 → producto 1; id 3 y 24 → producto 2; id 4 → producto 3.

**Se conservan los ids** a propósito: así `scans.product_id` sigue apuntando al
producto correcto y **las relaciones se mantienen intactas** sin tener que
remapear nada.

**Excluidos:** los 8 productos y 9 escaneos cuyo `barcode_raw` empieza por
`E2E-`. La validación lo comprueba y **aborta** si alguno se colara.

---

## Ficheros

| Fichero | Para qué sirve |
| --- | --- |
| `exportar.sh` | Exporta los 3 productos y 5 escaneos a CSV + manifiesto con SHA-256. Valida el origen y aborta si algo no cuadra. |
| `importar.sh` | Copia de seguridad del destino → preflight → importación transaccional → verificación. |
| `importar.sql` | La importación en sí (la ejecuta `importar.sh`). |
| `verificar.sql` | Comprobaciones del destino (contadores, relaciones, integridad, secuencias). Se puede pegar en el SQL Editor de Neon. |
| `revertir.sh` | Revisión lógica: borra solo lo importado (transaccional). |
| `restaurar.sh` | Revisión total: restaura la copia de seguridad (`.dump`). Alternativa nuclear. |
| `rehearsal.sh` | **Ensayo completo** sobre una base de datos desechable local. No toca Neon. |

---

## Procedimiento

### 0. Ensayo (opcional pero recomendado)

Ejecuta TODO el procedimiento contra una base de datos temporal que se crea y
se destruye sola. No toca Neon ni la base de datos de trabajo:

```bash
scripts/migrar-datos-neon/rehearsal.sh
```

Salida esperada:

```text
[ensayo] 3/6 Importando en la base de datos de ensayo
   Importacion correcta
[ensayo] 4/6 Comprobando el contenido importado
   3 productos, 5 escaneos, 0 huerfanos, 0 residuos E2E
[ensayo] 5/6 Reimportando (debe ser idempotente: 3 productos y 5 escaneos)
   Idempotente: sigue habiendo 3 productos y 5 escaneos
[ensayo] 6/6 Revirtiendo
   Reversion correcta: la base de datos de ensayo queda vacia
================================================================
 ENSAYO COMPLETO CORRECTO
================================================================
```

### 1. Exportar desde la base local

```bash
scripts/migrar-datos-neon/exportar.sh
```

Genera en `scripts/migrar-datos-neon/salida/`:

- `sgcbp_products.csv` (3 filas + cabecera)
- `sgcbp_scans.csv` (5 filas + cabecera)
- `manifiesto.txt` (ids, recuentos y SHA-256 de cada CSV)

La validación aborta si: no hay exactamente 3 productos y 5 escaneos, alguno
es `E2E-*`, algún `workspace_id`/`user_id` no es 1, o algún escaneo apunta a un
producto que no está en la selección.

### 2. Indicar la URL de Neon (sin dejarla en el historial)

```bash
read -rs -p "URL de Neon: " NEON_DATABASE_URL; export NEON_DATABASE_URL; echo
```

Cadenas admitidas (el script quita el sufijo `+psycopg` para `psql`/`pg_dump`):

```text
postgresql+psycopg://<USUARIO>:<CONTRASENA>@ep-xxx-pooler.REGION.aws.neon.tech/neondb?sslmode=require
```

> La URL **no** se escribe en el repositorio, **no** se imprime y **no** aparece
> en la lista de procesos: se pasa al contenedor por `stdin` y se borra al
> terminar. Cuando acabes: `unset NEON_DATABASE_URL`.

### 3. Importar

```bash
scripts/migrar-datos-neon/importar.sh
```

Qué hace, en orden:

1. **Copia de seguridad** del destino (`pg_dump` completo) en
   `salida/backups/neon_antes_<fecha>.dump`.
2. **Preflight** dentro de la misma transacción (aborta si el destino no es el
   esperado):
   - debe existir el `workspace` id 1;
   - debe existir el `usuario` id 1, activo y en el workspace 1;
   - no debe haber un producto con el mismo `barcode_raw` y **otro** id
     (sería un duplicado);
   - no debe haber un producto con el mismo id y **otro** `barcode_raw`;
   - lo mismo para los escaneos.
3. **Validación del CSV**: exactamente 3 productos y 5 escaneos, ninguno
   `E2E-*`, `workspace_id`/`user_id` coherentes y ninguna FK rota.
4. **Inserción** con `ON CONFLICT DO NOTHING` (idempotente).
5. **Comprobación posterior**: si no coinciden exactamente los 3 productos y
   los 5 escaneos (con sus valores), **la transacción se deshace entera**.
6. **Reinicio de las secuencias** (`setval(seq, max(id), true)`) para que el
   siguiente escaneo del backend no use un id ya ocupado.
7. `COMMIT` y **verificación** con `verificar.sql`.

Si algo falla, la salida es explícita y **no se ha modificado nada**:

```text
[migrar] La importacion ha fallado y se ha DESHECIDO (transaccion): no se ha modificado nada.
[migrar] La copia de seguridad previo sigue en: .../neon_antes_2026....dump
```

### 4. Verificar a mano (opcional)

```bash
read -rs -p "URL de Neon: " NEON_DATABASE_URL; export NEON_DATABASE_URL; echo
scripts/migrar-datos-neon/verificar.sql   # o copiarlo al SQL Editor de Neon
```

Los contadores esperados: **3 productos, 5 escaneos, 0 huérfanos, 0 E2E**.

### 5. Revisión

**Lógica** (borra solo lo importado; no toca `workspaces` ni `users`, así que
**la contraseña del admin no se ve afectada**):

```bash
read -rs -p "URL de Neon: " NEON_DATABASE_URL; export NEON_DATABASE_URL; echo
scripts/migrar-datos-neon/revertir.sh
```

Pide confirmar escribiendo `BORRAR`. Los productos y escaneos creados **después**
de la importación tienen ids distintos (las secuencias se reiniciaron) y **no
se tocan**.

**Total** (restaura la copia de seguridad; borra el contenido actual del
destino):

```bash
read -rs -p "URL de Neon: " NEON_DATABASE_URL; export NEON_DATABASE_URL; echo
scripts/migrar-datos-neon/restaurar.sh scripts/migrar-datos-neon/salida/backups/neon_antes_<fecha>.dump
```

---

## Garantías

| Garantía | Cómo se consigue |
| --- | --- |
| **Transaccional** | Todo dentro de un `BEGIN … COMMIT` de PostgreSQL. Si algo falla, `ROLLBACK` automático: no queda nada a medias. |
| **Conserva las relaciones** | Se importan los ids explícitos → `scans.product_id` sigue apuntando al producto correcto. |
| **Sin duplicados** | `ON CONFLICT DO NOTHING` + preflight que aborta ante un `barcode_raw` repetido con otro id (el `UNIQUE (workspace_id, barcode_raw)` del esquema). |
| **Idempotente** | Reejecutar la importación no duplica nada (verificado en el ensayo). |
| **Verificable antes y después** | Validación en el origen, preflight en el destino y comprobación posterior; `verificar.sql` para auditar cuando quieras. |
| **Copia de seguridad previa** | `pg_dump` del destino antes de tocar nada, guardado en `salida/backups/`. |
| **Reversible** | `revertir.sh` (lógica) y `restaurar.sh` (copia de seguridad). |
| **Sin residuos de prueba** | Validación explícita de `E2E-%` antes y después de importar; aborta si aparece alguno. |
| **Sin tocar la contraseña** | No se migran `workspaces` ni `users`: solo `products` y `scans`. |

## Notas

- `psql` y `pg_dump` son clientes **libpq**: no entienden el sufijo `+psycopg` de
  SQLAlchemy. Los scripts lo quitan automáticamente.
- El destino debe tener el esquema aplicado (`alembic upgrade head`) y el seed
  ejecutado (workspace 1 + usuario 1). En Neon ya está hecho.
- `salida/` está en `.gitignore`: los CSV y las copias de seguridad **no** se
  versionan.
