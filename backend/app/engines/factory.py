"""引擎工厂 - 根据 engine_type 返回对应实现"""
from typing import Any

from app.engines.base import BaseEngine
from app.engines.cloud import CloudVisionEngine
from app.engines.multimodal_llm import MultimodalLLMEngine

_ENGINE_REGISTRY: dict[str, type[BaseEngine]] = {
    "cloud_api": CloudVisionEngine,
    "multimodal_llm": MultimodalLLMEngine,
}

# cached default-constructed instances (reuse LLM/httpx connection pools)
_ENGINE_INSTANCES: dict[str, BaseEngine] = {}


def get_engine(engine_type: str, **kwargs: Any) -> BaseEngine:
    """根据 engine_type 创建引擎实例.

    特殊处理: multimodal_llm 引擎需要 settings, 自动注入.
    """
    cls = _ENGINE_REGISTRY.get(engine_type)
    if cls is None:
        raise ValueError(
            f"Unknown engine_type: {engine_type}. "
            f"Available: {list(_ENGINE_REGISTRY.keys())}"
        )

    custom = bool(kwargs)  # caller supplied custom construction kwargs
    if cls is MultimodalLLMEngine and "settings" not in kwargs:
        from app.config import get_settings
        kwargs["settings"] = get_settings()

    # cache default-constructed instances so LLM/httpx connection pools are
    # reused across tasks; custom-kwargs calls return fresh instances.
    if not custom:
        cached = _ENGINE_INSTANCES.get(engine_type)
        if cached is not None and type(cached) is cls:
            return cached

    inst = cls(**kwargs)
    if not custom:
        _ENGINE_INSTANCES[engine_type] = inst
    return inst


def register_engine(engine_type: str, cls: type[BaseEngine]) -> None:
    """注册自定义引擎 (用于扩展)"""
    _ENGINE_REGISTRY[engine_type] = cls
