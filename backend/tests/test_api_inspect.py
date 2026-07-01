"""/api/v1/inspect 上传端点测试 - 校验 X-Inspector-Id 与算法 code"""
import io
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.algorithm_registry import get_registry


@pytest.fixture(autouse=True)
def _reset_registry() -> None:
    get_registry()._cache = {}  # type: ignore[attr-defined]


def test_inspect_missing_inspector_id() -> None:
    """缺 X-Inspector-Id → 422 (FastAPI 校验)"""
    with TestClient(app) as client:
        r = client.post(
            "/api/v1/inspect/insulator-damage",
            files={"file": ("a.jpg", b"fake", "image/jpeg")},
            data={"meta": "{}"},
        )
    assert r.status_code in (400, 422)


def test_inspect_invalid_inspector_id() -> None:
    """X-Inspector-Id 格式错 → 400"""
    with TestClient(app) as client:
        r = client.post(
            "/api/v1/inspect/insulator-damage",
            files={"file": ("a.jpg", b"fake", "image/jpeg")},
            data={"meta": "{}"},
            headers={"X-Inspector-Id": "ab"},  # 太短
        )
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "INVALID_INSPECTOR_ID"


def test_inspect_unknown_algorithm() -> None:
    """未知算法 → 400"""
    with TestClient(app) as client:
        r = client.post(
            "/api/v1/inspect/nonexistent",
            files={"file": ("a.jpg", b"fake", "image/jpeg")},
            data={"meta": "{}"},
            headers={"X-Inspector-Id": "INSP-001"},
        )
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "INVALID_ALGORITHM"
