# AGENTS.md — Memoria técnica del proyecto SGCBP

Este archivo es la **memoria persistente del repositorio** para sesiones de
agente. Léelo antes de tocar código. Si tomas una decisión arquitectónica
nueva, actualízalo en el mismo commit. No es documentación decorativa.

## 1. Propósito

**SGCBP** (Sistema de Gestión de Códigos de Barras y Pesos): aplicación web
que registra el peso de productos identificados por código de barras. El peso
se introduce **una sola vez** por código; los escaneos posteriores lo
recuperan automáticamente. Cada escaneo queda en un historial exportable a
Excel `.xlsx`, con aislamiento lógico de datos por workspace.

El repo se llama `Facturador_Excel` por motivos históricos, pero el proyecto
es SGCBP; la raíz del repo ES la raíz del monorepo (sin subcarpeta extra).

## 2. Alcance

- **Implementado (V1)**:
  - Fase 1: PostgreSQL local (Docker), API FastAPI, frontend Angular,
    comunicación extremo a extremo, pantalla de escaneo.
  - Fase 2: autenticación, usuarios, sesión, aislamiento por workspace,
    historial, exportación XLSX.
- **NO implementar (fuera de V1)**:
  - Fase 3: despliegue (Neon, Render, frontend público).
  - Fase 4: parser GS1 (GTIN, peso embebido, fechas, seriales, lotes),
    estadísticas, gráficos, chatbot, IA, app móvil.
  - Nunca: microservicios, Kubernetes, Redis, colas, WebSockets, cloud storage.

## 3. Stack (obligatorio, no cambiar sin razón técnica fuerte)

| Capa | Tecnología |
| --- | --- |
| Backend | Python 3.13 · FastAPI 0.142 · SQLAlchemy 2.1 · Alembic 1.20 · Pydantic 2.13 · psycopg 3 · Uvicorn · pytest |
| Seguridad | Argon2id (`argon2-cffi`, sin passlib) · JWT (`PyJWT`) en cookie HttpOnly |
| Excel | openpyxl |
| Frontend | Angular 20 (standalone, TS, SCSS) — **sin librerías UI externas** |
| BD | PostgreSQL 16 vía Docker Compose |
| Nota | Angular 21+ exige Node ≥22.22; este entorno tiene Node 22.20 → se usa Angular 20 |

## 4. Estructura del monorepo

```
├── backend/
│   ├── app/
│   │   ├── api/            # routers + deps.py (único punto de auth)
│   │   ├── core/           # config (pydantic-settings), database, security
│   │   ├── models/         # ORM: Workspace, User, Product, Scan
│   │   ├── schemas/        # contratos Pydantic
│   │   ├── repositories/   # queries (TODAS filtran por workspace_id)
│   │   ├── services/       # weight, scan_service, auth_service, excel_export
│   │   ├── main.py         # app FastAPI + CORS + manejador global de errores
│   │   └── seed.py         # `python -m app.seed` (usuario dev)
│   ├── alembic/            # env.py toma DATABASE_URL de app.core.config
│   ├── tests/              # pytest con SQLite en memoria (StaticPool)
│   └── requirements.txt    # versiones pineadas
├── frontend/src/app/
│   ├── auth/               # login, AuthService, guards, interceptor
│   ├── scanner/            # pantalla principal (escaneo + alta de peso)
│   ├── dashboard/  products/  history/  reports/  shared/
│   └── environments        # apiUrl = http://localhost:8000/api
├── docs/                   # requirements, architecture, database, setup
├── scripts/e2e-ui.mjs      # verificación E2E de la UI (Edge headless CDP, sin deps)
├── docker-compose.yml      # SOLO PostgreSQL
├── start.sh                # arranque único (Git Bash Windows): todo el entorno
└── .env.example
```

## 5. Arquitectura

- `Lector USB (modo teclado) → Angular (:4200) → FastAPI (:8000) → PostgreSQL (:5432)`.
- Monolito modular. Dirección de dependencias backend:
  `api → services → repositories → models`. Los routers no hacen queries; los
  servicios no conocen HTTP.
- **Endpoint único de escaneo** `POST /api/scans` (decisión deliberada para
  no duplicar lógica en el frontend):
  - existe `(workspace, barcode_raw)` → crea scan → `201 {status:"existing"}`
  - no existe y sin peso → `200 {status:"needs_weight"}`
  - no existe con peso → crea producto + scan en una transacción → `201 {status:"created"}`
  - `IntegrityError` por concurrencia → rollback, reutilizar el producto ya
    creado, registrar el scan como `existing`.

