# GE-VIC M1 实施计划 — 多算法 + 报告 + 监控

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在 M0 单算法端到端基础上, 扩展到多算法 + LLM 报告生成 + 基础监控指标 (3 个核心 Prometheus 指标)。

**M0 收尾**: [`2026-07-01-gevic-m0-final.md`](./2026-07-01-gevic-m0-final.md) — 5 算法, 110 records, 27 e2e 通过。

**Spec 引用**:
- [`../specs/2026-07-01-image-recognition-architecture-design.md`](../specs/2026-07-01-image-recognition-architecture-design.md) V1.2 §18 M1
- [`../specs/2026-07-01-image-recognition-architecture-review-recommendations.md`](../specs/2026-07-01-image-recognition-architecture-review-recommendations.md) §1.7 SLO

**Tech Stack 新增**:
- **prometheus-client** 0.20+ (后端 metrics 暴露)
- **/metrics** 端点 (Prometheus 抓取格式)

---

## 1. M1 范围与不做

### 1.1 范围 (M1 必须做)

- [x] 已有 5 算法, 超出 M1 期望的 2-3 个
- [x] 已有 LLM 富化报告 (llm_enrichment 字段), 超出 M1 期望
- [ ] **基础监控指标 (3 个核心 Prometheus)** — M1 主要 TODO
  - `gevic_inspections_total` — 计数器, 按 status 标签
  - `gevic_inspection_duration_seconds` — 直方图, 按 algorithm_code 标签
  - `gevic_llm_tokens_total` — 计数器, 按 model + direction (prompt/completion) 标签
- [ ] /metrics 端点 (Prometheus 抓取格式)
- [ ] 健康检查升级 (区分 liveness / readiness)
- [ ] 状态机文档化 (M1 范围, 给后续维护者)

### 1.2 不做 (V1.0 边界外, 见主规范 §1.6)

- ❌ Grafana / 告警通道 (V1.0 只暴露指标)
- ❌ ECharts 看板图表 (M3+ 评估)
- ❌ 多用户鉴权 (并入大系统时统一处理)
- ❌ 审计日志 UI (M1 后置)
- ❌ 算法管理高级特性 (灰度 / 版本化 / A/B)

---

## 2. 验收标准 (M1 完成定义)

- [ ] `curl http://127.0.0.1:8000/metrics` 返回 Prometheus 文本格式
- [ ] 至少 3 个核心指标: `gevic_inspections_total`, `gevic_inspection_duration_seconds`, `gevic_llm_tokens_total`
- [ ] 上传一次后, 指标值相应增加
- [ ] `/health/live` 与 `/health/ready` 都返回 200
- [ ] e2e 测试覆盖指标端点
- [ ] 状态机文档完成 (含所有 9 个状态流转图)
- [ ] 单图识别 P95 延迟可通过指标观测

---

## 3. 文件结构 (M1 新增/修改)

```
backend/
├── app/
│   ├── services/
│   │   ├── metrics.py         # 新增: Prometheus 指标定义 + 注册
│   │   └── ...
│   ├── api/
│   │   ├── health.py          # 修改: 增加 /live, /ready
│   │   └── ...
│   └── main.py                # 修改: 挂载 /metrics, 启动时注册指标
├── tests/                     # (后端 pytest 暂未纳入, 沿用 e2e)
└── pyproject.toml             # 新增 prometheus-client 依赖

frontend/
└── tests/e2e/
    └── 08-metrics.spec.ts     # 新增: 验证 /metrics 端点

docs/
└── superpowers/
    ├── state-machine.md       # 新增: 状态机文档
    └── plans/
        └── 2026-07-01-gevic-m1-implementation.md  # 本文档
```

---

## 4. 任务清单

| 阶段 | 任务 | 标题 | 状态 |
|---|---|---|---|
| **监控** | T1 | 添加 prometheus-client 依赖 | TODO |
| | T2 | metrics 服务: 3 个核心指标 + 辅助 | TODO |
| | T3 | /metrics 端点 | TODO |
| | T4 | 识别任务中埋点 (Counter + Histogram) | TODO |
| | T5 | LLM 调用中埋点 (Token Counter) | TODO |
| **健康** | T6 | /health 拆分 liveness / readiness | TODO |
| **文档** | T7 | 状态机文档 | TODO |
| **测试** | T8 | e2e: 指标端点 | TODO |
| **验收** | T9 | M1 收尾 | TODO |

---

## Task 1: 添加 prometheus-client 依赖

**Files:**
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: 添加依赖**

在 `dependencies` 列表中添加:
```toml
"prometheus-client>=0.20.0",
```

