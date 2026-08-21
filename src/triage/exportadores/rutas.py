"""Rutas de descarga para exportadores específicos de cliente."""

from fastapi import APIRouter, HTTPException, Response, status

from triage.exportadores.dif import ErrorExportacionDif, generar_exportacion_dif
from triage.usuarios.seguridad import Sesion, UsuarioActual

router = APIRouter(prefix="/cotizaciones", tags=["exportaciones"])


@router.get("/{cotizacion_id}/exportaciones/dif.xlsx")
def descargar_dif(
    cotizacion_id: str,
    sesion: Sesion,
    _usuario: UsuarioActual,
) -> Response:
    """Descarga DIF sólo si precio final y tratamiento fiscal ya están confirmados."""

    try:
        exportacion = generar_exportacion_dif(sesion, cotizacion_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ErrorExportacionDif as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    return Response(
        content=exportacion.contenido,
        media_type=exportacion.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{exportacion.nombre_archivo}"',
            "Cache-Control": "no-store",
        },
    )
