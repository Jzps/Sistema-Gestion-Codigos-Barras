# Arquitectura — SGCBP

## Visión general

```
Lector USB (HID, modo teclado)
        │  secuencia + ENTER
        ▼
┌─────────────────┐   HTTP/JSON (cookie HttpOnly)   ┌──────────────────┐
│  Angular (SPA)  │ ──────────────────────────────▶ │  FastAPI (REST)  │
│  localhost:4200 │ ◀────────────────────────────── │  localhost:8000  │
└─────────────────┘                                 └────────┬─────────┘
                                                             │ SQLAlchemy 2
                                                             ▼
                                                    ┌──────────────────┐
                                                    │ PostgreSQL 16    │
                                                    │ (Docker Compose) │
                                                    └──────────────────┘
```

Monolito modular en monorepo. Sin microservicios ni infraestructura extra.

## Backend (capas)

```
api/            Routers FastAPI + deps (auth). Sin lógica de negocio.
  └─ deps.py    get_current_user: único punto que resuelve identidad
                (JWT de cookie → usuario → workspace). NUNCA se acepta
                workspace_id del cliente.
services/       Lógica de negocio: scan_service (flujo de escaneo),
                weight (conversión), auth_service, excel_export.
repositories/   Consultas SQLAlchemy. TODAS filtran por workspace_id.
models/         Entidades ORM (Workspace, User, Product, Scan).
schemas/        Contratos Pydantic de entrada/salida.
core/           config (pydantic-settings), database (engine/sesión),
                security (Argon2id + JWT).
```

Regla de dependencias: `api → services → repositories → models`. Nunca al
revés. Los routers no contienen queries; los servicios no conocen HTTP.

### Flujo de escaneo (endpoint único `POST /api/scans`)

Decisión: un solo endpoint maneja ambos casos para no duplicar lógica en el
frontend (el documento de requisitos permite explícitamente esta estrategia).

1. Autenticar (cookie JWT) → usuario + workspace.
2. Buscar producto por `(workspace_id, barcode_raw)`.
3. Existe → crear scan → `201 {status:"existing", product, scan}`.
4. No existe y no hay peso → `200 {status:"needs_weight", barcode}`.
5. No existe y hay peso → normalizar a kg, crear producto + scan →
   `201 {status:"created", product, scan}`.

La creación del producto y el scan se confirman en **una sola transacción**.
Ante una colisión de concurrencia (mismo barcode creado a la vez), se captura
`IntegrityError`, se reutiliza el producto existente y se registra el scan.

### Autenticación

- Login verifica usuario + contraseña (Argon2id) y emite JWT (HS256) con
  `sub = user.id`, expiración configurable (`ACCESS_TOKEN_EXPIRE_MINUTES`).
- El JWT viaja en cookie HttpOnly (`SameSite=Lax`, `Secure` según
  `COOKIE_SECURE`). El frontend Angular nunca lee el token.
- Limitación conocida y aceptada en V1: el JWT es stateless; tras logout el
  navegador borra la cookie, pero una copia del token seguiría siendo válida
  hasta expirar. Mitigación futura: lista de revocación o tokens opacos.

## Frontend (Angular standalone)

```
auth/       Login, AuthService (sesión), authGuard, interceptor withCredentials
scanner/    Pantalla principal: input con autofocus + flujo peso para códigos nuevos
dashboard/  Inicio con accesos directos
products/   Listado + edición inline (PATCH) + eliminación con confirmación (DELETE)
history/    Tabla de escaneos + eliminación con confirmación (DELETE) + exportación XLSX
reports/    Servicio de descarga del Excel
shared/     Modelos TS, layout/navbar, directiva autofocus, api-error (errores HTTP → mensajes)
```