## 6. Modelo de datos (conceptual)

```
WORKSPACES 1─N USERS
WORKSPACES 1─N PRODUCTS   UNIQUE(workspace_id, barcode_raw)
WORKSPACES 1─N SCANS      (workspace_id denormalizado a propósito)
USERS 1─N SCANS · PRODUCTS 1─N SCANS
```

- Una sola BD compartida; separación **lógica** por `workspace_id`.
- FKs con `ON DELETE CASCADE` desde workspace.
- Detalles columna a columna: `docs/database.md`.

## 7. Reglas de dominio (no romper)

1. **Identidad del producto**: unicidad `(workspace_id, barcode_raw)`. El
   código se guarda íntegro en `barcode_raw`. `barcode_type` y
   `product_identifier` existen SOLO como campos preparados para GS1 (Fase 4);
   no rellenarlos con lógica casera.
2. **Peso**: unidades `KG`/`LB`. Constantes en `services/weight.py`
   (1 LB = 0.45359237 kg). Todo cálculo con `Decimal`, jamás float. Se
   persiste `weight_value`+`weight_unit` (como se introdujo) y `weight_kg`
   (normalizado, 6 decimales). El backend es la autoridad: si el producto ya
   existe, el peso enviado se IGNORA (no se actualiza — eso es Fase futura).
3. **Escaneo**: cada lectura crea exactamente un `Scan`. No hay edición ni
   borrado de escaneos en V1.
4. **Aislamiento**: `workspace_id` se deriva SIEMPRE del usuario autenticado
   (`api/deps.py:get_current_user`), nunca del cuerpo/params de la petición.
   `GET /products/{id}` de otro workspace → 404 (no 403, para no filtrar
   existencia).
5. **Auth**: Argon2id para hashes; JWT HS256 en cookie HttpOnly
   `sgcbp_session` (`SameSite=Lax`, `Secure` por env `COOKIE_SECURE`).
   Limitación aceptada en V1: JWT stateless, tras logout una copia del token
   sigue válida hasta expirar. No devolver `password_hash` jamás.
6. **Errores**: nunca stack traces al cliente (manejador global en `main.py`).
   Los servicios lanzan `NotFoundError`/`ConflictError`
   (`services/errors.py`) y `main.py` los traduce a 404/409: los servicios
   no conocen HTTP.
7. **Producto ≠ scan** (corrección y borrado):
   - `PATCH /api/products/{id}` edita `barcode_raw`, `barcode_type`,
     `product_identifier`, `product_name`, `weight_value`, `weight_unit`;
     recalcula `weight_kg` con `services/weight.py`. Editar NO toca scans
     (referencian `product_id`; el historial se arma vía JOIN y muestra el
     dato corregido). Barcode duplicado en workspace → 409.
   - `DELETE /api/products/{id}` solo si NO tiene scans → si tiene, 409.
     Sin soft delete; sin migración.
   - `DELETE /api/scans/{id}` borra solo el evento; el producto queda intacto.
   - **No existe PATCH de scans a propósito**: eventos históricos inmutables;
     corregir = eliminar + re-escanear.

## 8. Convenciones de código

- Backend: español en docs/docstrings/comentarios; identificadores en inglés.
  Type hints modernos (`X | None`). SQLAlchemy 2.x con `Mapped`/`mapped_column`.
- Frontend: convención Angular 20 (`scanner.ts` + `scanner.html` + `.scss`,
  clase `Scanner`, standalone por defecto). Signals para estado, FormsModule
  con ngModel en formularios simples, interceptor con `withCredentials`.
- UI de corrección/borrado: edición inline en tarjeta y confirmación inline
  (sin modales ni librerías). Errores HTTP → mensajes vía
  `shared/api-error.ts:describeApiError` (409/404 reusan `detail` del backend).
  Actualización en caliente con signals (sin recargar ni state management).
- UI en español, paleta fría (variables CSS en `styles.scss`). El escaneo es
  la acción principal: campo de código con autofocus y retorno de foco tras
  cada operación.
- Commits/PR: no hay convención de equipo definida aún.
- Simplicidad > abstracción: nada de librerías/patrones nuevos sin necesidad.

## 9. Comandos

### Arranque completo (recomendado, Git Bash en Windows)

