# SGCBP — Sistema de Gestión de Códigos de Barras y Pesos

Aplicación web para registrar el peso de productos identificados por código de
barras. La primera vez que se escanea un código se introduce el peso **una sola
vez**; en escaneos posteriores el sistema reconoce el código y recupera el peso
automáticamente. Cada escaneo queda registrado en un historial exportable a
Excel (`.xlsx`), con aislamiento lógico de datos por workspace.

## Problema que resuelve

Flujo manual actual: escanear productos y registrar/recordar su peso a mano.
Con SGCBP:

```text
ESCANEAR → ¿código existe?
             ├── NO → pedir peso (kg/lb) → convertir → guardar producto → registrar escaneo
             └── SÍ → recuperar peso almacenado → registrar escaneo
HISTORIAL → EXPORTAR XLSX
```

## Stack

| Capa      | Tecnología                                                        |
| --------- | ----------------------------------------------------------------- |
| Frontend  | Angular (componentes standalone, TypeScript, SCSS)                |
| Backend   | Python · FastAPI · SQLAlchemy 2 · Alembic · Pydantic · Uvicorn    |
| Seguridad | Argon2id (hash de contraseñas) · JWT en cookie HttpOnly           |
| Excel     | openpyxl                                                          |
| BD        | PostgreSQL 16 (Docker Compose)                                    |
| Tests     | pytest (SQLite en memoria para la suite; migraciones en Postgres) |

## Arquitectura

```text
Lector USB (modo teclado) → Navegador → Angular → FastAPI → PostgreSQL
```

Monorepo:

```text
├── backend/     # API FastAPI (app/) + tests + alembic
├── frontend/    # SPA Angular
├── docs/        # requirements, architecture, database, setup
├── docker-compose.yml   # PostgreSQL local
└── .env.example
```

## Requisitos

- Python 3.11+ · Node 20+ (22 recomendado) · Docker Desktop

## Puesta en marcha

### Arranque rápido (un solo comando)

Una vez hecha la [configuración inicial](#configuración-inicial-solo-la-primera-vez), desde la raíz del monorepo en **Git Bash**:

```bash
./start.sh
```

El script levanta PostgreSQL si no está activo, aplica las migraciones, carga el seed y arranca backend y frontend a la vez, esperando a que la API responda en `/api/health`. **CTRL+C detiene ambos procesos.**

- Backend: http://localhost:8000 (docs: http://localhost:8000/docs)
- Frontend: http://localhost:4200

### Configuración inicial (solo la primera vez)

```bash
cp .env.example .env                # ajustar si se desea

cd backend
python -m venv .venv
.venv\Scripts\activate              # Windows (Git Bash)
pip install -r requirements.txt
cd ..

cd frontend
npm install
cd ..
```

### Arranque manual (alternativa a `start.sh`)

```bash
docker compose up -d                # PostgreSQL

cd backend
.venv\Scripts\activate
alembic upgrade head                # crea/actualiza el esquema
python -m app.seed                  # workspace + usuario admin de desarrollo
uvicorn app.main:app --reload       # API en http://localhost:8000

cd frontend
npm start                           # http://localhost:4200
```

## Credenciales de desarrollo

Creadas por `python -m app.seed` (solo entorno local, configurables en `.env`):

- Usuario: `admin` · Contraseña: `admin123` · Workspace: `Demo Workspace`

Para **cambiar la contraseña del administrador** (local o en Neon) hay un
comando aparte que la pide por consola sin eco y solo reescribe el hash:

```bash
cd backend && .venv/Scripts/python.exe -m app.reset_admin_password
```

Procedimiento completo: [docs/cambiar-contrasena-admin.md](docs/cambiar-contrasena-admin.md).

## Probar el flujo de escaneo

1. Inicia sesión en `http://localhost:4200`.
2. En la pantalla **Escanear**, escribe un código (o usa un lector USB: actúa
   como teclado y termina con Enter) y pulsa Enter.
3. Código nuevo → el sistema pide peso y unidad (KG/LB) → guardar.
   - El foco **permanece en el campo de código** (para que el lector USB no se
     equivoque): haz clic en **Peso** para escribir el peso a mano.
4. Escanea el mismo código otra vez → el peso aparece al instante.
5. **Historial** muestra fecha, hora, código, producto, peso, unidad y usuario;
   desde ahí se descarga el `.xlsx`.
6. En **Productos** puedes **Editar** cualquier producto (código, nombre,
   peso, unidad) y **Eliminar** los que no tengan escaneos (si los tiene, la
   app avisa y no borra nada). En **Historial** puedes **Eliminar** un
   escaneo incorrecto; el producto no se ve afectado.

## Tests

```bash
cd backend
.venv\Scripts\activate
pytest -q

cd ../frontend
CHROME_BIN='C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe' \
  npx ng test --watch=false --browsers=ChromeHeadless   # Windows sin Chrome

# E2E de la interfaz (con ./start.sh en marcha), desde la raíz:
node scripts/e2e-ui.mjs      # Edge headless vía CDP; 15 comprobaciones
```

## Despliegue en producción (Render + Neon)

La V1 está preparada para publicarse con **Neon** (PostgreSQL) + **Render**
(Docker para la API y Static Site para Angular). La guía completa —variables de
entorno, migraciones, orden de creación de los servicios, verificación— está en
**[docs/setup-deploy.md](docs/setup-deploy.md)**.

Resumen de lo esencial:

```bash
# Build de producción del frontend (genera environment.prod.ts desde API_URL
# y comprueba que el bundle no lleva direcciones locales):
cd frontend && API_URL=https://sgcbp-api.onrender.com npm run build:prod
```

- **Backend**: `backend/Dockerfile` (aplica las migraciones y sirve en
  `0.0.0.0:$PORT`). Variables: `ENV=production`, `DATABASE_URL` (Neon),
  `SECRET_KEY` (secreto), `COOKIE_SECURE=true`, `COOKIE_SAMESITE=none`,
  `CORS_ORIGINS`.
  - `COOKIE_SAMESITE=none` es **necesario** porque `onrender.com` está en la
    Public Suffix List: el frontend y la API son sitios cross-site y con
    `SameSite=lax` el navegador no envía la cookie → 401 al abrir Productos o
    Historial.
- **Frontend**: `Render Static Site` con *Root Directory* `frontend`, build
  command `npm ci && npm run build:prod` y publish path `dist/frontend/browser`.
- **Configuración insegura**: con `ENV=production` (o `COOKIE_SECURE=true`) la
  API **no arranca** si `SECRET_KEY` es la de ejemplo, si las cookies no son
  seguras o si `CORS_ORIGINS` apunta a localhost.
- `render.yaml` incluye un *blueprint* equivalente con los dos servicios.

## Documentación

- [docs/requirements.md](docs/requirements.md) — requisitos funcionales y alcance V1
- [docs/architecture.md](docs/architecture.md) — arquitectura y decisiones
- [docs/database.md](docs/database.md) — modelo de datos
- [docs/setup.md](docs/setup.md) — guía de instalación detallada (local)
- [docs/setup-deploy.md](docs/setup-deploy.md) — despliegue en Render + Neon
- [docs/cambiar-contrasena-admin.md](docs/cambiar-contrasena-admin.md) — cambiar la contraseña del admin
- [AGENTS.md](AGENTS.md) — memoria técnica del proyecto (reglas para agentes)
