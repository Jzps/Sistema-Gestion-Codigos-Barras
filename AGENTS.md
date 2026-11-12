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
  - Fase 3 (preparado, sin desplegar): configuración de producción del
    backend y del frontend, `render.yaml` y `docs/setup-deploy.md`.
- **NO implementar (fuera de V1)**:
  - Fase 4: parser GS1 (GTIN, peso embebido, fechas, seriales, lotes),
    estadísticas, gráficos, chatbot, IA, app móvil.
  - Nunca: microservicios, Kubernetes, Redis, colas, WebSockets, cloud storage.
  - Gestión de usuarios / registro público: **decidido expresamente NO
    implementarlo** (app de uso individual). El usuario inicial se crea con
    `python -m app.seed`.

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
│   │   ├── seed.py         # `python -m app.seed` (usuario dev)
│   │   └── reset_admin_password.py  # `python -m app.reset_admin_password`
│   │                          # (cambio interactivo del hash del admin)
│   ├── alembic/            # env.py toma DATABASE_URL de app.core.config
│   ├── tests/              # pytest con SQLite en memoria (StaticPool)
│   └── requirements.txt    # versiones pineadas
├── frontend/src/app/
│   ├── auth/               # login, AuthService, guards, interceptor
│   ├── scanner/            # pantalla principal (escaneo + alta de peso)
│   ├── dashboard/  products/  history/  reports/  shared/
│   └── environments        # environment.ts (dev) + environment.prod.ts (prod)
├── frontend/scripts/build-prod.mjs  # build de producción: genera
│                                   # environment.prod.ts desde API_URL y
│                                   # verifica que el bundle no lleva localhost
├── docs/                   # requirements, architecture, database, setup,
│                            # setup-deploy (Render + Neon)
├── scripts/e2e-ui.mjs      # verificación E2E de la UI (Edge headless CDP, sin deps)
├── scripts/migrar-datos-neon/  # kit de migración de datos a Neon:
│                              #   export/import/verificar/revertir + ensayo
├── render.yaml             # blueprint de Render (web service Docker + static site)
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
8. **Foco del escáner (regla dura)**: el lector USB escribe en el elemento que
   tiene el foco. El foco debe permanecer **SIEMPRE** en el campo de código,
   incluso con el formulario de peso abierto. El campo de peso **NO** lleva
   `appAutofocus` (ver `frontend/src/app/scanner/scanner.html`). Si se rompe
   esta regla, el siguiente código de barras se guarda como peso del producto
   anterior (corrupción silenciosa). El E2E lo verifica en cada ejecución.
9. **Configuración de producción**: con `ENV=production` (o `COOKIE_SECURE=true`)
   la API **no arranca** si `SECRET_KEY` es la de ejemplo, si `COOKIE_SECURE` es
   false o si `CORS_ORIGINS` apunta a localhost (validador en
   `app/core/config.py`). Los secretos viven solo en variables de entorno,
   nunca en el repo.
9b. **SameSite de la cookie**: `COOKIE_SAMESITE` (`lax` | `none` | `strict`,
   por defecto `lax`) decide el atributo `SameSite` de la cookie de sesión, y
   se usa **exactamente el mismo valor** al emitirla y al borrarla en el
   logout. `none` **exige** `COOKIE_SECURE=true` (si no, la app no arranca).
   Necesario cuando frontend y API están en sitios distintos: en Render,
   `onrender.com` está en la Public Suffix List, así que `sgcbp-web...` y
   `sgcbp-api...` son cross-site y con `lax` el navegador no envía la cookie
   → 401 en todos los endpoints protegidos.
10. **Descargas de ficheros**: la descarga del Excel se hace con
    `HttpClient` (`responseType: 'blob'` + `withCredentials: true`), **nunca**
    con `window.location.href`. Una navegación top-level a otro origen es un
    canal de autenticación frágil (el navegador aplica políticas de cookies
    cross-site más restrictivas) y, si la API responde 401, el usuario abandona
    la SPA y aterriza en una página JSON. El endpoint sigue exigiendo la
    cookie de sesión: no se debilita la autenticación.
