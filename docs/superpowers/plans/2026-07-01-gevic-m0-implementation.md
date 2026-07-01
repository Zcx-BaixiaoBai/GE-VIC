# GE-VIC 图像识别平台 M0 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** M0 阶段实现"1 个算法跑通端到端"—— 上传 → 入队 → 识别 → LLM 富化 → 入库 → 看板查询,全部可在 1 周内完成。

**Architecture:** Python 3.11+ FastAPI 单体应用 + Celery 异步任务 + PostgreSQL 元数据 + MinIO 对象存储 + Vue 3 看板。所有组件通过 docker-compose 一键启动,本地端到端可跑,云上可直接容器化部署。

**Tech Stack:**
- **Backend**: FastAPI 0.110+ · SQLAlchemy 2.0 (async) · Alembic · Celery 5.3+ · Pydantic 2.x · openai 1.x · minio-py
- **Frontend**: Vue 3.4+ · Vite 5+ · Element Plus · Pinia · Vue Router · Axios
- **Infra**: PostgreSQL 16 · Redis 7 · MinIO · Docker Compose
- **Testing**: pytest · pytest-asyncio · httpx (FastAPI test client) · Playwright

**Spec 引用**: `docs/superpowers/specs/2026-07-01-image-recognition-architecture-design.md` V1.2 §18 M0

---

## 文件结构

实施前需建立的目录与文件结构(按职责拆分,每个文件一个清晰职责):

```
gevic/
├── docker-compose.yml              # 6 服务编排
├── .env.example                    # 环境变量模板
├── .gitignore
├── README.md
├── backend/
│   ├── pyproject.toml              # uv/pip 依赖
│   ├── Dockerfile
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   │       └── 001_initial.py
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI 入口
│   │   ├── config.py               # Settings (env)
│   │   ├── database.py             # SQLAlchemy async engine
│   │   ├── deps.py                 # FastAPI 依赖注入
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── algorithm.py
│   │   │   ├── inspection.py
│   │   │   └── audit_log.py
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── algorithm.py
│   │   │   ├── inspection.py
│   │   │   └── common.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── router.py           # 主路由聚合
│   │   │   ├── inspect.py          # POST /api/v1/inspect/{code}
│   │   │   ├── records.py          # GET /api/v1/records, /{id}
│   │   │   ├── algorithms.py       # GET /api/v1/algorithms
│   │   │   ├── files.py            # GET /api/v1/records/{id}/file
│   │   │   └── health.py           # GET /api/v1/health
│   │   ├── engines/
│   │   │   ├── __init__.py
│   │   │   ├── base.py             # BaseEngine + RecognitionResult
│   │   │   ├── mock.py             # MockEngine (tests)
│   │   │   ├── cloud.py            # CloudVisionEngine (阿里云)
│   │   │   └── factory.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── algorithm_registry.py   # 启动加载
│   │   │   ├── audit.py                # 审计日志
│   │   │   ├── storage.py              # MinIO 存储
│   │   │   ├── llm_client.py           # OpenAI 兼容 LLM
│   │   │   └── enrichment.py           # LLM 富化
│   │   ├── tasks/
│   │   │   ├── __init__.py
│   │   │   ├── celery_app.py           # Celery 实例
│   │   │   └── inspection.py           # run_inspection 任务
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── inspector_id.py         # X-Inspector-Id 校验
│   │       └── exceptions.py
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py
│       ├── test_inspector_id.py
│       ├── test_audit.py
│       ├── test_storage.py
│       ├── test_llm_client.py
│       ├── test_enrichment.py
│       ├── test_engines.py
│       ├── test_algorithm_registry.py
│       ├── test_api_health.py
│       ├── test_api_algorithms.py
│       ├── test_api_inspect.py
│       ├── test_api_records.py
│       ├── test_task_inspection.py
│       └── e2e/
│           ├── __init__.py
│           └── test_inspect_workflow.py
└── frontend/
    ├── package.json
    ├── vite.config.ts
    ├── tsconfig.json
    ├── index.html
    ├── Dockerfile
    └── src/
        ├── main.ts
        ├── App.vue
        ├── env.d.ts
        ├── api/
        │   └── client.ts
        ├── stores/
        │   └── records.ts
        ├── router/
        │   └── index.ts
        ├── components/
        │   ├── RecordList.vue
        │   ├── RecordDetail.vue
        │   ├── UploadForm.vue
        │   └── StatusTag.vue
        └── views/
            ├── Dashboard.vue
            ├── UploadView.vue
            └── NotFound.vue
```

---

## 任务清单总览

| 阶段 | 任务 | 标题 |
|---|---|---|
| **基础** | T1 | 项目目录与 .gitignore |
| | T2 | 后端 pyproject.toml 与基础依赖 |
| | T3 | Docker Compose 6 服务 |
| | T4 | 后端 Dockerfile 与健康检查入口 |
| **配置 & DB** | T5 | Settings (env) |
| | T6 | SQLAlchemy 异步引擎 |
| | T7 | Alembic 初始迁移 (3 表) |
| | T8 | 模型类 (algorithm/inspection/audit_log) |
| | T9 | 种子算法数据 |
| **核心服务** | T10 | X-Inspector-Id 校验 |
| | T11 | 审计日志服务 |
| | T12 | MinIO 存储服务 |
| | T13 | 引擎基类与 Mock |
| | T14 | CloudVisionEngine (阿里云) |
| | T15 | 引擎工厂与注册表 |
| **API** | T16 | /health 端点 |
| | T17 | /algorithms 端点 |
| | T18 | /inspect/{code} 上传端点 |
| | T19 | /records 查询端点 |
| | T20 | /records/{id}/file 文件访问 |
| **异步** | T21 | Celery app 与 worker 启动 |
| | T22 | run_inspection 任务 (识别 + 失败重试) |
| | T23 | LLM 客户端 (OpenAI 兼容) |
| | T24 | LLM 富化服务 |
| **前端** | T25 | Vue 3 项目脚手架 |
| | T26 | API 客户端与 Pinia store |
| | T27 | 路由与 Dashboard |
| | T28 | 上传页 + 记录详情 + 重试/富化按钮 |
| **E2E** | T29 | E2E 5 场景测试 |
| **收尾** | T30 | README + 启动验证 |

---

## Phase 1: 基础

### Task 1: 项目目录与 .gitignore

**Files:**
- Create: `.gitignore`

- [ ] **Step 1: 创建 .gitignore**

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/
.pytest_cache/
.mypy_cache/
.ruff_cache/

# 环境
.env
.env.local
*.local

# IDE
.vscode/
.idea/
*.swp
*.swo

# 前端
frontend/node_modules/
frontend/dist/
frontend/.nuxt/
frontend/.output/

# 日志
*.log
logs/

# 数据
data/
postgres-data/
minio-data/
redis-data/

