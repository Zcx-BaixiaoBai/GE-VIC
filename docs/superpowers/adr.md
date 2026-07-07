# GE-VIC 架构决策记录 (ADR)

> 决策记录遵循 ADR (Architecture Decision Records) 风格, 编号 ADR-XXX。
> 文档日期: 2026-07-06

(后续 ADR 见后)

---

## ADR-001: 任务队列选型 — Celery

**状态**: 已接受

**背景**: 识别任务耗时数秒到数十秒, 同步执行会阻塞 HTTP 上传接口。

**决策**: 使用 Celery + Redis 作为任务队列。

**备选**:
- RQ (Redis Queue): API 简单, 但生态较小
- Dramatiq: 现代, 但社区规模小
- 自建线程池: 无外部依赖, 但失去持久化能力

**理由**:
- Celery 生态成熟 (10+ 年), 文档全
- 招人容易 (HR 熟悉, 招聘网站常见要求)
- 踩过的坑已经被社区解决
- 内部场景改算法频率低, 维护成本可控

**后果**:
- ✅ 异步任务解耦, 上传秒级返回 202
- ✅ 重试机制成熟 (指数退避)
- ⚠️ 需要维护 Celery worker 进程
- ⚠️ Redis 作为 broker 单点 (主规范 §4.3.3 决定 V1.0 不部署 Redis 集群)

---

## ADR-002: 对象存储 — MinIO

**状态**: 已接受

**背景**: 需要存储上传的图像/视频, 容量从 GB 增长到 TB 级。

**决策**: 使用 MinIO (S3 兼容)。

**备选**:
- 本地盘: 简单, 但难扩展
- 直接用云存储 (阿里云 OSS / AWS S3): 即用即付, 但绑死厂商
- FastDFS: 国产, 但文档少

**理由**:
- S3 兼容接口标准, 后续易迁 S3/OSS
- 单二进制部署, 维护简单
- 支持多桶/多租户 (未来需要时)
- 内部场景可单机运行, V1.0 资源占用低

**后果**:
- ✅ 标准 S3 接口, 切换云存储零代码改动
- ✅ 单机部署即可
- ⚠️ 需要管理 MinIO 进程

---

## ADR-003: 前端技术栈 — Vue 3 + Element Plus

**状态**: **偏离**主规范 §3.1 推荐 (FastAPI + HTMX), 采用 Vue

**背景**: 主规范推荐 FastAPI 模板 + HTMX/Alpine.js 极简方案, 但实际开发中:

**决策**: 使用 Vue 3 + Vite + Element Plus + Pinia。

**理由 (偏离文档化)**:
- Vue 生态成熟, 团队熟悉
- Element Plus 组件库开箱即用 (表单/对话框/抽屉/表格)
- 复杂状态管理 (算法配置表单, 实时指标) 用 Vue 响应式更清晰
- 前端工程师招人容易

**V1.0 范围内控制**:
- 不用 ECharts (主规范 §6.1 警告的"臃肿源头")
- 不用 TypeScript 高级特性 (保持简单)
- 不用状态管理库 (除 Pinia 之外)

**后果**:
- ✅ 开发效率高, 1 周可上线
- ✅ 组件库丰富, UI 一致性高
- ⚠️ 前端构建链复杂 (npm, Vite, 依赖管理)
- ⚠️ M3+ 如果引入大屏, 需评估 ECharts 引入 (主规范 ADR-007)

---

## ADR-004: LLM 厂商 — MiniMax M3 (可切换)

**状态**: 已接受 (主规范 §3 推荐通义千问, 实际使用 MiniMax)

**背景**: V1.0 需要多模态 LLM 识别图像内容。

**决策**: 默认 MiniMax M3, 通过 `LLM_BASE_URL` / `LLM_API_KEY` 可切换到任何 OpenAI 兼容厂商。

**支持的厂商**:
- MiniMax M3 (默认, 推理能力强, 支持多模态)
- 通义千问 qwen-vl-plus (主规范推荐, 国内合规)
- OpenAI gpt-4o / gpt-4o-mini
- DeepSeek (纯文本)
- Ollama 本地模型 (llava 等)

**切换方法**: 修改 `.env.local`:
```bash
LLM_API_KEY=sk-xxx
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-vl-plus
```

**理由**:
- 不绑死厂商, 内部可按成本/合规切换
- OpenAI 兼容接口是行业标准
- 多模态能力是关键 (V1.0 核心)

**后果**:
- ✅ 厂商可替换, 不锁死
- ⚠️ 不同厂商的 prompt 效果差异, 切换需重新调优

---

## ADR-005: 富化触发位置 — Celery 任务内同步

**状态**: 已接受

**背景**: 主任务 (识别) 完成后, 需要 LLM 生成维护建议 (富化)。

