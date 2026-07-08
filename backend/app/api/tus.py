"""TUS 1.0.0 协议核心端点 - 断点续传 + 进度查询

实现的核心扩展 (tus.io protocol 1.0.0):
  - Creation (POST /uploads)
  - Creation-With-Upload (POST /uploads + body)
  - Expiration (响应头 Upload-Expires)
  - Termination (DELETE /uploads/{id})

端点:
  OPTIONS  /api/v1/uploads                    -> 协议能力声明
  POST     /api/v1/uploads                    -> 创建会话 (+ 可选一次性上传)
  HEAD     /api/v1/uploads/{id}               -> 查询 offset
  PATCH    /api/v1/uploads/{id}               -> 写入一个分片
  DELETE   /api/v1/uploads/{id}               -> 取消

完成上传后, 客户端调 POST /api/v1/inspect/{code}/from-upload/{session_id}
进入识别流程 (与原 POST /inspect/{code} 等价, 但文件已上传完)。
"""
import base64
import asyncio
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_global_sessionmaker
from app.models import UploadSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/uploads", tags=["uploads"])

TUS_VERSION = "1.0.0"
TUS_EXTENSIONS = "creation,creation-with-upload,expiration,termination"
TUS_MAX_SIZE = 600 * 1024 * 1024  # 600MB 硬上限 (cpolar 友好, 可调)

# 解析 TUS Upload-Metadata header: "key b64value,key b64value,..."
_META_RE = re.compile(r"([^,\s]+)\s+([^,\s]*)")


def _parse_tus_metadata(header: str | None) -> dict[str, str]:
    if not header:
        return {}
    out: dict[str, str] = {}
    for m in _META_RE.finditer(header):
        key, val = m.group(1), m.group(2)
        try:
            out[key] = base64.b64decode(val).decode("utf-8", errors="replace") if val else ""
        except Exception:
            out[key] = val
    return out


