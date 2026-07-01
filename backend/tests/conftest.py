"""pytest fixtures - 测试公共设施"""
import os
from collections.abc import AsyncIterator
from typing import Any

import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# 测试前强制注入所需环境变量 (避免 Settings 校验失败)
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://gevic:gevic_dev_password@localhost:5432/gevic")
os.environ.setdefault("LLM_BASE_URL", "https://example.com/v1")
os.environ.setdefault("LLM_API_KEY", "test-key")
os.environ.setdefault("LLM_MODEL", "gpt-4o-mini")
os.environ.setdefault("LLM_MAX_INPUT_TOKENS", "4000")
os.environ.setdefault("LLM_MAX_OUTPUT_TOKENS", "1000")


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """连接到测试 DB, 用于需要真实 DB 的测试 (V1.0 多数测试用 mock)"""
    url = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://gevic:gevic_dev_password@localhost:5432/gevic",
    )
    engine = create_async_engine(url)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as session:
        yield session
        await session.rollback()
    await engine.dispose()


@pytest_asyncio.fixture
async def async_session_maker() -> Any:
    """返回 sessionmaker 工厂"""
    url = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://gevic:gevic_dev_password@localhost:5432/gevic",
    )
    engine = create_async_engine(url)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    yield sm
    await engine.dispose()