**决策**: 富化在 Celery 任务内同步调用, 不拆独立队列。

**理由**:
- 失败隔离: 富化失败不影响主任务状态 (主任务 SUCCESS, enrichment_status 独立)
- 流程简单: 单任务完成主识别 + 富化
- 后续可拆: M2 评估是否需要独立富化队列 (如富化成为独立服务)

**实现** (`backend/app/tasks/inspection.py`):
```python
if inspection.status == "SUCCESS":
    if settings.task_sync_mode:
        await _run_enrichment_async(record_id)
    else:
        celery_app.send_task("app.tasks.enrichment.enrich_inspection", ...)
```

**后果**:
- ✅ 主任务 SUCCESS 富化失败仍 SUCCESS
- ⚠️ 同步模式下富化阻塞识别队列 (M2 拆独立队列解决)

---

## ADR-006: 算法注册表刷新 — 启动加载 + 滚动重启

**状态**: 已接受 (主规范 §4.3.3)

**背景**: 算法配置变更后, 新算法需要立即生效。

**决策**: 算法注册表启动时从 DB 加载到内存, 修改后通过重启进程生效。

**理由**:
- 内部场景改算法频率低 (月度级别)
- 实现简单, 1 天工作量
- 避免 LISTEN/NOTIFY / Redis pub/sub 复杂度

**不实现**:
- ❌ 启动后热刷新
- ❌ 算法变更 WebSocket 推送
- ❌ 算法灰度

**后果**:
- ✅ 改算法 = SQL UPDATE + 重启 worker
- ⚠️ 重启期间短时不可用 (< 5s)

---

## ADR-007: 算法引擎类型 — 3 种 (cloud_api / mock / multimodal_llm)

**状态**: 已接受

**背景**: 不同识别场景需要不同引擎 (云厂商 API, 测试 mock, 多模态 LLM)。

**决策**: 引擎注册表支持 3 种类型:

| 引擎类型 | 用途 | 引擎基类 |
|---|---|---|
| `cloud_api` | 接入云厂商视觉 API (阿里云/腾讯云) | `CloudVisionEngine` |
| `mock` | 测试场景, 返回预设结果 | `MockEngine` |
| `multimodal_llm` | 用多模态 LLM 直接识别 | `MultimodalLLMEngine` |

**扩展**: 未来可加 `hikon_brain` (海康超脑, M2 PoC), `local_model` (本地模型, M3+)

**后果**:
- ✅ 算法注册表抽象统一 (`engine_type` 字段)
- ✅ 新引擎只需实现 `BaseEngine` 接口
- ⚠️ 引擎配置 schema 各异 (`engine_config: JSONB`)

---

## ADR-008: 临时文件管理 — 极简 (无磁盘临时文件)

**状态**: 已接受 (主规范 §4.3.1 推荐)

**决策**: 视频抽帧完全在内存中完成, 不创建磁盘临时文件。

**实现**:
- `multimodal_llm.py::_extract_video_frames` 用 `imageio.imiter(file_bytes)` 直接从内存读取
- 用 `PIL.Image` + `io.BytesIO()` 编码 JPEG
- 整个过程无磁盘 I/O

**不实现**:
- ❌ 复杂临时文件管理库
- ❌ Celery worker 临时目录管理

**后果**:
- ✅ 简单可靠, 无需清理逻辑
- ⚠️ 未来本地模型推理需补充临时文件策略

---

## ADR-009: 数据库 — PostgreSQL 16 + 异步 (asyncpg)

**状态**: 已接受

**背景**: 数据量预期 1000+ records/月, 关系型数据库适合复杂查询。

**决策**: PostgreSQL 16 + SQLAlchemy 2.0 异步 + asyncpg。

**理由**:
- PG 生态成熟, JSONB 字段支持 (用于 `recognition` / `llm_enrichment`)
- 异步 IO 提升并发
- 单机可跑 (8GB RAM)

**表结构 (5 张, V1.0)**:
- `algorithms` (5)
- `inspections` (110+)
- `audit_logs` (V1.0 简化)
- `enrichment_logs` (V1.0 简化)
- `alembic_version`

**不实现**:
- ❌ 分库分表 (V1.0 数据量不需要)
- ❌ 读写分离 (V1.0 QPS 不需要)

**后果**:
- ✅ 单机 PG 满足 V1.0 需求
- ⚠️ 写入 QPS > 100 时需评估分库

---

## ADR-010: 富化结果与主任务独立存储

**状态**: 已接受

**背景**: 富化可能失败, 不能影响主任务状态。

**决策**: 富化结果存 `inspections.llm_enrichment` (JSONB), 富化状态存 `inspections.enrichment_status` (独立字段)。

