"""审计日志服务测试"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.audit import AuditAction, AuditResult, AuditService


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_log_success(mock_session: AsyncMock) -> None:
    """记录成功操作"""
    service = AuditService(mock_session)
    await service.log(
        actor="INSP-001",
        action=AuditAction.UPLOAD,
        resource_type="inspection",
        resource_id="1024",
        source_ip="192.168.1.1",
        result=AuditResult.SUCCESS,
    )
    assert mock_session.add.called
    log = mock_session.add.call_args[0][0]
    assert log.actor == "INSP-001"
    assert log.action == "upload"
    assert log.resource_type == "inspection"
    assert log.resource_id == "1024"
    assert log.source_ip == "192.168.1.1"
    assert log.result == "success"
    assert log.occurred_at is not None


@pytest.mark.asyncio
async def test_log_failure_with_error(mock_session: AsyncMock) -> None:
    """记录失败操作带错误码"""
    service = AuditService(mock_session)
    await service.log(
        actor="INSP-001",
        action=AuditAction.QUERY,
        resource_type="inspection",
        result=AuditResult.FAILED,
        error_code="INVALID_ALGORITHM",
    )
    log = mock_session.add.call_args[0][0]
    assert log.result == "failed"
    assert log.error_code == "INVALID_ALGORITHM"
