# GE-VIC 图像识别平台 (M2)

> 基础设施巡检图像识别后端 + 管理看板
> 设计规范: docs/superpowers/specs/2026-07-01-image-recognition-architecture-design.md (V1.3)
> 当前里程碑: **M2 — 生产可用性** (断点续传 + 客户端压缩 + 进度反馈 + 公网部署)

### 里程碑

| 里程碑 | 状态 | 关键交付 | 交付报告 |
|---|---|---|---|
| M0 端到端 | ✅ 完成 | 1 个算法跑通端到端 (上传 → 入队 → 识别 → 富化 → 看板) | [m0-final](./docs/superpowers/plans/2026-07-01-gevic-m0-final.md) |
| M1 多算法+监控 | ✅ 完成 | 5 算法 + LLM 报告 + 13 Prometheus 指标 | [m1-final](./docs/superpowers/plans/2026-07-01-gevic-m1-final.md) |
| **M2 生产可用性** | ✅ 完成 | TUS 断点续传 + 客户端压缩 + 进度条 + 公网部署 (cpolar) | [m2-final](./docs/superpowers/plans/2026-07-01-gevic-m2-final.md) |

### 快速链接

- 📖 [完整设计规范 V1.3](./docs/superpowers/specs/2026-07-01-image-recognition-architecture-design.md)
- 🚀 [生产部署指南 (cpolar / 公网映射)](./docs/DEPLOYMENT.md)
- 📋 [架构决策记录 (ADR)](./docs/superpowers/adr.md)
- 📊 [M2 实施计划](./docs/superpowers/plans/2026-07-01-gevic-m2-implementation.md)
- 🔌 [上传协议细节 (TUS)](./docs/superpowers/upload-protocol.md)

## 架构总览

- **接入层**: FastAPI 0.110+ (Python 3.11+)
- **任务层**: Celery 5.3+ + Redis
- **引擎层**: 插件化适配器 (CloudVision / MultimodalLLM)
- **数据层**: PostgreSQL 16 + MinIO
- **前端**: Vue 3.4 + Vite 5 + Element Plus + Pinia + Vue Router
- **LLM**: OpenAI 兼容 chat API (DashScope / OpenAI / 自建网关)
- **上传协议**: TUS 1.0.0 (断点续传) + Canvas 客户端压缩

## 服务端口

| 服务 | 端口 |
|---|---|
| backend (FastAPI) | 8000 |
| frontend (Vite) | 5173 |
| postgres | 5432 |
| redis | 6379 |
| minio | 9000/9001 |

### M2 核心能力 - 大文件上传

| 文件类型 | 大小限制 | 上传方式 | 用户体验 |
|---|---|---|---|
| 图片 (jpg/png/webp/heic) | 20MB (raw) / 500KB (压缩后实际) | Canvas 客户端压缩 → 小文件走 multipart, 大文件走 TUS | 实时进度条 |
| 视频 (mp4/mov/avi/mkv) | 500MB | TUS 断点续传 (分片 5MB) | 实时进度条 + 自动重试 5 次 + 断网续传 |
| HEIC (iPhone 原生) | 20MB | 透传给后端 (Chrome/Firefox 不能 canvas 解码 HEIC) | 进度条 |

详见 [上传协议细节](./docs/superpowers/upload-protocol.md) 和 [ADR-002](./docs/superpowers/adr.md)。

## 快速启动 (Docker Compose, 生产路径)

```bash
cp .env.example .env
# 编辑 .env 填入真实 LLM_API_KEY 等
docker compose up -d

# 跑迁移 (一次性, M0 + M1 + M2 全部迁移)
docker compose exec backend alembic upgrade head

# 浏览器访问
# - 前端: http://localhost:5173
# - 后端: http://localhost:8000/docs
# - MinIO 控制台: http://localhost:9001 (gevic_admin / gevic_dev_password)
```

## 本地开发 (Windows / 无 Docker)

### 一次性安装本地服务