**好处**:
- 主任务 SUCCESS + 富化失败 = 用户能看到识别结果, 提示"智能建议生成中"
- 重试只重试富化, 不需要重跑识别

**后果**:
- ✅ 主/富化完全解耦
- ✅ 失败隔离, 符合主规范 §1.7 SLO

---

## ADR-011: 单机部署 (V1.0), 容器化 (V2.0)

**状态**: 已接受 (主规范 §6.3)

**背景**: V1.0 3 人内部系统, V2.0 才考虑云部署。

**决策**:
- V1.0: Docker Compose 单机 (PostgreSQL + Redis + MinIO + Backend + Worker + Frontend)
- V2.0: 评估 K8s 部署 (M3+)
- 不实现: 多区域容灾, 自动扩缩容, Service Mesh

**V1.0 部署清单**:
- 6 个 Docker 容器
- 1 台 Linux 服务器 (8GB RAM 即可)
- Nginx 反向代理 (可选, 内网可直接访问)

**后果**:
- ✅ V1.0 部署简单, 1 小时可起
- ⚠️ 单点故障 (主规范 §6.3 明确接受)

---

## ADR-012: 日志 — 结构化 + 本地文件

**状态**: 已接受 (主规范 §14.2)

**决策**: 使用 Python `logging` + JSON 格式 + 写本地文件。

**关键事件**:
- 上传接收 / 入队 / 任务开始 / 引擎调用 / 任务完成 / 失败重试
- 每条日志含 `record_id`, `algorithm_code`, `inspector_id`

**不实现**:
- ❌ ELK / Loki
- ❌ 日志聚合服务
- ❌ 日志搜索 UI

**后果**:
- ✅ 简单, 无外部依赖
- ⚠️ 多机部署时日志分散, V2.0 评估中央化

---

## ADR-013: 监控 — Prometheus 端点 + 9 个核心指标

**状态**: 已接受 (主规范 §14.3 + §1.7)

**决策**: 暴露 `/metrics` 端点, 9 个核心指标, V1.0 不部署 Grafana。

**3 核心指标 (主规范 §14.3)**:
1. `gevic_inspections_total{algorithm, status}` (Counter)
2. `gevic_inspection_duration_seconds{algorithm, engine}` (Histogram)
3. `gevic_engine_call_errors_total{engine, error_code}` (Counter)

**6 辅助指标**:
4. `gevic_upload_duration_seconds{algorithm}` (SLO 验证, §1.7)
5. `gevic_dependency_up{component}` (告警用, §14.4)
6. `gevic_algorithms_count` (Gauge)
7. `gevic_http_requests_total{endpoint, method, status}` (Counter)
8. `gevic_enrichment_total{status}` (Counter)
9. `gevic_llm_tokens_total{model, direction}` (Counter)
10. `gevic_process_start_time_seconds` (Gauge, SLO uptime 计算)

**2 告警 (主规范 §14.4)**:
- GevicDependencyDown (PromQL 规则已就绪)
- GevicWorkerDown (PromQL 规则已就绪)

**不部署**:
- ❌ Grafana 看板 (M3+ 评估)
- ❌ Alertmanager (V2.0 接入大平台统一)

**后果**:
- ✅ SLO 可手动查询验证
- ✅ 部署 Alertmanager 时直接粘贴 PromQL
﻿

---

## ADR-014: 断点续传方案 — TUS 1.0.0 协议

**状态**: 已接受

**日期**: 2026-07-07

**背景**: M1 部署到 cpolar 公网映射后, 用户反馈:
- 5-15MB 手机相册原图 30s 必超时
- 50-500MB 视频无法上传 (后端 20MB bug)
- 弱网抖断必须重传
- 无进度反馈, 用户以为卡死反复刷新

**决策**: 客户端 + 服务端实现 TUS 1.0.0 协议 (tus.io), 文件 ≥ 5MB 走 TUS 断点续传, < 5MB 走原 multipart (cpolar 也能秒传)。

**协议细节**:
- 客户端 (`useTusUpload.ts`, 250 行, 0 依赖)
  - XHR `upload.onprogress` 拿真实进度
  - 失败自动重试 5 次, 指数退避 (1s, 2s, 4s, 8s, 15s)
  - 断点续传: 重试时用 HEAD 拿服务端 offset, 跳过已上传部分
  - localStorage 存 session, 跨页面/刷新恢复
- 服务端 (`tus.py`, 260 行)
  - 临时文件存 `./upload-tmp/{session_id}.bin`
  - DB `upload_sessions` 表跟踪状态
  - 24h 过期 + 启动时 GC
  - 完成后 `POST /inspect/{code}/from-upload/{id}` 把临时文件转 Inspection