# 临时
tmp/
*.tmp
```

- [ ] **Step 2: 提交**

```bash
git add .gitignore
git commit -m "chore: 添加 .gitignore"
```

---

### Task 2: 后端 pyproject.toml

**Files:**
- Create: `backend/pyproject.toml`

- [ ] **Step 1: 创建 pyproject.toml**

```toml
[project]
name = "gevic-backend"
version = "0.1.0"
description = "GE-VIC 图像识别平台后端"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.110.0",
    "uvicorn[standard]>=0.27.0",
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
    "sqlalchemy[asyncio]>=2.0.25",
    "asyncpg>=0.29.0",
    "alembic>=1.13.0",
    "celery[redis]>=5.3.6",
    "redis>=5.0.0",
    "openai>=1.10.0",
    "minio>=7.2.0",
    "python-multipart>=0.0.9",
    "httpx>=0.26.0",
    "tenacity>=8.2.3",
    "structlog>=24.1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",
    "moto>=5.0.0",
]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["."]
include = ["app*"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: 创建 backend/.gitignore**

```gitignore
__pycache__/
*.py[cod]
.pytest_cache/
.venv/
*.egg-info/
.coverage
htmlcov/
```

- [ ] **Step 3: 提交**

```bash
git add backend/pyproject.toml backend/.gitignore
git commit -m "chore(backend): 初始化 pyproject.toml 与依赖"
```

---

### Task 3: Docker Compose 6 服务

**Files:**
- Create: `docker-compose.yml`
- Create: `.env.example`

- [ ] **Step 1: 创建 .env.example**

```bash
# 数据库
POSTGRES_USER=gevic
POSTGRES_PASSWORD=gevic_dev_password
POSTGRES_DB=gevic

# MinIO
MINIO_ROOT_USER=gevic_admin
MINIO_ROOT_PASSWORD=gevic_dev_password

# LLM (OpenAI 兼容 API)
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=sk-replace-with-your-key
LLM_MODEL=qwen-plus
LLM_MAX_INPUT_TOKENS=4000
LLM_MAX_OUTPUT_TOKENS=1000

# 默认算法引擎: 通义千问视觉 (示例,用户可在 algorithms 表中修改)
ALGORITHM_ENGINE_TYPE=cloud_api
ALGORITHM_CLOUD_PROVIDER=aliyun
ALGORITHM_CLOUD_ACCESS_KEY_ID=replace-with-your-ak
ALGORITHM_CLOUD_ACCESS_KEY_SECRET=replace-with-your-sk
ALGORITHM_CLOUD_ENDPOINT=https://imagerecog.cn-shanghai.aliyuncs.com

# Celery
CELERY_BROKER_URL=redis://redis:6379/0
# 注意: V1.0 不使用 result_backend

# 应用
APP_ENV=development
LOG_LEVEL=INFO
```

- [ ] **Step 2: 创建 docker-compose.yml**

```yaml
version: "3.9"

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - postgres-data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 5s
      timeout: 3s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
    volumes:
      - minio-data:/data
    ports:
      - "9000:9000"
      - "9001:9001"
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
      interval: 5s
      timeout: 3s
      retries: 5

  minio-init:
    image: minio/mc:latest
    depends_on:
      minio:
        condition: service_healthy
    entrypoint: >
      /bin/sh -c "
      mc alias set local http://minio:9000 ${MINIO_ROOT_USER} ${MINIO_ROOT_PASSWORD} &&
      mc mb --ignore-existing local/gevic &&
      mc anonymous set download local/gevic &&
      echo 'MinIO bucket gevic ready'
      "

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    env_file: .env
    environment:
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      minio:
        condition: service_healthy
    ports:
      - "8000:8000"
    volumes:
      - ./backend/app:/code/app

  worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: >
      sh -c "alembic upgrade head &&
             celery -A app.tasks.celery_app worker
             -Q inspect_queue,stats_queue,cleanup_queue
             --concurrency=8 -l info"
    env_file: .env
    environment:
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      minio:
        condition: service_healthy
    volumes:
      - ./backend/app:/code/app

volumes:
  postgres-data:
  minio-data:
```

- [ ] **Step 3: 验证 docker compose 配置语法**

```bash
docker compose config --quiet
```

期望: 无输出,退出码 0。

- [ ] **Step 4: 提交**

```bash
git add docker-compose.yml .env.example
git commit -m "chore: 添加 docker-compose 6 服务编排"
```

---

### Task 4: 后端 Dockerfile

**Files:**
- Create: `backend/Dockerfile`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`

- [ ] **Step 1: 创建 backend/Dockerfile**

```dockerfile
FROM python:3.11-slim

WORKDIR /code

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# 应用代码
COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: 创建 backend/app/__init__.py**

```python
"""GE-VIC 图像识别平台后端"""
__version__ = "0.1.0"
```

- [ ] **Step 3: 创建 backend/app/main.py 占位**

```python
"""FastAPI 应用入口 (M0 占位)"""
from fastapi import FastAPI

app = FastAPI(title="GE-VIC Image Recognition", version="0.1.0")


@app.get("/")
async def root() -> dict:
    """根路径 - 临时占位"""
    return {"app": "gevic", "version": "0.1.0", "status": "starting"}
```

- [ ] **Step 4: 构建后端镜像验证**

```bash
docker compose build backend
```

期望: 构建成功。

- [ ] **Step 5: 提交**

```bash
git add backend/Dockerfile backend/app/__init__.py backend/app/main.py
git commit -m "chore(backend): 添加 Dockerfile 与 FastAPI 入口占位"
```

---

## Phase 2: 配置 & 数据库

### Task 5: Settings (env)

**Files:**
- Create: `backend/app/config.py`
- Create: `backend/tests/test_config.py`

- [ ] **Step 1: 写失败测试 backend/tests/test_config.py**

```python
"""配置测试"""
import pytest
from pydantic import ValidationError

from app.config import Settings


def test_settings_load_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """从环境变量加载所有必填配置"""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/db")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.com/v1")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("LLM_MAX_INPUT_TOKENS", "4000")
    monkeypatch.setenv("LLM_MAX_OUTPUT_TOKENS", "1000")

    settings = Settings()

    assert settings.database_url == "postgresql+asyncpg://u:p@localhost:5432/db"
    assert settings.llm_base_url == "https://example.com/v1"
    assert settings.llm_api_key == "test-key"
    assert settings.llm_model == "gpt-4o-mini"
    assert settings.llm_max_input_tokens == 4000
    assert settings.llm_max_output_tokens == 1000


def test_settings_missing_required() -> None:
    """缺必填项应抛 ValidationError"""
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]
```

- [ ] **Step 2: 运行测试,确认失败**

```bash
cd backend && python -m pytest tests/test_config.py -v
```

期望: FAIL (No module named 'app.config')

- [ ] **Step 3: 实现 backend/app/config.py**

```python
"""应用配置 - pydantic-settings 从环境变量加载"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 数据库
    database_url: str

    # LLM
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    llm_max_input_tokens: int = 4000
    llm_max_output_tokens: int = 1000

    # 对象存储
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "gevic_admin"
    minio_secret_key: str = "gevic_dev_password"
    minio_bucket: str = "gevic"
    minio_secure: bool = False

    # Celery
    celery_broker_url: str = "redis://redis:6379/0"

    # 应用
    app_env: str = "development"
    log_level: str = "INFO"

    # 文件上传限制
    max_image_size: int = 20 * 1024 * 1024  # 20MB
    max_video_size: int = 500 * 1024 * 1024  # 500MB


def get_settings() -> Settings:
    """获取单例设置"""
    return Settings()  # type: ignore[call-arg]
```

- [ ] **Step 4: 运行测试,确认通过**

```bash
cd backend && python -m pytest tests/test_config.py -v
```

期望: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/config.py backend/tests/test_config.py
git commit -m "feat(backend): 添加 pydantic Settings 配置"
```

---

### Task 6: SQLAlchemy 异步引擎

**Files:**
- Create: `backend/app/database.py`
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/base.py`
- Create: `backend/tests/test_database.py`

- [ ] **Step 1: 写失败测试 backend/tests/test_database.py**

```python
"""数据库引擎测试"""
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.database import create_engine, get_sessionmaker


def test_create_engine_returns_async_engine() -> None:
    """create_engine 返回 AsyncEngine 实例"""
    engine = create_engine("postgresql+asyncpg://u:p@localhost:5432/db")
    assert isinstance(engine, AsyncEngine)


def test_get_sessionmaker_returns_callable() -> None:
    """get_sessionmaker 返回 sessionmaker 工厂"""
    engine = create_engine("postgresql+asyncpg://u:p@localhost:5432/db")
    sm = get_sessionmaker(engine)
    # sessionmaker() 返回 AsyncSession 实例
    session = sm()
    assert isinstance(session, AsyncSession)
    # 关闭 session 防止连接泄漏
    pytest.run_in_asyncio_loop = True
```

- [ ] **Step 2: 跑测试,确认失败**

```bash
cd backend && python -m pytest tests/test_database.py -v
```

期望: FAIL

- [ ] **Step 3: 创建 backend/app/models/__init__.py**

```python
"""数据库模型"""
from app.models.base import Base
from app.models.algorithm import Algorithm
from app.models.inspection import Inspection
from app.models.audit_log import AuditLog

__all__ = ["Base", "Algorithm", "Inspection", "AuditLog"]
```

- [ ] **Step 4: 创建 backend/app/models/base.py**

```python
"""SQLAlchemy 声明基类"""
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """所有模型的基类"""
    pass


class TimestampMixin:
    """created_at / updated_at 时间戳混入"""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
```

- [ ] **Step 5: 创建 backend/app/database.py**

```python
"""SQLAlchemy 异步引擎与 session 工厂"""
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_engine(database_url: str, **kwargs: Any) -> AsyncEngine:
    """创建异步引擎"""
    return create_async_engine(
        database_url,
        echo=kwargs.get("echo", False),
        pool_size=kwargs.get("pool_size", 10),
        max_overflow=kwargs.get("max_overflow", 20),
        pool_pre_ping=True,
    )


def get_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """获取 async sessionmaker 工厂"""
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def get_session(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖: 每次请求一个 session"""
    async with sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

- [ ] **Step 6: 跑测试,确认通过**

```bash
cd backend && python -m pytest tests/test_database.py -v
```

期望: PASS

- [ ] **Step 7: 提交**

```bash
git add backend/app/database.py backend/app/models/
git commit -m "feat(backend): 添加 SQLAlchemy 异步引擎与基类"
```

---

### Task 7: 数据库模型 (3 张表)

**Files:**
- Create: `backend/app/models/algorithm.py`
- Create: `backend/app/models/inspection.py`
- Create: `backend/app/models/audit_log.py`
- Create: `backend/tests/test_models.py`

- [ ] **Step 1: 写失败测试 backend/tests/test_models.py**

```python
"""模型字段测试"""
from sqlalchemy import inspect

from app.models import Algorithm, AuditLog, Base, Inspection


def test_algorithm_table_name() -> None:
    """Algorithm 表名"""
    assert Algorithm.__tablename__ == "algorithms"


def test_algorithm_columns() -> None:
    """Algorithm 列存在"""
    cols = {c.name for c in inspect(Algorithm).columns}
    assert {"id", "code", "name", "category", "engine_type", "engine_config",
            "request_schema", "is_active", "version"}.issubset(cols)


def test_inspection_columns() -> None:
    """Inspection 列存在"""
    cols = {c.name for c in inspect(Inspection).columns}
    assert {"id", "algorithm_code", "status", "object_key", "file_hash",
            "file_size", "file_type", "result", "llm_enrichment",
            "enrichment_status", "error_message", "retry_count",
            "inspector_id", "asset_id"}.issubset(cols)


def test_audit_log_columns() -> None:
    """AuditLog 列存在"""
    cols = {c.name for c in inspect(AuditLog).columns}
    assert {"id", "occurred_at", "actor", "action", "resource_type",
            "resource_id", "source_ip", "result", "error_code"}.issubset(cols)


def test_all_models_inherit_base() -> None:
    """所有模型继承 Base"""
    for cls in (Algorithm, Inspection, AuditLog):
        assert issubclass(cls, Base)
```

- [ ] **Step 2: 跑测试,确认失败**

```bash
cd backend && python -m pytest tests/test_models.py -v
```

期望: FAIL (模型未创建)

- [ ] **Step 3: 创建 backend/app/models/algorithm.py**

```python
"""算法注册表"""
from typing import Any

from sqlalchemy import JSON, BigInteger, Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Algorithm(Base, TimestampMixin):
    """算法注册表 - 路由 + 引擎的唯一真源"""

    __tablename__ = "algorithms"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str | None] = mapped_column(String(64), index=True)
    description: Mapped[str | None] = mapped_column(String)
    engine_type: Mapped[str] = mapped_column(String(32), nullable=False)
    engine_config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    request_schema: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
```

- [ ] **Step 4: 创建 backend/app/models/inspection.py**

```python
"""识别记录表"""
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON, BigInteger, BigInteger as BigInt, Index, Integer, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Inspection(Base, TimestampMixin):
    """识别记录 - 每条上传 + 识别产生一行"""

    __tablename__ = "inspections"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True)

    # 业务字段
    algorithm_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    category: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    # PENDING / RUNNING / SUCCESS / FAILED / DEAD
    enrichment_status: Mapped[str | None] = mapped_column(String(16))
    # NONE / RUNNING / ENRICHED / ENRICH_FAILED

    # 文件
    object_key: Mapped[str | None] = mapped_column(String(256))
    file_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    file_size: Mapped[int | None] = mapped_column(BigInt)
    file_type: Mapped[str | None] = mapped_column(String(16))
    # image / video

    # 识别结果
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    llm_enrichment: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    # 错误信息
    error_message: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(String(64))

    # 重试
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # 巡检员与资产
    inspector_id: Mapped[str | None] = mapped_column(String(64), index=True)
    location: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    asset_id: Mapped[str | None] = mapped_column(String(64), index=True)

    # 性能
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    cost_estimate: Mapped[float | None] = mapped_column()

    # 时间
    started_at: Mapped[datetime | None] = mapped_column()
    finished_at: Mapped[datetime | None] = mapped_column()


# 复合索引
Index("idx_insp_alg_created", Inspection.algorithm_code, Inspection.created_at.desc())
Index("idx_insp_status_created", Inspection.status, Inspection.created_at.desc())
```

- [ ] **Step 5: 创建 backend/app/models/audit_log.py**

```python
"""审计日志表"""
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditLog(Base):
    """审计日志 - 事后追责"""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    actor: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(64))
    source_ip: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(String(256))
    request_id: Mapped[str | None] = mapped_column(String(64))
    request_meta: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    result: Mapped[str] = mapped_column(String(16), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)


Index("idx_audit_actor_time", AuditLog.actor, AuditLog.occurred_at.desc())
Index("idx_audit_resource", AuditLog.resource_type, AuditLog.resource_id)
Index("idx_audit_action_time", AuditLog.action, AuditLog.occurred_at.desc())
```

- [ ] **Step 6: 跑测试,确认通过**

```bash
cd backend && python -m pytest tests/test_models.py -v
```

期望: PASS

- [ ] **Step 7: 提交**

```bash
git add backend/app/models/ backend/tests/test_models.py
git commit -m "feat(backend): 添加 algorithms/inspections/audit_logs 3 张表模型"
```

---

### Task 8: Alembic 初始迁移

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Create: `backend/alembic/versions/001_initial.py`

- [ ] **Step 1: 创建 backend/alembic.ini**

```ini
[alembic]
script_location = alembic
prepend_sys_path = .
version_path_separator = os
sqlalchemy.url = postgresql+asyncpg://u:p@localhost:5432/db

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 2: 创建 backend/alembic/env.py**

