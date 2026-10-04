# Base de datos — SGCBP

Una única base PostgreSQL compartida. La separación entre clientes es
**lógica** (columna `workspace_id` en todas las tablas de datos), no física.

## Modelo entidad-relación

```
WORKSPACES 1 ─── N USERS
WORKSPACES 1 ─── N PRODUCTS
WORKSPACES 1 ─── N SCANS
USERS      1 ─── N SCANS
PRODUCTS   1 ─── N SCANS
```

## Tablas

### workspaces

| Columna    | Tipo                     | Notas              |
| ---------- | ------------------------ | ------------------ |
| id         | INTEGER PK               |                    |
| name       | VARCHAR(120) UNIQUE      |                    |
| created_at | TIMESTAMPTZ DEFAULT now()|                    |

### users

| Columna       | Tipo                      | Notas                          |
| ------------- | ------------------------- | ------------------------------ |
| id            | INTEGER PK                |                                |
| workspace_id  | INTEGER FK → workspaces   | ON DELETE CASCADE, indexado    |
| username      | VARCHAR(60) UNIQUE        |                                |
| email         | VARCHAR(255) UNIQUE       |                                |
| password_hash | VARCHAR(255)              | Argon2id; nunca sale de la API |
| role          | VARCHAR(20)               | `admin` / `operator`           |
| is_active     | BOOLEAN DEFAULT true      |                                |
| created_at    | TIMESTAMPTZ DEFAULT now() |                                |
| updated_at    | TIMESTAMPTZ DEFAULT now() |                                |

### products

| Columna            | Tipo                      | Notas                                   |
| ------------------ | ------------------------- | --------------------------------------- |
| id                 | INTEGER PK                |                                         |
| workspace_id       | INTEGER FK → workspaces   | ON DELETE CASCADE, indexado             |
| barcode_raw        | VARCHAR(128)              | código íntegro, tal como llega          |
| barcode_type       | VARCHAR(32) NULL          | reservado para GS1 (Fase 4)             |
| product_identifier | VARCHAR(64) NULL          | reservado para GTIN (Fase 4)            |
| product_name       | VARCHAR(255) NULL         |                                         |
| weight_value       | NUMERIC(12,4)             | valor tal como se introdujo             |
| weight_unit        | VARCHAR(2)                | CHECK `IN ('KG','LB')`                  |
| weight_kg          | NUMERIC(14,6)             | normalizado a kilogramos                |
| created_at         | TIMESTAMPTZ DEFAULT now() |                                         |
| updated_at         | TIMESTAMPTZ DEFAULT now() |                                         |

**Clave de identidad V1**: `UNIQUE (workspace_id, barcode_raw)`.

### scans

| Columna      | Tipo                      | Notas                                |
| ------------ | ------------------------- | ------------------------------------ |
| id           | INTEGER PK                |                                      |
| workspace_id | INTEGER FK → workspaces   | ON DELETE CASCADE, indexado          |
| product_id   | INTEGER FK → products     | ON DELETE CASCADE, indexado          |
| user_id      | INTEGER FK → users        | ON DELETE CASCADE                    |
| scanned_at   | TIMESTAMPTZ DEFAULT now() | indexado (ordenación del historial)  |

`scans` denormaliza intencionadamente `workspace_id` (además del que tendría
vía producto) para que el historial se filtre directamente por tenant.

## Migraciones

- El esquema lo gestiona **Alembic** (`backend/alembic/`), migración inicial
  `0001`. No se usa `create_all` para el esquema real (solo como atajo en
  tests con SQLite).
- Ejecutar: `cd backend && alembic upgrade head`.
- `alembic/env.py` toma la URL de `DATABASE_URL` (misma fuente que la app).

## Convenciones

- Pesos con `NUMERIC` (Decimal en Python), nunca float.
- Timestamps con zona horaria y `server_default=now()`.
- Borrado en cascada desde el workspace: eliminar un workspace elimina sus
  usuarios, productos y escaneos.
