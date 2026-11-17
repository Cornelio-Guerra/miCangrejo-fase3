def test_health_reporta_modo_de_contingencia(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "micangrejo-api",
        "database": "sqlite (contingencia)",
        "ia": "reglas (contingencia)",
        "email": "simulado (contingencia)",
        "storage": "desactivado (fotos opcionales)",
        "whatsapp": "solo webhook local",
        "telegram": "desactivado",
        "sla_dias": 5,
    }