```powershell
# 0. (首次) 下载 MinIO 二进制到 minio/minio.exe (108MB, 不随仓库分发)
#    Invoke-WebRequest https://dl.min.io/server/minio/release/windows-amd64/minio.exe -OutFile minio\minio.exe

# 1. 启动 PostgreSQL / Redis / MinIO (pgserver + 真实 MinIO 持久化 + redis-server)
powershell -File scripts\start-services.ps1

# 2. 启动后端 + 前端
powershell -File scripts\start-app.ps1
```

### 本地同步模式 (Windows 无需 Celery worker)

| 环境变量 | 默认 | 说明 |
|---|---|---|
| `TASK_SYNC_MODE` | `false` | `true` 时任务在 API 进程内同步执行, 不依赖 Celery worker (Windows 本地开发用) |

**生产部署 (Linux/Docker 或 cpolar 映射)**: 保持 `TASK_SYNC_MODE=false`, 由 Celery worker 异步消费 + 真实 LLM 接入。详见 [DEPLOYMENT.md](./docs/DEPLOYMENT.md)。

### 手动启动 (无 scripts)

```bash
# 启依赖 (PG/Redis/MinIO 任意方式)
# 1) 或用 docker compose 仅启动数据服务: docker compose up -d postgres redis minio minio-init
# 2) 或用本地 start-services.ps1

# 启后端
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
$env:DATABASE_URL="postgresql+asyncpg://postgres@127.0.0.1:5432/gevic"
$env:LLM_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
$env:LLM_API_KEY="your-key"
$env:LLM_MODEL="qwen-plus"
$env:MINIO_ENDPOINT="127.0.0.1:9000"
$env:MINIO_ACCESS_KEY="gevic_admin"
$env:MINIO_SECRET_KEY="gevic_dev_password"
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# 另开终端启 worker (生产模式, 非 demo)
celery -A app.tasks.celery_app worker -Q inspect_queue,stats_queue -l info

# 另开终端启前端
cd ../frontend
npm install
npm run dev
```

## 测试

```bash
# 后端单元测试 (55+ 项, 含 9 项 TUS 协议测试, 无需 DB/服务)
cd backend
.\.venv\Scripts\python.exe -m pytest -v

# 前端 E2E (需 backend + frontend 运行)
cd frontend
npx playwright install chromium
npm run test:e2e
# 跑指定套件: npx playwright test tests/e2e/09-tus-upload.spec.ts
```

## 新增算法

仅需在 `algorithms` 表 INSERT 一行配置, 无需修改代码:

```sql
INSERT INTO algorithms (code, name, category, engine_type, engine_config, is_active, version)
VALUES (
    'my-algo',
    '我的算法',
    '供配电',
    'cloud_api',
    '{"provider": "aliyun", "endpoint": "https://...", "action": "RecognizeXxx", "access_key_id": "AK", "access_key_secret": "SK"}',
    true,
    1
);
```

新端点 `POST /api/v1/inspect/my-algo` 立即生效。

## M0 任务清单

详见 `docs/superpowers/plans/2026-07-01-gevic-m0-implementation.md` (30 个任务)

## M0 验证清单

- [x] `pytest -v` 全部通过 (46/46)
- [x] `npm run build` 成功
- [x] 9 个 API 端点全部注册
- [x] 同步模式 SUCCESS + ENRICHED 端到端可走通
- [ ] `docker compose up -d` 6 服务都 healthy (需本机 Docker)
- [ ] 浏览器人工测试 (运行 start-app.ps1 后访问 http://127.0.0.1:5173)
- [ ] 算法表 INSERT 新行后, 新端点可调用
- [ ] X-Inspector-Id 格式校验生效
- [x] audit_logs 表记录关键操作
- [x] 失败记录有"重试"按钮, 成功记录有 LLM 富化显示

## 下一步 (M1)

M1 计划独立成文 (`docs/superpowers/plans/2026-07-01-gevic-m1-implementation.md`):
- 增加 2-3 个算法
- LLM 报告生成
- Prometheus 指标 + 告警
- ECharts 看板图表
