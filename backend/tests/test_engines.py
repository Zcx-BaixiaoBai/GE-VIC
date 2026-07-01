"""引擎测试 - 基类与 Mock"""
import asyncio
from dataclasses import asdict

import pytest

from app.engines.base import BaseEngine, EngineError, RecognitionResult
from app.engines.mock import MockEngine


def test_recognition_result_dataclass() -> None:
    """RecognitionResult 可序列化"""
    r = RecognitionResult(
        success=True,
        data={"defects": []},
        summary="ok",
        error_code=None,
        error_message=None,
        raw_response=None,
        cost_estimate=0.001,
        duration_ms=100,
    )
    d = asdict(r)
    assert d["success"] is True
    assert d["summary"] == "ok"


def test_mock_engine_returns_success() -> None:
    """MockEngine 默认返回成功"""
    engine = MockEngine(defects_to_return=[{"type": "破损", "confidence": 0.9}])
    result = asyncio.run(
        engine.recognize(
            file_bytes=b"fake",
            filename="test.jpg",
            meta={"asset_id": "X1"},
            config={},
        )
    )
    assert result.success is True
    assert result.data["defects"][0]["type"] == "破损"


def test_mock_engine_can_simulate_failure() -> None:
    """MockEngine 可模拟失败"""
    engine = MockEngine(simulate_failure=True, error_code="MOCK_TIMEOUT")
    result = asyncio.run(
        engine.recognize(file_bytes=b"fake", filename="t.jpg", meta={}, config={})
    )
    assert result.success is False
    assert result.error_code == "MOCK_TIMEOUT"


def test_base_engine_cannot_be_instantiated() -> None:
    """BaseEngine 抽象类不能直接实例化"""
    with pytest.raises(TypeError):
        BaseEngine()  # type: ignore[abstract]
