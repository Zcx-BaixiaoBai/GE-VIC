"""FastAPI 应用入口"""
import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api import api_router
from app.config import Settings, get_settings
from app.database import dispose_engine, get_global_sessionmaker
from app.services.algorithm_registry import get_registry
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
        except Exception as e:
            logger.warning("Failed to load algorithm registry on startup: %s", e)
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

# 挂载业务路由
app.include_router(api_router)


@app.get("/")
async def root() -> dict:
    """根路径"""
    return {"app": "gevic", "version": __version__, "status": "running"}


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
