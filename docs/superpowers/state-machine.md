# GE-VIC 状态机

> 描述识别任务与 LLM 富化的状态流转,作为代码、测试、运维的共同参考。
> 创建时间: 2026-07-06 (M1 实施期间)

---

## 1. 主任务状态 (字段: `inspections.status`)

| 状态 | 含义 | 触发条件 | 终态? |
|---|---|---|---|
| `PENDING` | 已接收请求, 等待执行 | `POST /api/v1/inspect/{code}` 成功写入 | 否 |
| `RUNNING` | 正在调用引擎识别 | 任务从队列取出, 进入识别流程 | 否 |
| `SUCCESS` | 识别完成 (含富化失败, 富化独立流转) | 引擎返回 success=True | ✅ 终态 |
| `FAILED` | 识别失败, 自动重试中 (retry_count < 3) | 引擎抛异常 | 否 (会转为 DEAD 或重试回 RUNNING) |
| `DEAD` | 重试耗尽 (retry_count ≥ 3), 需人工干预 | 超过 max_retries | ✅ 终态 |

### 1.1 主任务状态流转图

```
PENDING ──(worker picks up)──> RUNNING
                                   │
                          ┌────────┼────────┐
                          ↓        ↓        ↓
                       SUCCESS   FAILED   DEAD (retry ≥ 3)
                          │        │
                          │   ←── retry (backoff)
                          │        │
                          │        └──(retry exhausted)──> DEAD
                          ↓
                     (继续富化,见 §2)
```

### 1.2 重试机制

- **触发**: 引擎抛异常 (LLM 5xx, 网络超时, etc.)
- **次数**: 默认 3 次 (`tasks/inspection.py: _run_inspection_async`)
- **间隔**: 当前是立即重试, 后续可加重试退避
- **状态**: 重试期间保持 `RUNNING` (前端显示"识别中"), 不引入独立的 `RETRYING`

---

## 2. 富化状态 (字段: `inspections.enrichment_status`)

| 状态 | 含义 | 触发条件 | 终态? |
|---|---|---|---|
| `NULL` | 未开始 (主任务非 SUCCESS) | 初始 | 否 |
| `ENRICHING` | 正在调 LLM 富化 | 主任务 SUCCESS 后立即设置 | 否 |
| `ENRICHED` | 富化完成 | LLM 返回成功 | ✅ 终态 |
| `ENRICH_FAILED` | 富化失败, 可手动重试 | LLM 抛异常 | ✅ 终态 (可手动重置为 ENRICHING) |

### 2.1 富化状态流转图

```
NULL ──(主任务 SUCCESS)──> ENRICHING ──(LLM 成功)──> ENRICHED
                                       │
                                       └──(LLM 失败)──> ENRICH_FAILED
                                                            │
                                                            └──(手动 /enrich)──> ENRICHING
```

### 2.2 关键约束: 主任务与富化完全独立

- `status` 与 `enrichment_status` 是**两个独立维度**
- 富化失败时, 主 `status` 仍为 `SUCCESS`, `enrichment_status` 为 `ENRICH_FAILED`
- App 端展示"识别完成, 智能建议生成中", 并提供 `/enrich` 端点触发重试
- 重新富化时, 旧的 `llm_enrichment` 数据保留, 新的覆盖

---

## 3. 复合状态示例

| 主 status | enrichment_status | 用户看到的 |
|---|---|---|
| PENDING | NULL | 等待处理 |
| RUNNING | NULL | 识别中 |
| SUCCESS | ENRICHING | 识别完成, 富化中 |
| SUCCESS | ENRICHED | 识别完成 + 富化完成 (完整结果) |
| SUCCESS | ENRICH_FAILED | 识别完成, 富化失败 (可重试) |
| FAILED | NULL | 识别失败 (自动重试) |
| DEAD | NULL | 识别失败, 重试耗尽 (需人工重试) |

---

## 4. 端点行为

| 端点 | 适用状态 | 说明 |
|---|---|---|
| `POST /api/v1/inspect/{code}` | 任意 (新写入 PENDING) | 接收文件, 创建记录 |
| `POST /api/v1/records/{id}/retry` | FAILED, DEAD | 重置 status=PENDING, 重新入队 |
| `POST /api/v1/records/{id}/enrich` | ENRICHED, ENRICH_FAILED | 重置 enrichment_status=ENRICHING, 重新富化 |
| `GET /api/v1/records/{id}` | 任意 | 查询当前状态 |
| `GET /api/v1/records?status=...` | 任意 | 按状态过滤 |

---

## 5. 实现位置

