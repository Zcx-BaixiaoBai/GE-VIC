"""Algorithm CRUD API - list/toggle/create/delete"""
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.deps import get_inspector_id
from app.models import Algorithm
from app.schemas.algorithm import AlgorithmOut
from app.services.algorithm_registry import get_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/algorithms", tags=["admin-algorithms"])


class AlgorithmCreateIn(BaseModel):
    """�����㷨����"""
    code: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-z0-9-]+$")
    name: str = Field(..., min_length=1, max_length=128)
    category: str | None = None
    description: str | None = None
    engine_type: str = Field(..., pattern=r"^(cloud_api|mock|local_model|hikvision_brain|multimodal_llm)$")
    engine_config: dict[str, Any] = Field(default_factory=dict)
    request_schema: dict[str, Any] | None = None


class AlgorithmUpdateIn(BaseModel):
    """�����㷨����"""
    is_active: bool | None = None
    name: str | None = None
    category: str | None = None
    description: str | None = None
    engine_config: dict[str, Any] | None = None


@router.get("", response_model=list[AlgorithmOut])
async def list_algorithms_full(
    include_inactive: bool = False,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(get_inspector_id),
) -> list[AlgorithmOut]:
    """�г������㷨 (settings ҳ��, �ɰ�����ͣ��)"""
    from app.services.algorithm_registry import get_registry, to_dict
    stmt = select(Algorithm)
    if not include_inactive:
        stmt = stmt.where(Algorithm.is_active.is_(True))
    result = await session.execute(stmt)
    items = [AlgorithmOut(**to_dict(a)) for a in result.scalars().all()]
    return items


@router.post("", response_model=AlgorithmOut, status_code=201)
async def create_algorithm(
    body: AlgorithmCreateIn,
    session: AsyncSession = Depends(get_session),
    inspector_id: str = Depends(get_inspector_id),
) -> AlgorithmOut:
    """�����㷨"""
    from app.services.algorithm_registry import to_dict
    # ��� code �Ƿ��Ѵ���
    existing = await session.execute(select(Algorithm).where(Algorithm.code == body.code))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409,
            detail={"code": "ALGORITHM_EXISTS", "message": f"Algorithm {body.code} already exists"},
        )
    now = datetime.now(timezone.utc)
    algo = Algorithm(
        code=body.code,
        name=body.name,
        category=body.category,
        description=body.description,
        engine_type=body.engine_type,
        engine_config=body.engine_config,
        request_schema=body.request_schema,
        is_active=True,
        version=1,
        created_at=now,
        updated_at=now,
    )
    session.add(algo)
    await session.commit()
    await session.refresh(algo)
    logger.info("Algorithm %s created by %s", body.code, inspector_id)
    get_registry().upsert(algo)
    return AlgorithmOut(**to_dict(algo))


@router.patch("/{code}", response_model=AlgorithmOut)
async def update_algorithm(
    code: str,
    body: AlgorithmUpdateIn,
    session: AsyncSession = Depends(get_session),
    inspector_id: str = Depends(get_inspector_id),
) -> AlgorithmOut:
    """�����㷨 (����/ͣ��, ����, �� config)"""
    from app.services.algorithm_registry import to_dict
    result = await session.execute(select(Algorithm).where(Algorithm.code == code))
    algo = result.scalar_one_or_none()
    if algo is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "ALGORITHM_NOT_FOUND", "message": f"Algorithm {code} not found"},
        )
    if body.is_active is not None:
        algo.is_active = body.is_active
    if body.name is not None:
        algo.name = body.name
    if body.category is not None:
        algo.category = body.category
    if body.description is not None:
        algo.description = body.description
    if body.engine_config is not None:
        algo.engine_config = body.engine_config
    algo.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(algo)
    logger.info("Algorithm %s updated by %s", code, inspector_id)
    get_registry().upsert(algo)
    return AlgorithmOut(**to_dict(algo))


class AlgorithmTestIn(BaseModel):
    """测试请求体 (可选: 用临时 engine_config 测试未保存的配置)"""
    engine_config: dict[str, Any] | None = None


class AlgorithmTestOut(BaseModel):
    """算法测试结果"""
    success: bool
    message: str
    engine_type: str
    duration_ms: int | None = None
    model: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    error_code: str | None = None
    detail: dict[str, Any] | None = None


@router.post("/{code}/test", response_model=AlgorithmTestOut)
async def test_algorithm(
    code: str,
    body: AlgorithmTestIn | None = None,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(get_inspector_id),
) -> AlgorithmTestOut:
    """测试算法连通性"""
    import time
    result = await session.execute(select(Algorithm).where(Algorithm.code == code))
    algo = result.scalar_one_or_none()
    if algo is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "ALGORITHM_NOT_FOUND", "message": f"Algorithm {code} not found"},
        )
    cfg = (body.engine_config if body and body.engine_config is not None else algo.engine_config) or {}
    from app.engines.factory import get_engine
    engine = get_engine(algo.engine_type)
    start = time.monotonic()
    try:
        hc = await engine.health_check(cfg)
    except Exception as e:
        return AlgorithmTestOut(
            success=False,
            message=f"health_check 抛异常: {e}",
            engine_type=algo.engine_type,
            error_code="HEALTH_CHECK_EXCEPTION",
            duration_ms=int((time.monotonic() - start) * 1000),
        )
    duration = int((time.monotonic() - start) * 1000)
    return AlgorithmTestOut(
        success=bool(hc.get("ok")),
        message=hc.get("message", ""),
        engine_type=algo.engine_type,
        duration_ms=hc.get("duration_ms", duration),
        model=hc.get("model"),
        prompt_tokens=hc.get("prompt_tokens"),
        completion_tokens=hc.get("completion_tokens"),
        total_tokens=hc.get("total_tokens"),
        error_code=hc.get("error_code"),
        detail=hc,
    )


@router.delete("/{code}", status_code=204)
async def delete_algorithm(
    code: str,
    session: AsyncSession = Depends(get_session),
    inspector_id: str = Depends(get_inspector_id),
) -> None:
    """ɾ���㷨"""
    result = await session.execute(select(Algorithm).where(Algorithm.code == code))
    algo = result.scalar_one_or_none()
    if algo is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "ALGORITHM_NOT_FOUND", "message": f"Algorithm {code} not found"},
        )
    await session.execute(delete(Algorithm).where(Algorithm.code == code))
    await session.commit()
    get_registry().remove(code)
    logger.info("Algorithm %s deleted by %s", code, inspector_id)
