"""算法列表端点 - 始终从 DB 实时查询 (避免新创建的算法不显示)"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import Algorithm
from app.schemas.algorithm import AlgorithmListOut, AlgorithmOut
from app.services.algorithm_registry import to_dict

router = APIRouter(prefix="/algorithms", tags=["algorithms"])


@router.get("", response_model=AlgorithmListOut)
async def list_algorithms(
    session: AsyncSession = Depends(get_session),
) -> AlgorithmListOut:
    """列出所有已启用的算法 (实时查 DB, 保证创建后立即可见)"""
    stmt = select(Algorithm).where(Algorithm.is_active.is_(True)).order_by(Algorithm.code)
    result = await session.execute(stmt)
    items = [AlgorithmOut(**to_dict(a)) for a in result.scalars().all()]
    return AlgorithmListOut(items=items, total=len(items))
