from datetime import datetime
from io import BytesIO

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUser, DbSession
from app.repositories import scans as scans_repo
from app.services import scan_service
from app.services.excel_export import build_scans_xlsx

router = APIRouter(prefix="/reports", tags=["reports"])

_XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/scans.xlsx")
def export_scans_xlsx(user: CurrentUser, db: DbSession) -> StreamingResponse:
    """Genera y descarga el historial del workspace. El archivo se crea en
    memoria bajo demanda; no se guarda en disco."""
    scans = scans_repo.list_history(db, user.workspace_id, limit=10000)
    rows = [scan_service.to_scan_out(scan) for scan in scans]
    content = build_scans_xlsx(rows)
    filename = f"scans_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
    return StreamingResponse(
        BytesIO(content),
        media_type=_XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
