def test_health_reports_database_and_model(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json["data"]
    assert data["status"] == "ok"
    assert data["database"] == "ok"
    assert data["model"]["loaded"] is True
    assert data["model"]["version"].startswith("rf-")


def test_unknown_route_returns_json_error(client):
    res = client.get("/api/does-not-exist")
    assert res.status_code == 404
    assert res.json["error"]["code"] == "NOT_FOUND"


def test_wrong_method_returns_json_error(client):
    res = client.delete("/api/health")
    assert res.status_code == 405
    assert res.json["error"]["code"] == "METHOD_NOT_ALLOWED"


def test_security_headers_present(client):
    res = client.get("/api/health")
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert res.headers["Cache-Control"] == "no-store"


def test_legacy_frontend_routes_are_gone(client):
    # Flask no longer renders HTML pages; the React client does.
    for path in ("/frontdesk", "/doctor", "/test-pdf", "/api/generate-pdf"):
        assert client.get(path).status_code == 404