```bash
./start.sh   # Postgres + migraciones + seed + backend + frontend a la vez.
             # CTRL+C detiene ambos procesos. Espera a /api/health.
```

### Infraestructura

```bash
docker compose up -d                 # PostgreSQL local
```

### Backend (desde `backend/`, venv activado)

```bash
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -r requirements.txt
alembic upgrade head                 # aplicar migraciones
alembic downgrade base               # revertir (dev)
alembic revision --autogenerate -m "msg"   # nueva migración tras tocar modelos
python -m app.seed                   # usuario dev: admin / admin123 (Demo Workspace)
uvicorn app.main:app --reload        # API :8000, docs en /docs
pytest -q                            # tests (SQLite en memoria, sin Docker)
```

### Frontend (desde `frontend/`)

```bash
npm install
npm start                            # :4200
npm run build                        # verificación de build
# Tests (Karma+Jasmine). En esta máquina no hay Chrome: usar Edge (Chromium).
CHROME_BIN='C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe' \
  npx ng test --watch=false --browsers=ChromeHeadless
```

### E2E de la UI (con `./start.sh` en marcha)

```bash
node scripts/e2e-ui.mjs              # Edge headless vía CDP; 11 comprobaciones
```

## 10. Verificación actual (estado real comprobado)

- `pytest`: 47/47 OK (auth, 401s, conversión KG/LB, flujo escaneo
  nuevo/existente, aislamiento entre workspaces, XLSX, PATCH de productos,
  borrado seguro de productos y scans).
- Corrección/borrado verificados en vivo (curl): PATCH nombre+peso LB
  (recalcula `weight_kg`), PATCH barcode, 409 por barcode duplicado, 409 al
  borrar producto con scans, 204 al borrar scan y luego producto, 404 tras
  borrado. Swagger lista PATCH/DELETE con 404/409 documentados.
- Alembic `upgrade`/`downgrade`/`upgrade` OK contra PostgreSQL 16 en Docker.
- Flujo vivo con curl: login → needs_weight → created (44.09 LB → 19.998888 kg)
  → existing → historial → XLSX válido → logout → 401.
- CORS :4200→:8000 con credenciales OK; cookie HttpOnly verificada.
- `ng build` OK (Angular 20).
- `./start.sh` OK en Git Bash: levanta todo y CTRL+C deja 8000/4200 libres.
  OJO: uvicorn en el script va SIN --reload a propósito (el reloader
  rearranca al servidor al matarlo externamente y rompe el apagado limpio).
- Frontend: `ng test` 10/10 OK (products + history con HttpTestingController);
  `ng build` OK. E2E real con `scripts/e2e-ui.mjs` (Edge headless CDP):
  11/11 OK — login UI, escaneo nuevo/existente, edición con actualización en
  caliente, 409 duplicado, 409 borrar producto con scans, borrar scans,
  borrar producto sin scans, escaneo tras editar usa datos actualizados,
  layout a 480px sin scroll horizontal.

## 11. Reglas que el agente NO debe romper

1. No aceptar `workspace_id` del cliente en ningún endpoint.
2. No escribir queries que toquen datos de usuario sin filtrar por
   `workspace_id`.
3. No usar float para pesos ni `Base.metadata.create_all` para el esquema
   real (eso es Alembic; `create_all` solo en tests).
4. No implementar parser GS1, estadísticas, despliegue ni nada de Fase 3/4
   aunque "sea útil".
5. No añadir dependencias (ni backend ni frontend) sin justificación.
6. No hardcodear secretos; todo sensible va por `.env` (en `.gitignore`).
7. No cambiar el stack ni la estructura de capas sin actualizar este archivo.
8. Mantener el endpoint de escaneo único salvo que cambie el requisito.
9. No añadir PATCH/edición de scans (eventos inmutables) ni borrado de
   productos con scans saltándose la política 409.
10. No duplicar la conversión de pesos: toda recalibración pasa por
    `services/weight.py`.

## 12. Futuras extensiones previstas (diseño ya preparado, NO implementar)

- **Fase 3**: Neon + Render. `backend/Dockerfile` ya existe; config por env.
- **Fase 4**: parser GS1 sobre `barcode_raw` → rellenar `barcode_type` /
  `product_identifier`; estadísticas y gráficos.
- Posibles: edición de peso con auditoría, roles con permisos finos,
  revocación de tokens.