- [ ] **Step 2: 安装**

```bash
cd backend
.venv\Scripts\pip install prometheus-client
```

- [ ] **Step 3: 验证**

```bash
.venv\Scripts\python.exe -c "import prometheus_client; print(prometheus_client.__version__)"
# 应输出 0.20.x 或更新
```

- [ ] **Step 4: 提交**

```bash
git add backend/pyproject.toml backend/uv.lock 2>/dev/null || true
git commit -m "feat(backend): 添加 prometheus-client 依赖 (M1)"
```

---

## Task 2: metrics 服务

**Files:**
- Create: `backend/app/services/metrics.py`

- [ ] **Step 1: 创建 metrics.py**

```python
"""Prometheus 指标定义与注册.

M1 阶段 3 个核心指标:
- gevic_inspections_total: 计数器, 按 status 标签 (PENDING/RUNNING/SUCCESS/FAILED/DEAD)
- gevic_inspection_duration_seconds: 直方图, 按 algorithm_code 标签
- gevic_llm_tokens_total: 计数器, 按 model + direction 标签

辅助:
- gevic_enrichment_total: 计数器, 按 status 标签
- gevic_algorithms_count: Gauge, 当前活跃算法数
"""
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, REGISTRY

# 3 个核心指标
INSPECTIONS_TOTAL = Counter(
    "gevic_inspections_total",
    "识别任务总数, 按最终状态分组",
    labelnames=("algorithm_code", "status"),
)

INSPECTION_DURATION = Histogram(
    "gevic_inspection_duration_seconds",
    "单次识别耗时 (秒), 包含 LLM 富化",
    labelnames=("algorithm_code",),
    buckets=(0.5, 1, 2, 5, 10, 20, 30, 60, 120, 300),
)

LLM_TOKENS_TOTAL = Counter(
    "gevic_llm_tokens_total",
    "LLM token 用量, 按模型和方向",
    labelnames=("model", "direction"),  # direction: prompt | completion
)

# 辅助指标
ENRICHMENT_TOTAL = Counter(
    "gevic_enrichment_total",
    "LLM 富化总数, 按状态分组",
    labelnames=("status",),  # ENRICHED | ENRICH_FAILED
)

ALGORITHMS_COUNT = Gauge(
    "gevic_algorithms_count",
    "当前活跃算法数",
)


def get_metrics() -> bytes:
    """返回 Prometheus 文本格式的指标数据."""
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    return generate_latest(REGISTRY)
```

- [ ] **Step 2: 验证导入**

```bash
cd backend
.venv\Scripts\python.exe -c "from app.services.metrics import INSPECTIONS_TOTAL, INSPECTION_DURATION, LLM_TOKENS_TOTAL; print('OK')"
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/services/metrics.py
git commit -m "feat(backend): 定义 3 个核心 Prometheus 指标 (M1)"
```

---

## Task 3: /metrics 端点

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: 导入并挂载**

在 `app/main.py` 中:

```python
from fastapi.responses import Response
from app.services.metrics import get_metrics
from prometheus_client import CONTENT_TYPE_LATEST

@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    """Prometheus 抓取端点 (无认证, 内部网络)"""
    return Response(content=get_metrics(), media_type=CONTENT_TYPE_LATEST)
```

- [ ] **Step 2: 重启后端并测试**

```bash
# 杀掉旧后端
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object {
  $_.CommandLine -match "uvicorn" -and $_.CommandLine -match "127.0.0.1"
} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

# 启动新后端
powershell -ExecutionPolicy Bypass -File scripts\start-app-real.ps1

# 验证
curl http://127.0.0.1:8000/metrics | head -20
# 应看到 Prometheus 文本格式, 含 gevic_* 指标 (即使为 0)
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/main.py
git commit -m "feat(backend): 挂载 /metrics 端点 (M1)"
```

---

## Task 4: 识别任务埋点

**Files:**
- Modify: `backend/app/tasks/inspection.py`

- [ ] **Step 1: 找到识别结果处理位置**

定位 `inspection.py` 中 `if not recognition.success` 与 `inspection.status = "SUCCESS"` 之间的代码。

- [ ] **Step 2: 埋点 (Counter + Histogram)**

在 `inspection.status = "SUCCESS"` **之后** (主任务成功的分支):

```python
from app.services.metrics import INSPECTIONS_TOTAL, INSPECTION_DURATION

INSPECTIONS_TOTAL.labels(
    algorithm_code=inspection.algorithm_code,
    status="SUCCESS",
).inc()
INSPECTION_DURATION.labels(
    algorithm_code=inspection.algorithm_code,
).observe(inspection.duration_ms / 1000.0)
```

