"""文件访问端点 - 签名 URL 重定向"""
from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_session
from app.models import Inspection
from app.utils.exceptions import NotFoundError
from app.services.storage import StorageService

router = APIRouter(prefix="/records", tags=["files"])


@router.get("/{record_id}/file")
async def get_record_file(
    record_id: int,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    """获取记录原文件的签名 URL (302 重定向)"""
    stmt = select(Inspection).where(Inspection.id == record_id)
    result = await session.execute(stmt)
    inspection = result.scalar_one_or_none()
    if inspection is None or not inspection.object_key:
        raise NotFoundError(f"Record {record_id} not found or has no file")

    storage = StorageService.from_settings(settings)
    url = storage.get_file_url(inspection.object_key)
    return RedirectResponse(url=url)


@router.get("/{record_id}/file/{idx}")
async def get_record_batch_file(
    record_id: int,
    idx: int,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    """获取批次中第 idx 个文件 (0-indexed) 的签名 URL. idx=0 是主文件."""
    stmt = select(Inspection).where(Inspection.id == record_id)
    result = await session.execute(stmt)
    inspection = result.scalar_one_or_none()
    if inspection is None:
        raise NotFoundError(f"Record {record_id} not found")
    if not inspection.is_batch or not inspection.batch_files:
        raise NotFoundError(f"Record {record_id} is not a batch inspection")
    if idx < 0 or idx >= len(inspection.batch_files):
        raise NotFoundError(f"Batch file index {idx} out of range (0..{len(inspection.batch_files)-1})")
    object_key = inspection.batch_files[idx]["object_key"]
    storage = StorageService.from_settings(settings)
    url = storage.get_file_url(object_key)
    return RedirectResponse(url=url)
