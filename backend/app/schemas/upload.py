from pydantic import BaseModel, Field


class SignUploadIn(BaseModel):
    filename: str = Field(min_length=1, max_length=200)
    content_type: str = Field(pattern=r"^image/(jpeg|png|webp)$")
    size: int = Field(gt=0, description="Bytes; el navegador lo conoce antes de subir")


class SignUploadOut(BaseModel):
    path: str
    upload_url: str
    method: str = "PUT"
    headers: dict[str, str]
    expires_in_s: int
    public_url: str | None
