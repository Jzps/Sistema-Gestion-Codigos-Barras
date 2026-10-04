# SGCBP — Sistema de Gestión de Códigos de Barras y Pesos

Aplicación web para registrar el peso de productos identificados por código de
barras. La primera vez que se escanea un código se introduce el peso **una sola
vez**; en escaneos posteriores el sistema reconoce el código y recupera el peso
automáticamente. Cada escaneo queda registrado en un historial exportable a
Excel (`.xlsx`), con aislamiento lógico de datos por workspace.

## Problema que resuelve

Flujo manual actual: escanear productos y registrar/recordar su peso a mano.
Con SGCBP:

```
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

```
Lector USB (modo teclado) → Navegador → Angular → FastAPI → PostgreSQL
```

Monorepo:

```
├── backend/     # API FastAPI (app/) + tests + alembic
├── frontend/    # SPA Angular
├── docs/        # requirements, architecture, database, setup
├── docker-compose.yml   # PostgreSQL local
└── .env.example
```

## Requisitos

- Python 3.11+ · Node 20+ · Docker Desktop

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

## Probar el flujo de escaneo

1. Inicia sesión en `http://localhost:4200`.
2. En la pantalla **Escanear**, escribe un código (o usa un lector USB: actúa
   como teclado y termina con Enter) y pulsa Enter.
3. Código nuevo → el sistema pide peso y unidad (KG/LB) → guardar.
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
node scripts/e2e-ui.mjs
```

## Documentación

- [docs/requirements.md](docs/requirements.md) — requisitos funcionales y alcance V1
- [docs/architecture.md](docs/architecture.md) — arquitectura y decisiones
- [docs/database.md](docs/database.md) — modelo de datos
- [docs/setup.md](docs/setup.md) — guía de instalación detallada
- [AGENTS.md](AGENTS.md) — memoria técnica del proyecto (reglas para agentes)
