"""API 健康检查测试"""
from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint() -> None:
    """/api/v1/health 返回 200"""
    with TestClient(app) as client:
        r = client.get("/api/v1/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert "version" in body
        assert "env" in body


def test_root_endpoint() -> None:
    """根路径返回 app 信息"""
    with TestClient(app) as client:
        r = client.get("/")
        assert r.status_code == 200
        body = r.json()
        assert body["app"] == "gevic"
        assert body["status"] == "running"
