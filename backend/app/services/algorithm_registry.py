"""算法注册表 - 启动加载 + 热刷新

V1.0 简化: 启动加载到内存字典, 增删算法需重启
后续可加 LISTEN/NOTIFY 通知
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

    def get(self, code: str) -> Algorithm | None:
        """按 code 查找"""
        return self._cache.get(code)

    def get_required(self, code: str) -> Algorithm:
        """按 code 查找, 找不到抛 KeyError"""
        algo = self.get(code)
        if algo is None:
            raise KeyError(f"Algorithm not found or inactive: {code}")
        return algo

    def all(self) -> list[Algorithm]:
        """所有算法列表"""
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
    # 脱敏: 隐藏 secret 字段
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
