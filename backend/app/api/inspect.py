"""POST /api/v1/inspect/{code} - 鏍稿績涓婁紶绔偣"""
import hashlib
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_global_sessionmaker
from app.models import Inspection
from app.schemas.inspection import InspectionCreateOut
from app.services.algorithm_registry import AlgorithmRegistry, get_registry
from app.services.audit import AuditAction, AuditResult, AuditService
from app.services.storage import StorageService
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inspect", tags=["inspect"])


async def _session_dep() -> AsyncSession:
    sm = get_global_sessionmaker()
    async with sm() as session:
        yield session


@router.post("/{algorithm_code}", response_model=InspectionCreateOut, status_code=202)
async def inspect(
    algorithm_code: str,
    request: Request,
    file: UploadFile = File(...),
    meta: str = Form("{}"),
    x_inspector_id: str | None = Header(default=None, alias="X-Inspector-Id"),
    registry: AlgorithmRegistry = Depends(get_registry),
    session: AsyncSession = Depends(_session_dep),
) -> InspectionCreateOut:
    """Upload file and submit inspection task."""
    try:
        from app.utils.inspector_id import validate_inspector_id
        inspector_id = validate_inspector_id(x_inspector_id)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_INSPECTOR_ID", "message": str(e)},
        )

    algo = await registry.get(algorithm_code, session)
    if algo is None:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_ALGORITHM",
                "message": f"Algorithm not found or inactive: {algorithm_code}",
            },
        )

    try:
        meta_dict = json.loads(meta) if meta else {}
        if not isinstance(meta_dict, dict):
            raise ValueError("meta must be a JSON object")
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_META", "message": str(e)},
        )

    file_bytes = await file.read()
    settings = get_settings()
    max_size = settings.max_image_size
    if len(file_bytes) > max_size:
        raise HTTPException(
            status_code=413,
            detail={
                "code": "FILE_TOO_LARGE",
                "message": f"File exceeds max size {max_size} bytes",
            },
        )

    if not file_bytes:
        raise HTTPException(
            status_code=400,
            detail={"code": "EMPTY_FILE", "message": "Uploaded file is empty"},
        )

    filename = file.filename or "upload.bin"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    image_exts = {"jpg", "jpeg", "png", "bmp", "webp", "gif"}
    video_exts = {"mp4", "mov", "avi", "mkv"}
    if ext in image_exts:
        file_type = "image"
    elif ext in video_exts:
        file_type = "video"
    else:
        file_type = "other"

    inspection = Inspection(
        algorithm_code=algorithm_code,
        category=algo.category,
        status="PENDING",
        inspector_id=inspector_id,
        asset_id=meta_dict.get("asset_id"),
        location=meta_dict.get("location"),
        request_meta={
            **meta_dict,
            "inspector_id": inspector_id,
            "filename": filename,
            "file_type": file_type,
        },
        file_size=len(file_bytes),
        file_type=file_type,
        file_hash=hashlib.sha256(file_bytes).hexdigest(),
        retry_count=0,
    )
    session.add(inspection)
    await session.flush()
    record_id = inspection.id

    content_type = file.content_type or "application/octet-stream"
    storage = StorageService.from_settings(settings)
    try:
        object_key = storage.upload_file(
            file_bytes=file_bytes,
            filename=filename,
            record_id=record_id,
            content_type=content_type,
        )
        inspection.object_key = object_key
    except Exception as e:
        logger.exception("MinIO upload failed")
        inspection.status = "FAILED"
        inspection.error_code = "STORAGE_ERROR"
        inspection.error_message = str(e)
        audit = AuditService(session)
        await audit.log(
            actor=inspector_id,
            action=AuditAction.UPLOAD,
            resource_type="inspection",
            resource_id=str(record_id),
            source_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            request_id=request.headers.get("x-request-id"),
            request_meta={"algorithm_code": algorithm_code, "file_size": len(file_bytes)},
            result=AuditResult.FAILED,
            error_code="STORAGE_ERROR",
            error_message=str(e),
        )
        await session.commit()
        raise HTTPException(
            status_code=500,
            detail={"code": "STORAGE_ERROR", "message": str(e)},
        )

    # 鍏堝啓 audit log + 鎻愪氦, 鍐嶆姇閫掍换鍔?(閬垮厤浠诲姟璇讳笉鍒版湭鎻愪氦璁板綍)
    audit = AuditService(session)
    await audit.log(
        actor=inspector_id,
        action=AuditAction.UPLOAD,
        resource_type="inspection",
        resource_id=str(record_id),
        source_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        request_id=request.headers.get("x-request-id"),
        request_meta={"algorithm_code": algorithm_code, "file_size": len(file_bytes)},
        result=AuditResult.SUCCESS,
    )
    await session.commit()

    # 鍚屾妯″紡: 鍦?API 杩涚▼鍐呯洿鎺ヨ窇浠诲姟 (await 閬垮厤 event loop 鍐茬獊)
    await session.close()  # Release connection before running task

    if settings.task_sync_mode:
        from app.tasks.inspection import _run_inspection_async
        try:
            logger.info("Running task in sync mode for record_id=%s", record_id)
            await _run_inspection_async(record_id)
        except Exception as e:
            logger.exception("Sync task execution failed")
    else:
        # 寮傛妯″紡: 鎶曢€?Celery 浠诲姟 (worker 寮傛娑堣垂)
        try:
            celery_app.send_task(
                "app.tasks.inspection.run_inspection",
                kwargs={"record_id": record_id},
                queue="inspect_queue",
            )
        except Exception as e:
            logger.exception("Celery enqueue failed (record will be picked up by next worker)")

    return InspectionCreateOut(
        record_id=record_id,
        algorithm_code=algorithm_code,
        status="PENDING",
        created_at=inspection.created_at or datetime.now(timezone.utc),
        status_url=f"/api/v1/records/{record_id}",
    )



