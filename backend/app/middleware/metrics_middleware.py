"""HTTP request timing middleware - tracks upload + request metrics"""
import time
from typing import Callable

from fastapi import Request, Response
from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware

# 上传接口耗时 (主规范 SLO: P95 < 500ms)
UPLOAD_DURATION = Histogram(
    "gevic_upload_duration_seconds",
    "上传接口耗时 (秒)",
    labelnames=("algorithm",),
    buckets=(0.05, 0.1, 0.2, 0.3, 0.5, 0.8, 1.0, 2.0, 5.0),
)

# HTTP 请求计数
HTTP_REQUESTS_TOTAL = Counter(
    "gevic_http_requests_total",
    "HTTP 请求总数",
    labelnames=("endpoint", "method", "status"),
)


def _normalize_path(path: str) -> str:
    """路径归一化, 避免高基数"""
    parts = path.strip("/").split("/")
    if len(parts) >= 4 and parts[0] == "api" and parts[1] == "v1":
        if parts[2] == "records" and parts[3].isdigit():
            return "/" + "/".join(parts[:3]) + "/{id}"
        if parts[2] == "inspect":
            return "/" + "/".join(parts[:3]) + "/{code}"
    return path


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start = time.monotonic()
        response = await call_next(request)
        duration = time.monotonic() - start
        if request.url.path != "/metrics":
            endpoint = _normalize_path(request.url.path)
            HTTP_REQUESTS_TOTAL.labels(
                endpoint=endpoint,
                method=request.method,
                status=str(response.status_code),
            ).inc()
            if request.url.path.startswith("/api/v1/inspect/"):
                algo = request.url.path.split("/")[-1]
                UPLOAD_DURATION.labels(algorithm=algo).observe(duration)
        return response