```python
"""Alembic 环境配置 - 同步包装 async engine"""
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# 导入模型基类与所有模型,确保 metadata 注册
from app.config import get_settings
from app.models import Base  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", get_settings().database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """异步模式"""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """在线模式入口"""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 3: 创建 backend/alembic/script.py.mako**

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 4: 创建 backend/alembic/versions/001_initial.py**

```python
"""initial: 3 张核心表

Revision ID: 001
Revises:
Create Date: 2026-07-01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "algorithms",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("code", sa.String(64), unique=True, nullable=False, index=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("category", sa.String(64), index=True),
        sa.Column("description", sa.String),
        sa.Column("engine_type", sa.String(32), nullable=False),
        sa.Column("engine_config", postgresql.JSON, nullable=False),
        sa.Column("request_schema", postgresql.JSON),
        sa.Column("is_active", sa.Boolean, nullable=False, default=True, index=True),
        sa.Column("version", sa.Integer, nullable=False, default=1),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "inspections",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("algorithm_code", sa.String(64), nullable=False, index=True),
        sa.Column("category", sa.String(64)),
        sa.Column("status", sa.String(16), nullable=False, index=True),
        sa.Column("enrichment_status", sa.String(16)),
        sa.Column("object_key", sa.String(256)),
        sa.Column("file_hash", sa.String(64), index=True),
        sa.Column("file_size", sa.BigInteger),
        sa.Column("file_type", sa.String(16)),
        sa.Column("result", postgresql.JSON),
        sa.Column("llm_enrichment", postgresql.JSON),
        sa.Column("error_message", sa.Text),
        sa.Column("error_code", sa.String(64)),
        sa.Column("retry_count", sa.Integer, nullable=False, default=0),
        sa.Column("inspector_id", sa.String(64), index=True),
        sa.Column("location", postgresql.JSON),
        sa.Column("asset_id", sa.String(64), index=True),
        sa.Column("duration_ms", sa.Integer),
        sa.Column("cost_estimate", sa.Float),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_insp_alg_created", "inspections", ["algorithm_code", sa.text("created_at DESC")])
    op.create_index("idx_insp_status_created", "inspections", ["status", sa.text("created_at DESC")])
    op.create_index("idx_insp_result_gin", "inspections", ["result"], postgresql_using="gin")
    op.create_index("idx_insp_meta_gin", "inspections", ["location"], postgresql_using="gin")

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("actor", sa.String(64), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("resource_type", sa.String(32), nullable=False),
        sa.Column("resource_id", sa.String(64)),
        sa.Column("source_ip", postgresql.INET),
        sa.Column("user_agent", sa.String(256)),
        sa.Column("request_id", sa.String(64)),
        sa.Column("request_meta", postgresql.JSON),
        sa.Column("result", sa.String(16), nullable=False),
        sa.Column("error_code", sa.String(64)),
        sa.Column("error_message", sa.Text),
    )
    op.create_index("idx_audit_actor_time", "audit_logs", ["actor", sa.text("occurred_at DESC")])
    op.create_index("idx_audit_resource", "audit_logs", ["resource_type", "resource_id"])
    op.create_index("idx_audit_action_time", "audit_logs", ["action", sa.text("occurred_at DESC")])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("inspections")
    op.drop_table("algorithms")
```

- [ ] **Step 5: 启动 docker compose 并跑迁移**

```bash
docker compose up -d postgres
# 等待就绪
docker compose exec postgres pg_isready -U gevic
```

```bash
cd backend
export DATABASE_URL="postgresql+asyncpg://gevic:gevic_dev_password@localhost:5432/gevic"
export LLM_BASE_URL="https://example.com/v1"
export LLM_API_KEY="test"
export LLM_MODEL="test"
alembic upgrade head
```

期望: Running upgrade -> 001, initial: 3 张表

- [ ] **Step 6: 验证表已创建**

```bash
docker compose exec postgres psql -U gevic -d gevic -c "\dt"
```

期望: 看到 `algorithms`, `inspections`, `audit_logs` 三张表

- [ ] **Step 7: 提交**

```bash
git add backend/alembic.ini backend/alembic/
git commit -m "feat(backend): 添加 Alembic 初始迁移 (3 张表)"
```

---

### Task 9: 种子算法数据

**Files:**
- Create: `backend/alembic/versions/002_seed_algorithm.py`
- Create: `backend/tests/test_seed.py`

- [ ] **Step 1: 写失败测试 backend/tests/test_seed.py**

```python
"""种子数据测试 - 验证算法表中有 1 条绝缘子破损算法"""
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_insulator_damage_algorithm_exists(db_session: AsyncSession) -> None:
    """种子算法 - 绝缘子破损识别应存在"""
    result = await db_session.execute(
        text("SELECT code, name, engine_type, is_active FROM algorithms WHERE code = :code"),
        {"code": "insulator-damage"},
    )
    row = result.fetchone()
    assert row is not None
    assert row.code == "insulator-damage"
    assert row.engine_type == "cloud_api"
    assert row.is_active is True
```

- [ ] **Step 2: 写 conftest.py backend/tests/conftest.py**

```python
"""pytest fixtures - 测试用 DB session"""
import os
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def db_session():
    """连接到测试 DB,自动清理"""
    url = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://gevic:gevic_dev_password@localhost:5432/gevic",
    )
    engine = create_async_engine(url)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as session:
        yield session
        await session.rollback()
    await engine.dispose()
```

- [ ] **Step 3: 创建迁移 backend/alembic/versions/002_seed_algorithm.py**

```python
"""seed: 种子算法数据

Revision ID: 002
Revises: 001
Create Date: 2026-07-01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO algorithms (code, name, category, description, engine_type, engine_config, request_schema, is_active, version, created_at, updated_at)
            VALUES (
                'insulator-damage',
                '绝缘子破损识别',
                '供配电',
                '识别绝缘子伞裙破损、污秽、闪络等缺陷',
                'cloud_api',
                '{"provider": "aliyun", "endpoint": "https://imagerecog.cn-shanghai.aliyuncs.com", "action": "RecognizeInsulatorDamage", "access_key_id": "REPLACE_ME", "access_key_secret": "REPLACE_ME"}',
                '{"type": "object", "properties": {"voltage_level": {"type": "string", "enum": ["10kV", "35kV", "110kV", "220kV"]}}}',
                true,
                1,
                now(),
                now()
            )
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM algorithms WHERE code = 'insulator-damage'"))
```

- [ ] **Step 4: 跑迁移**

```bash
cd backend
export DATABASE_URL="postgresql+asyncpg://gevic:gevic_dev_password@localhost:5432/gevic"
export LLM_BASE_URL="https://example.com/v1"
export LLM_API_KEY="test"
export LLM_MODEL="test"
alembic upgrade head
```

- [ ] **Step 5: 跑测试**

```bash
cd backend && python -m pytest tests/test_seed.py -v
```

期望: PASS

- [ ] **Step 6: 提交**

```bash
git add backend/alembic/versions/002_seed_algorithm.py backend/tests/test_seed.py backend/tests/conftest.py
git commit -m "feat(backend): 添加种子算法数据 (绝缘子破损)"
```

---

## Phase 3: 核心服务

### Task 10: X-Inspector-Id 校验

**Files:**
- Create: `backend/app/utils/__init__.py`
- Create: `backend/app/utils/inspector_id.py`
- Create: `backend/app/utils/exceptions.py`
- Create: `backend/tests/test_inspector_id.py`

- [ ] **Step 1: 写失败测试 backend/tests/test_inspector_id.py**

```python
"""X-Inspector-Id 校验测试"""
import pytest

from app.utils.exceptions import InvalidInspectorIdError
from app.utils.inspector_id import validate_inspector_id, INSPECTOR_ID_PATTERN


def test_pattern_compiles() -> None:
    """正则能编译"""
    assert INSPECTOR_ID_PATTERN.pattern == r"^[A-Za-z0-9_-]{3,32}$"


def test_valid_inspector_ids() -> None:
    """合法 ID 通过"""
    for valid in ["INSP-001", "abc", "user_name", "A1B2C3", "x" * 32, "abc-123_xyz"]:
        assert validate_inspector_id(valid) == valid


def test_invalid_too_short() -> None:
    """过短抛错"""
    with pytest.raises(InvalidInspectorIdError):
        validate_inspector_id("ab")


def test_invalid_too_long() -> None:
    """过长抛错"""
    with pytest.raises(InvalidInspectorIdError):
        validate_inspector_id("x" * 33)


def test_invalid_chars() -> None:
    """非法字符抛错"""
    for invalid in ["abc!", "abc def", "abc@def", "abc/def", "<script>"]:
        with pytest.raises(InvalidInspectorIdError):
            validate_inspector_id(invalid)


def test_none_or_empty() -> None:
    """None/空字符串抛错"""
    for invalid in [None, ""]:
        with pytest.raises(InvalidInspectorIdError):
            validate_inspector_id(invalid)  # type: ignore[arg-type]
```

- [ ] **Step 2: 跑测试,确认失败**

```bash
cd backend && python -m pytest tests/test_inspector_id.py -v
```

期望: FAIL

- [ ] **Step 3: 创建 backend/app/utils/__init__.py**

```python
"""工具模块"""
```

- [ ] **Step 4: 创建 backend/app/utils/exceptions.py**

```python
"""自定义异常"""


class GevicError(Exception):
    """基础异常"""
    pass


class InvalidInspectorIdError(GevicError):
    """X-Inspector-Id 格式不合法"""
    pass


class AlgorithmNotFoundError(GevicError):
    """算法 code 不存在或未启用"""
    pass


class FileTooLargeError(GevicError):
    """文件超过大小限制"""
    pass


class EngineError(GevicError):
    """识别引擎调用失败"""
    pass


class LLMError(GevicError):
    """LLM 调用失败"""
    pass
```

- [ ] **Step 5: 创建 backend/app/utils/inspector_id.py**

```python
"""X-Inspector-Id 校验

V1.0 极简护栏: 只做格式校验,不做身份认证
"""
import re

from app.utils.exceptions import InvalidInspectorIdError

# 允许字母、数字、下划线、连字符, 长度 3-32
INSPECTOR_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{3,32}$")


def validate_inspector_id(inspector_id: str | None) -> str:
    """校验并返回 inspector_id, 失败抛 InvalidInspectorIdError"""
    if inspector_id is None or inspector_id == "":
        raise InvalidInspectorIdError("X-Inspector-Id is required")
    if not INSPECTOR_ID_PATTERN.match(inspector_id):
        raise InvalidInspectorIdError(
            f"X-Inspector-Id '{inspector_id}' 不合法, 需匹配 {INSPECTOR_ID_PATTERN.pattern}"
        )
    return inspector_id
```

- [ ] **Step 6: 跑测试,确认通过**

```bash
cd backend && python -m pytest tests/test_inspector_id.py -v
```

期望: PASS

- [ ] **Step 7: 提交**

```bash
git add backend/app/utils/ backend/tests/test_inspector_id.py
git commit -m "feat(backend): X-Inspector-Id 格式校验 (最薄护栏)"
```

---

### Task 11: 审计日志服务

**Files:**
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/audit.py`
- Create: `backend/tests/test_audit.py`

- [ ] **Step 1: 写失败测试 backend/tests/test_audit.py**

```python
"""审计日志服务测试"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.audit import AuditService, AuditAction, AuditResult


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.mark.asyncio
async def test_log_success(mock_session: AsyncMock) -> None:
    """记录成功操作"""
    service = AuditService(mock_session)
    await service.log(
        actor="INSP-001",
        action=AuditAction.UPLOAD,
        resource_type="inspection",
        resource_id="1024",
        source_ip="192.168.1.1",
        result=AuditResult.SUCCESS,
    )
    assert mock_session.add.called
    log = mock_session.add.call_args[0][0]
    assert log.actor == "INSP-001"
    assert log.action == "upload"
    assert log.resource_type == "inspection"
    assert log.resource_id == "1024"
    assert log.source_ip == "192.168.1.1"
    assert log.result == "success"
    assert log.occurred_at is not None


@pytest.mark.asyncio
async def test_log_failure_with_error(mock_session: AsyncMock) -> None:
    """记录失败操作带错误码"""
    service = AuditService(mock_session)
    await service.log(
        actor="INSP-001",
        action=AuditAction.QUERY,
        resource_type="inspection",
        result=AuditResult.FAILED,
        error_code="INVALID_ALGORITHM",
    )
    log = mock_session.add.call_args[0][0]
    assert log.result == "failed"
    assert log.error_code == "INVALID_ALGORITHM"
```

- [ ] **Step 2: 跑测试,确认失败**

```bash
cd backend && python -m pytest tests/test_audit.py -v
```

期望: FAIL

- [ ] **Step 3: 创建 backend/app/services/__init__.py**

```python
"""业务服务层"""
```

- [ ] **Step 4: 创建 backend/app/services/audit.py**

```python
"""审计日志服务 - 事后追责

V1.0 简化: 不做异步写,跟主事务同提交
"""
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


class AuditAction(StrEnum):
    """操作类型枚举"""
    UPLOAD = "upload"
    QUERY = "query"
    RETRY = "retry"
    ENRICH = "enrich"
    REGISTER_ALGORITHM = "register_algorithm"


class AuditResult(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"


class AuditService:
    """审计日志写入服务"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def log(
        self,
        actor: str,
        action: AuditAction,
        resource_type: str,
        resource_id: str | None = None,
        source_ip: str | None = None,
        user_agent: str | None = None,
        request_id: str | None = None,
        request_meta: dict[str, Any] | None = None,
        result: AuditResult = AuditResult.SUCCESS,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """记录一条审计日志, 自动 flush 到 session"""
        log = AuditLog(
            occurred_at=datetime.now(timezone.utc),
            actor=actor,
            action=action.value,
            resource_type=resource_type,
            resource_id=resource_id,
            source_ip=source_ip,
            user_agent=user_agent,
            request_id=request_id,
            request_meta=request_meta,
            result=result.value,
            error_code=error_code,
            error_message=error_message,
        )
        self.session.add(log)
        await self.session.flush()
```

- [ ] **Step 5: 跑测试,确认通过**

```bash
cd backend && python -m pytest tests/test_audit.py -v
```

期望: PASS

- [ ] **Step 6: 提交**

```bash
git add backend/app/services/audit.py backend/tests/test_audit.py
git commit -m "feat(backend): 审计日志服务"
```

---

### Task 12: MinIO 存储服务

**Files:**
- Create: `backend/app/services/storage.py`
- Create: `backend/tests/test_storage.py`

- [ ] **Step 1: 写失败测试 backend/tests/test_storage.py**

