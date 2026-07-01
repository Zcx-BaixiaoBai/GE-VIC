"""数据库引擎测试"""
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.database import create_engine, get_sessionmaker


def test_create_engine_returns_async_engine() -> None:
    """create_engine 返回 AsyncEngine 实例"""
    engine = create_engine("postgresql+asyncpg://u:p@localhost:5432/db")
    assert isinstance(engine, AsyncEngine)
    # 关闭同步部分
    import asyncio
    asyncio.run(engine.dispose())


def test_get_sessionmaker_returns_callable() -> None:
    """get_sessionmaker 返回 sessionmaker 工厂"""
    engine = create_engine("postgresql+asyncpg://u:p@localhost:5432/db")
    sm = get_sessionmaker(engine)
    session = sm()
    assert isinstance(session, AsyncSession)
    import asyncio
    asyncio.run(session.close())
    asyncio.run(engine.dispose())