11. **Cambio de contraseña**: `python -m app.reset_admin_password` es el ÚNICO
    mecanismo de la V1 para cambiar la contraseña de un usuario existente (no
    hay endpoint de API). Pide la contraseña por consola sin eco, la confirma
    dos veces, exige 1 carácter mínimo y **solo** reescribe
    `users.password_hash` (UPDATE dirigido en `repositories/users.py`). Nunca
    imprime la contraseña ni su hash, ni la guarda en archivos o variables de
    entorno. No se modifica `app/core/security.py` ni el resto del sistema de
    autenticación.

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
- **Descargas**: se piden con `HttpClient` (`responseType: 'blob'`), se
  guardan con `URL.createObjectURL` + un `<a download>` y se libera la URL con
  `URL.revokeObjectURL`. Los errores se muestran con
  `shared/api-error.ts:describeApiError` (el 401 da el aviso de sesión
  caducada sin salir de la aplicación).
- **Entornos de Angular**: `src/environments/environment.ts` (dev, localhost) y
  `environment.prod.ts` (prod). El build de producción se hace SIEMPRE con
  `npm run build:prod` (`frontend/scripts/build-prod.mjs`): exige `API_URL`,
  genera `environment.prod.ts` y verifica que el bundle no contenga
  direcciones locales. `angular.json` sustituye `environment.ts` por
  `environment.prod.ts` en la configuración `production` (fileReplacements).
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
python -m app.reset_admin_password   # cambia el hash del admin (interactivo, sin eco)
uvicorn app.main:app --reload        # API :8000, docs en /docs
pytest -q                            # tests (SQLite en memoria, sin Docker)
```

### Frontend (desde `frontend/`)

```bash
npm install
npm start                            # :4200
npm run build                        # verificación de build (dev)
npm run build:prod                   # build de PRODUCCIÓN (exige API_URL)
# Tests (Karma+Jasmine). En esta máquina no hay Chrome: usar Edge (Chromium).
CHROME_BIN='C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe' \
  npx ng test --watch=false --browsers=ChromeHeadless
