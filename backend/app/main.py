"""FastAPI 应用入口"""
import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from prometheus_client import Gauge

from app import __version__
from app.api import api_router
from app.config import Settings, get_settings
from app.database import dispose_engine, get_global_sessionmaker
from app.services.algorithm_registry import get_registry
from app.services.metrics import DEPENDENCY_UP, ALGORITHMS_COUNT
from app.utils.exceptions import (
    AlgorithmNotFoundError,
    FileTooLargeError,
    GevicError,
    InvalidInspectorIdError,
    LLMError,
    NotFoundError,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def _setup_logging(settings: Settings) -> None:
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        force=True,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时加载算法注册表; 关闭时释放连接"""
    settings = get_settings()
    _setup_logging(settings)
    sm = get_global_sessionmaker()
    async with sm() as session:
        registry = get_registry()
        try:
            await registry.load(session)
            logger.info("Algorithm registry loaded: %d algorithms", len(registry))
            # 指标: 活跃算法数
            try:
                from app.services.metrics import ALGORITHMS_COUNT
                from sqlalchemy import select, func
                from app.models.algorithm import Algorithm
                stmt = select(func.count()).select_from(Algorithm).where(Algorithm.is_active == True)
                result = await session.execute(stmt)
                active_count = result.scalar() or 0
                ALGORITHMS_COUNT.set(active_count)
                logger.info("Active algorithms count metric: %d", active_count)
            except Exception as e:
                logger.warning("Failed to update algorithms count metric: %s", e)
        except Exception as e:
            logger.warning("Failed to load algorithm registry on startup: %s", e)

    # ????? TUS ????
    try:
        from app.api.tus import gc_expired_sessions
        await gc_expired_sessions()
    except Exception as e:
        logger.warning("TUS GC failed on startup: %s", e)

    yield
    await dispose_engine()


app = FastAPI(
    title="GE-VIC Image Recognition",
    version=__version__,
    description="基础设施巡检图像识别平台",
    lifespan=lifespan,
)

# CORS - 开发环境放开
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def metrics_middleware(request, call_next):
    """HTTP 请求埋点 (主规范 §1.7 SLO 验证)"""
    import time
    from app.middleware.metrics_middleware import HTTP_REQUESTS_TOTAL, UPLOAD_DURATION
    start = time.monotonic()
    response = await call_next(request)
    duration = time.monotonic() - start
    # 简化端点标签: 用 path 去掉 query, 限制基数
    endpoint = request.url.path.split("?")[0]
    # 上传接口单独走 UPLOAD_DURATION (SLO < 500ms)
    if endpoint.startswith("/api/v1/inspect/") and request.method == "POST":
        algo = endpoint.rsplit("/", 1)[-1] if "/" in endpoint else "unknown"
        UPLOAD_DURATION.labels(algorithm=algo).observe(duration)
    # 通用 HTTP 计数
    HTTP_REQUESTS_TOTAL.labels(
        method=request.method,
        endpoint=endpoint,
        status=str(response.status_code),
    ).inc()
    return response

# 挂载业务路由
app.include_router(api_router)


@app.get("/")
async def root() -> dict:
    """根路径"""
    return {"app": "gevic", "version": __version__, "status": "running"}


# 进程启动时间 (用于 SLO 可用性计算)
import time as _time
_PROCESS_START_TIME = _time.time()
PROCESS_START_TIME = Gauge(
    "gevic_process_start_time_seconds",
    "进程启动时间 (Unix timestamp, 用于 uptime 计算)",
)
PROCESS_START_TIME.set(_PROCESS_START_TIME)


@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    """Prometheus 抓取端点 (无认证, 仅限内部网络)"""
    from app.services.metrics import render_metrics
    body, content_type = render_metrics()
    return Response(content=body, media_type=content_type)


@app.get("/health/live")
async def liveness() -> dict:
    """进程存活探针 (用于 k8s livenessProbe)"""
    return {"status": "alive"}


@app.get("/health/ready")
async def readiness() -> dict:
    """依赖就绪探针 (用于 k8s readinessProbe)"""
    from app.database import get_global_sessionmaker
    from app.services.storage import StorageService
    checks: dict = {}
    # Postgres
    try:
        from sqlalchemy import text
        sm = get_global_sessionmaker()
        async with sm() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
        DEPENDENCY_UP.labels(component="postgres").set(1)
    except Exception as e:
        checks["database"] = f"error: {e}"
        DEPENDENCY_UP.labels(component="postgres").set(0)
    # MinIO
    try:
        storage = StorageService.from_settings(get_settings())
        if storage.client.bucket_exists(storage.bucket):
            checks["minio"] = "ok"
            DEPENDENCY_UP.labels(component="minio").set(1)
        else:
            checks["minio"] = "bucket_missing"
            DEPENDENCY_UP.labels(component="minio").set(0)
    except Exception as e:
        checks["minio"] = f"error: {e}"
        DEPENDENCY_UP.labels(component="minio").set(0)
    # Redis
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(get_settings().celery_broker_url)
        await r.ping()
        await r.aclose()
        checks["redis"] = "ok"
        DEPENDENCY_UP.labels(component="redis").set(1)
    except Exception as e:
        checks["redis"] = f"error: {e}"
        DEPENDENCY_UP.labels(component="redis").set(0)
    all_ok = all(v == "ok" for v in checks.values())
    return {"status": "ready" if all_ok else "degraded", "checks": checks}


# 统一异常处理
@app.exception_handler(GevicError)
async def gevic_error_handler(request: Request, exc: GevicError) -> JSONResponse:
    code_map: dict[type[GevicError], tuple[int, str]] = {
        InvalidInspectorIdError: (400, "INVALID_INSPECTOR_ID"),
        AlgorithmNotFoundError: (400, "INVALID_ALGORITHM"),
        FileTooLargeError: (413, "FILE_TOO_LARGE"),
        LLMError: (502, "LLM_ERROR"),
        NotFoundError: (404, "NOT_FOUND"),
        GevicError: (500, "INTERNAL_ERROR"),
    }
    status_code, error_code = 500, "INTERNAL_ERROR"
    for cls, (sc, ec) in code_map.items():
        if isinstance(exc, cls):
            status_code, error_code = sc, ec
            break
    return JSONResponse(
        status_code=status_code,
        content={"code": error_code, "message": str(exc)},
    )
