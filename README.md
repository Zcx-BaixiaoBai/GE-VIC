# GE-VIC 图像识别平台 (M0)

> 基础设施巡检图像识别后端 + 管理看板
> 设计规范: docs/superpowers/specs/2026-07-01-image-recognition-architecture-design.md
> M0 目标: 1 个算法跑通端到端 (上传 → 入队 → 识别 → LLM 富化 → 入库 → 看板查询)

## 架构总览

- **接入层**: FastAPI 0.110+ (Python 3.11+)
- **任务层**: Celery 5.3+ + Redis
- **引擎层**: 插件化适配器 (Mock / CloudVision)
- **数据层**: PostgreSQL 16 + MinIO
- **前端**: Vue 3.4 + Vite 5 + Element Plus + Pinia + Vue Router
- **LLM**: OpenAI 兼容 chat API (DashScope / OpenAI / 自建网关)

## 服务端口

| 服务 | 端口 |
|---|---|
| backend (FastAPI) | 8000 |
| frontend (Vite) | 5173 |
| postgres | 5432 |
| redis | 6379 |
| minio | 9000/9001 |

## 快速启动 (Docker Compose)

```bash
cp .env.example .env
# 编辑 .env 填入真实 LLM_API_KEY 等
docker compose up -d

# 跑迁移 (一次性)
docker compose exec backend alembic upgrade head

# 浏览器访问
# - 前端: http://localhost:5173
# - 后端: http://localhost:8000/docs
# - MinIO 控制台: http://localhost:9001 (gevic_admin / gevic_dev_password)
```

## 本地开发 (无 Docker)

### 后端

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"

# 启动 PostgreSQL / Redis / MinIO (任选)
# 1) 启动本地服务并配置 DATABASE_URL 等
# 2) 或使用 docker compose 仅启动数据服务

# 跑迁移
$env:DATABASE_URL="postgresql+asyncpg://gevic:gevic_dev_password@localhost:5432/gevic"
$env:LLM_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
$env:LLM_API_KEY="your-key"
$env:LLM_MODEL="qwen-plus"
alembic upgrade head

# 启动 API
uvicorn app.main:app --reload --port 8000

# 另开终端启动 worker
celery -A app.tasks.celery_app worker -Q inspect_queue,stats_queue --loglevel=info
```

### 前端

```bash
cd frontend
npm install
npm run dev
# 浏览器 http://localhost:5173
```

## 测试

```bash
# 后端单元测试
cd backend
.\.venv\Scripts\python.exe -m pytest -v

# 前端 E2E (需 backend + frontend 运行)
cd frontend
npx playwright install chromium
npm run test:e2e
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

详见 `docs/superpowers/plans/2026-07-01-gevic-m0-implementation.md`

## M0 验证清单

- [x] 后端 pytest 46 项全过
- [x] 前端 `npm run build` 成功
- [x] FastAPI 应用可导入, 9 个 API 端点全部注册
- [ ] `docker compose up -d` 6 服务 healthy
- [ ] 浏览器 http://localhost:5173 上传 + 查看 + 重试
- [ ] 算法表 INSERT 新行后, 新端点可调用
- [ ] X-Inspector-Id 格式校验生效
- [ ] audit_logs 表记录关键操作
- [ ] 失败记录有"重试"按钮, 成功记录有 LLM 富化显示

## 下一步 (M1)

M1 计划独立成文 (`docs/superpowers/plans/2026-07-01-gevic-m1-implementation.md`):
- 增加 2-3 个算法
- LLM 报告生成
- Prometheus 指标 + 告警
- ECharts 看板图表
