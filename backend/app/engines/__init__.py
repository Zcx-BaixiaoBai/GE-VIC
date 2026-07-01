"""引擎适配器层"""
from app.engines.base import BaseEngine, EngineError, RecognitionResult
from app.engines.factory import get_engine, register_engine

__all__ = [
    "BaseEngine",
    "EngineError",
    "RecognitionResult",
    "get_engine",
    "register_engine",
]