- El interceptor HTTP añade `withCredentials: true` a todas las llamadas.
- El guard funcional protege rutas; el backend vuelve a validar siempre.
- Sin librerías UI externas: SCSS propio (paleta fría: blanco/azules).
- Corrección/borrado: edición en tarjeta inline y confirmación inline (sin
  modales). Tras cada operación la lista se actualiza en caliente (signals),
  sin recargar la página. Los errores 409/404 muestran el `detail` en español
  del backend vía `shared/api-error.ts`; 422/401/red tienen mensajes propios.
- El frontend nunca recalcula `weight_kg`: lo muestra tal como lo devuelve
  la API (el backend es la autoridad de conversión).
- Tests de componentes con `HttpTestingController` (Karma/Jasmine; en
  Windows sin Chrome usar Edge vía `CHROME_BIN`) y E2E real de la UI con
  `scripts/e2e-ui.mjs` (Edge headless por CDP, sin dependencias).

## Endpoints

| Método | Ruta                      | Auth | Descripción                                       |
| ------ | ------------------------- | ---- | ------------------------------------------------- |
| GET    | `/api/health`             | No   | Estado de la API y la BD                          |
| POST   | `/api/auth/login`         | No   | Login; fija cookie HttpOnly                       |
| POST   | `/api/auth/logout`        | No   | Borra la cookie                                   |
| GET    | `/api/auth/me`            | Sí   | Usuario actual (+ workspace)                      |
| POST   | `/api/scans`              | Sí   | Flujo de escaneo (ver arriba)                     |
| GET    | `/api/scans`              | Sí   | Historial del workspace, más reciente primero     |
| DELETE | `/api/scans/{id}`         | Sí   | Elimina un escaneo incorrecto (204; 404 cross-ws) |
| GET    | `/api/products`           | Sí   | Productos del workspace                           |
| GET    | `/api/products/{id}`      | Sí   | Producto por id (404 si es de otro workspace)     |
| PATCH  | `/api/products/{id}`      | Sí   | Corrección parcial (409 si barcode duplicado)     |
| DELETE | `/api/products/{id}`      | Sí   | Solo sin escaneos (409 si tiene historial)        |
| GET    | `/api/reports/scans.xlsx` | Sí   | Descarga del historial en Excel                   |

## Corrección y eliminación (decisiones de diseño)

1. **Producto ≠ scan.** El producto es la ficha de un código; el scan es un
   evento histórico. Editar un producto nunca modifica scans.
2. **`barcode_raw` editable.** Los scans referencian `product_id` (FK), no el
   texto del código. Al corregir un barcode no se toca ningún scan; el
   historial, que se construye vía JOIN al producto, muestra el dato
   corregido — justo lo esperado al corregir un error de captura. Cambiar a
   un barcode ya usado en el mismo workspace devuelve **409**.
3. **Peso al actualizar.** Si PATCH trae `weight_value` y/o `weight_unit`,
   `weight_kg` se recalcula combinando lo enviado con lo almacenado, usando
   el mismo `services/weight.py` (sin duplicar conversión).
4. **Borrado de productos protegido.** Solo se elimina un producto **sin
   escaneos**; con historial → **409** y mensaje indicando eliminar primero
   los scans. Borrar el historial es así una decisión explícita, scan a scan.
   No hay soft delete: la política 409 es suficiente y más simple. No
   requirió migración (sin cambios de esquema).
5. **Scans inmutables.** No existe `PATCH /api/scans/{id}` a propósito: un
   evento pasado no se edita; la corrección es eliminarlo y re-escanear.
6. **Errores de dominio.** Los servicios lanzan `NotFoundError` /
   `ConflictError` (`services/errors.py`) y `main.py` los traduce a 404/409
   con exception handlers: los servicios no conocen HTTP.

## Preparado para el futuro (sin implementar)

- `barcode_type` / `product_identifier` en `products` → parser GS1 (Fase 4).
- `backend/Dockerfile` → despliegue en Render (Fase 3).
- `role` en `users` → permisos por rol.
- Configuración por entorno vía `.env` → mismo binario en dev/prod.
