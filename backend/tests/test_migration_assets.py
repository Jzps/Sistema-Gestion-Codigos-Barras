"""Pruebas de los recursos de migracion de datos (scripts/migrar-datos-neon).

No ejecutan la migracion: comprueban que los recursos existen y que siguen
conteniendo las garantias de seguridad (transaccion, idempotencia, exclusion
de los registros E2E, verificacion de relaciones y reinicio de secuencias).
Si alguien edita el kit y elimina una de esas barreras, estas pruebas fallan.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

KIT = Path(__file__).resolve().parents[2] / "scripts" / "migrar-datos-neon"

#: Ficheros que forman parte del kit.
REQUIRED_FILES = (
    "README.md",
    "exportar.sh",
    "importar.sh",
    "importar.sql",
    "verificar.sql",
    "revertir.sh",
    "restaurar.sh",
    "rehearsal.sh",
)

#: Ids que se migran (3 productos y 5 escaneos reales; nada de E2E).
PRODUCT_IDS = "1,2,3"
SCAN_IDS = "1,2,3,4,24"


@pytest.fixture(scope="module")
def kit() -> Path:
    if not KIT.is_dir():
        pytest.skip("el kit de migracion no esta en este checkout")
    return KIT


def test_all_required_files_exist(kit: Path):
    missing = [name for name in REQUIRED_FILES if not (kit / name).is_file()]
    assert not missing, f"faltan ficheros del kit: {missing}"


def test_shell_scripts_are_syntactically_valid(kit: Path):
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash no disponible en este entorno")
    for name in ("exportar.sh", "importar.sh", "revertir.sh", "restaurar.sh", "rehearsal.sh"):
        result = subprocess.run(
            [bash, "-n", str(kit / name)], capture_output=True, text=True
        )
        assert result.returncode == 0, f"{name}: {result.stderr}"


def test_import_sql_is_transactional(kit: Path):
    sql = (kit / "importar.sql").read_text(encoding="utf-8")
    assert "BEGIN;" in sql
    assert "COMMIT;" in sql
    assert sql.index("BEGIN;") < sql.index("COMMIT;")
    # La importacion no se hace si la transaccion falla.
    assert "ON_ERROR_STOP on" in sql


def test_import_is_idempotent(kit: Path):
    sql = (kit / "importar.sql").read_text(encoding="utf-8")
    assert sql.count("ON CONFLICT DO NOTHING") >= 2  # products y scans


def test_import_excludes_e2e_records(kit: Path):
    """Los registros de prueba E2E no se pueden colar en el destino."""
    sql = (kit / "importar.sql").read_text(encoding="utf-8")
    assert "E2E%" in sql
    assert "abortando" in sql.lower()


def test_import_verifies_relations_and_sequences(kit: Path):
    sql = (kit / "importar.sql").read_text(encoding="utf-8")
    # Se comprueban las relaciones (escaneos con producto) tras importar.
    assert "LEFT JOIN products" in sql
    assert "huerfano" in sql.lower()
    # Se reinician las secuencias para que el backend no use ids ocupados.
    assert "setval" in sql
    assert "pg_get_serial_sequence('products', 'id')" in sql
    assert "pg_get_serial_sequence('scans', 'id')" in sql


def test_import_preflight_checks_workspace_and_user(kit: Path):
    sql = (kit / "importar.sql").read_text(encoding="utf-8")
    assert "FROM workspaces WHERE id = 1" in sql
    assert "FROM users WHERE id = 1 AND workspace_id = 1 AND is_active" in sql
    # El UNIQUE (workspace_id, barcode_raw) se comprueba antes de insertar.
    assert "barcode_raw" in sql


def test_verificar_sql_covers_the_expected_counters(kit: Path):
    sql = (kit / "verificar.sql").read_text(encoding="utf-8")
    assert "productos_esperados" in sql
    assert "escaneos_esperados" in sql
    assert "escaneos_huerfanos" in sql
    assert "codigos_duplicados" in sql
    assert "productos_e2e" in sql


def test_export_uses_the_expected_ids(kit: Path):
    export = (kit / "exportar.sh").read_text(encoding="utf-8")
    assert f'PRODUCT_IDS="${{PRODUCT_IDS:-{PRODUCT_IDS}}}"' in export
    assert f'SCAN_IDS="${{SCAN_IDS:-{SCAN_IDS}}}"' in export
    assert "EXPECTED_PRODUCTS=3" in export
    assert "EXPECTED_SCANS=5" in export
    assert "E2E%" in export


def test_import_script_takes_a_backup_before_importing(kit: Path):
    script = (kit / "importar.sh").read_text(encoding="utf-8")
    backup = script.index("pg_dump")
    import_step = script.index("sgcbp_importar.sql")
    assert backup < import_step, "la copia de seguridad debe hacerse antes de importar"


def test_revert_only_touches_the_migrated_rows(kit: Path):
    """La reversion no debe tocar workspaces ni users (la contrasena del admin)."""
    script = (kit / "revertir.sh").read_text(encoding="utf-8")
    assert "DELETE FROM scans" in script
    assert "DELETE FROM products" in script
    assert "DELETE FROM users" not in script
    assert "DELETE FROM workspaces" not in script


def test_no_neon_url_is_hardcoded_in_the_kit(kit: Path):
    """Ninguna credencial de Neon puede quedar escrita en el repositorio.

    Se busca una URL con usuario Y contrasena (no un simple host de ejemplo).
    """
    # El usuario y la contrasena no pueden contener "<" ni ">" (placeholders
    # como <USUARIO>:<CONTRASENA> en la documentacion si son validos) ni "$"
    # (referencias a variables de shell, como en rehearsal.sh).
    url_con_credenciales = re.compile(r"postgresql(\+psycopg)?://[^\s:@/<>$]+:[^\s@/<>$]+@")
    for name in REQUIRED_FILES:
        content = (kit / name).read_text(encoding="utf-8")
        assert not url_con_credenciales.search(content), (
            f"{name} contiene una URL de conexion con credenciales"
        )
