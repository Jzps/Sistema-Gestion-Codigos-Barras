# Guía de instalación — SGCBP (desarrollo local)

## Arranque rápido

Con la configuración inicial ya hecha (`.env`, `backend/.venv`,
`frontend/node_modules`), desde la raíz en **Git Bash**:

```bash
./start.sh
```

Levanta PostgreSQL si hace falta, aplica migraciones, carga el seed y arranca
backend + frontend a la vez (espera a `/api/health`). CTRL+C detiene todo.
Las secciones siguientes documentan el proceso manual equivalente.

## Prerrequisitos

| Herramienta | Versión mínima | Comprobación            |
| ----------- | -------------- | ----------------------- |
| Python      | 3.11           | `python --version`      |
| Node.js     | 20 (LTS 22 ok) | `node --version`        |
| Docker      | 24+            | `docker --version`      |

## 1. Variables de entorno

```bash
cp .env.example .env
```

Valores por defecto válidos para desarrollo local. **Nunca** subir `.env` a git.

## 2. Base de datos (PostgreSQL en Docker)

```bash
docker compose up -d
docker compose ps        # sgcbp_db debe aparecer "healthy"
```

Datos persistidos en el volumen `pgdata`. Para reiniciar desde cero:
`docker compose down -v && docker compose up -d`.

## 3. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows (PowerShell/CMD)
# source .venv/bin/activate   # Linux/macOS
pip install -r requirements.txt
```

### Migraciones y datos iniciales

```bash
alembic upgrade head     # crea el esquema (workspaces, users, products, scans)
python -m app.seed       # workspace + usuario admin de desarrollo
```

Seed crea (configurable en `.env`):

- Workspace: `Demo Workspace`
- Usuario: `admin` / `admin123` (rol admin) — **solo desarrollo**

### Ejecutar la API

```bash
uvicorn app.main:app --reload
```

- API: http://localhost:8000
- Documentación interactiva (OpenAPI): http://localhost:8000/docs
- Healthcheck: http://localhost:8000/api/health

## 4. Frontend

```bash
cd frontend
npm install
npm start
```

Aplicación en http://localhost:4200. La URL de la API se configura en
`frontend/src/environments/environment.ts` (`apiUrl`).

## 5. Prueba rápida del flujo completo

1. Entra en http://localhost:4200 e inicia sesión con `admin / admin123`.
2. En **Escanear**, escribe `7501234567890` y pulsa Enter (un lector USB
   real funciona igual: escribe los dígitos y envía Enter solo).
3. El sistema indica *Producto no registrado*: introduce `44.09` y elige `LB`.
4. Verás la confirmación con el peso normalizado: ≈ `20 kg`.
5. Vuelve a escanear el mismo código: el peso aparece al instante, sin pedirlo.
6. En **Historial** verás ambos eventos; pulsa **Exportar Excel** para
   descargar el `.xlsx`.

## 6. Tests

### Backend

```bash
cd backend
.venv\Scripts\activate
pytest -q
```

La suite usa SQLite en memoria y no necesita Docker. Cubre: autenticación,
protección de endpoints, conversión KG/LB, flujo de escaneo (nuevo/existente),
aislamiento entre workspaces, exportación XLSX, PATCH de productos y
borrado seguro (productos y scans).

### Frontend

```bash
cd frontend
# En Windows sin Chrome instalado, apuntar Karma a Edge (Chromium):
CHROME_BIN='C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe' \
  npx ng test --watch=false --browsers=ChromeHeadless
```

Tests de componentes de Productos e Historial con `HttpTestingController`:
renderizado de acciones, llamadas PATCH/DELETE correctas, actualización del
estado y manejo de errores 404/409.

### E2E de la interfaz

Con `./start.sh` en marcha:

```bash
node scripts/e2e-ui.mjs
```

Conduce la aplicación real en Edge headless (DevTools Protocol, sin
dependencias externas): login, escaneo completo, edición de producto, errores
409, eliminación de scans y de producto, y layout a 480px.

## Solución de problemas

| Síntoma                                    | Causa probable y solución                                  |
| ------------------------------------------ | ---------------------------------------------------------- |
| `connection refused` al migrar             | Postgres no está arriba: `docker compose up -d`            |
| 401 en todas las llamadas del frontend     | Falta cookie: el interceptor ya la envía; revisa CORS y que uses `localhost:4200` (origen permitido en `CORS_ORIGINS`) |
| Puerto 5432 ocupado                        | Ya hay un Postgres local: para el otro servicio o cambia el puerto en `docker-compose.yml` y `DATABASE_URL` |
| Puerto 8000/4200 ocupado                   | Otro proceso usándolo: ciérralo o cambia el puerto         |
| Cambios de modelos sin efecto              | Falta migración: `alembic revision --autogenerate -m "..." && alembic upgrade head` |