在 `inspection.status = "FAILED"` / `"DEAD"` **之后**:
```python
INSPECTIONS_TOTAL.labels(
    algorithm_code=inspection.algorithm_code,
    status=inspection.status,
).inc()
```

- [ ] **Step 3: 验证**

启动后端, 上传一次, 检查 `gevic_inspections_total{status="SUCCESS"}` 增加。

- [ ] **Step 4: 提交**

```bash
git add backend/app/tasks/inspection.py
git commit -m "feat(backend): 识别任务埋点 (Counter + Histogram) (M1)"
```

---

## Task 5: LLM Token 埋点

**Files:**
- Modify: `backend/app/services/llm_client.py` (或调用 LLM 的地方)

- [ ] **Step 1: 找到 chat_with_images / chat 调用**

定位返回 `usage` 字段的位置 (通常在 response.usage)。

- [ ] **Step 2: 埋点**

```python
from app.services.metrics import LLM_TOKENS_TOTAL

# 在拿到 response 后, 提取 usage
usage = response.get("usage", {}) or {}
if usage:
    LLM_TOKENS_TOTAL.labels(model=model, direction="prompt").inc(usage.get("prompt_tokens", 0))
    LLM_TOKENS_TOTAL.labels(model=model, direction="completion").inc(usage.get("completion_tokens", 0))
```

- [ ] **Step 3: 富化任务也埋点**

在 `app/services/enrichment.py` 或 `tasks/inspection.py` 的富化部分, 同样埋点 (复用 `LLM_TOKENS_TOTAL`)。

- [ ] **Step 4: 验证**

上传一次, 检查 `gevic_llm_tokens_total` 增加。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/llm_client.py backend/app/services/enrichment.py
git commit -m "feat(backend): LLM 调用埋点 Token 计数器 (M1)"
```

---

## Task 6: /health 拆分

**Files:**
- Modify: `backend/app/api/health.py` (或 main.py)

- [ ] **Step 1: 添加 /health/live 与 /health/ready**

```python
@app.get("/health/live")
async def liveness() -> dict:
    """进程存活 (用于 k8s livenessProbe)"""
    return {"status": "alive"}


@app.get("/health/ready")
async def readiness() -> dict:
    """依赖就绪 (用于 k8s readinessProbe): 检查 DB / Redis / MinIO"""
    from app.database import get_global_sessionmaker
    from app.services.storage import get_storage
    checks = {}
    try:
        sm = get_global_sessionmaker()
        async with sm() as session:
            await session.execute("SELECT 1")
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"
    # ... 类似检查 redis, minio
    all_ok = all(v == "ok" for v in checks.values())
    return {"status": "ready" if all_ok else "degraded", "checks": checks}
```

- [ ] **Step 2: 验证**

```bash
curl http://127.0.0.1:8000/health/live
curl http://127.0.0.1:8000/health/ready
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/api/health.py
git commit -m "feat(backend): 健康检查拆分 liveness/readiness (M1)"
```

---

## Task 7: 状态机文档

**Files:**
- Create: `docs/superpowers/state-machine.md`

- [ ] **Step 1: 创建文档**

```markdown
# GE-VIC 状态机

## 主任务状态 (字段: inspections.status)

| 状态 | 含义 | 触发 |
|---|---|---|
| PENDING | 已接收, 等待执行 | POST /inspect 立即写入 |
| RUNNING | 正在调用 LLM 识别 | 任务开始时设置 |
| SUCCESS | 识别完成 (含富化失败, 富化独立流转) | 引擎返回成功 |
| FAILED | 识别失败, 自动重试中 | 异常抛出 |
| DEAD | 重试耗尽 (≤ 3 次), 需人工干预 | 超过 max_retries |

## 富化状态 (字段: inspections.enrichment_status)

| 状态 | 含义 | 触发 |
|---|---|---|
| NULL | 未开始 (主任务非 SUCCESS) | 初始 |
| ENRICHING | 正在调 LLM 富化 | 任务开始时 |
| ENRICHED | 富化完成 | LLM 返回成功 |
| ENRICH_FAILED | 富化失败, 可手动重试 | LLM 异常 |

## 状态流转图

```
主任务:
  PENDING → RUNNING → SUCCESS
                     → FAILED (重试 1, 2, 3, → DEAD)

富化 (在 SUCCESS 后):
  NULL → ENRICHING → ENRICHED
                 → ENRICH_FAILED (可手动 /enrich 重试)
```

