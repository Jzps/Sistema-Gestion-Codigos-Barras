# Cambiar la contraseña del administrador — SGCBP

Comando independiente para cambiar la contraseña del usuario administrador
(`admin`) **en la base de datos de producción (Neon)**.

- No modifica el workspace, el rol, el email ni ningún otro dato.
- No cambia el sistema de autenticación: reescribe el hash Argon2id guardado,
  exactamente lo que haría un "cambio de contraseña" en la aplicación.
- La contraseña **no** se escribe en ningún archivo, **no** se lee de ninguna
  variable de entorno y **no** se imprime ni se registra en ningún log.
- No ejecuta el seed ni crea nada.

---

## Qué hace, paso a paso

1. Conecta con `DATABASE_URL` (misma fuente que la aplicación).
2. Comprueba que el usuario existe. Si no existe, **aborta sin pedir nada** y
   sin tocar la base de datos.
3. Pide la nueva contraseña por consola, **sin eco en pantalla** (`getpass`).
4. La pide **dos veces** y exige que coincidan.
5. Valida que tenga **al menos 16 caracteres**.
6. Genera el hash con el **mismo mecanismo que la aplicación**
   (`app.core.security.hash_password` → Argon2id).
7. Actualiza **únicamente** la columna `password_hash` de ese usuario (un
   `UPDATE` dirigido, no una asignación del ORM) y confirma la transacción.
8. Verifica que el hash guardado valida la nueva contraseña y confirma el
   éxito **sin mostrar la contraseña ni su hash**.

Si algo falla en cualquier punto, la transacción se deshace: la base de datos
queda intacta.

---

## Cómo ejecutarlo desde la terminal Bash de Windows (Git Bash)

### Preparación (una sola vez)

```bash
cd /c/ruta/al/repo/Facturador_Excel/backend
python -m venv .venv
.venv/Scripts/activate          # o: source .venv/Scripts/activate
pip install -r requirements.txt
```

### Opción A — desde tu máquina, contra Neon (recomendada)

```bash
cd /c/ruta/al/repo/Facturador_Excel/backend

# Apunta a Neon SOLO para esta sesión. En Git Bash usa `export`:
export DATABASE_URL='postgresql+psycopg://<USUARIO>:<CONTRASENA>@ep-xxx-pooler.REGION.aws.neon.tech/neondb?sslmode=require'

# Ejecuta el comando (no necesita el venv activo si usas la ruta completa):
.venv/Scripts/python.exe -m app.reset_admin_password
```

Salida esperada:

```text
Usuario encontrado: admin (rol=admin)
Workspace: Demo Workspace

Nueva contrasena para 'admin' (minimo 16 caracteres):
Nueva contrasena:
Repite la nueva contrasena:

[OK] Contrasena actualizada para el usuario 'admin'.
     Solo se ha modificado el hash de contrasena.
```

> ⚠️ **Gotcha de Git Bash**: el prefijo `DATABASE_URL=... comando` **no**
> funciona con ejecutables de Windows (`python.exe`): la variable no llega al
> proceso. Usa `export` (como arriba) o `set DATABASE_URL=...`. Y **entrecomilla
> siempre la URL**: la contraseña de Neon puede llevar caracteres que el shell
> interpretaría.

Para **deshacer** la variable al terminar:

```bash
unset DATABASE_URL
```

Para actuar sobre otro usuario:

```bash
.venv/Scripts/python.exe -m app.reset_admin_password --username otro_usuario
```

Ayuda:

```bash
.venv/Scripts/python.exe -m app.reset_admin_password --help
```

### Opción B — desde la Shell de Render

En el panel de Render, abre la **Shell** del Web Service (`sgcbp-api`): allí
`DATABASE_URL` ya está definida y el comando se ejecuta contra Neon sin
tocar nada de tu máquina.

```bash
python -m app.reset_admin_password
```

> En planes de pago. En el plan free no hay Shell: usa la opción A.

### Opción C — contra la base de datos local (desarrollo)

```bash
cd backend
.venv/Scripts/python.exe -m app.reset_admin_password
```

Sin `DATABASE_URL` usa el `.env` local (PostgreSQL de Docker Compose).

---

## Comprobación

```bash
# Login con la nueva contraseña (debe devolver 200)
curl -s -o /dev/null -w "%{http_code}\n" -X POST \
  https://sgcbp-api.onrender.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"<TU_NUEVA_CONTRASENA>"}'
```

Y con la antigua debe devolver **401**.

---

## Notas

- **Sesiones abiertas**: cambiar la contraseña **no invalida** los JWT ya
  emitidos. Los tokens emitidos antes del cambio siguen siendo válidos hasta
  expirar (`ACCESS_TOKEN_EXPIRE_MINUTES`, 720 por defecto = 12 h). Si necesitas
  cerrar sesión inmediatamente, reinicia el Web Service en Render (cambia
  `SECRET_KEY` y haz un redeploy).
- **Longitud mínima**: 16 caracteres. El comando reintenta hasta 3 veces.
- **Terminal sin eco**: si el terminal no puede ocultar lo que escribes, el
  comando avisa con `[!] Aviso: esta terminal no permite ocultar lo que
  escribes...`. En ese caso escribe la contraseña en otro sitio y pégala con
  Ctrl+V / clic derecho.
- **No hay límite de intentos**: el comando es de administración, se ejecuta
  con acceso a la base de datos. La protección contra fuerza bruta de la API
  (`POST /api/auth/login`) no aplica aquí.

## Ficheros relacionados

| Fichero | Papel |
| --- | --- |
| `backend/app/reset_admin_password.py` | El comando (`python -m app.reset_admin_password`) |
| `backend/app/core/security.py` | `hash_password` / `verify_password` (Argon2id) — **no se modifican** |
| `backend/app/repositories/users.py` | `update_password_hash`: UPDATE dirigido solo al hash |
| `backend/tests/test_reset_admin_password.py` | 17 pruebas del comando |
