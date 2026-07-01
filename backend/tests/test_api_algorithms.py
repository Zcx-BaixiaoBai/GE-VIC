"""算法列表 API 测试 - 验证已注册算法"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app.services.algorithm_registry import get_registry


def test_algorithms_empty_without_db() -> None:
    """DB 不可用时, 列表为空 (启动时加载失败降级)"""
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
    """加载种子数据后能列出 insulator-damage"""
    from datetime import datetime, timezone
    from types import SimpleNamespace

    fake_algo = SimpleNamespace(
        code="insulator-damage",
        name="绝缘子破损识别",
        category="供配电",
        description="识别绝缘子伞裙破损",
        engine_type="cloud_api",
        is_active=True,
        version=1,
        engine_config={"provider": "aliyun"},
        request_schema=None,
    )
    get_registry()._cache = {"insulator-damage": fake_algo}  # type: ignore[attr-defined]

    with TestClient(app) as client:
        r = client.get(
            "/api/v1/algorithms",
            headers={"X-Inspector-Id": "INSP-001"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["code"] == "insulator-damage"
    # engine_config 已被脱敏,不应含 secret
    assert "access_key_secret" not in body["items"][0]["engine_config"]
