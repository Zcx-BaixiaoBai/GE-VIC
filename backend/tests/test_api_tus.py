"""/api/v1/uploads TUS ????????

????? DB (mock session), ???:
  - ??? (Tus-Resumable, Tus-Version, Tus-Extension)
  - ???? + Creation-With-Upload
  - HEAD ?? offset
  - PATCH ????
  - DELETE ??
  - ?? offset -> 409
"""
import base64
import os
from typing import Any

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://gevic:gevic_dev_password@localhost:5432/gevic")
os.environ.setdefault("LLM_BASE_URL", "https://example.com/v1")
os.environ.setdefault("LLM_API_KEY", "test-key")
os.environ.setdefault("LLM_MODEL", "gpt-4o-mini")


class FakeResult:
    def __init__(self, scalar=None):
        self._scalar = scalar

    def scalar_one_or_none(self):
        return self._scalar


class _FakeAsyncSession:
    def __init__(self, sessions):
        self.sessions = sessions
        self.added = []
        self.deleted = []

    async def execute(self, stmt):
        # First match by id (very rough)
        for s in self.sessions.values():
            return FakeResult(s)
        return FakeResult(None)

    async def commit(self):
        pass

    async def flush(self):
        pass

    async def refresh(self, obj):
        if obj.id and obj.id not in self.sessions:
            self.sessions[obj.id] = obj

    def add(self, obj):
        self.added.append(obj)
        if obj.id is None:
            obj.id = "deadbeef" + str(len(self.sessions))
        self.sessions[obj.id] = obj

    async def delete(self, obj):
        self.deleted.append(obj)
        self.sessions.pop(obj.id, None)

    async def close(self):
        pass

    async def rollback(self):
        pass


class _FakeAsyncSessionCtx:
    def __init__(self, sessions):
        self._sess = _FakeAsyncSession(sessions)

    async def __aenter__(self):
        return self._sess

    async def __aexit__(self, *args):
        pass


class FakeUploadSession:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


@pytest.fixture
def fake_app(monkeypatch, tmp_path):
    from app.main import app
    from app.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "upload_tmp_dir", str(tmp_path))

    from app.api import tus as tus_mod
    from app.database import get_global_sessionmaker

    sessions = {}

    def make_session():
        return _FakeAsyncSessionCtx(sessions)

    sm = MagicMock()
    sm.return_value = make_session()
    monkeypatch.setattr(tus_mod, "get_global_sessionmaker", lambda: sm)
    monkeypatch.setattr("app.api.inspect.get_global_sessionmaker", lambda: sm)

    return app, sessions


from unittest.mock import MagicMock


def test_tus_options_returns_protocol_headers(fake_app):
    app, _ = fake_app
    with TestClient(app) as client:
        r = client.options("/api/v1/uploads")
    assert r.status_code == 204
    assert r.headers.get("Tus-Resumable") == "1.0.0"
    assert r.headers.get("Tus-Version") == "1.0.0"
    assert "creation" in r.headers.get("Tus-Extension", "")
    assert "termination" in r.headers.get("Tus-Extension", "")


def test_tus_create_session(fake_app):
    app, sessions = fake_app
    with TestClient(app) as client:
        r = client.post(
            "/api/v1/uploads",
            headers={
                "Tus-Resumable": "1.0.0",
                "Upload-Length": "1024",
                "Upload-Metadata": "filename " + base64.b64encode(b"test.jpg").decode() + ",filetype " + base64.b64encode(b"image/jpeg").decode(),
            },
        )
    assert r.status_code == 201
    assert "Location" in r.headers
    assert r.headers.get("Tus-Resumable") == "1.0.0"
    assert r.headers.get("Upload-Offset") == "0"
    assert len(sessions) == 1


def test_tus_create_with_upload_single_chunk(fake_app):
    app, sessions = fake_app
    body = b"hello-world" * 100
    with TestClient(app) as client:
        r = client.post(
            "/api/v1/uploads",
            headers={"Tus-Resumable": "1.0.0", "Upload-Length": str(len(body))},
            content=body,
        )
    assert r.status_code == 201
    assert r.headers.get("Upload-Offset") == str(len(body))
    sess = list(sessions.values())[0]
    assert sess.offset == len(body)
    assert sess.total_size == len(body)


def test_tus_head_returns_offset(fake_app):
    app, sessions = fake_app
    with TestClient(app) as client:
        r = client.post("/api/v1/uploads", headers={"Tus-Resumable": "1.0.0", "Upload-Length": "1000"})
        loc = r.headers["Location"]
        h = client.head(loc)
    assert h.status_code == 200
    assert h.headers.get("Upload-Offset") == "0"
    assert h.headers.get("Upload-Length") == "1000"


def test_tus_patch_appends_chunk(fake_app):
    app, sessions = fake_app
    with TestClient(app) as client:
        r = client.post("/api/v1/uploads", headers={"Tus-Resumable": "1.0.0", "Upload-Length": "1000"})
        loc = r.headers["Location"]
        p = client.patch(loc, headers={"Upload-Offset": "0", "Content-Type": "application/offset+octet-stream"}, content=b"x" * 400)
        assert p.status_code == 204
        assert p.headers.get("Upload-Offset") == "400"
        p2 = client.patch(loc, headers={"Upload-Offset": "400", "Content-Type": "application/offset+octet-stream"}, content=b"y" * 600)
        assert p2.status_code == 204
        assert p2.headers.get("Upload-Offset") == "1000"


def test_tus_patch_offset_mismatch_409(fake_app):
    app, sessions = fake_app
    with TestClient(app) as client:
        r = client.post("/api/v1/uploads", headers={"Tus-Resumable": "1.0.0", "Upload-Length": "1000"})
        loc = r.headers["Location"]
        p = client.patch(loc, headers={"Upload-Offset": "999", "Content-Type": "application/offset+octet-stream"}, content=b"x" * 100)
    assert p.status_code == 409


def test_tus_delete_cancels(fake_app):
    app, sessions = fake_app
    with TestClient(app) as client:
        r = client.post("/api/v1/uploads", headers={"Tus-Resumable": "1.0.0", "Upload-Length": "1000"})
        loc = r.headers["Location"]
        d = client.delete(loc)
    assert d.status_code == 204
    assert list(sessions.values())[0].status == "cancelled"


def test_tus_wrong_version_412(fake_app):
    app, _ = fake_app
    with TestClient(app) as client:
        r = client.post("/api/v1/uploads", headers={"Tus-Resumable": "0.0.1", "Upload-Length": "100"})
    assert r.status_code == 412


def test_tus_get_status_json(fake_app):
    app, sessions = fake_app
    with TestClient(app) as client:
        r = client.post("/api/v1/uploads", headers={"Tus-Resumable": "1.0.0", "Upload-Length": "2000"})
        loc = r.headers["Location"]
        sid = loc.rsplit("/", 1)[-1]
        client.patch(loc, headers={"Upload-Offset": "0", "Content-Type": "application/offset+octet-stream"}, content=b"x" * 1000)
        g = client.get(f"/api/v1/uploads/{sid}/status")
    assert g.status_code == 200
    body = g.json()
    assert body["total_size"] == 2000
    assert body["offset"] == 1000
    assert body["progress"] == 0.5
    assert body["status"] == "uploading"