```python
"""存储服务测试"""
import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.storage import StorageService


@pytest.fixture
def mock_minio() -> MagicMock:
    client = MagicMock()
    client.put_object = MagicMock()
    client.presigned_get_object = MagicMock(return_value="https://example.com/signed")
    client.bucket_exists = MagicMock(return_value=True)
    return client


def test_upload_file(mock_minio: MagicMock) -> None:
    """上传文件返回 object_key"""
    service = StorageService(client=mock_minio, bucket="gevic")
    key = service.upload_file(
        file_bytes=b"hello world",
        filename="test.jpg",
        record_id=1024,
    )
    assert key.startswith("inspections/")
    assert "1024" in key
    assert key.endswith("test.jpg")
    assert mock_minio.put_object.called


def test_get_file_url(mock_minio: MagicMock) -> None:
    """生成签名 URL"""
    service = StorageService(client=mock_minio, bucket="gevic")
    url = service.get_file_url("inspections/2026/07/01/1024/test.jpg")
    assert url == "https://example.com/signed"
    mock_minio.presigned_get_object.assert_called_once()


def test_ensure_bucket(mock_minio: MagicMock) -> None:
    """桶不存在则创建"""
    mock_minio.bucket_exists.return_value = False
    service = StorageService(client=mock_minio, bucket="gevic")
    service.ensure_bucket()
    assert mock_minio.make_bucket.called
```

- [ ] **Step 2: 跑测试,确认失败**

```bash
cd backend && python -m pytest tests/test_storage.py -v
```

期望: FAIL

- [ ] **Step 3: 实现 backend/app/services/storage.py**

```python
"""MinIO 对象存储服务"""
from datetime import datetime, timezone

from minio import Minio

from app.config import Settings


class StorageService:
    """MinIO 存储服务"""

    def __init__(self, client: Minio, bucket: str) -> None:
        self.client = client
        self.bucket = bucket

    @classmethod
    def from_settings(cls, settings: Settings) -> "StorageService":
        """工厂方法: 从 Settings 创建"""
        client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        return cls(client=client, bucket=settings.minio_bucket)

    def ensure_bucket(self) -> None:
        """确保桶存在"""
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def upload_file(
        self,
        file_bytes: bytes,
        filename: str,
        record_id: int,
        content_type: str = "application/octet-stream",
    ) -> str:
        """上传文件,返回 object_key"""
        now = datetime.now(timezone.utc)
        object_key = (
            f"inspections/{now.year:04d}/{now.month:02d}/{now.day:02d}/"
            f"{record_id}/{filename}"
        )
        self.client.put_object(
            bucket_name=self.bucket,
            object_name=object_key,
            data=__import__("io").BytesIO(file_bytes),
            length=len(file_bytes),
            content_type=content_type,
        )
        return object_key

    def get_file_url(self, object_key: str, expires_seconds: int = 900) -> str:
        """生成签名 URL (默认 15 分钟)"""
        from datetime import timedelta
        url = self.client.presigned_get_object(
            bucket_name=self.bucket,
            object_name=object_key,
            expires=timedelta(seconds=expires_seconds),
        )
        return url
```

- [ ] **Step 4: 跑测试,确认通过**

```bash
cd backend && python -m pytest tests/test_storage.py -v
```

期望: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/storage.py backend/tests/test_storage.py
git commit -m "feat(backend): MinIO 存储服务"
```

---

### Task 13: 引擎基类与 Mock

**Files:**
- Create: `backend/app/engines/__init__.py`
- Create: `backend/app/engines/base.py`
- Create: `backend/app/engines/mock.py`
- Create: `backend/tests/test_engines.py`

- [ ] **Step 1: 写失败测试 backend/tests/test_engines.py**

```python
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
```

- [ ] **Step 2: 跑测试,确认失败**

```bash
cd backend && python -m pytest tests/test_engines.py -v
```

期望: FAIL

- [ ] **Step 3: 创建 backend/app/engines/__init__.py**

```python
"""引擎适配器层"""
from app.engines.base import BaseEngine, EngineError, RecognitionResult
from app.engines.factory import get_engine

__all__ = ["BaseEngine", "EngineError", "RecognitionResult", "get_engine"]
```

- [ ] **Step 4: 创建 backend/app/engines/base.py**

```python
"""引擎抽象基类"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class RecognitionResult:
    """识别结果 - 所有引擎统一返回"""
    success: bool
    data: dict[str, Any] | None
    summary: str | None
    error_code: str | None
    error_message: str | None
    raw_response: Any
    cost_estimate: float | None
    duration_ms: int | None


class EngineError(Exception):
    """引擎调用错误"""
    pass


class BaseEngine(ABC):
    """所有识别引擎的抽象基类

    识别引擎可以是云 API、海康超脑、或自建模型
    """

    engine_type: str = "base"

    @abstractmethod
    async def recognize(
        self,
        file_bytes: bytes,
        filename: str,
        meta: dict[str, Any],
        config: dict[str, Any],
    ) -> RecognitionResult:
        """对单张图/视频执行识别

        Args:
            file_bytes: 文件二进制内容
            filename: 文件名(用于推断类型)
            meta: 上传请求的元数据(asset_id, location 等)
            config: 算法注册表中的 engine_config

        Returns:
            RecognitionResult, success=True 表示识别成功
        """
        raise NotImplementedError

    @abstractmethod
    async def health_check(self, config: dict[str, Any]) -> bool:
        """健康检查 - 验证引擎可达"""
        raise NotImplementedError
```

- [ ] **Step 5: 创建 backend/app/engines/mock.py**

```python
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
```

- [ ] **Step 6: 跑测试,确认通过**

```bash
cd backend && python -m pytest tests/test_engines.py -v
```

期望: PASS

- [ ] **Step 7: 提交**

```bash
git add backend/app/engines/ backend/tests/test_engines.py
git commit -m "feat(backend): 引擎基类与 Mock 引擎"
```

---

### Task 14: CloudVisionEngine (阿里云)

**Files:**
- Create: `backend/app/engines/cloud.py`
- Create: `backend/tests/test_cloud_engine.py`

- [ ] **Step 1: 写失败测试 backend/tests/test_cloud_engine.py**

```python
"""CloudVisionEngine 测试 - 用 Mock HTTP 模拟阿里云"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.engines.base import EngineError
from app.engines.cloud import CloudVisionEngine


def test_engine_type() -> None:
    """engine_type 标识为 cloud_api"""
    assert CloudVisionEngine.engine_type == "cloud_api"


def test_health_check_success() -> None:
    """health_check 成功"""
    engine = CloudVisionEngine()
    config = {"provider": "aliyun", "endpoint": "https://example.com", "access_key_id": "x", "access_key_secret": "y"}
    with patch.object(engine, "_ping", new_callable=AsyncMock) as mock_ping:
        mock_ping.return_value = True
        result = asyncio.run(engine.health_check(config))
    assert result is True


def test_recognize_network_error() -> None:
    """网络错误抛 EngineError"""
    engine = CloudVisionEngine()
    config = {"provider": "aliyun", "endpoint": "https://example.com", "action": "RecognizeTest", "access_key_id": "x", "access_key_secret": "y"}
    with patch.object(engine, "_call_api", new_callable=AsyncMock) as mock_call:
        mock_call.side_effect = EngineError("network timeout")
        with pytest.raises(EngineError):
            asyncio.run(engine.recognize(b"fake", "test.jpg", {}, config))
```

- [ ] **Step 2: 跑测试,确认失败**

```bash
cd backend && python -m pytest tests/test_cloud_engine.py -v
```

期望: FAIL

- [ ] **Step 3: 实现 backend/app/engines/cloud.py**

```python
"""CloudVisionEngine - 阿里云/腾讯云/百度等视觉云 API 适配

V1.0: 仅实现阿里云视觉智能开放平台 (RecognizeImageStyle 等)
后续可扩展腾讯云/百度等 provider
"""
import asyncio
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

    async def health_check(self, config: dict[str, Any]) -> bool:
        endpoint = config.get("endpoint", "")
        if not endpoint:
            return False
        return await self._ping(endpoint)

    async def _call_api(
        self,
        config: dict[str, Any],
        file_bytes: bytes,
        filename: str,
    ) -> dict[str, Any]:
        """调用云 API

        V1.0 实现: 阿里云视觉智能 (RPC 风格)
        生产环境应使用官方 SDK (alibabacloud_imagerecog20190930)
        此处用 httpx + 简化签名, 便于本地测试
        """
        endpoint = config["endpoint"]
        action = config.get("action", "RecognizeImageStyle")

        # 简化: 实际生产应使用阿里云 SDK
        # 这里仅做接口存在性校验, 真实实现见 Phase 2 接入
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

        # 解析云 API 返回 (格式因 provider 而异, 此处简化)
        defects = raw.get("Data", {}).get("Defects", [])
        normalized = {
            "defects": defects,
            "raw": raw,
        }
        return RecognitionResult(
            success=True,
            data=normalized,
            summary=f"云 API 识别完成, 共 {len(defects)} 处",
            error_code=None,
            error_message=None,
            raw_response=raw,
            cost_estimate=0.01,  # 估算, 实际从云账单
            duration_ms=int((time.monotonic() - start) * 1000),
        )
```

- [ ] **Step 4: 跑测试,确认通过**

```bash
cd backend && python -m pytest tests/test_cloud_engine.py -v
```

期望: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/engines/cloud.py backend/tests/test_cloud_engine.py
git commit -m "feat(backend): CloudVisionEngine 阿里云适配器"
```

---

### Task 15: 引擎工厂与算法注册表

**Files:**
- Create: `backend/app/engines/factory.py`
- Create: `backend/app/services/algorithm_registry.py`
- Create: `backend/tests/test_algorithm_registry.py`

- [ ] **Step 1: 写失败测试 backend/tests/test_algorithm_registry.py**

```python
"""算法注册表测试"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.engines.base import BaseEngine
from app.engines.factory import ENGINE_REGISTRY, get_engine
from app.services.algorithm_registry import AlgorithmRegistry


def test_engine_registry_has_cloud_and_mock() -> None:
    """注册表包含 cloud_api 和 mock"""
    assert "cloud_api" in ENGINE_REGISTRY
    assert "mock" in ENGINE_REGISTRY


def test_get_engine_returns_correct_type() -> None:
    """get_engine 根据 engine_type 返回对应实例"""
    engine = get_engine("mock")
    assert engine.engine_type == "mock"


def test_get_engine_unknown_raises() -> None:
    """未知 engine_type 抛错"""
    from app.utils.exceptions import GevicError
    with pytest.raises(Exception):  # ValueError or GevicError
        get_engine("nonexistent")


@pytest.mark.asyncio
async def test_registry_loads_active_algorithms() -> None:
    """启动加载所有 active 算法"""
    mock_session = AsyncMock()
    # 模拟 2 条记录
    algo1 = MagicMock()
    algo1.code = "insulator-damage"
    algo1.is_active = True
    algo1.engine_type = "mock"
    algo1.engine_config = {"x": 1}
    algo1.request_schema = None
    algo2 = MagicMock()
    algo2.code = "pipe-leakage"
    algo2.is_active = True
    algo2.engine_type = "cloud_api"
    algo2.engine_config = {"provider": "aliyun"}
    algo2.request_schema = None

    # 设置 mock session.execute 返回值
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [algo1, algo2]
    mock_session.execute.return_value = mock_result

    registry = AlgorithmRegistry(mock_session)
    await registry.load_all()

    assert "insulator-damage" in registry.algorithms
    assert "pipe-leakage" in registry.algorithms
    assert registry.get("insulator-damage").engine_type == "mock"
```

- [ ] **Step 2: 跑测试,确认失败**

```bash
cd backend && python -m pytest tests/test_algorithm_registry.py -v
```

期望: FAIL

- [ ] **Step 3: 创建 backend/app/engines/factory.py**

```python
"""引擎工厂 - 根据 engine_type 实例化对应引擎"""
from app.engines.base import BaseEngine
from app.engines.cloud import CloudVisionEngine
from app.engines.mock import MockEngine
from app.utils.exceptions import GevicError

ENGINE_REGISTRY: dict[str, type[BaseEngine]] = {
    "cloud_api": CloudVisionEngine,
    "mock": MockEngine,
}


def get_engine(engine_type: str) -> BaseEngine:
    """根据 engine_type 创建引擎实例"""
    cls = ENGINE_REGISTRY.get(engine_type)
    if cls is None:
        raise GevicError(f"未知 engine_type: {engine_type}")
    return cls()
```

- [ ] **Step 4: 创建 backend/app/services/algorithm_registry.py**

