from fastapi import APIRouter, HTTPException, status

from app.core.config import get_settings
from app.schemas.upload import SignUploadIn, SignUploadOut
from app.services import storage_service

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("/sign", response_model=SignUploadOut,
             summary="URL firmada para subir la foto directo a Storage (PUT desde el navegador)")
def sign_upload(payload: SignUploadIn) -> SignUploadOut:
    if not get_settings().storage_enabled:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "El almacenamiento de fotos no está configurado; envía el reporte sin foto")
    try:
        return SignUploadOut(**storage_service.create_signed_upload(payload.filename, payload.content_type, payload.size))
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc))
    except Exception as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"Storage no disponible: {type(exc).__name__}")
