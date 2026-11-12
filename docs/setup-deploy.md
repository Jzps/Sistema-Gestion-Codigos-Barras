# Despliegue en Render + Neon — SGCBP

Guía para publicar la V1 (uso individual) con:

- **Frontend**: Angular 20 compilado a estáticos → **Render Static Site**
- **Backend**: FastAPI en Docker → **Render Web Service**
- **Base de datos**: PostgreSQL → **Neon**

> Esta guía no ejecuta nada por ti: describe exactamente qué introducir en
> cada panel. Ningún secreto se escribe en el repositorio.

---

## 0. Antes de empezar

| Requisito | Detalle |
| --- | --- |
| Cuenta de Neon | Plan gratuito suficiente (0.5 GB) |
| Cuenta de Render | Plan gratuito suficiente (los servicios free se duermen tras 15 min) |
| Repo en GitHub | Ya existe: `https://github.com/Jzps/Facturador_Excel.git` |
| **Rama a desplegar** | **`V1`** — es la rama con el código; `main` está en el commit inicial |

> ⚠️ **Importante**: la rama `main` del repositorio **no contiene la aplicación**
> (solo el primer commit). Configura Render con la rama `V1`, o fusiona `V1` en
> `main` antes de desplegar.

---

## 1. Neon — crear la base de datos

1. Entra en <https://console.neon.tech> → **Create Project** → nombre `sgcbp`.
2. Elige una región (la más cercana a ti; el *pooler* de Neon enruta igual).
3. Neon crea el esquema `neondb` y el rol por defecto.

### 1.1. Copiar la cadena de conexión

En **Connection Details** Neon muestra dos hosts:

| Host | Uso |
| --- | --- |
| `ep-xxx-pooler.REGION.aws.neon.tech` | **La aplicación** (vía PgBouncer, aguanta muchas conexiones) |
| `ep-xxx.REGION.aws.neon.tech` | **Conexión directa**: úsala para las migraciones de Alembic |

Abre la pestaña **Connection string** y copia los dos valores con el formato
`postgresql` (NO `postgres://`): Render y Alembic los convierten a
`postgresql+psycopg://`.

**Cadena para la aplicación** (guarda en un sitio seguro, es una contraseña):

```text
postgresql+psycopg://<USUARIO>:<CONTRASENA>@ep-xxx-pooler.REGION.aws.neon.tech/neondb?sslmode=require
```

**Cadena directa** (para migraciones):

```text
postgresql+psycopg://<USUARIO>:<CONTRASENA>@ep-xxx.REGION.aws.neon.tech/neondb?sslmode=require
```

> `?sslmode=require` es **obligatorio** en Neon: sin él la conexión falla.

### 1.2. (Opcional) Ajustar la escala a cero

Neon suspende la base de datos tras unos minutos de inactividad: la primera
petición tras la suspensión tarda unos segundos. Es normal y no afecta a la
correctitud. Si prefieres que no se suspenda, cambia el plan en Neon.

---

## 2. Migraciones de Alembic contra Neon

**Ejecútalas desde tu máquina, ANTES del primer despliegue**, con la cadena
**directa** (no la del pooler):

```bash
cd backend
.venv\Scripts\activate

# Solo en esta sesión: no guardes la URL de Neon en el .env local si no quieres.
set DATABASE_URL=postgresql+psycopg://<USUARIO>:<CONTRASENA>@ep-xxx.REGION.aws.neon.tech/neondb?sslmode=require

alembic upgrade head
```

Salida esperada:

```text
INFO  [alembic.runtime.migration] Running upgrade  -> 0001, Esquema inicial: ...
```

Comprobación:

```bash
alembic current     # -> 0001 (head)
alembic check       # -> "No new upgrade operations detected."
```

> El `Dockerfile` también ejecuta `alembic upgrade head` al arrancar, así que
> el despliegue es idempotente. Si prefieres que solo se aplique al desplegar
> (no en cada arranque), sobrescribe el **Start Command** del Web Service con:
> `uvicorn app.main:app --host 0.0.0.0 --port $PORT` y quita el `alembic` del
> `CMD` del Dockerfile.

### 2.1. Crear el usuario inicial (seed)

No hay registro público (decisión de alcance): el primer usuario se crea con
el seed. **Ejecútalo una vez** contra Neon:

```bash
set DATABASE_URL=postgresql+psycopg://<USUARIO>:<CONTRASENA>@ep-xxx-pooler.REGION.aws.neon.tech/neondb?sslmode=require
python -m app.seed
```

