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
products/   Listado de productos del workspace
history/    Tabla de escaneos + botón de exportación XLSX
reports/    Servicio de descarga del Excel
shared/     Modelos TS, layout/navbar, directiva autofocus
```

- El interceptor HTTP añade `withCredentials: true` a todas las llamadas.
- El guard funcional protege rutas; el backend vuelve a validar siempre.
- Sin librerías UI externas: SCSS propio (paleta fría: blanco/azules).

## Endpoints

| Método | Ruta                      | Auth | Descripción                                  |
| ------ | ------------------------- | ---- | -------------------------------------------- |
| GET    | `/api/health`             | No   | Estado de la API y la BD                     |
| POST   | `/api/auth/login`         | No   | Login; fija cookie HttpOnly                  |
| POST   | `/api/auth/logout`        | No   | Borra la cookie                              |
| GET    | `/api/auth/me`            | Sí   | Usuario actual (+ workspace)                 |
| POST   | `/api/scans`              | Sí   | Flujo de escaneo (ver arriba)                |
| GET    | `/api/scans`              | Sí   | Historial del workspace, más reciente primero|
| GET    | `/api/products`           | Sí   | Productos del workspace                      |
| GET    | `/api/products/{id}`      | Sí   | Producto por id (404 si es de otro workspace)|
| GET    | `/api/reports/scans.xlsx` | Sí   | Descarga del historial en Excel              |

## Preparado para el futuro (sin implementar)

- `barcode_type` / `product_identifier` en `products` → parser GS1 (Fase 4).
- `backend/Dockerfile` → despliegue en Render (Fase 3).
- `role` en `users` → permisos por rol.
- Configuración por entorno vía `.env` → mismo binario en dev/prod.
