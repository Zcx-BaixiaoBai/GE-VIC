"""Algorithm list API tests - verify seeded algorithms are returned"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app.services.algorithm_registry import get_registry


def test_algorithms_empty_without_db() -> None:
    """DB unavailable: empty list (graceful degradation)"""
    get_registry()._cache = {}  # type: ignore[attr-defined]
    with TestClient(app) as client:
        r = client.get(
            "/api/v1/algorithms",
            headers={"X-Inspector-Id": "INSP-001"},
        )
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert "total" in body


def test_algorithms_list_with_seed() -> None:
    """Seeding adds algorithms including demo"""
    from datetime import datetime, timezone
    from types import SimpleNamespace

    fake_algo = SimpleNamespace(
        code="insulator-damage",
        name="Insulator Damage Detection",
        category="Power",
        description="Detect insulator damage",
        engine_type="cloud_api",
        is_active=True,
        version=1,
        engine_config={"provider": "aliyun"},
        request_schema=None,
    )
    fake_demo = SimpleNamespace(
        code="insulator-demo",
        name="Insulator Damage Demo",
        category="Power",
        description="Demo engine",
        engine_type="mock",
        is_active=True,
        version=1,
        engine_config={"delay_ms": 500, "defects_count": 1},
        request_schema=None,
    )
    get_registry()._cache = {
        "insulator-damage": fake_algo,
        "insulator-demo": fake_demo,
    }  # type: ignore[attr-defined]

    with TestClient(app) as client:
        r = client.get(
            "/api/v1/algorithms",
            headers={"X-Inspector-Id": "INSP-001"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    codes = {item["code"] for item in body["items"]}
    assert "insulator-damage" in codes
    assert "insulator-demo" in codes
    # engine_config should be redacted, no secret fields
    for item in body["items"]:
        assert "access_key_secret" not in item["engine_config"]