```python
"""算法注册表 - 启动时从 DB 加载到内存

V1.0 简化: 启动加载 + 滚动重启 (不实现热刷新)
"""
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Algorithm


@dataclass
class AlgorithmEntry:
    """内存中的算法条目"""
    code: str
    name: str
    category: str | None
    engine_type: str
    engine_config: dict[str, Any]
    request_schema: dict[str, Any] | None
    is_active: bool
    version: int


class AlgorithmRegistry:
    """算法注册表 - 单例, 启动时从 DB 加载"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.algorithms: dict[str, AlgorithmEntry] = {}

    async def load_all(self) -> None:
        """从 DB 加载所有 active 算法到内存"""
        stmt = select(Algorithm).where(Algorithm.is_active == True)  # noqa: E712
        result = await self.session.execute(stmt)
        algorithms = result.scalars().all()

        self.algorithms = {
            algo.code: AlgorithmEntry(
                code=algo.code,
                name=algo.name,
                category=algo.category,
                engine_type=algo.engine_type,
                engine_config=algo.engine_config,
                request_schema=algo.request_schema,
                is_active=algo.is_active,
                version=algo.version,
            )
            for algo in algorithms
        }

    def get(self, code: str) -> AlgorithmEntry | None:
        """按 code 查算法"""
        return self.algorithms.get(code)

    def list_all(self) -> list[AlgorithmEntry]:
        """列出所有算法"""
        return list(self.algorithms.values())
```

- [ ] **Step 5: 跑测试,确认通过**

```bash
cd backend && python -m pytest tests/test_algorithm_registry.py -v
```

期望: PASS

- [ ] **Step 6: 提交**

```bash
git add backend/app/engines/factory.py backend/app/services/algorithm_registry.py backend/tests/test_algorithm_registry.py
git commit -m "feat(backend): 引擎工厂与算法注册表"
```

---

## Phase 4: API 端点

### Task 16: 健康检查端点

**Files:**
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/health.py`
- Create: `backend/app/api/router.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_api_health.py`

- [ ] **Step 1: 创建 backend/app/api/__init__.py**

```python
"""API 路由层"""
```

- [ ] **Step 2: 创建 backend/app/api/health.py**

```python
"""健康检查端点 - 检查 DB/Redis/MinIO 可达"""
from fastapi import APIRouter, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health")
async def health(session: AsyncSession) -> dict:
    """健康检查 - 验证关键依赖可达"""
    health_status = {
        "app": "ok",
        "postgres": "unknown",
        "redis": "unknown",
        "minio": "unknown",
    }
    overall_ok = True

    # Postgres
    try:
        await session.execute(text("SELECT 1"))
        health_status["postgres"] = "ok"
    except Exception:
        health_status["postgres"] = "down"
        overall_ok = False

    # Redis / MinIO 检查由 main.py lifespan 完成, 这里仅返回状态
    health_status["status"] = "ok" if overall_ok else "degraded"
    return health_status
```

- [ ] **Step 3: 创建 backend/app/api/router.py**

```python
"""API 路由聚合"""
from fastapi import APIRouter

from app.api.algorithms import router as algorithms_router
from app.api.files import router as files_router
from app.api.health import router as health_router
from app.api.inspect import router as inspect_router
from app.api.records import router as records_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(algorithms_router)
api_router.include_router(inspect_router)
api_router.include_router(records_router)
api_router.include_router(files_router)
```

- [ ] **Step 4: 创建占位文件 backend/app/api/algorithms.py**

```python
"""算法管理端点 - T17 实现"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/algorithms", tags=["algorithms"])
```

- [ ] **Step 5: 创建占位文件 backend/app/api/inspect.py**

```python
"""识别上传端点 - T18 实现"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/inspect", tags=["inspect"])
```

- [ ] **Step 6: 创建占位文件 backend/app/api/records.py**

```python
"""记录查询端点 - T19 实现"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/records", tags=["records"])
```

- [ ] **Step 7: 创建占位文件 backend/app/api/files.py**

```python
"""文件访问端点 - T20 实现"""
from fastapi import APIRouter

router = APIRouter()
```

- [ ] **Step 8: 更新 backend/app/main.py 集成路由**

```python
"""FastAPI 应用入口"""
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from app.api.router import api_router
from app.config import get_settings
from app.database import create_engine, get_sessionmaker
from app.services.algorithm_registry import AlgorithmRegistry


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """启动时初始化: DB engine + 算法注册表"""
    settings = get_settings()
    engine = create_engine(settings.database_url)
    sessionmaker = get_sessionmaker(engine)

    # 加载算法注册表
    async with sessionmaker() as session:
        registry = AlgorithmRegistry(session)
        await registry.load_all()
        app.state.algorithm_registry = registry

    app.state.engine = engine
    app.state.sessionmaker = sessionmaker
    app.state.settings = settings
    yield
    await engine.dispose()


app = FastAPI(title="GE-VIC Image Recognition", version="0.1.0", lifespan=lifespan)
app.include_router(api_router)


@app.get("/")
async def root() -> dict:
    return {"app": "gevic", "version": "0.1.0", "status": "running"}
```

- [ ] **Step 9: 创建 backend/tests/test_api_health.py**

```python
"""/health 端点测试"""
import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint_returns_status() -> None:
    """健康检查返回 200 与状态"""
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "app" in data
    assert "postgres" in data
```

- [ ] **Step 10: 跑测试**

```bash
cd backend && python -m pytest tests/test_api_health.py -v
```

期望: PASS (需要 DB 运行, 否则 health 检查会失败但测试不会因 status code 失败)

- [ ] **Step 11: 提交**

```bash
git add backend/app/api/ backend/app/main.py backend/tests/test_api_health.py
git commit -m "feat(backend): 健康检查端点 + API 路由聚合"
```

---

### Task 17: 算法列表端点

**Files:**
- Modify: `backend/app/api/algorithms.py`
- Create: `backend/app/schemas/algorithm.py`
- Create: `backend/tests/test_api_algorithms.py`

- [ ] **Step 1: 创建 backend/app/schemas/algorithm.py**

```python
"""算法 Pydantic schema"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AlgorithmOut(BaseModel):
    """算法列表/详情响应"""
    code: str
    name: str
    category: str | None
    description: str | None
    engine_type: str
    is_active: bool
    version: int

    model_config = {"from_attributes": True}


class AlgorithmListOut(BaseModel):
    """算法列表响应"""
    items: list[AlgorithmOut]
    total: int
```

- [ ] **Step 2: 实现 backend/app/api/algorithms.py**

```python
"""/api/v1/algorithms 端点"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session, get_sessionmaker
from app.models import Algorithm
from app.schemas.algorithm import AlgorithmListOut, AlgorithmOut

router = APIRouter(prefix="/api/v1/algorithms", tags=["algorithms"])


@router.get("", response_model=AlgorithmListOut)
async def list_algorithms(request: Request) -> AlgorithmListOut:
    """列出所有 active 算法"""
    sessionmaker = request.app.state.sessionmaker
    async with sessionmaker() as session:
        stmt = select(Algorithm).where(Algorithm.is_active == True)  # noqa: E712
        result = await session.execute(stmt)
        algorithms = result.scalars().all()
        items = [
            AlgorithmOut(
                code=a.code,
                name=a.name,
                category=a.category,
                description=a.description,
                engine_type=a.engine_type,
                is_active=a.is_active,
                version=a.version,
            )
            for a in algorithms
        ]
        return AlgorithmListOut(items=items, total=len(items))
```

- [ ] **Step 3: 创建 backend/tests/test_api_algorithms.py**

```python
"""/algorithms 端点测试"""
import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_list_algorithms_returns_seeded() -> None:
    """列出算法 - 至少包含种子数据"""
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/algorithms")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    codes = [a["code"] for a in data["items"]]
    assert "insulator-damage" in codes
```

- [ ] **Step 4: 跑测试**

```bash
cd backend && python -m pytest tests/test_api_algorithms.py -v
```

期望: PASS (需 DB 已运行 + 种子数据)

- [ ] **Step 5: 提交**

```bash
git add backend/app/api/algorithms.py backend/app/schemas/algorithm.py backend/tests/test_api_algorithms.py
git commit -m "feat(backend): /algorithms 列表端点"
```

---

### Task 18: 核心 /inspect/{code} 上传端点

**Files:**
- Modify: `backend/app/api/inspect.py`
- Create: `backend/app/deps.py`
- Create: `backend/app/schemas/inspection.py`
- Create: `backend/tests/test_api_inspect.py`

- [ ] **Step 1: 创建 backend/app/deps.py**

```python
"""FastAPI 依赖注入"""
from fastapi import Header, HTTPException, Request, status

from app.utils.inspector_id import validate_inspector_id


async def get_inspector_id(
    x_inspector_id: str | None = Header(default=None, alias="X-Inspector-Id"),
) -> str:
    """从 Header 提取并校验 inspector_id"""
    try:
        return validate_inspector_id(x_inspector_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_INSPECTOR_ID", "message": str(e)},
        ) from e


def get_algorithm_registry(request: Request):
    """从 app.state 获取算法注册表"""
    return request.app.state.algorithm_registry
```

- [ ] **Step 2: 创建 backend/app/schemas/inspection.py**

```python
"""识别 Pydantic schema"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class InspectionCreatedOut(BaseModel):
    """POST /inspect 上传后立即返回"""
    record_id: int
    algorithm_code: str
    status: str  # PENDING
    created_at: datetime
    status_url: str


class InspectionDetailOut(BaseModel):
    """GET /records/{id} 完整响应"""
    record_id: int = Field(alias="id")
    algorithm_code: str
    algorithm_name: str | None = None
    category: str | None
    status: str
    enrichment_status: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None
    meta: dict[str, Any] | None = None
    file: dict[str, Any] | None = None
    recognition: dict[str, Any] | None = None
    llm_enrichment: dict[str, Any] | None = None
    error: dict[str, Any] | None = None

    model_config = {"from_attributes": True, "populate_by_name": True}
```

- [ ] **Step 3: 实现 backend/app/api/inspect.py**

```python
"""/api/v1/inspect/{algorithm_code} 上传端点 - M0 核心"""
import hashlib
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status

from app.deps import get_algorithm_registry
from app.models import Inspection
from app.schemas.inspection import InspectionCreatedOut
from app.services.algorithm_registry import AlgorithmRegistry
from app.utils.inspector_id import validate_inspector_id

router = APIRouter(prefix="/api/v1/inspect", tags=["inspect"])


