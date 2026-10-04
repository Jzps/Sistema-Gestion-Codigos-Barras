from fastapi import APIRouter, Query, Response, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.scan import ScanOut, ScanRequest, ScanResponse
from app.services import scan_service
from app.repositories import scans as scans_repo

router = APIRouter(prefix="/scans", tags=["scans"])


@router.post("", response_model=ScanResponse)
def create_scan(
    payload: ScanRequest, response: Response, user: CurrentUser, db: DbSession
) -> ScanResponse:
    """Entrada unica del flujo de escaneo. El workspace se toma del usuario
    autenticado; nunca del cuerpo de la peticion."""
    result = scan_service.handle_scan(
        db, workspace_id=user.workspace_id, user_id=user.id, payload=payload
    )
    response.status_code = (
        status.HTTP_200_OK
        if result.status == "needs_weight"
        else status.HTTP_201_CREATED
    )
    return result


@router.get("", response_model=list[ScanOut])
def list_scans(
    user: CurrentUser,
    db: DbSession,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[ScanOut]:
    scans = scans_repo.list_history(db, user.workspace_id, limit=limit, offset=offset)
    return [scan_service.to_scan_out(scan) for scan in scans]
