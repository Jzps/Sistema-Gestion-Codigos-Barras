# Backend SGCBP - imagen de produccion para Render (web service).
#
# En desarrollo local el backend se ejecuta con uvicorn directamente
# (ver README.md y docs/setup.md); esta imagen es para el despliegue.
FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render asigna el puerto en la variable de entorno PORT y exige escuchar en
# 0.0.0.0. `alembic upgrade head` es idempotente: aplica las migraciones
# pendientes contra la base de datos configurada en DATABASE_URL (Neon).
#
# En planes de pago de Render se puede mover la migracion a un
# `preDeployCommand` para que no se ejecute en cada arranque.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

# Healthcheck propio (Render tambien puede usar su propio health check path
# contra /api/health). Se usa Python porque la imagen slim no trae curl.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/api/health', timeout=4).read()"