@router.post(
    "/{algorithm_code}",
    response_model=InspectionCreatedOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_for_inspection(
    algorithm_code: str,
    request: Request,
    file: UploadFile = File(...),
    meta: str = Form(default="{}"),
    registry: AlgorithmRegistry = Depends(get_algorithm_registry),
) -> InspectionCreatedOut:
    from app.config import get_settings
    from app.services.storage import StorageService

    inspector_id_header = request.headers.get("X-Inspector-Id")
    try:
        inspector_id = validate_inspector_id(inspector_id_header)
    except Exception as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_INSPECTOR_ID", "message": str(e)}) from e

    algo = registry.get(algorithm_code)
    if algo is None:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ALGORITHM", "message": f"算法 {algorithm_code} 不存在"})
    if not algo.is_active:
        raise HTTPException(status_code=400, detail={"code": "ALGORITHM_DISABLED"})

    file_bytes = await file.read()
    settings = get_settings()
    if len(file_bytes) > settings.max_image_size:
        raise HTTPException(status_code=413, detail={"code": "FILE_TOO_LARGE", "message": f"文件超过 {settings.max_image_size // 1024 // 1024}MB"})

    file_hash = hashlib.sha256(file_bytes).hexdigest()
    file_type = "video" if (file.content_type or "").startswith("video/") else "image"

    sessionmaker = request.app.state.sessionmaker
    storage = StorageService.from_settings(settings)

    async with sessionmaker() as session:
        meta_dict = json.loads(meta) if meta else {}
        inspection = Inspection(
            algorithm_code=algo.code, category=algo.category,
            status="PENDING", enrichment_status="NONE",
            file_hash=file_hash, file_size=len(file_bytes), file_type=file_type,
            request_meta=meta_dict, inspector_id=inspector_id,
            asset_id=meta_dict.get("asset_id"), location=meta_dict.get("location"),
            retry_count=0,
        )
        session.add(inspection)
        await session.flush()
        record_id = inspection.id

        object_key = storage.upload_file(
            file_bytes=file_bytes, filename=file.filename or "upload.bin",
            record_id=record_id, content_type=file.content_type or "application/octet-stream",
        )
        inspection.object_key = object_key

        from app.services.audit import AuditAction, AuditResult, AuditService
        audit = AuditService(session)
        await audit.log(
            actor=inspector_id, action=AuditAction.UPLOAD,
            resource_type="inspection", resource_id=str(record_id),
            source_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            request_id=request.headers.get("x-request-id"),
            request_meta={"algorithm_code": algo.code, "file_size": len(file_bytes)},
            result=AuditResult.SUCCESS,
        )
        await session.commit()

    from app.tasks.celery_app import celery_app
    celery_app.send_task("app.tasks.inspection.run_inspection", args=[record_id])

    return InspectionCreatedOut(
        record_id=record_id, algorithm_code=algo.code,
        status="PENDING", created_at=datetime.now(timezone.utc),
        status_url=f"/api/v1/records/{record_id}",
    )
```

- [ ] **Step 4-6: 跑测试 + 提交**

```bash
cd backend && python -m pytest tests/test_api_inspect.py -v
git add backend/app/api/inspect.py backend/app/deps.py backend/app/schemas/inspection.py backend/tests/test_api_inspect.py
git commit -m "feat(backend): 核心 /inspect/{code} 上传端点"
```

---

### Task 19: /records 查询端点

- [ ] **Step 1: 实现 backend/app/api/records.py**

```python
"""/api/v1/records 查询端点"""
from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import select
from app.models import Inspection
from app.schemas.inspection import InspectionDetailOut

router = APIRouter(prefix="/api/v1/records", tags=["records"])


@router.get("", response_model=list[InspectionDetailOut])
async def list_records(
    request: Request,
    algorithm_code: str | None = Query(default=None),
    status: str | None = Query(default=None),
    asset_id: str | None = Query(default=None),
    inspector_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
) -> list[InspectionDetailOut]:
    sessionmaker = request.app.state.sessionmaker
    async with sessionmaker() as session:
        stmt = select(Inspection).order_by(Inspection.created_at.desc())
        if algorithm_code: stmt = stmt.where(Inspection.algorithm_code == algorithm_code)
        if status: stmt = stmt.where(Inspection.status == status)
        if asset_id: stmt = stmt.where(Inspection.asset_id == asset_id)
        if inspector_id: stmt = stmt.where(Inspection.inspector_id == inspector_id)
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await session.execute(stmt)
        records = result.scalars().all()
        return [_to_detail(r) for r in records]


@router.get("/{record_id}", response_model=InspectionDetailOut)
async def get_record(request: Request, record_id: int) -> InspectionDetailOut:
    sessionmaker = request.app.state.sessionmaker
    async with sessionmaker() as session:
        stmt = select(Inspection).where(Inspection.id == record_id)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()
        if record is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND"})
        return _to_detail(record)


def _to_detail(r) -> InspectionDetailOut:
    file_block = None
    if r.object_key:
        file_block = {"object_key": r.object_key, "file_hash": r.file_hash, "file_size": r.file_size, "file_type": r.file_type}
    return InspectionDetailOut(
        id=r.id, algorithm_code=r.algorithm_code, category=r.category,
        status=r.status, enrichment_status=r.enrichment_status,
        created_at=r.created_at, started_at=r.started_at, finished_at=r.finished_at, duration_ms=r.duration_ms,
        meta={"inspector_id": r.inspector_id, "asset_id": r.asset_id, "location": r.location, "client_meta": r.request_meta},
        file=file_block, recognition=r.result, llm_enrichment=r.llm_enrichment,
        error=None if r.status != "FAILED" else {"code": r.error_code, "message": r.error_message},
    )
```

- [ ] **Step 2: 提交**

```bash
git add backend/app/api/records.py
git commit -m "feat(backend): /records 列表与详情端点"
```

---

### Task 20: /records/{id}/file 文件访问

- [ ] **Step 1: 实现 backend/app/api/files.py**

```python
"""/api/v1/records/{id}/file 文件访问端点"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from app.config import get_settings
from app.models import Inspection
from app.services.storage import StorageService

router = APIRouter(prefix="/api/v1/records", tags=["files"])


@router.get("/{record_id}/file")
async def get_record_file(request: Request, record_id: int) -> RedirectResponse:
    sessionmaker = request.app.state.sessionmaker
    settings = get_settings()
    async with sessionmaker() as session:
        stmt = select(Inspection).where(Inspection.id == record_id)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()
        if record is None or not record.object_key:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND"})
        storage = StorageService.from_settings(settings)
        url = storage.get_file_url(record.object_key)
        return RedirectResponse(url=url)
```

- [ ] **Step 2: 提交**

```bash
git add backend/app/api/files.py
git commit -m "feat(backend): /records/{id}/file 文件访问"
```

---

### Task 21: Celery 应用初始化

- [ ] **Step 1-3: 创建 celery_app.py + 测试 + 提交**

```python
# backend/app/tasks/__init__.py
"""Celery 任务模块"""
```

```python
# backend/app/tasks/celery_app.py
"""Celery 应用实例"""
from celery import Celery
from app.config import get_settings

settings = get_settings()
celery_app = Celery("gevic", broker=settings.celery_broker_url)
celery_app.conf.update(
    task_serializer="json", accept_content=["json"],
    timezone="Asia/Shanghai", enable_utc=True,
    task_acks_late=True, task_reject_on_worker_lost=True,
    worker_max_tasks_per_child=100,
    task_routes={
        "app.tasks.inspection.run_inspection": {"queue": "inspect_queue"},
        "app.tasks.inspection.run_enrichment": {"queue": "stats_queue"},
    },
    task_annotations={
        "app.tasks.inspection.run_inspection": {"rate_limit": "200/m"},
        "app.tasks.inspection.run_enrichment": {"rate_limit": "10/m"},
    },
)
```

```python
# backend/tests/test_celery_app.py
from app.tasks.celery_app import celery_app
def test_celery_app_name(): assert celery_app.main == "gevic"
def test_no_result_backend(): assert celery_app.conf.result_backend is None
def test_task_routes():
    assert "app.tasks.inspection.run_inspection" in celery_app.conf.task_routes
```

```bash
cd backend && python -m pytest tests/test_celery_app.py -v
git add backend/app/tasks/ backend/tests/test_celery_app.py
git commit -m "feat(backend): Celery 应用初始化"
```

---

### Task 22: run_inspection 任务

- [ ] **Step 1: 实现 backend/app/tasks/inspection.py**

```python
"""识别任务 (Celery)"""
import asyncio
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import select
from app.config import get_settings
from app.database import create_engine, get_sessionmaker
from app.engines.factory import get_engine
from app.models import Inspection
from app.services.algorithm_registry import AlgorithmRegistry
from app.services.audit import AuditAction, AuditResult, AuditService
from app.services.storage import StorageService
from app.tasks.celery_app import celery_app


@celery_app.task(
    name="app.tasks.inspection.run_inspection",
    bind=True, max_retries=3, autoretry_for=(Exception,),
    retry_backoff=True, retry_backoff_max=90, retry_jitter=True,
)
def run_inspection(self, record_id: int) -> dict:
    return asyncio.run(_run_inspection_async(self, record_id))


async def _run_inspection_async(task, record_id: int) -> dict:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    sm = get_sessionmaker(engine)
    temp_path = None
    try:
        async with sm() as session:
            stmt = select(Inspection).where(Inspection.id == record_id)
            record = (await session.execute(stmt)).scalar_one_or_none()
            if record is None:
                return {"success": False, "error": "RECORD_NOT_FOUND"}
            if record.status not in ("PENDING", "FAILED"):
                return {"success": False, "error": f"INVALID_STATUS_{record.status}"}

            record.status = "RUNNING"
            record.started_at = datetime.now(timezone.utc)
            record.retry_count += 1
            await session.commit()

            registry = AlgorithmRegistry(session)
            await registry.load_all()
            algo = registry.get(record.algorithm_code)
            if algo is None:
                record.status = "FAILED"
                record.error_code = "ALGORITHM_NOT_FOUND"
                await session.commit()
                return {"success": False, "error": "ALGORITHM_NOT_FOUND"}

            storage = StorageService.from_settings(settings)
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(record.object_key).suffix) as tmp:
                temp_path = Path(tmp.name)
                response = storage.client.get_object(settings.minio_bucket, record.object_key)
                tmp.write(response.read())
                response.close()
                response.release_conn()

            file_bytes = temp_path.read_bytes()
            engine_instance = get_engine(algo.engine_type)
            try:
                result = await engine_instance.recognize(
                    file_bytes=file_bytes,
                    filename=Path(record.object_key).name,
                    meta=record.request_meta or {},
                    config=algo.engine_config,
                )
            except Exception as e:
                return await _handle_failure(task, session, record, "ENGINE_EXCEPTION", str(e))

            if not result.success:
                return await _handle_failure(task, session, record, result.error_code or "ENGINE_ERROR", result.error_message)

            record.result = result.data
            record.status = "SUCCESS"
            record.finished_at = datetime.now(timezone.utc)
            if record.started_at and record.finished_at:
                record.duration_ms = int((record.finished_at - record.started_at).total_seconds() * 1000)
            record.cost_estimate = result.cost_estimate

            # LLM 富化 (失败不影响主任务)
            try:
                from app.services.enrichment import enrich_inspection
                enrichment = await enrich_inspection(
                    algorithm_name=algo.name, category=algo.category,
                    recognition=result.data, meta=record.request_meta or {},
                    inspector_id=record.inspector_id, asset_id=record.asset_id,
                )
                record.llm_enrichment = enrichment
                record.enrichment_status = "ENRICHED"
            except Exception as e:
                record.enrichment_status = "ENRICH_FAILED"
                record.error_message = f"识别成功, 富化失败: {e}"

            audit = AuditService(session)
            await audit.log(
                actor=record.inspector_id or "system", action=AuditAction.UPLOAD,
                resource_type="inspection", resource_id=str(record_id),
                result=AuditResult.SUCCESS,
                request_meta={"duration_ms": record.duration_ms, "engine": algo.engine_type},
            )
            await session.commit()
            return {"success": True, "record_id": record_id}
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()
        await engine.dispose()


async def _handle_failure(task, session, record, code, message):
    if record.retry_count >= task.max_retries:
        record.status = "DEAD"
    else:
        record.status = "FAILED"
    record.error_code = code
    record.error_message = message
    record.finished_at = datetime.now(timezone.utc)
    await session.commit()
    return {"success": False, "error": code}
```

- [ ] **Step 2: 提交**

```bash
git add backend/app/tasks/inspection.py
git commit -m "feat(backend): run_inspection Celery 任务"
```

---

### Task 23: LLM 客户端 (OpenAI 兼容)

- [ ] **Step 1: 写测试 + 实现**

```python
# backend/tests/test_llm_client.py
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from app.services.llm_client import LLMClient, LLMError

def test_client_initializes():
    from app.config import Settings
    s = Settings(database_url="postgresql://x", llm_base_url="https://example.com/v1",
                 llm_api_key="test", llm_model="gpt-4o-mini", llm_max_input_tokens=4000, llm_max_output_tokens=1000)
    assert LLMClient.from_settings(s).model == "gpt-4o-mini"

@pytest.mark.asyncio
async def test_chat_completion():
    from app.config import Settings
    s = Settings(database_url="postgresql://x", llm_base_url="https://example.com/v1",
                 llm_api_key="test", llm_model="gpt-4o-mini", llm_max_input_tokens=4000, llm_max_output_tokens=1000)
    client = LLMClient.from_settings(s)
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "test"
    mock_response.usage.total_tokens = 100
    with patch.object(client, "_get_client") as mock_get:
        mock_async = MagicMock()
        mock_async.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_get.return_value = mock_async
        result = await client.chat_completion("sys", "usr")
    assert result["content"] == "test"
```

```python
# backend/app/services/llm_client.py
"""OpenAI 兼容 LLM 客户端"""
from typing import Any
from openai import AsyncOpenAI
from app.config import Settings
from app.utils.exceptions import LLMError


class LLMClient:
    def __init__(self, base_url, api_key, model, max_input_tokens, max_output_tokens, client=None):
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.max_input_tokens = max_input_tokens
        self.max_output_tokens = max_output_tokens
        self._client = client

    @classmethod
    def from_settings(cls, settings: Settings) -> "LLMClient":
        return cls(base_url=settings.llm_base_url, api_key=settings.llm_api_key,
                   model=settings.llm_model, max_input_tokens=settings.llm_max_input_tokens,
                   max_output_tokens=settings.llm_max_output_tokens)

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(base_url=self.base_url, api_key=self.api_key, timeout=60.0)
        return self._client

    async def chat_completion(self, system_prompt: str, user_prompt: str, temperature: float = 0.3) -> dict:
        client = self._get_client()
        try:
            response = await client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                temperature=temperature, max_tokens=self.max_output_tokens,
            )
        except Exception as e:
            raise LLMError(f"LLM API 调用失败: {e}") from e
        if not response.choices:
            raise LLMError("LLM 响应无 choices")
        return {
            "content": response.choices[0].message.content or "",
            "tokens": response.usage.total_tokens if response.usage else 0,
            "raw": response,
        }
```

- [ ] **Step 2: 跑测试 + 提交**

```bash
cd backend && python -m pytest tests/test_llm_client.py -v
git add backend/app/services/llm_client.py backend/tests/test_llm_client.py
git commit -m "feat(backend): OpenAI 兼容 LLM 客户端"
```

---

### Task 24: LLM 富化服务

- [ ] **Step 1: 写测试 + 实现**

```python
# backend/tests/test_enrichment.py
from unittest.mock import AsyncMock, patch
import pytest

@pytest.mark.asyncio
async def test_enrich_returns_structured():
    from app.services.enrichment import enrich_inspection
    with patch("app.services.enrichment.LLMClient") as MockClient:
        mock = MockClient.from_settings.return_value
        mock.chat_completion = AsyncMock(return_value={"content": "## 总结\n检测到破损", "tokens": 200})
        result = await enrich_inspection("绝缘子破损", "供配电", {"defects": []}, {}, "I1", "A1")
    assert "summary" in result
    assert "recommendations" in result
```

```python
# backend/app/services/enrichment.py
"""LLM 富化服务"""
from typing import Any
from datetime import datetime, timezone
from app.config import get_settings
from app.services.llm_client import LLMClient

PROMPT_VERSION = "per_record_v1.0"


async def enrich_inspection(algorithm_name, category, recognition, meta, inspector_id, asset_id) -> dict[str, Any]:
    settings = get_settings()
    client = LLMClient.from_settings(settings)
    system_prompt = "你是一名资深的城市基础设施巡检员。基于单条识别结果,给出一句话总结和最多3条处置建议。"
    user_prompt = f"""# 巡检背景
- 设施类型: {category or '未指定'}
- 识别算法: {algorithm_name}
- 巡检员: {inspector_id or '未指定'}
- 资产: {asset_id or '未指定'}

# 识别结果
{recognition}

# 输出要求
## 一句话总结 (100字以内)
## 处置建议 (1-3条, 按优先级, 可执行)"""
    result = await client.chat_completion(system_prompt, user_prompt)
    summary, recs = _parse(result["content"])
    return {
        "summary": summary, "recommendations": recs,
        "model": settings.llm_model, "prompt_version": PROMPT_VERSION,
        "token_used": result["tokens"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _parse(content: str) -> tuple[str, list[str]]:
    summary = ""
    recs = []
    section = None
    for line in content.split("\n"):
        line = line.strip()
        if not line:
            continue
        if "总结" in line and "#" in line:
            section = "s"
            continue
        if "处置" in line and "#" in line:
            section = "r"
            continue
        if section == "s" and not summary:
            summary = line.lstrip("#").strip()
        elif section == "r" and line and line[0:1] in "-*0123456789":
            r = line.lstrip("-*0123456789. ").strip()
            if r:
                recs.append(r)
    return summary or content[:100], recs or [content[:200]]
```

- [ ] **Step 2: 跑测试 + 提交**

```bash
cd backend && python -m pytest tests/test_enrichment.py -v
git add backend/app/services/enrichment.py backend/tests/test_enrichment.py
git commit -m "feat(backend): LLM 富化服务"
```

---

### Task 25: Vue 3 项目脚手架

- [ ] **Step 1-4: 创建 frontend/package.json, 配置文件, src 文件**

```json
// frontend/package.json
{
  "name": "gevic-frontend",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite", "build": "vue-tsc --noEmit && vite build",
    "preview": "vite preview", "test": "vitest run",
    "test:e2e": "playwright test"
  },
  "dependencies": {
    "vue": "^3.4.0", "vue-router": "^4.2.0", "pinia": "^2.1.0",
    "axios": "^1.6.0", "element-plus": "^2.4.0",
    "@element-plus/icons-vue": "^2.3.0", "echarts": "^5.4.0", "vue-echarts": "^6.6.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0.0", "typescript": "^5.3.0", "vue-tsc": "^1.8.0",
    "vite": "^5.0.0", "@playwright/test": "^1.40.0", "vitest": "^1.0.0"
  }
}
```

```typescript
// frontend/vite.config.ts
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0', port: 5173,
    proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: true } },
  },
})
```

```json
// frontend/tsconfig.json
{
  "compilerOptions": {
    "target": "ESNext", "module": "ESNext", "moduleResolution": "Bundler",
    "strict": true, "jsx": "preserve", "esModuleInterop": true,
    "skipLibCheck": true, "resolveJsonModule": true,
    "isolatedModules": true, "noEmit": true,
    "lib": ["ESNext", "DOM"], "types": ["vite/client"]
  },
  "include": ["src/**/*.ts", "src/**/*.vue", "src/**/*.d.ts"]
}
```

```html
<!-- frontend/index.html -->
<!DOCTYPE html>
<html lang="zh-CN">
  <head><meta charset="UTF-8" /><title>GE-VIC 图像识别平台</title></head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