Crea el workspace `Demo Workspace` y el usuario `admin` / `admin123`
(contraseña definida en `SEED_ADMIN_PASSWORD`; **cámbiala antes de ejecutar el
seed** si no quieres la de por defecto).

> ⚠️ Si ejecutas el seed con la contraseña por defecto, cámbiala después. En la
> V1 **no hay endpoint para cambiar contraseñas**: si la cambias después del
> seed, actualiza el hash con `python -m app.seed` sobre una base limpia o
> edita la fila directamente. Lo más simple: define `SEED_ADMIN_PASSWORD` con
> tu contraseña real **antes** de ejecutar el seed.

### 2.2. Cambiar la contraseña del administrador (después del primer despliegue)

Hay un comando independiente para cambiar la contraseña del usuario `admin`
**sin tocar el seed** y sin que la contraseña pase por ningún archivo ni por
variables de entorno:

```bash
python -m app.reset_admin_password
```

Detalles y procedimiento completo en
[docs/cambiar-contrasena-admin.md](cambiar-contrasena-admin.md).

### 2.3. Migrar los datos reales del entorno local a Neon

La base de datos de Neon se crea **vacía** (solo con el seed), así que en
producción no aparece ningún producto ni escaneo hasta que se migran los
datos del entorno local.

El procedimiento completo, reversible y verificable está en
**[`scripts/migrar-datos-neon/README.md`](../scripts/migrar-datos-neon/README.md)**.
Resumen:

```bash
# 1) Ensayo sobre una base de datos desechable (no toca Neon)
scripts/migrar-datos-neon/rehearsal.sh

# 2) Exportar los 3 productos y 5 escaneos reales del entorno local
scripts/migrar-datos-neon/exportar.sh

# 3) Indicar la URL de Neon sin dejarla en el historial
read -rs -p "URL de Neon: " NEON_DATABASE_URL; export NEON_DATABASE_URL; echo

# 4) Importar (hace copia de seguridad, valida, importa y verifica)
scripts/migrar-datos-neon/importar.sh
```

Datos que se migran (los residuos de las pruebas E2E **no** se migran):

| products.id | barcode_raw | Nombre | Peso |
| --- | --- | --- | --- |
| 1 | `7501234567890` | Caja demo | 44.09 LB |
| 2 | `SNPK91365` | Prueba | 32.00 LB |
| 3 | `LIVE-1` | Producto live | 10.00 KG |

| scans.id | product_id | scanned_at |
| --- | --- | --- |
| 1 | 1 | 2026-10-04 18:47:05.410875+00 |
| 2 | 1 | 2026-10-04 18:47:05.461674+00 |
| 3 | 2 | 2026-10-04 19:42:06.298468+00 |
| 4 | 3 | 2026-10-04 20:06:22.597834+00 |
| 24 | 2 | 2026-11-08 18:45:41.720283+00 |

> Los ids se conservan para que las relaciones (`scans.product_id`) sigan
> apuntando al producto correcto. `workspace_id` y `user_id` son 1 en origen y
> en destino (el seed los crea así). La importación es **transaccional**,
> **idempotente**, hace **copia de seguridad** previa y se puede **revertir**.

---

## 3. Render — orden recomendado

El orden importa: el backend necesita conocer el dominio público del frontend
(CORS) y el frontend necesita conocer la URL de la API. Por eso:

1. **Primero** el Static Site → así conoces su dominio.
2. **Después** el Web Service → ya puedes fijar `CORS_ORIGINS`.
3. **Último**, vuelve al Static Site → rellena `API_URL` y redespliega.

### 3.1. Static Site (frontend)

**New → Static Site**, conectando el repositorio:

| Campo | Valor |
| --- | --- |
| Repository | `Jzps/Facturador_Excel` |
| Branch | **`V1`** |
| Root Directory | `frontend` |
| Build Command | `npm ci && npm run build:prod` |
| Publish Directory | `dist/frontend/browser` |
| Environment | `API_URL` = `https://sgcbp-api.onrender.com` (se rellena en el paso 3.3) |

**Environment variables** del Static Site:

| Clave | Valor | ¿Secreto? |
| --- | --- | --- |
| `API_URL` | `https://sgcbp-api.onrender.com` (URL de la API **sin** `/api` y **sin** barra final) | no |
| `NODE_VERSION` | `22` | no |