def _ensure_tmp_dir() -> Path:
    settings = get_settings()
    p = Path(settings.upload_tmp_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _tus_base_headers() -> dict[str, str]:
    return {
        "Tus-Resumable": TUS_VERSION,
        "Tus-Version": TUS_VERSION,
        "Tus-Extension": TUS_EXTENSIONS,
        "Tus-Max-Size": str(TUS_MAX_SIZE),
    }


async def _session_dep() -> AsyncSession:
    sm = get_global_sessionmaker()
    async with sm() as session:
        yield session


@router.options("", include_in_schema=False)
async def options_uploads() -> Response:
    """TUS 协议能力声明"""
    return Response(status_code=204, headers=_tus_base_headers())


@router.options("/{session_id}", include_in_schema=False)
async def options_uploads_one(session_id: str) -> Response:
    return Response(status_code=204, headers=_tus_base_headers())


@router.post("", status_code=201)
async def create_upload(
    request: Request,
    upload_length: int = Header(..., alias="Upload-Length", ge=1, le=TUS_MAX_SIZE),
    upload_metadata: str | None = Header(default=None, alias="Upload-Metadata"),
    upload_defer_length: int | None = Header(default=None, alias="Upload-Defer-Length"),
    tus_resumable: str | None = Header(default=None, alias="Tus-Resumable"),
    session: AsyncSession = Depends(_session_dep),
) -> Response:
    """创建上传会话 (可选带首个分片 - Creation-With-Upload)"""
    if tus_resumable and tus_resumable != TUS_VERSION:
        raise HTTPException(status_code=412, detail="Tus-Resumable version mismatch")

    meta = _parse_tus_metadata(upload_metadata)
    filename = meta.get("filename") or meta.get("name") or "upload.bin"
    content_type = meta.get("filetype") or meta.get("type") or "application/octet-stream"
    file_type = meta.get("file_type") or _guess_file_type(filename)

    tmp_dir = _ensure_tmp_dir()
    sm = get_global_sessionmaker()
    async with sm() as session:
        new_id = _new_id()
        tmp_path = tmp_dir / f"{new_id}.bin"
        tmp_path.touch()

        sess = UploadSession(
            id=new_id,
            total_size=upload_length,
            offset=0,
            filename=filename,
            content_type=content_type,
            metadata_json=meta,
            tmp_path=str(tmp_path),
            file_type=file_type,
            status="uploading",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        session.add(sess)
        await session.commit()
        await session.refresh(sess)
        session_id = sess.id

    base_url = str(request.base_url).rstrip("/")
    location = f"{base_url}/api/v1/uploads/{session_id}"

    headers = _tus_base_headers()
    headers["Location"] = location
    headers["Upload-Expires"] = (datetime.now(timezone.utc) + timedelta(hours=24)).strftime(
        "%a, %d %b %Y %H:%M:%S GMT"
    )

    # Creation-With-Upload: 同一个请求 body 直接作为首个分片写入
    body = await request.body()
    if body:
        written = await _write_chunk(session_id, body, expected_offset=0)
        if not written:
            raise HTTPException(status_code=409, detail="Offset mismatch on create-with-upload")
        headers["Upload-Offset"] = str(len(body))
    else:
        headers["Upload-Offset"] = "0"

    return Response(status_code=201, headers=headers)


@router.head("/{session_id}", include_in_schema=False)
async def head_upload(
    session_id: str,
    session: AsyncSession = Depends(_session_dep),
) -> Response:
    """查询上传进度 (用于断点续传)"""
    sess = await _get_session(session, session_id)
    if sess is None:
        return Response(status_code=404, headers=_tus_base_headers())
    headers = _tus_base_headers()
    headers["Upload-Offset"] = str(sess.offset)
    headers["Upload-Length"] = str(sess.total_size)
    headers["Upload-Expires"] = sess.expires_at.strftime("%a, %d %b %Y %H:%M:%S GMT")
    headers["Cache-Control"] = "no-store"
    return Response(status_code=200, headers=headers)


@router.patch("/{session_id}", include_in_schema=False)
async def patch_upload(
    session_id: str,
    request: Request,
    upload_offset: int = Header(..., alias="Upload-Offset", ge=0),
    content_type: str = Header(default="application/offset+octet-stream"),
    session: AsyncSession = Depends(_session_dep),
) -> Response:
    """追加一个分片"""
    if "application/offset+octet-stream" not in content_type:
        raise HTTPException(status_code=415, detail="Content-Type must be application/offset+octet-stream")

    sess = await _get_session(session, session_id)
    if sess is None:
        return Response(status_code=404, headers=_tus_base_headers())
    if sess.status != "uploading":
        raise HTTPException(status_code=410, detail=f"Session is {sess.status}")
    if upload_offset != sess.offset:
        # 客户端与服务端不同步 - 客户端应该先 HEAD 一下拿到正确 offset
        return Response(
            status_code=409,
            headers={**_tus_base_headers(), "Upload-Offset": str(sess.offset)},
        )

    body = await request.body()
    if not body:
        return Response(status_code=204, headers={**_tus_base_headers(), "Upload-Offset": str(sess.offset)})

    new_offset = sess.offset + len(body)
    if new_offset > sess.total_size:
        raise HTTPException(status_code=413, detail="Chunk exceeds Upload-Length")

    # 追加写 (异步, 大文件场景用 aiofiles 更佳, 这里先同步)
    tmp_path = Path(sess.tmp_path)
    await asyncio.to_thread(_append_bytes, tmp_path, body)

    sess.offset = new_offset
    if new_offset == sess.total_size:
        sess.status = "completed"
    await session.commit()

    headers = _tus_base_headers()
    headers["Upload-Offset"] = str(new_offset)
    return Response(status_code=204, headers=headers)


@router.delete("/{session_id}", include_in_schema=False)
async def delete_upload(
    session_id: str,
    session: AsyncSession = Depends(_session_dep),
) -> Response:
    """取消上传 (清理临时文件)"""
    sess = await _get_session(session, session_id)
    if sess is None:
        return Response(status_code=404, headers=_tus_base_headers())
    _cleanup_session(sess)
    sess.status = "cancelled"
    await session.commit()
    return Response(status_code=204, headers=_tus_base_headers())


@router.get("/{session_id}/status")
async def get_session_status(
    session_id: str,
    session: AsyncSession = Depends(_session_dep),
) -> dict[str, Any]:
    """给前端用的 JSON 状态查询 (兼容非 TUS 客户端)"""
    sess = await _get_session(session, session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail={"code": "SESSION_NOT_FOUND", "message": "Session not found"})
    return {
        "id": sess.id,
        "offset": sess.offset,
        "total_size": sess.total_size,
        "progress": (sess.offset / sess.total_size) if sess.total_size > 0 else 0,
        "status": sess.status,
        "filename": sess.filename,
        "expires_at": sess.expires_at.isoformat() if sess.expires_at else None,
    }


# ----------------- helpers -----------------

def _new_id() -> str:
    import uuid as _u
    return _u.uuid4().hex


def _append_bytes(path: Path, data: bytes) -> None:
    """Append a chunk to the temp file (runs in a thread to avoid blocking the loop)."""
    with path.open("ab") as f:
        f.write(data)


def _guess_file_type(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in {"jpg", "jpeg", "png", "bmp", "webp", "gif", "heic"}:
        return "image"
    if ext in {"mp4", "mov", "avi", "mkv", "webm"}:
        return "video"
    return "other"


async def _get_session(session: AsyncSession, session_id: str) -> UploadSession | None:
    stmt = select(UploadSession).where(UploadSession.id == session_id)
    r = await session.execute(stmt)
    return r.scalar_one_or_none()


async def _write_chunk(session_id: str, body: bytes, expected_offset: int) -> bool:
    """同步方式写首个分片 (Creation-With-Upload 用)"""
    sm = get_global_sessionmaker()
    async with sm() as session:
        sess = await _get_session(session, session_id)
        if sess is None or sess.offset != expected_offset:
            return False
        await asyncio.to_thread(_append_bytes, Path(sess.tmp_path), body)
        sess.offset = expected_offset + len(body)
        if sess.offset == sess.total_size:
            sess.status = "completed"
        await session.commit()
    return True


def _cleanup_session(sess: UploadSession) -> None:
    try:
        p = Path(sess.tmp_path)
        if p.exists():
            p.unlink()
    except Exception as e:
        logger.warning("Failed to cleanup tmp file %s: %s", sess.tmp_path, e)


async def gc_expired_sessions() -> int:
    """清理过期会话 (启动时调用)"""
    sm = get_global_sessionmaker()
    deleted = 0
    async with sm() as session:
        stmt = select(UploadSession).where(UploadSession.expires_at < datetime.now(timezone.utc))
        for sess in (await session.execute(stmt)).scalars():
            _cleanup_session(sess)
            await session.delete(sess)
            deleted += 1
        await session.commit()
    if deleted:
        logger.info("GC: cleaned %d expired upload sessions", deleted)
    return deleted