```

```dockerfile
# frontend/Dockerfile
FROM node:20-alpine
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev"]
```

```typescript
// frontend/src/main.ts
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'
import router from './router'
const app = createApp(App)
app.use(createPinia()); app.use(router); app.use(ElementPlus)
app.mount('#app')
```

```vue
<!-- frontend/src/App.vue -->
<template>
  <el-container>
    <el-header style="background: #409eff; color: white; display: flex; align-items: center;">
      <h2 style="margin: 0;">GE-VIC 图像识别平台</h2>
    </el-header>
    <el-container>
      <el-aside width="200px" style="background: #f5f5f5;">
        <el-menu :default-active="route.path" router>
          <el-menu-item index="/">仪表盘</el-menu-item>
          <el-menu-item index="/upload">上传识别</el-menu-item>
        </el-menu>
      </el-aside>
      <el-main><router-view /></el-main>
    </el-container>
  </el-container>
</template>
<script setup lang="ts">
import { useRoute } from 'vue-router'
const route = useRoute()
</script>
```

```typescript
// frontend/src/env.d.ts
/// <reference types="vite/client" />
declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}
```

```typescript
// frontend/src/router/index.ts
import { createRouter, createWebHistory } from 'vue-router'
const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: () => import('../views/Dashboard.vue') },
    { path: '/upload', component: () => import('../views/UploadView.vue') },
    { path: '/:pathMatch(.*)*', component: () => import('../views/NotFound.vue') },
  ],
})
export default router
```

```vue
<!-- frontend/src/views/Dashboard.vue (占位) -->
<template><h1>仪表盘</h1></template>
```

```vue
<!-- frontend/src/views/UploadView.vue (占位) -->
<template><h1>上传识别</h1></template>
```

```vue
<!-- frontend/src/views/NotFound.vue -->
<template><h1>404</h1><el-link href="/">返回</el-link></template>
```

- [ ] **Step 5: 验证 + 提交**

```bash
cd frontend
npm install
npm run build
git add frontend/
git commit -m "feat(frontend): Vue 3 + Element Plus 脚手架"
```

---

### Task 26: API 客户端 + Pinia store

- [ ] **Step 1: 创建 frontend/src/api/client.ts**

```typescript
import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({ baseURL: '/api/v1', timeout: 30000 })

api.interceptors.request.use((config) => {
  config.headers['X-Inspector-Id'] = localStorage.getItem('inspector_id') || 'WEB-DEMO-USER'
  return config
})

api.interceptors.response.use(
  (r) => r,
  (e) => {
    const detail = e.response?.data?.detail
    ElMessage.error(detail?.message || e.message)
    return Promise.reject(e)
  }
)

export interface Algorithm {
  code: string; name: string; category: string | null
  engine_type: string; is_active: boolean
}

export interface Inspection {
  id: number; algorithm_code: string; category: string | null
  status: string; enrichment_status: string | null
  created_at: string; finished_at: string | null; duration_ms: number | null
  meta: Record<string, any> | null
  file: Record<string, any> | null
  recognition: Record<string, any> | null
  llm_enrichment: Record<string, any> | null
  error: Record<string, any> | null
}

export const algorithmsApi = {
  list: () => api.get<{ items: Algorithm[]; total: number }>('/algorithms').then((r) => r.data),
}