> `API_URL` se consume en tiempo de **build** por `frontend/scripts/build-prod.mjs`:
> valida la URL, genera `src/environments/environment.prod.ts` y compila. Si
> falta la variable, el build **falla** (no se publica un bundle con
> `localhost`). Cambia `API_URL` ⇒ hay que **redesplegar** (Deploy → Manual
> Deploy) para que se aplique.

**Routing** (en la pestaña *Settings → Routing*): añade un rewrite

```text
/*  →  /index.html
```

Sin este rewrite, recargar una ruta interna (`/historial`) devuelve un 404:
Angular es una SPA y todas las rutas deben servir `index.html`.

**Anota el dominio** que Render asigna, p. ej. `https://sgcbp-web.onrender.com`.
Lo necesitas para `CORS_ORIGINS`.

### 3.2. Web Service (backend)

**New → Web Service**, conectando el mismo repositorio:

| Campo | Valor |
| --- | --- |
| Repository | `Jzps/Facturador_Excel` |
| Branch | **`V1`** |
| Root Directory | `backend` (Render detecta `backend/Dockerfile`) |
| Runtime | Docker |
| Health Check Path | `/api/health` |
| Instance Type | `free` (o `starter` para no dormir) |

En Docker, Render usa el `Dockerfile` del *Root Directory*; no hay *Build
Command* propio. El arranque lo define el `CMD` de `backend/Dockerfile`:

```text
alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

**Environment variables** del Web Service:

| Clave | Valor | ¿Secreto? |
| --- | --- | --- |
| `ENV` | `production` | no |
| `DATABASE_URL` | `postgresql+psycopg://<USUARIO>:<CONTRASENA>@ep-xxx-pooler.REGION.aws.neon.tech/neondb?sslmode=require` | **SÍ** |
| `SECRET_KEY` | `secrets.token_hex(32)` generado por Render (*Generate*) | **SÍ** |
| `ALGORITHM` | `HS256` | no |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `720` | no |
| `COOKIE_SECURE` | `true` | no |
| `COOKIE_SAMESITE` | `none` | no |
| `CORS_ORIGINS` | `https://sgcbp-web.onrender.com` (dominio real del frontend, **sin** barra final ni `/`) | no |
| `HOST` | `0.0.0.0` | no |
| `PORT` | *lo asigna Render; no lo definas* | — |

#### ⚠️ `COOKIE_SAMESITE=none` es obligatoria en este despliegue

**Sin esta variable la aplicación no funciona**, aunque el login "parezca"
correcto:

- `onrender.com` está en la **Public Suffix List** → `sgcbp-web.onrender.com` y
  `sgcbp-api.onrender.com` son **sitios distintos (cross-site)**.
- Con `SameSite=lax` (valor por defecto) el navegador **no envía** la cookie en
  las peticiones XHR cross-site → `/api/products` y `/api/scans` responden
  **401** y la UI muestra *"Tu sesión ha expirado. Vuelve a iniciar sesión."*.
- El login sí funciona, porque esa petición no necesita cookie y el
  `Set-Cookie` sí se guarda (guardar no está restringido por SameSite; solo el
  envío).

Por eso `COOKIE_SAMESITE=none` **exige** `COOKIE_SECURE=true` (los navegadores
rechazan una cookie `SameSite=None` sin `Secure`). La API **falla al arrancar**
si se configura `COOKIE_SAMESITE=none` con `COOKIE_SECURE=false`.

> Cambio **manual**: en el panel de Render → `sgcbp-api` → *Environment* →
> añadir `COOKIE_SAMESITE` = `none` y guardar. Render reinicia el servicio
> solo. `COOKIE_SECURE=true` ya existe y **se conserva**.

### 3.3. Volver al Static Site

Rellena `API_URL=https://sgcbp-api.onrender.com` y haz **Manual Deploy**.
Si el Web Service se llama de otra forma, `API_URL` debe coincidir con su
dominio real (`https://<nombre-del-servicio>.onrender.com`).

---

## 4. Alternativa: Blueprint (`render.yaml`)

El repo incluye `render.yaml` (Render Blueprint). Aplica el flujo así:

1. **New → Blueprint** → selecciona el repo y la rama `V1`.
2. Render te pedirá los valores marcados `sync: false`:
   - `DATABASE_URL` (cadena de Neon, con contraseña)
   - `CORS_ORIGINS` (dominio del frontend)
   - `API_URL` (dominio de la API)