| 字段 | 文件 | 行 |
|---|---|---|
| `inspections.status` | `backend/app/tasks/inspection.py` | `_run_inspection_async()` |
| `inspections.enrichment_status` | `backend/app/tasks/inspection.py` | `_run_inspection_async()` + `_run_enrichment_async()` |
| 模型类 | `backend/app/models/inspection.py` | `Inspection.status`, `Inspection.enrichment_status` |
| 富化重试 API | `backend/app/api/records.py` | `POST /records/{id}/enrich` |
| 主重试 API | `backend/app/api/records.py` | `POST /records/{id}/retry` |

---

## 6. Prometheus 指标关联

| 指标 | 来源状态 | 类型 |
|---|---|---|
| `gevic_inspections_total{status="SUCCESS"}` | 主 SUCCESS | Counter |
| `gevic_inspections_total{status="FAILED"}` | 主 FAILED | Counter |
| `gevic_inspections_total{status="DEAD"}` | 主 DEAD | Counter |
| `gevic_inspection_duration_seconds` | SUCCESS 时记录耗时 | Histogram |
| `gevic_enrichment_total{status="ENRICHED"}` | 富化 ENRICHED | Counter |
| `gevic_enrichment_total{status="ENRICH_FAILED"}` | 富化 ENRICH_FAILED | Counter |
| `gevic_llm_tokens_total` | 任何 LLM 调用 | Counter (prompt + completion) |

可观测 SLO:
- `histogram_quantile(0.95, rate(gevic_inspection_duration_seconds_bucket[5m]))` < 30s
- `sum(rate(gevic_inspections_total{status="FAILED"}[5m])) / sum(rate(gevic_inspections_total[5m]))` < 5%

---

## 7. 已知问题 / 待改进

- [ ] 重试无退避: 当前立即重试, 应加重试退避 (5s, 30s, 2m)
- [ ] DEAD 状态无告警: 应有 Prometheus alert
- [ ] 富化重试无次数限制: 应限制最大重试次数避免无限循环
- [ ] 状态机无版本号: 后续若扩展状态 (如 CANCELLED), 需要迁移策略
﻿

## 8. TUS 上传会话状态机 (V1.3 新增, 字段: `upload_sessions.status`)

> M2 引入, 用于断点续传会话管理。详见 [upload-protocol.md](./upload-protocol.md) 和 [ADR-014](./adr.md)。

| 状态 | 含义 | 触发条件 | 终态? |
|---|---|---|---|
| `uploading` | 已创建, 正在接收分片 | `POST /uploads` 成功 | 否 |
| `completed` | 所有分片已接收, `offset == total_size` | 最后一个 `PATCH` 写完 | ✅ (待 finalize) |
| `cancelled` | 客户端主动取消 | `DELETE /uploads/{id}` | ✅ |

### 8.1 TUS 状态流转图

```
       POST /uploads
            ↓
       uploading ←──────────────────────┐
            │                            │ (重试, HEAD 拿 offset 后
            │ PATCH (分片 1, 2, ...)     │  继续 PATCH)
            ↓                            │
       uploading                          │
            │ (offset == total_size)     │
            ↓                            │
       completed                          │
            │                            │
            ↓                            │
   POST /inspect/{code}/from-upload/{id} │
            │                            │
            ↓                            │
   (delete session row + 临时文件)        │
            ↓                            │
       (终态消失)                          │
                                          │
       DELETE /uploads/{id} ──→ cancelled (终态)
```

### 8.2 关键不变量

- `offset <= total_size` 永远成立
- 写分片前必须校验请求 `Upload-Offset == session.offset`, 不匹配返 409
- `status='completed'` 后, 临时文件可被 finalize 路由读出 + 删
- `status='cancelled'` 后, 临时文件立即删
- 24h 过期 (无 finalize 也无续传): 启动时 `gc_expired_sessions` 清

### 8.3 异常路径

| 场景 | 行为 |
|---|---|
| 客户端 PATCH 中断 | 服务端保持 `uploading` + 当前 offset, 不动 |
| 客户端重新选同一文件 | 走 `useTusUpload.ts::loadStored`, 复用 session, HEAD 拿 offset, 续传 |
| 后端崩 + 重启 | 内存状态丢失, 但 DB + 临时文件还在, 客户端续传正常 |
| 临时文件被人为删 | `status=completed` 后 finalize 报 410 UPLOAD_FILE_MISSING |
| session 过期被 GC | 客户端再次上传会 HEAD 拿 404, 自动清理 localStorage, 重新建 session |

## 9. V1.3 更新日志

- §8 + §9 (本节) 新增 TUS 状态机
- §7 已知问题中"重试无退避"已通过 TUS 实现 (5 次指数退避)
- §7 已知问题中"状态机无版本号"已记录 (扩展 CANCELLED 等需迁移策略)
