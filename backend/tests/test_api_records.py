"""/api/v1/records query endpoint tests.

Verify error paths and parameter validation. Full DB flow tested in E2E.
"""
from fastapi.testclient import TestClient

from app.main import app


def test_records_list_requires_inspector_id() -> None:
    """GET /records requires X-Inspector-Id"""
    with TestClient(app) as client:
        r = client.get("/api/v1/records")
    assert r.status_code in (400, 422)


def test_records_list_with_invalid_inspector_id() -> None:
    """Invalid X-Inspector-Id returns 400"""
    with TestClient(app) as client:
        r = client.get("/api/v1/records", headers={"X-Inspector-Id": "x"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "INVALID_INSPECTOR_ID"


def test_record_detail_with_invalid_inspector_id() -> None:
    """Invalid X-Inspector-Id returns 400"""
    with TestClient(app) as client:
        r = client.get("/api/v1/records/1", headers={"X-Inspector-Id": "xx"})
    assert r.status_code == 400


def test_retry_invalid_inspector_id() -> None:
    """Invalid X-Inspector-Id returns 400"""
    with TestClient(app) as client:
        r = client.post("/api/v1/records/1/retry", headers={"X-Inspector-Id": "x"})
    assert r.status_code == 400


def test_enrich_invalid_inspector_id() -> None:
    """Invalid X-Inspector-Id returns 400"""
    with TestClient(app) as client:
        r = client.post("/api/v1/records/1/enrich", headers={"X-Inspector-Id": "x"})
    assert r.status_code == 400


def test_records_endpoints_registered() -> None:
    """Verify records endpoints are registered in the OpenAPI schema"""
    paths = app.openapi().get("paths", {})
    assert "/api/v1/records" in paths
    assert "/api/v1/records/{record_id}" in paths
    assert "/api/v1/records/{record_id}/retry" in paths
    assert "/api/v1/records/{record_id}/enrich" in paths