```

### E2E de la UI (con `./start.sh` en marcha)

```bash
node scripts/e2e-ui.mjs              # Edge headless vía CDP; 15 comprobaciones
```

### Producción (Render + Neon)

```bash
# Ver docs/setup-deploy.md para el procedimiento completo.
cd frontend && API_URL=https://sgcbp-api.onrender.com npm run build:prod
```

## 10. Verificación actual (estado real comprobado)

- `pytest`: **109/109 OK** (auth, 401s, conversión KG/LB, flujo escaneo
  nuevo/existente, aislamiento entre workspaces, XLSX, PATCH de productos,
  borrado seguro de productos y scans, validación de configuración de
  producción, cambio de contraseña del admin, atributo SameSite de la
  cookie de sesión, **kit de migración de datos a Neon**).
- Corrección/borrado verificados en vivo (curl): PATCH nombre+peso LB
  (recalcula `weight_kg`), PATCH barcode, 409 por barcode duplicado, 409 al
  borrar producto con scans, 204 al borrar scan y luego producto, 404 tras
  borrado. Swagger lista PATCH/DELETE con 404/409 documentados.
- Alembic: `upgrade`/`downgrade`/`upgrade` OK contra PostgreSQL 16 en Docker
  (verificado en una BD limpia desechable, sin tocar la BD de trabajo);
  `alembic check` → "No new upgrade operations detected" (modelos y migraciones
  en sincronía); `alembic current` → `0001 (head)`.
- Flujo vivo con curl: login → needs_weight → created (44.09 LB → 19.998888 kg)
  → existing → historial → XLSX válido → logout → 401.
- CORS :4200→:8000 con credenciales OK; cookie HttpOnly verificada.
- `ng build` OK (Angular 20) y `npm run build:prod` OK: el bundle de
  producción **no contiene ninguna dirección local** (verificado por grep) y
  publica en `frontend/dist/frontend/browser`.
- `./start.sh` OK en Git Bash: levanta todo y CTRL+C deja 8000/4200 libres.
  OJO: uvicorn en el script va SIN --reload a propósito (el reloader
  rearranca al servidor al matarlo externamente y rompe el apagado limpio).
- Frontend: `ng test` 13/13 OK (products + history con HttpTestingController,
  incluida la descarga del XLSX por HTTP con credenciales);
  `ng build` OK. La descarga del XLSX se ha verificado end-to-end con el
  frontend compilado y el backend real en un escenario cross-site: 200, blob
  XLSX válido descargado y el usuario sigue en la SPA (sin navegación).
  E2E real con `scripts/e2e-ui.mjs` (Edge headless CDP):
  **15/15 OK** — login UI, escaneo nuevo/existente, **foco del lector USB
  (el código nunca va al campo de peso)**, edición con actualización en
  caliente, 409 duplicado, 409 borrar producto con scans, borrar scans,
  borrar producto sin scans, escaneo tras editar usa datos actualizados,
  layout a 480px sin scroll horizontal y **limpieza sin residuos en la BD**.
- Validación de producción comprobada: con `ENV=production` la API **falla al
  arrancar** si `SECRET_KEY` es la de ejemplo, si `COOKIE_SECURE=false` o si
  `CORS_ORIGINS` apunta a localhost; con configuración correcta arranca.
- Migración a Neon **ensayada** de principio a fin contra una base de datos
  desechable (`scripts/migrar-datos-neon/rehearsal.sh`): exportar → backup →
  importar (transaccional) → verificar (3 productos, 5 escaneos, 0 huérfanos,
  0 E2E) → reimportar (idempotente) → revertir. La BD de ensayo se destruye
  al terminar y **Neon no se ha tocado**.
- `COOKIE_SAMESITE` comprobado: `lax` por defecto, `none` emite
  `SameSite=None` (+ `Secure`, `HttpOnly`, `Path=/`, `Max-Age`), el logout
  borra la cookie con el **mismo** `SameSite` y el flujo
  login → `/api/auth/me` → `/api/products` → `/api/scans` → logout → 401
  sigue verde.

## 11. Reglas que el agente NO debe romper

1. No aceptar `workspace_id` del cliente en ningún endpoint.
2. No escribir queries que toquen datos de usuario sin filtrar por
   `workspace_id`.
3. No usar float para pesos ni `Base.metadata.create_all` para el esquema
   real (eso es Alembic; `create_all` solo en tests).
4. No implementar parser GS1, estadísticas ni nada de Fase 4 aunque "sea
   útil". El despliegue (Fase 3) solo se *prepara* aquí: no se ejecuta.
5. No añadir dependencias (ni backend ni frontend) sin justificación.
6. No hardcodear secretos; todo sensible va por variables de entorno (`.env`
   en local, panel de Render en producción) y nunca al repositorio.
7. No cambiar el stack ni la estructura de capas sin actualizar este archivo.
8. Mantener el endpoint de escaneo único salvo que cambie el requisito.
9. No añadir PATCH/edición de scans (eventos inmutables) ni borrado de
   productos con scans saltándose la política 409.
10. No duplicar la conversión de pesos: toda recalibración pasa por
    `services/weight.py`.
12. No romper el foco del escáner (regla 8 de la sección 7) ni relajar la
    validación de configuración de producción (regla 9 de la sección 7).
13. No compilar el frontend de producción sin `API_URL`: el bundle publicado
    nunca debe apuntar a `localhost`.
14. No volver a las descargas por `window.location.href` (regla 10 de la
    sección 7).

## 12. Migración de datos a Neon

- `scripts/migrar-datos-neon/` es el **único** mecanismo para mover datos entre
  bases de datos (Alembic solo gestiona el esquema).
- Migran **3 productos y 5 escaneos reales** (ids 1,2,3 y 1,2,3,4,24). Los
  registros `E2E-*` **no** se migran: la validación aborta si se colaran.
- Garantías obligatorias (hay tests que las vigilan en
  `backend/tests/test_migration_assets.py`): una sola transacción,
  `ON CONFLICT DO NOTHING` (idempotencia), preflight de `workspace`/`usuario`
  y de duplicados, comprobación posterior de relaciones y escaneo huérfano,
  `setval` de las secuencias, copia de seguridad previa y reversión.
- `scripts/migrar-datos-neon/rehearsal.sh` ensaya el procedimiento entero
  contra una base de datos desechable. **Ejecutar el ensayo antes de tocar
  Neon.**
- La URL de Neon va por variable de entorno; **nunca** al repositorio.

## 13. Futuras extensiones previstas (diseño ya preparado, NO implementar)

- **Fase 3 (despliegue)**: Neon + Render. Ya está todo preparado
  (`backend/Dockerfile`, `render.yaml`, `frontend/scripts/build-prod.mjs`,
  `docs/setup-deploy.md`); falta únicamente ejecutarlo desde el panel.
- **Fase 4**: parser GS1 sobre `barcode_raw` → rellenar `barcode_type` /
  `product_identifier`; estadísticas y gráficos.
- Posibles: edición de peso con auditoría, roles con permisos finos,
  revocación de tokens, paginación/búsqueda en historial y productos,
  gestión de usuarios (decidido NO implementado en esta V1).