## 关键约束

- 主 `status` 与 `enrichment_status` **完全独立**: 富化失败时, 主 `status` 仍为 `SUCCESS`。
- 重试期间状态 = `RUNNING` (前端展示"识别中"), 不引入独立的 `RETRYING` 状态。
- `DEAD` 记录 `error_message` 供排查, 前端显示"重试"按钮调用 `/records/{id}/retry`。
- 富化可通过前端 "生成富化报告" / "重新富化" 按钮手动触发, 调 `POST /records/{id}/enrich`。
```

- [ ] **Step 2: 提交**

```bash
git add docs/superpowers/state-machine.md
git commit -m "docs: 状态机文档 (M1)"
```

---

## Task 8: e2e 测试 — 指标端点

**Files:**
- Create: `frontend/tests/e2e/08-metrics.spec.ts`

- [ ] **Step 1: 创建测试**

```typescript
import { test, expect } from '@playwright/test'

test('API: /metrics returns Prometheus text format', async ({ request }) => {
  const r = await request.get('http://127.0.0.1:8000/metrics')
  expect(r.status()).toBe(200)
  const body = await r.text()
  expect(body).toContain('# HELP')
  expect(body).toContain('# TYPE')
  expect(body).toMatch(/gevic_inspections_total/)
})

test('API: /health/live returns 200', async ({ request }) => {
  const r = await request.get('http://127.0.0.1:8000/health/live')
  expect(r.status()).toBe(200)
  const body = await r.json()
  expect(body.status).toBe('alive')
})

test('API: /health/ready returns 200 when all deps ok', async ({ request }) => {
  const r = await request.get('http://127.0.0.1:8000/health/ready')
  expect(r.status()).toBe(200)
  const body = await r.json()
  expect(body.checks).toBeDefined()
})
```

- [ ] **Step 2: 跑测试**

```bash
cd frontend
npx playwright test tests/e2e/08-metrics.spec.ts --reporter=line
```

- [ ] **Step 3: 提交**

```bash
git add frontend/tests/e2e/08-metrics.spec.ts
git commit -m "test(frontend): e2e 指标 + 健康检查端点 (M1)"
```

---

## Task 9: M1 收尾

- [ ] **Step 1: 全部 e2e 通过**

```bash
cd frontend
npx playwright test --reporter=line --grep-invert "upload to multimodal|batch upload with joint|bad engine_config|test algorithm"
# (排除需要真实 LLM 上传的 3 个慢测试)
```

- [ ] **Step 2: 验证指标真实数据**

```bash
# 上传一次
curl -F "file=@test-image.jpg" -H "X-Inspector-Id: admin001" http://127.0.0.1:8000/api/v1/inspect/multimodal-inspector

# 等 30s, 查询指标
sleep 30
curl http://127.0.0.1:8000/metrics | grep gevic_
# 应看到:
#   gevic_inspections_total{algorithm_code="multimodal-inspector",status="SUCCESS"} 1.0
#   gevic_inspection_duration_seconds_bucket{...,le="30.0"} 1.0
#   gevic_llm_tokens_total{model="MiniMax-M3",direction="prompt"} 1234.0
#   gevic_llm_tokens_total{model="MiniMax-M3",direction="completion"} 567.0
```

- [ ] **Step 3: 创建 M1 Final 文档**

参考 M0 final 模板: `docs/superpowers/plans/2026-07-01-gevic-m1-final.md`

- [ ] **Step 4: 提交**

```bash
git add docs/superpowers/plans/2026-07-01-gevic-m1-final.md
git commit -m "docs: M1 收尾 (2026-07-XX)"
```

---

## 自审清单 (M1 完成后)

- [ ] `curl /metrics` 返回 Prometheus 文本格式
- [ ] 3 个核心指标都有数据 (上传后数值 > 0)
- [ ] `/health/live` 与 `/health/ready` 都返回 200
- [ ] e2e 测试 08-metrics.spec.ts 全部通过
- [ ] 状态机文档完整, 9 个状态都有说明
- [ ] 整个 e2e (除 LLM 慢测试) 全通过
- [ ] 后端日志无新增 ERROR/CRITICAL

## M2 准备 (海康超脑 PoC)

M1 完成后, M2 进入独立 PoC 任务:
- 海康超脑 ISAPI 集成 (V1.0 没做)
- PoC 失败 → 保持 M1 状态
- PoC 成功 → 进入 M3 规模化规划

**M1 完成标准: 监控指标可观测业务健康度, 多算法 + LLM 报告流程稳定, 状态机清晰。**
