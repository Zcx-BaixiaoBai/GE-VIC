"""CloudVisionEngine - 阿里云/腾讯云/百度等视觉云 API 适配

V1.0: 仅实现阿里云视觉智能开放平台 (RecognizeImageStyle 等)
后续可扩展腾讯云/百度等 provider
"""
import base64
import time
from typing import Any

import httpx

from app.engines.base import BaseEngine, EngineError, RecognitionResult


class CloudVisionEngine(BaseEngine):
    """云视觉 API 引擎

    配置格式 (engine_config):
    {
        "provider": "aliyun",
        "endpoint": "https://imagerecog.cn-shanghai.aliyuncs.com",
        "action": "RecognizeInsulatorDamage",
        "access_key_id": "...",
        "access_key_secret": "...",
        "timeout_sec": 30  # 可选, 默认 30
    }
    """

    engine_type = "cloud_api"

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self.http = http_client or httpx.AsyncClient(timeout=30.0)

    async def _ping(self, endpoint: str) -> bool:
        """检查 endpoint 可达"""
        try:
            response = await self.http.get(endpoint, timeout=5.0)
            return response.status_code < 500
        except Exception:
            return False

    async def health_check(self, config: dict[str, Any]) -> dict[str, Any]:
        import time
        endpoint = config.get("endpoint", "")
        if not endpoint:
            return {"ok": False, "message": "endpoint 未配置", "error_code": "MISSING_ENDPOINT"}
        start = time.monotonic()
        try:
            ok = await self._ping(endpoint)
            return {
                "ok": ok,
                "message": "endpoint 可达" if ok else "endpoint 不可达 (5xx 或网络错误)",
                "duration_ms": int((time.monotonic() - start) * 1000),
            }
        except Exception as e:
            return {
                "ok": False,
                "message": f"endpoint 探测异常: {e}",
                "error_code": "ENDPOINT_PROBE_ERROR",
                "duration_ms": int((time.monotonic() - start) * 1000),
            }

    async def _call_api(
        self,
        config: dict[str, Any],
        file_bytes: bytes,
        filename: str,
    ) -> dict[str, Any]:
        """调用云 API

        V1.0 实现: 简化 HTTP POST 形式 (实际生产应使用官方 SDK)
        此处保留接口, 真实接入时按 provider 实现具体签名
        """
        endpoint = config["endpoint"]
        action = config.get("action", "RecognizeImageStyle")

        try:
            response = await self.http.post(
                endpoint,
                json={
                    "Action": action,
                    "ImageURL": f"data:image/jpeg;base64,{base64.b64encode(file_bytes).decode()[:100]}",
                },
                headers={"Authorization": f"APPCODE {config.get('access_key_id', '')}"},
                timeout=float(config.get("timeout_sec", 30)),
            )
        except (httpx.TimeoutException, httpx.RequestError) as e:
            raise EngineError(f"网络错误: {e}") from e

        if response.status_code != 200:
            raise EngineError(f"HTTP {response.status_code}: {response.text[:200]}")

        try:
            return response.json()
        except Exception as e:
            raise EngineError(f"响应解析失败: {e}") from e

    async def recognize(
        self,
        file_bytes: bytes,
        filename: str,
        meta: dict[str, Any],
        config: dict[str, Any],
    ) -> RecognitionResult:
        start = time.monotonic()
        try:
            raw = await self._call_api(config, file_bytes, filename)
        except EngineError as e:
            return RecognitionResult(
                success=False,
                data=None,
                summary=None,
                error_code="ENGINE_HTTP_ERROR",
                error_message=str(e),
                raw_response=None,
                cost_estimate=None,
                duration_ms=int((time.monotonic() - start) * 1000),
            )

        # 简化: 假设 raw.data.elements 是检测列表
        data = raw.get("Data", {}) or {}
        elements = data.get("Elements", []) if isinstance(data, dict) else []

        defects = [
            {
                "type": "cloud_detected",
                "confidence": float(elem.get("Confidence", 0.0))
                if isinstance(elem, dict)
                else 0.0,
                "raw": elem,
            }
            for elem in elements
        ]

        return RecognitionResult(
            success=True,
            data={"defects": defects, "raw_filename": filename, "meta_received": meta},
            summary=f"云端识别: 检测到 {len(defects)} 处",
            error_code=None,
            error_message=None,
            raw_response=raw,
            cost_estimate=None,
            duration_ms=int((time.monotonic() - start) * 1000),
        )

    async def close(self) -> None:
        await self.http.aclose()