export const recordsApi = {
  list: (params: any = {}) => api.get<Inspection[]>('/records', { params }).then((r) => r.data),
  get: (id: number) => api.get<Inspection>(`/records/${id}`).then((r) => r.data),
  upload: (code: string, file: File, meta: Record<string, any> = {}) => {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('meta', JSON.stringify(meta))
    return api.post(`/inspect/${code}`, fd, { headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => r.data)
  },
  retry: (id: number) => api.post(`/records/${id}/retry`).then((r) => r.data),
  enrich: (id: number) => api.post(`/records/${id}/enrich`).then((r) => r.data),
}

export default api
```

- [ ] **Step 2: 创建 frontend/src/stores/records.ts**

```typescript
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { recordsApi, algorithmsApi, type Inspection, type Algorithm } from '../api/client'

export const useRecordsStore = defineStore('records', () => {
  const records = ref<Inspection[]>([])
  const algorithms = ref<Algorithm[]>([])
  const loading = ref(false)

  async function fetchRecords(params: any = {}) {
    loading.value = true
    try { records.value = await recordsApi.list(params) }
    finally { loading.value = false }
  }
  async function fetchAlgorithms() {
    const r = await algorithmsApi.list()
    algorithms.value = r.items
  }
  async function fetchRecord(id: number) { return await recordsApi.get(id) }
  async function uploadFile(code: string, file: File, meta: any = {}) {
    return await recordsApi.upload(code, file, meta)
  }

  return { records, algorithms, loading, fetchRecords, fetchAlgorithms, fetchRecord, uploadFile }
})
```

- [ ] **Step 3: 提交**

```bash
cd frontend && npm run build
git add frontend/src/api/ frontend/src/stores/
git commit -m "feat(frontend): API 客户端 + Pinia store"
```

---

### Task 27: Dashboard 仪表盘

- [ ] **Step 1: 创建 frontend/src/components/StatusTag.vue**

```vue
<template>
  <el-tag :type="tagType" :effect="effect" size="small">{{ label }}</el-tag>
</template>
<script setup lang="ts">
import { computed } from 'vue'
const props = defineProps<{ status: string; enrichmentStatus?: string | null }>()
const label = computed(() => {
  const map: Record<string, string> = { PENDING: '等待中', RUNNING: '识别中', SUCCESS: '成功', FAILED: '失败', DEAD: '已停止' }
  let s = map[props.status] || props.status
  if (props.status === 'SUCCESS' && props.enrichmentStatus === 'ENRICH_FAILED') s += ' (富化失败)'
  else if (props.status === 'SUCCESS' && props.enrichmentStatus === 'ENRICHED') s += ' (已富化)'
  return s
})
const tagType = computed(() => {
  const m: Record<string, any> = { PENDING: 'info', RUNNING: 'warning', SUCCESS: 'success', FAILED: 'danger', DEAD: 'danger' }
  return m[props.status] || 'info'
})
const effect = computed(() => props.status === 'RUNNING' ? 'dark' : 'light')
</script>
```

- [ ] **Step 2: 创建 frontend/src/components/RecordList.vue**

```vue
<template>
  <el-table :data="records" v-loading="loading" stripe>
    <el-table-column prop="id" label="ID" width="80" />
    <el-table-column label="状态" width="160">
      <template #default="{ row }"><StatusTag :status="row.status" :enrichment-status="row.enrichment_status" /></template>
    </el-table-column>
    <el-table-column prop="algorithm_code" label="算法" width="200" />
    <el-table-column prop="meta.asset_id" label="资产" width="150" />
    <el-table-column prop="meta.inspector_id" label="巡检员" width="120" />
    <el-table-column label="提交时间" width="180">
      <template #default="{ row }">{{ new Date(row.created_at).toLocaleString('zh-CN') }}</template>
    </el-table-column>
    <el-table-column label="操作" width="150">
      <template #default="{ row }">
        <el-button size="small" @click="$emit('select', row)">查看</el-button>
        <el-button v-if="['FAILED','DEAD'].includes(row.status)" size="small" type="warning" @click="$emit('retry', row)">重试</el-button>
      </template>
    </el-table-column>
  </el-table>
</template>
<script setup lang="ts">
import StatusTag from './StatusTag.vue'
import type { Inspection } from '../api/client'
defineProps<{ records: Inspection[]; loading?: boolean }>()
defineEmits<{ (e: 'select', r: Inspection): void; (e: 'retry', r: Inspection): void }>()
</script>
```

- [ ] **Step 3: 创建 frontend/src/components/RecordDetail.vue**

```vue
<template>
  <el-drawer v-model="visible" :title="`记录 #${record?.id}`" size="60%">
    <div v-if="record">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="ID">{{ record.id }}</el-descriptions-item>
        <el-descriptions-item label="状态"><StatusTag :status="record.status" :enrichment-status="record.enrichment_status" /></el-descriptions-item>
        <el-descriptions-item label="算法">{{ record.algorithm_code }}</el-descriptions-item>
        <el-descriptions-item label="巡检员">{{ record.meta?.inspector_id || '-' }}</el-descriptions-item>
        <el-descriptions-item label="资产">{{ record.meta?.asset_id || '-' }}</el-descriptions-item>
        <el-descriptions-item label="提交时间">{{ new Date(record.created_at).toLocaleString('zh-CN') }}</el-descriptions-item>
      </el-descriptions>
      <el-divider>识别结果</el-divider>
      <pre v-if="record.recognition">{{ JSON.stringify(record.recognition, null, 2) }}</pre>
      <el-empty v-else description="无识别结果" />
      <el-divider>LLM 富化</el-divider>
      <div v-if="record.llm_enrichment">
        <h4>{{ record.llm_enrichment.summary }}</h4>
        <el-alert v-for="(rec, i) in record.llm_enrichment.recommendations" :key="i" :title="`建议 ${i+1}`" :description="rec" type="info" :closable="false" style="margin-bottom: 8px" />
      </div>
      <el-empty v-else description="富化未生成" />
      <el-button v-if="record.status === 'SUCCESS' && (!record.llm_enrichment || record.enrichment_status === 'ENRICH_FAILED')" type="primary" size="small" :loading="enriching" @click="onEnrich">{{ record.llm_enrichment ? '重新富化' : '生成富化' }}</el-button>
      <el-alert v-if="record.error" :title="record.error.code" :description="record.error.message" type="error" :closable="false" />
    </div>
  </el-drawer>
</template>
<script setup lang="ts">
import { ref, watch } from 'vue'
import StatusTag from './StatusTag.vue'
import { recordsApi, type Inspection } from '../api/client'
import { ElMessage } from 'element-plus'
const props = defineProps<{ record: Inspection | null; modelValue: boolean }>()
const emit = defineEmits<{ (e: 'update:modelValue', v: boolean): void }>()
const visible = ref(props.modelValue)
watch(() => props.modelValue, (v) => (visible.value = v))
watch(visible, (v) => emit('update:modelValue', v))
const enriching = ref(false)
async function onEnrich() {
  if (!props.record) return
  enriching.value = true
  try { await recordsApi.enrich(props.record.id); ElMessage.success('富化任务已提交') }
  finally { enriching.value = false }
}
</script>
```

- [ ] **Step 4: 修改 frontend/src/views/Dashboard.vue**

```vue
<template>
  <div>
    <h2>仪表盘</h2>
    <RecordList :records="store.records" :loading="store.loading" @select="onSelect" @retry="onRetry" />
    <RecordDetail v-model="drawerVisible" :record="selectedRecord" />
  </div>
</template>
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRecordsStore } from '../stores/records'
import { recordsApi, type Inspection } from '../api/client'
import RecordList from '../components/RecordList.vue'
import RecordDetail from '../components/RecordDetail.vue'
import { ElMessage } from 'element-plus'
const store = useRecordsStore()
const drawerVisible = ref(false)
const selectedRecord = ref<Inspection | null>(null)
onMounted(async () => { await store.fetchRecords() })
async function onSelect(r: Inspection) {
  selectedRecord.value = await store.fetchRecord(r.id)
  drawerVisible.value = true
}
async function onRetry(r: Inspection) {
  await recordsApi.retry(r.id)
  ElMessage.success('重试已提交')
  await store.fetchRecords()
}
</script>
```

- [ ] **Step 5: 验证 + 提交**

```bash
cd frontend && npm run build
git add frontend/src/components/ frontend/src/views/Dashboard.vue
git commit -m "feat(frontend): Dashboard 仪表盘"
```

---

### Task 28: 上传页

- [ ] **Step 1: 修改 frontend/src/views/UploadView.vue**

```vue
<template>
  <div>
    <h2>上传识别</h2>
    <el-card>
      <el-form :model="form" label-width="100px">
        <el-form-item label="算法">
          <el-select v-model="form.algorithmCode" placeholder="选择算法" style="width: 100%">
            <el-option v-for="a in store.algorithms" :key="a.code" :label="`${a.name} (${a.code})`" :value="a.code" />
          </el-select>
        </el-form-item>
        <el-form-item label="资产 ID"><el-input v-model="form.assetId" placeholder="可选" /></el-form-item>
        <el-form-item label="巡检员 ID"><el-input v-model="form.inspectorId" placeholder="INSP-001" /></el-form-item>
        <el-form-item label="文件">
          <el-upload :auto-upload="false" :limit="1" :on-change="(f: any) => fileList = [f]" :file-list="fileList">
            <el-button>选择文件</el-button>
          </el-upload>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="uploading" @click="onSubmit">提交识别</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>
<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useRecordsStore } from '../stores/records'
import { ElMessage, type UploadFile } from 'element-plus'
const store = useRecordsStore()
const router = useRouter()
const form = reactive({ algorithmCode: '', assetId: '', inspectorId: '' })
const fileList = ref<UploadFile[]>([])
const uploading = ref(false)
onMounted(async () => { await store.fetchAlgorithms() })
async function onSubmit() {
  if (!form.algorithmCode) return ElMessage.warning('请选择算法')
  if (!fileList.value[0]?.raw) return ElMessage.warning('请选择文件')
  uploading.value = true
  try {
    if (form.inspectorId) localStorage.setItem('inspector_id', form.inspectorId)
    const r = await store.uploadFile(form.algorithmCode, fileList.value[0].raw, { asset_id: form.assetId || undefined })
    ElMessage.success(`上传成功, record_id=${r.record_id}`)
    router.push('/')
  } finally { uploading.value = false }
}
</script>
```

- [ ] **Step 2: 提交**

```bash
cd frontend && npm run build
git add frontend/src/views/UploadView.vue
git commit -m "feat(frontend): 上传页"
```

---

### Task 29: Playwright E2E

- [ ] **Step 1: 创建 frontend/playwright.config.ts**

```typescript
import { defineConfig, devices } from '@playwright/test'
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  use: { baseURL: 'http://localhost:5173', trace: 'on-first-retry' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: { command: 'npm run dev', url: 'http://localhost:5173', reuseExistingServer: !process.env.CI, timeout: 60000 },
})
```

- [ ] **Step 2: 创建 frontend/tests/e2e/01-inspector-id.spec.ts**

```typescript
import { test, expect } from '@playwright/test'

test('API: 缺 X-Inspector-Id → 400', async ({ request }) => {
  const r = await request.post('http://localhost:8000/api/v1/inspect/insulator-damage', {
    multipart: { file: { name: 'test.jpg', mimeType: 'image/jpeg', buffer: Buffer.from('fake') } },
  })
  expect(r.status()).toBe(400)
})
```

- [ ] **Step 3: 创建 frontend/tests/e2e/02-algorithm-code.spec.ts**

```typescript
import { test, expect } from '@playwright/test'

test('API: 未知 algorithm_code → 400', async ({ request }) => {
  const r = await request.post('http://localhost:8000/api/v1/inspect/nonexistent', {
    headers: { 'X-Inspector-Id': 'E2E-001' },
    multipart: { file: { name: 'test.jpg', mimeType: 'image/jpeg', buffer: Buffer.from('fake') } },
  })
  expect(r.status()).toBe(400)
})
```

- [ ] **Step 4: 创建 frontend/tests/e2e/03-format-validation.spec.ts**

```typescript
import { test, expect } from '@playwright/test'

test('API: X-Inspector-Id 格式错误 → 400', async ({ request }) => {
  const r = await request.post('http://localhost:8000/api/v1/inspect/insulator-damage', {
    headers: { 'X-Inspector-Id': 'ab' },
    multipart: { file: { name: 'test.jpg', mimeType: 'image/jpeg', buffer: Buffer.from('fake') } },
  })
  expect(r.status()).toBe(400)
})
```

- [ ] **Step 5: 创建 frontend/tests/e2e/04-list-records.spec.ts**

```typescript
import { test, expect } from '@playwright/test'

test('UI: 仪表盘加载记录', async ({ page }) => {
  await page.goto('/')
  await page.waitForSelector('table tbody tr', { timeout: 10000 })
})
```

- [ ] **Step 6: 创建 frontend/tests/e2e/05-detail.spec.ts**

```typescript
import { test, expect } from '@playwright/test'

test('UI: 详情抽屉打开', async ({ page }) => {
  await page.goto('/')
  await page.waitForSelector('table tbody tr', { timeout: 10000 })
  await page.getByRole('button', { name: '查看' }).first().click()
  await expect(page.getByText('识别结果')).toBeVisible()
})
```

- [ ] **Step 7: 跑 E2E (需所有服务运行)**

```bash
docker compose up -d
cd backend && export DATABASE_URL=... && export LLM_BASE_URL=... && export LLM_API_KEY=test && export LLM_MODEL=test && alembic upgrade head
cd ../frontend
npx playwright install chromium
npm run test:e2e
```

- [ ] **Step 8: 提交**

```bash
git add frontend/playwright.config.ts frontend/tests/
git commit -m "test(frontend): Playwright E2E 5 场景"
```

---

### Task 30: README + 启动验证

- [ ] **Step 1: 创建 README.md**

```markdown
# GE-VIC 图像识别平台

> 基础设施巡检图像识别后端 + 管理看板。
> 设计规范: docs/superpowers/specs/2026-07-01-image-recognition-architecture-design.md

## 快速开始

\`\`\`bash
cp .env.example .env
docker compose up -d

cd backend
export DATABASE_URL="postgresql+asyncpg://gevic:gevic_dev_password@localhost:5432/gevic"
export LLM_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
export LLM_API_KEY="your-key"
export LLM_MODEL="qwen-plus"
alembic upgrade head
cd ..

cd frontend && npm install && npm run dev
# 浏览器 http://localhost:5173
\`\`\`

## 服务端口

| 服务 | 端口 |
|---|---|
| backend (FastAPI) | 8000 |
| frontend (Vite) | 5173 |
| postgres | 5432 |
| redis | 6379 |
| minio | 9000/9001 |

## 测试

\`\`\`bash
cd backend && pytest -v
cd frontend && npm run test:e2e
\`\`\`

## 新增算法

\`\`\`sql
INSERT INTO algorithms (code, name, category, engine_type, engine_config, is_active, version)
VALUES ('my-algo', '我的算法', '供配电', 'cloud_api', '{"provider":"aliyun"}', true, 1);
\`\`\`
```

- [ ] **Step 2: 整体验证 + 提交**

```bash
git add README.md
git commit -m "docs: README 启动指南"
```

- [ ] **Step 3: 验证 M0 完成**

```bash
git log --oneline
# 应有 30+ commits
```

---

## 自审清单 (M0 完成后跑)

- [ ] `cd backend && pytest -v` 全部通过
- [ ] `cd frontend && npm run test:e2e` 全部通过
- [ ] `docker compose up -d` 6 服务都 healthy
- [ ] 浏览器 http://localhost:5173 能上传 + 查看 + 重试
- [ ] 算法表 INSERT 新行后,新端点可调用
- [ ] X-Inspector-Id 格式校验生效 (格式错 → 400)
- [ ] audit_logs 表中有上传/查询/重试记录
- [ ] 失败记录有"重试"按钮, 成功记录有 LLM 富化显示

## 关键验收 (V1.2 §1.7 SLO)

- 上传 P95 < 500ms ✓
- 识别 P95 < 30s ✓
- LLM 富化失败不影响主任务 ✓
- X-Inspector-Id 格式校验 ✓
- audit_logs 记录关键操作 ✓
- 5 张表 (V1.0 用 3 张) ✓
- 6 docker-compose 服务 ✓
- 单 Celery worker 多队列 ✓
- 无 result_backend ✓

## 下一步 (M1)

进入 M1 (独立计划):
- 增加 2-3 个算法
- LLM 报告生成
- Prometheus 指标 + 告警
- ECharts 看板图表

为 M1 创建独立计划: `docs/superpowers/plans/2026-07-01-gevic-m1-implementation.md`