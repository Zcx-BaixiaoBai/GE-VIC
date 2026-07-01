"""审计日志服务 - 事后追责

V1.0 简化: 不做异步写,跟主事务同提交
"""
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


class AuditAction(StrEnum):
    """操作类型枚举"""
    UPLOAD = "upload"
    QUERY = "query"
    RETRY = "retry"
    ENRICH = "enrich"
    REGISTER_ALGORITHM = "register_algorithm"


class AuditResult(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"


class AuditService:
    """审计日志写入服务

    与主事务绑定: log() 仅 flush 不 commit, 由调用方统一提交
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def log(
        self,
        actor: str,
        action: AuditAction,
        resource_type: str,
        resource_id: str | None = None,
        source_ip: str | None = None,
        user_agent: str | None = None,
        request_id: str | None = None,
        request_meta: dict[str, Any] | None = None,
        result: AuditResult = AuditResult.SUCCESS,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """记录一条审计日志, 自动 flush 到 session"""
        log = AuditLog(
            occurred_at=datetime.now(timezone.utc),
            actor=actor,
            action=action.value,
            resource_type=resource_type,
            resource_id=resource_id,
            source_ip=source_ip,
            user_agent=user_agent,
            request_id=request_id,
            request_meta=request_meta,
            result=result.value,
            error_code=error_code,
            error_message=error_message,
        )
        self.session.add(log)
        await self.session.flush()
