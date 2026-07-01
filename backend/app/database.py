"""SQLAlchemy 异步引擎与 Session 工厂"""
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import Settings, get_settings


def create_engine(database_url: str, **kwargs: object) -> AsyncEngine:
    """根据 URL 创建异步引擎"""
    return create_async_engine(
        database_url,
        echo=False,
        pool_size=kwargs.pop("pool_size", 20),
        max_overflow=kwargs.pop("max_overflow", 10),
        pool_pre_ping=kwargs.pop("pool_pre_ping", True),
    )


def get_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """获取 Session 工厂"""
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """获取全局单例引擎"""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(settings.database_url)
    return _engine


def get_global_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """获取全局 Session 工厂"""
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = get_sessionmaker(get_engine())
    return _sessionmaker


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI 依赖: 获取一个 Session, 自动关闭"""
    sm = get_global_sessionmaker()
    async with sm() as session:
        yield session


async def dispose_engine() -> None:
    """关闭引擎 (在应用关闭时调用)"""
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _sessionmaker = None
