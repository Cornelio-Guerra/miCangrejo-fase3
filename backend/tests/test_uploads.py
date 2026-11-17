"""POST /api/v1/uploads/sign sin Supabase Storage configurado."""

SIGN = "/api/v1/uploads/sign"


def test_sign_sin_storage_503(client):
    response = client.post(SIGN, json={"filename": "foto.jpg", "content_type": "image/jpeg", "size": 1024})
    assert response.status_code == 503
    assert "no está configurado" in response.json()["detail"]


def test_sign_content_type_invalido_422(client):
    response = client.post(SIGN, json={"filename": "doc.pdf", "content_type": "application/pdf", "size": 1024})
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "content_type"]


def test_sign_tamano_cero_422(client):
    response = client.post(SIGN, json={"filename": "foto.png", "content_type": "image/png", "size": 0})
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "size"]