**备选**:
| 方案 | 优点 | 缺点 | 决策 |
|---|---|---|---|
| tus-js-client (成熟库) | 生态好 | 多 30KB, 黑盒难调试 | ❌ |
| 自己写 (最终选) | 0 依赖, 250 行, 全可控 | 要自己写测试 | ✅ |
| 直传 MinIO presigned | 绕过 cpolar 性能最好 | 需额外 cpolar 隧道到 MinIO, 复杂 | ❌ (留给 M3+) |
| 后端 nginx 上传模块 | 性能好 | 需要部署 nginx, 平台耦合 | ❌ |
| 分片哈希去重 | 支持秒传 | 实现复杂, 当前用不上 | ❌ (未来可加) |

**理由**:
- TUS 协议是 HTTP 文件上传的事实标准 (Dropbox / Vimeo / Cloudflare 都用)
- 250 行自己写比引入 30KB 依赖更可控
- 0 依赖 = 不增加前端 bundle 体积 (Vite 拆 chunk 后 client.js 只大 8KB)
- 服务端纯 FastAPI, 无新中间件

**度量**:
- 5MB 照片: 40s → 1.5s (压缩后 500KB)
- 50MB 视频: 不可用 → 7 分钟 (有进度条)
- 100MB 视频抖断 50%: 不可用 → 15 分钟 (自动续传)

---

## ADR-015: 客户端图片压缩 — Canvas API (无依赖)

**状态**: 已接受

**日期**: 2026-07-07

**背景**: M1 部署后, 5-15MB 手机原图在 cpolar 弱网下必超时。简单的"调大 axios timeout"治标不治本 — 5MB 文件在 1Mbps 网络下要 40s, 用户不会等。

**决策**: 选完文件后, 浏览器端用 Canvas 缩放 + JPEG 0.85 重新编码, 5MB → 500KB (10x 缩小), 视觉几乎无损。

**参数**:
- 长边 ≤ 1920px (4K 显示器足够, AI 识别也用不到更高)
- JPEG 质量 0.85 (肉眼几乎无损)
- 跳过阈值: < 800KB 不压 (收益小, 浪费时间)
- 跳过: 视频 / GIF / HEIC / SVG / ICO
- 失败透传 (HEIC 在 Chrome/Firefox 走这里)

**备选**:
| 方案 | 优点 | 缺点 | 决策 |
|---|---|---|---|
| Canvas (最终选) | 浏览器原生, 0 依赖 | 不能解 HEIC | ✅ |
| heic2any (npm) | 解决 HEIC | 多 200KB, 慢 | ❌ (透传给后端) |
| 后端压缩 (PIL) | 统一处理 | 已经上传了, 治标不治本 | ❌ |
| OffscreenCanvas + Worker | 不卡 UI | 复杂, 当前不需要 | ❌ (未来) |

**理由**:
- 90% 场景是 Chrome/Firefox 桌面浏览器, HEIC 不是问题
- iPhone Safari 用户直接能解 HEIC, 走 Canvas
- 透传策略兜底: 任何压缩失败都不阻塞上传

**度量**:
- 5MB iPhone 照片 → 500KB (10x)
- 视觉差异: 主观 1920px 长边 0.85 JPEG 与原图肉眼看不出
- 压缩耗时: 5MB 约 200-500ms (用户感觉不到)

---

## ADR-016: 文件大小按 file_type 分支 (修 M1 bug)

**状态**: 已接受

**日期**: 2026-07-07

**背景**: M1 代码 `inspect.py` 第 80 行用 `max_size = settings.max_image_size` 不论文件类型, 导致视频上传被 20MB 拒绝, 而 config 里早就定义 `max_video_size: int = 500MB` 但从未被读取。

**决策**: 按文件扩展名分支: `image` 走 max_image_size=20MB, `video` 走 max_video_size=500MB, `other` 兜底按 image 限。

**修法**:
```python
ext = filename.rsplit(".", 1)[-1].lower()
if ext in image_exts:        # jpg/png/bmp/webp/gif/heic
    file_type = "image"; max_size = settings.max_image_size
elif ext in video_exts:      # mp4/mov/avi/mkv/webm
    file_type = "video"; max_size = settings.max_video_size
else:
    file_type = "other"; max_size = settings.max_image_size
```

同步修 `inspect_batch` 端点 (内层循环也用 fmax)。

**理由**:
- 修法简单, 不引入新配置
- 保留兜底 (other 按 image 限, 不放大)
- 与 config 中早就定义但未使用的 `max_video_size` 一致

**教训**:
- 单元测试要覆盖 happy path, 而非只测 INVALID_ALGORITHM
- 添加新配置项时, 要搜 "用到没" (ripgrep `max_image_size` / `max_video_size`)
