"""算法列表端点"""
from fastapi import APIRouter

from app.deps import RegistryDep
from app.schemas.algorithm import AlgorithmListOut, AlgorithmOut
from app.services.algorithm_registry import to_dict

router = APIRouter(prefix="/algorithms", tags=["algorithms"])


@router.get("", response_model=AlgorithmListOut)
async def list_algorithms(registry: RegistryDep) -> AlgorithmListOut:
    """列出所有已注册且启用的算法"""
    items = [AlgorithmOut(**to_dict(a)) for a in registry.all()]
    return AlgorithmListOut(items=items, total=len(items))