@router.post("/{algorithm_code}/batch", response_model=InspectionCreateOut, status_code=202)
async def inspect_batch(
    algorithm_code: str,
    request: Request,
    files: list[UploadFile] = File(..., description="多个文件, 会联合分析 (同一个 LLM 调用看所有图)"),
    meta: str = Form("{}"),
    x_inspector_id: str | None = Header(default=None, alias="X-Inspector-Id"),
    registry: AlgorithmRegistry = Depends(get_registry),
    session: AsyncSession = Depends(_session_dep),
) -> InspectionCreateOut:
    """批量上传 + 联合分析.

    上传 N 个文件, 后端创建 1 条 Inspection, 引擎会一次性看到所有图并交叉分析.
    """
    try:
        from app.utils.inspector_id import validate_inspector_id
        inspector_id = validate_inspector_id(x_inspector_id)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_INSPECTOR_ID", "message": str(e)},
        )

    if not files:
        raise HTTPException(
            status_code=400,
            detail={"code": "NO_FILES", "message": "At least one file is required"},
        )
    if len(files) > 20:
        raise HTTPException(
            status_code=400,
            detail={"code": "TOO_MANY_FILES", "message": "Batch supports up to 20 files"},
        )

    algo = await registry.get(algorithm_code, session)
    if algo is None:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_ALGORITHM", "message": f"Algorithm not found or inactive: {algorithm_code}"},
        )

    try:
        meta_dict = json.loads(meta) if meta else {}
        if not isinstance(meta_dict, dict):
            raise ValueError("meta must be a JSON object")
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_META", "message": str(e)},
        )

    settings = get_settings()
    max_size = settings.max_image_size
    storage = StorageService.from_settings(settings)

    image_exts = {"jpg", "jpeg", "png", "bmp", "webp", "gif"}
    video_exts = {"mp4", "mov", "avi", "mkv"}
    file_entries = []
    primary_filename = ""
    primary_type = "image"
    primary_hash = ""
    primary_size = 0

    for i, uf in enumerate(files):
        fb = await uf.read()
        if not fb:
            raise HTTPException(status_code=400, detail={"code": "EMPTY_FILE", "message": f"File #{i} is empty"})
        if len(fb) > max_size:
            raise HTTPException(status_code=413, detail={"code": "FILE_TOO_LARGE", "message": f"File #{i} exceeds {max_size} bytes"})
        fname = uf.filename or f"file_{i}.bin"
        ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
        ftype = "image" if ext in image_exts else ("video" if ext in video_exts else "other")
        fhash = hashlib.sha256(fb).hexdigest()
        object_key = storage.upload_file(
            file_bytes=fb,
            filename=fname,
            record_id=None,
            content_type=uf.content_type or "application/octet-stream",
        )
        file_entries.append({
            "object_key": object_key,
            "filename": fname,
            "mime_type": uf.content_type,
            "file_type": ftype,
            "file_size": len(fb),
            "file_hash": fhash,
        })
        if i == 0:
            primary_filename = fname
            primary_type = ftype
            primary_hash = fhash
            primary_size = len(fb)

    inspection = Inspection(
        algorithm_code=algorithm_code,
        category=algo.category,
        status="PENDING",
        inspector_id=inspector_id,
        asset_id=meta_dict.get("asset_id"),
        location=meta_dict.get("location"),
        request_meta={
            **meta_dict,
            "inspector_id": inspector_id,
            "filename": primary_filename,
            "file_type": primary_type,
            "is_batch": True,
            "batch_size": len(file_entries),
            "batch_filenames": [f["filename"] for f in file_entries],
        },
        object_key=file_entries[0]["object_key"],
        file_size=primary_size,
        file_type=primary_type,
        file_hash=primary_hash,
        is_batch=True,
        batch_files=file_entries,
        retry_count=0,
    )
    session.add(inspection)
    await session.flush()
    record_id = inspection.id

    audit = AuditService(session)
    await audit.log(
        actor=inspector_id,
        action=AuditAction.UPLOAD,
        resource_type="inspection",
        resource_id=str(record_id),
        source_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        request_id=request.headers.get("x-request-id"),
        request_meta={"algorithm_code": algorithm_code, "batch_size": len(file_entries), "files": [f["filename"] for f in file_entries]},
        result=AuditResult.SUCCESS,
    )
    await session.commit()
    await session.close()

    if settings.task_sync_mode:
        from app.tasks.inspection import _run_inspection_async
        try:
            logger.info("Running batch task in sync mode for record_id=%s (size=%d)", record_id, len(file_entries))
            await _run_inspection_async(record_id)
        except Exception as e:
            logger.exception("Sync batch task failed")
    else:
        try:
            celery_app.send_task(
                "app.tasks.inspection.run_inspection",
                kwargs={"record_id": record_id},
                queue="inspect_queue",
            )
        except Exception as e:
            logger.exception("Celery enqueue failed for batch")

    return InspectionCreateOut(
        record_id=record_id,
        algorithm_code=algorithm_code,
        status="PENDING",
        created_at=inspection.created_at or datetime.now(timezone.utc),
        status_url=f"/api/v1/records/{record_id}",
    )
