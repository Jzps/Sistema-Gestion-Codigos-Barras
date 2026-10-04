from fastapi import APIRouter, Query, Response, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.scan import ScanOut, ScanRequest, ScanResponse
from app.services import scan_service
from app.repositories import scans as scans_repo

router = APIRouter(prefix="/scans", tags=["scans"])


@router.post(
    "",
    response_model=ScanResponse,
    summary="Procesa un escaneo (existente, nuevo con peso, o pide peso)",
)
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


@router.get(
    "",
    response_model=list[ScanOut],
    summary="Historial de escaneos del workspace (más recientes primero)",
)
def list_scans(
    user: CurrentUser,
    db: DbSession,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[ScanOut]:
    scans = scans_repo.list_history(db, user.workspace_id, limit=limit, offset=offset)
    return [scan_service.to_scan_out(scan) for scan in scans]


@router.delete(
    "/{scan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Elimina un escaneo incorrecto del historial",
    responses={404: {"description": "Escaneo inexistente o de otro workspace"}},
)
def delete_scan(scan_id: int, user: CurrentUser, db: DbSession) -> None:
    """Borra solo el evento (p. ej. una doble lectura accidental); el producto
    asociado no se modifica. No existe PATCH de scans: son eventos inmutables
    y la corrección es eliminar y volver a escanear."""
    scan_service.delete_scan(db, workspace_id=user.workspace_id, scan_id=scan_id)
