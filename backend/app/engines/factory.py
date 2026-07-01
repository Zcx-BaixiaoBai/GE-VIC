"""引擎工厂 - 根据 engine_type 返回对应实现"""
from typing import Any

from app.engines.base import BaseEngine
from app.engines.cloud import CloudVisionEngine
from app.engines.mock import MockEngine

# 引擎类型注册表
_ENGINE_REGISTRY: dict[str, type[BaseEngine]] = {
    "cloud_api": CloudVisionEngine,
    "mock": MockEngine,
}


def get_engine(engine_type: str, **kwargs: Any) -> BaseEngine:
    """根据 engine_type 创建引擎实例

    Args:
        engine_type: 算法注册表中的 engine_type 字段
        **kwargs: 透传给引擎构造函数 (如 http_client, defects_to_return)

    Returns:
        BaseEngine 实例

    Raises:
        ValueError: 未知 engine_type
    """
    cls = _ENGINE_REGISTRY.get(engine_type)
    if cls is None:
        raise ValueError(
            f"Unknown engine_type: {engine_type}. "
            f"Available: {list(_ENGINE_REGISTRY.keys())}"
        )
    return cls(**kwargs)


def register_engine(engine_type: str, cls: type[BaseEngine]) -> None:
    """注册自定义引擎 (用于扩展)"""
    _ENGINE_REGISTRY[engine_type] = cls
