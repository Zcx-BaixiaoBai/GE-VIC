"""FastAPI 依赖注入"""
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_session
from app.services.algorithm_registry import AlgorithmRegistry, get_registry
from app.utils.exceptions import InvalidInspectorIdError
from app.utils.inspector_id import validate_inspector_id

SettingsDep = Annotated[Settings, Depends(get_settings)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
RegistryDep = Annotated[AlgorithmRegistry, Depends(get_registry)]


async def get_inspector_id(
    x_inspector_id: Annotated[str | None, Header(alias="X-Inspector-Id")] = None,
) -> str:
    """FastAPI 依赖: 校验 X-Inspector-Id, 返回合法值"""
    try:
        return validate_inspector_id(x_inspector_id)
    except InvalidInspectorIdError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail={"code": "INVALID_INSPECTOR_ID", "message": str(e)})


InspectorDep = Annotated[str, Depends(get_inspector_id)]
