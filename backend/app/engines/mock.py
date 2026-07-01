"""Mock 引擎 - 用于测试和离线开发"""
import asyncio
import time
from typing import Any

from app.engines.base import BaseEngine, RecognitionResult


class MockEngine(BaseEngine):
    """Mock 引擎 - 返回预设结果,不调任何外部服务"""

    engine_type = "mock"

    def __init__(
        self,
        defects_to_return: list[dict[str, Any]] | None = None,
        simulate_failure: bool = False,
        error_code: str = "MOCK_ERROR",
        delay_seconds: float = 0.0,
    ) -> None:
        self.defects_to_return = defects_to_return or []
        self.simulate_failure = simulate_failure
        self.error_code = error_code
        self.delay_seconds = delay_seconds

    async def recognize(
        self,
        file_bytes: bytes,
        filename: str,
        meta: dict[str, Any],
        config: dict[str, Any],
    ) -> RecognitionResult:
        start = time.monotonic()
        if self.delay_seconds > 0:
            await asyncio.sleep(self.delay_seconds)

        if self.simulate_failure:
            return RecognitionResult(
                success=False,
                data=None,
                summary=None,
                error_code=self.error_code,
                error_message=f"Mock 模拟失败: {self.error_code}",
                raw_response=None,
                cost_estimate=0.0,
                duration_ms=int((time.monotonic() - start) * 1000),
            )

        # 默认返回 1 个缺陷
        defects = self.defects_to_return or [
            {
                "type": "破损",
                "confidence": 0.85,
                "bbox": [10, 20, 100, 200],
                "severity": "medium",
                "description": "Mock 引擎检测到破损 (测试用)",
            }
        ]
        return RecognitionResult(
            success=True,
            data={"defects": defects, "raw_filename": filename, "meta_received": meta},
            summary=f"Mock: 检测到 {len(defects)} 处问题",
            error_code=None,
            error_message=None,
            raw_response={"mock": True, "file_size": len(file_bytes)},
            cost_estimate=0.0,
            duration_ms=int((time.monotonic() - start) * 1000),
        )

    async def health_check(self, config: dict[str, Any]) -> bool:
        return True
