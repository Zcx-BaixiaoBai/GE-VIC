"""算法注册表 - 启动加载 + 运行时热更新

V1.1: 支持新增/更新/删除算法后, 缓存自动失效, 避免上传页看不到刚创建的算法
"""
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Algorithm


class AlgorithmRegistry:
    """进程内算法注册表缓存

    key: algorithm.code
    value: Algorithm ORM 对象
    """

    def __init__(self) -> None:
        self._cache: dict[str, Algorithm] = {}
        self._loaded_at: datetime | None = None

    async def load(self, session: AsyncSession) -> None:
        """从 DB 加载所有启用的算法到内存"""
        stmt = select(Algorithm).where(Algorithm.is_active.is_(True))
        result = await session.execute(stmt)
        algorithms = result.scalars().all()
        self._cache = {algo.code: algo for algo in algorithms}
        self._loaded_at = datetime.now(timezone.utc)

    async def refresh(self, session: AsyncSession) -> None:
        """重新从 DB 加载 (用于外部直接修改 DB 后的全量刷新)"""
        await self.load(session)

    def invalidate(self, code: str | None = None) -> None:
        """失效缓存. code 为 None 时清空全部, 否则只清空指定 code."""
        if code is None:
            self._cache.clear()
        else:
            self._cache.pop(code, None)

    def upsert(self, algo: Algorithm) -> None:
        """插入或更新单条缓存 (调用方负责 commit 之后再调用)."""
        if not algo.is_active:
            self._cache.pop(algo.code, None)
        else:
            self._cache[algo.code] = algo
        _bust_llm_client_cache()  # algorithm config may have changed -> drop cached LLM clients

    def remove(self, code: str) -> None:
        """从缓存移除"""
        self._cache.pop(code, None)

    async def get(self, code: str, session: AsyncSession | None = None) -> Algorithm | None:
        """按 code 查找. 缓存未命中时 (e.g. 后启动后新增) 可选地从 DB 回填."""
        cached = self._cache.get(code)
        if cached is not None:
            return cached
        if session is None:
            return None
        stmt = select(Algorithm).where(Algorithm.code == code, Algorithm.is_active.is_(True))
        result = await session.execute(stmt)
        algo = result.scalar_one_or_none()
        if algo is not None:
            self._cache[code] = algo
        return algo

    def get_required(self, code: str) -> Algorithm:
        """按 code 查找 (同步), 找不到抛 KeyError. 仅在缓存命中时可用."""
        algo = self._cache.get(code)
        if algo is None:
            raise KeyError(f"Algorithm not found in cache: {code}")
        return algo

    def all(self) -> list[Algorithm]:
        """当前缓存中所有算法 (可能不含启动后新增的)"""
        return list(self._cache.values())

    def __len__(self) -> int:
        return len(self._cache)

    def __contains__(self, code: str) -> bool:
        return code in self._cache

    @property
    def loaded_at(self) -> datetime | None:
        return self._loaded_at


# 全局单例
_registry: AlgorithmRegistry | None = None


def get_registry() -> AlgorithmRegistry:
    """获取全局注册表实例 (lazy init)"""
    global _registry
    if _registry is None:
        _registry = AlgorithmRegistry()
    return _registry


def reset_registry() -> None:
    """重置 (主要用于测试)"""
    global _registry
    _registry = None


def to_dict(algo: Algorithm) -> dict[str, Any]:
    """序列化为 API 响应格式 (不暴露 engine_config 凭据)"""
    config = algo.engine_config or {}
    safe_config = {k: v for k, v in config.items() if "secret" not in k.lower() and "key" not in k.lower()}
    safe_config["provider"] = config.get("provider")

    return {
        "code": algo.code,
        "name": algo.name,
        "category": algo.category,
        "description": algo.description,
        "engine_type": algo.engine_type,
        "is_active": algo.is_active,
        "version": algo.version,
        "engine_config": safe_config,
        "request_schema": algo.request_schema,
    }


def _bust_llm_client_cache() -> None:
    """Invalidate cached LLM clients (called when algorithm configs change)."""
    try:
        from app.services.llm_client import invalidate_llm_client_cache
        invalidate_llm_client_cache()
    except Exception:
        pass