3. Render crea los dos servicios y **genera** un `SECRET_KEY` seguro
   (`generateValue: true`).

**Limitación**: los dominios los genera Render y pueden llevar sufijo
(`sgcbp-web-xyz.onrender.com`). Si el CORS que introdujeste no coincide
exactamente con el dominio real, la API rechazará las llamadas del navegador
con un error de CORS. **Verifica el dominio real en el panel y corrige
`CORS_ORIGINS` si hace falta** (el Web Service se reinicia al cambiar una
variable de entorno).

---

## 5. Verificación tras el despliegue

```bash
# 1. La API responde y ve la base de datos
curl -s https://sgcbp-api.onrender.com/api/health
# {"status":"ok","db":"ok"}

# 2. El frontend carga
curl -sI https://sgcbp-web.onrender.com/ | head -1     # HTTP/2 200

# 3. El bundle publicado NO apunta a localhost
curl -s https://sgcbp-web.onrender.com/main-<hash>.js | grep -c localhost   # -> 0
```

Y en el navegador:

1. `https://sgcbp-web.onrender.com` → login con `admin` / tu contraseña.
   - DevTools → *Application* → *Cookies* → `https://sgcbp-api.onrender.com`:
     la cookie `sgcbp_session` debe existir con **SameSite=None** y **Secure**.
     Si pone `SameSite=Lax`, falta `COOKIE_SAMESITE=none` en el servicio.
2. Escanear un código → pide peso → **fíjate en que el foco sigue en el campo
   de código** (clic en "Peso" para escribirlo).
3. Historial → la fila aparece → **Exportar Excel** descarga un `.xlsx` válido.
4. Productos → editar un peso en LB → se ve el equivalente en kg.

---

## 6. Notas y límites conocidos

- **Plan free de Render**: el Web Service se duerme tras 15 min de inactividad
  y la primera petición tarda en despertar (~30 s). Para uso diario, plan
  `starter`.
- **Neon**: escala a cero tras inactividad; la primera petición tras suspender
  tarda unos segundos.
- **HTTPS**: Render emite un certificado TLS automático; por eso
  `COOKIE_SECURE=true` es obligatorio (la cookie de sesión no viaja sin HTTPS).
- **Sin proxy inverso propio**: Render enruta `*.onrender.com` al servicio. Si
  usas un dominio propio, añádelo también a `CORS_ORIGINS`.
- **Sesiones**: el JWT es *stateless* (12 h por defecto). Tras cerrar sesión, una
  copia del token sigue siendo válida hasta expirar. Limitación conocida y
  aceptada en la V1.
- **Un solo usuario**: la V1 no tiene gestión de usuarios ni registro público.
  El usuario se crea con el seed (paso 2.1).
- **CORS**: solo se permite el origen exacto configurado en `CORS_ORIGINS`
  (con credenciales). Si añades un dominio nuevo, actualiza la variable.

---

## 7. Problemas frecuentes

| Síntoma | Causa probable y solución |
| --- | --- |
| El frontend carga pero la API da error de CORS | `CORS_ORIGINS` no coincide con el dominio real (verifica en el panel, sin barra final) |
| El login funciona pero Productos/Historial muestran *"Tu sesión ha expirado"* (401) | Falta `COOKIE_SAMESITE=none` en `sgcbp-api` (con `COOKIE_SECURE=true`). Los dos subdominios de `onrender.com` son sitios cross-site y con `SameSite=lax` el navegador no envía la cookie |
| `500 Internal server error` al arrancar | `ENV=production` con `SECRET_KEY` de ejemplo, `COOKIE_SECURE=false` o CORS a localhost → el proceso muere con un mensaje explícito en los logs |
| `connection refused` / `server closed the connection unexpectedly` | Falta `?sslmode=require` en `DATABASE_URL`, o falta `pool_recycle` (ya está en el código) |
| El login devuelve 401 siempre | `SECRET_KEY` cambió entre arranques (invalida los tokens) o el reloj del servidor va desviado |
| La app funciona en local pero en Render no | El bundle apunta a `localhost`: revisa que el build command sea `npm run build:prod` y que `API_URL` esté definida |
| Error al ejecutar las migraciones contra Neon | Usa la conexión **directa** (sin `-pooler`) para Alembic |
| Al recargar `/historial` sale 404 | Falta el rewrite `/* → /index.html` en el Static Site |
