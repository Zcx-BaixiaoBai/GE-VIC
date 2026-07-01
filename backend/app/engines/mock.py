"""Mock 引擎 - 用于测试、离线开发、演示"""
import asyncio
import time
from typing import Any

from app.engines.base import BaseEngine, RecognitionResult


class MockEngine(BaseEngine):
    """Mock 引擎

    可通过 config 控制行为:
    - delay_ms: int - 模拟识别延迟 (默认 0)
    - defects_count: int - 返回的缺陷数量 (默认 1)
    - simulate_failure: bool - 是否模拟失败 (默认 False)
    - error_code: str - 失败时的错误码 (默认 MOCK_ERROR)
    """

    engine_type = "mock"

    def __init__(
        self,
        defects_to_return: list[dict[str, Any]] | None = None,
        simulate_failure: bool = False,
        error_code: str = "MOCK_ERROR",
        delay_seconds: float = 0.0,
    ) -> None:
        self.defects_to_return = defects_to_return
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

        # 从 config 读取动态行为
        delay_ms = config.get("delay_ms", int(self.delay_seconds * 1000))
        if delay_ms > 0:
            await asyncio.sleep(delay_ms / 1000.0)

        simulate_failure = config.get("simulate_failure", self.simulate_failure)
        error_code = config.get("error_code", self.error_code)
        if simulate_failure:
            return RecognitionResult(
                success=False,
                data=None,
                summary=None,
                error_code=error_code,
                error_message=f"Mock 模拟失败: {error_code}",
                raw_response=None,
                cost_estimate=0.0,
                duration_ms=int((time.monotonic() - start) * 1000),
            )

        # 缺陷数量
        if self.defects_to_return is not None:
            defects = self.defects_to_return
        else:
            count = config.get("defects_count", 1)
            defects = [
                {
                    "type": "破损",
                    "confidence": 0.85 + i * 0.05,
                    "bbox": [10 + i * 50, 20, 100 + i * 50, 200],
                    "severity": ["low", "medium", "high"][i % 3],
                    "description": f"Mock 引擎检测到破损 #{i + 1}",
                }
                for i in range(count)
            ]

        any_high = any(d.get("severity") == "high" for d in defects)
        severity = "critical" if any_high else "moderate"
        return RecognitionResult(
            success=True,
            data={
                "defects": defects,
                "raw_filename": filename,
                "meta_received": meta,
                "file_size": len(file_bytes),
                "asset_id": meta.get("asset_id"),
            },
            summary=f"Mock 识别: 检测到 {len(defects)} 处缺陷, 严重程度 {severity}",
            error_code=None,
            error_message=None,
            raw_response={"mock": True, "config_used": config, "engine_version": "1.0"},
            cost_estimate=0.0,
            duration_ms=int((time.monotonic() - start) * 1000),
        )

    async def health_check(self, config: dict[str, Any]) -> bool:
        return True
