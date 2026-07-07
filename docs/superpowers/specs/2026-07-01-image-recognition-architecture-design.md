
---

## 版本变更记录

| 版本 | 日期 | 变更 |
|---|---|---|
| V1.0 | 2026-07-01 | 初版, M0 实施 |
| V1.1 | 2026-07-01 | 取消鉴权 + 完整响应结构 |
| V1.2 | 2026-07-01 | 评审后定稿 (集成边界, 未来扩展) |
| **V1.3** | **2026-07-07** | **M2 增量: TUS 断点续传 + 客户端压缩 + 文件大小分支 (详见下方)** |

### V1.3 新增章节 (相对 V1.2)

> 本节为变更摘要, 完整协议与设计详见 [upload-protocol.md](../upload-protocol.md) 和 [ADR-014/015/016](../adr.md)。完整设计如需追溯, 以 V1.2 正文 + 本变更记录 + 新增配套文档为准。

#### §18.2 大文件上传协议 (TUS 1.0.0)

**V1.3 新增**, 原 §18 仅有"小文件 multipart"。

| 文件类型 | 大小 | 协议 | 体验 |
|---|---|---|---|
| 图片 ≤ 20MB | raw | Canvas 客户端压缩 → 小文件走 multipart, 大文件走 TUS | 实时进度条 |
| 视频 ≤ 500MB | raw | TUS 1.0.0 (5MB 分片) | 进度条 + 续传 + 5 次重试 |
| HEIC | ≤ 20MB | 透传 (Chrome/Firefox) / 压缩 (Safari) | 进度条 |

**新增端点**:
- `POST /api/v1/uploads` - TUS 创建会话
- `PATCH /api/v1/uploads/{id}` - 追加分片
- `HEAD /api/v1/uploads/{id}` - 查询 offset
- `DELETE /api/v1/uploads/{id}` - 取消
- `POST /api/v1/inspect/{code}/from-upload/{id}` - finalize

**配置项 (V1.3 新增)**:
- `max_video_size` (已有, V1.3 真正生效)
- `tus_threshold` = 5MB
- `tus_chunk_size` = 5MB
- `upload_tmp_dir` = `./upload-tmp/`

**新数据表**: `upload_sessions` (alembic 006)

#### §18.3 客户端图片压缩 (V1.3 新增)

- 选完文件后立即压缩 (不等用户点提交)
- Canvas 等比缩放 + JPEG 0.85
- 长边 ≤ 1920px
- 跳过视频 / GIF / HEIC / SVG / ICO / 已 < 800KB

#### §18.4 文件大小按 file_type 分支 (V1.3 修 M1 bug)

| file_type | 限制 | 说明 |
|---|---|---|
| image | 20MB | 已有 (不变) |
| video | 500MB | V1.3 真正生效 (M1 用了 image 的 20MB) |
| other | 20MB | 兜底 |

#### §18.5 文档体系扩展 (V1.3 新增)

- `docs/superpowers/upload-protocol.md` - TUS 协议实现细节
- `docs/DEPLOYMENT.md` - 生产部署指南 (含 cpolar)

### V1.3 影响范围 (与 V1.2 兼容性)

- ✅ **后向兼容**: 旧的 `POST /api/v1/inspect/{code}` multipart 仍可用, 小文件 (< 5MB) 自动走该路径
- ✅ **客户端零侵入升级**: 用户刷新页面即用上 M2 能力, 旧浏览器无 HEIC 压缩但能透传
- ✅ **数据兼容**: 老的 `inspections` 表无 schema 变更, `upload_sessions` 是新表

### V1.3 未做 (留给 V1.4 / M3+)

- 直传 MinIO presigned multipart (绕过反代)
- 客户端视频 H.264 重编码
- S3 multipart 协议本地化 (dropbox-style)
- 跨会话秒传 (hash 去重)
﻿# 图像识别架构设计规范 V1.2

如对本规范有任何疑问或建议，请在评审记录表中填写，版本变更将通过变更记录表追溯。

### 13.7 未来集成说明（V1.2 新增）

本系统设计为可作为**大平台的子模块**独立部署。**鉴权、API 网关、多租户等横切关注点由大平台统一处理**，本系统仅实现核心业务能力。

| 能力 | 本系统是否做 | 由谁提供 |
|---|---|---|
| 用户鉴权（SSO/OAuth） | **不做** | 大平台 |
| API 网关（限速/熔断） | **不做** | 大平台 |
| 多租户隔离 | **不做** | 大平台 |
| 审计日志收集 | 本系统写本地文件 | 大平台集中采集 |
| 监控告警通道（钉钉/邮件） | 本系统只暴露 Prometheus 指标 | 大平台统一告警 |
| 文件存储（MinIO） | 本系统自管 | 并入时迁移到统一 OSS |
| 业务核心能力（识别/富化/报告） | **本系统做** | — |

**集成时**：
- 大平台网关统一代理到本系统 API
- `X-Inspector-Id` 等业务标识由大平台网关注入
- 本系统的 MinIO/PostgreSQL 迁移到大平台统一存储
- 监控指标对接大平台 Prometheus


# 图像识别架构设计规范 V1.2

> **项目名称**：GE-VIC 图像识别平台
> **文档版本**：1.2
> **编制日期**：2026-07-01
> **状态**：待多方评审
> **保密级别**：内部

---

## 0. 文档元信息

### 0.1 变更记录

| 版本 | 日期 | 变更内容 | 作者 |
|---|---|---|---|
| 1.0 | 2026-07-01 | 初稿，提交评审 | - |

**Prompt 模板**：V1.0 硬编码在代码内（V1.2 简化，prompt_versions 表 V2.0 评估）。
| 1.1 | 2026-07-01 | 评审前增补：① **取消鉴权**（端点由巡检员 App 内置写死，不由一线员工选择），§13 重写为"无鉴权模式"；② 增补**完整响应结构**（识别结果 + LLM 总结与建议 + 元数据身份），便于巡检员 App 解析，新增 §7.3.5；③ §6 数据模型新增 `llm_enrichment` JSONB 字段；④ §11 拆分为"逐条记录 LLM 富化（实时）"与"周期性 LLM 报告"两条路径；⑤ §1.3/§1.5 新增"无鉴权"与"响应自洽"目标和约束 | - |

### 0.2 评审记录

| 评审方 | 评审日期 | 评审人 | 结论 | 备注 |
|---|---|---|---|---|
| （待填写） | | | | |
| （待填写） | | | | |
| （待填写） | | | | |

### 0.3 关联文档

- （暂无，后续补充：API 详细规范、运维手册、测试报告等）

---

## 1. 项目背景与目标

### 1.1 业务背景

本项目服务于**基础设施巡检**业务领域，主要面向：

- **供配电设施**：变电站、配电柜、架空线路、绝缘子等
- **供水设施**：水管、阀门、水表、水池、水塔等
- **排水设施**：排水管道、检查井、泵站、化粪池等
- **建筑基础**：地基、桥墩、挡土墙、建筑外立面等

巡检员在日常巡检中会拍摄大量现场照片和视频，原始素材上传后需要借助图像识别算法进行缺陷、异常和状态的自动判定，识别结果需要长期存档以备追溯与复盘。

### 1.2 业务痛点

| 痛点 | 说明 |
|---|---|
| 人工判定效率低 | 大量素材靠人眼判读，效率低、标准不一 |
| 识别算法碎片化 | 不同设施类型需要不同算法，调用方式不统一 |
| 结果追溯困难 | 缺乏统一的存档与查询入口 |
| 缺乏智能化 | 原始识别结果未做聚合分析与决策建议 |
| 难以扩展 | 巡检覆盖范围扩大后，算法和接入点持续增加 |

### 1.3 设计目标

1. **固定工作流**：建立"上传 → 入队 → 识别 → 入库 → 统计 → 展示"的端到端固定流程，所有算法共享同一管线。
2. **算法可插拔**：每种识别算法对应一个固定 API 端点，算法增删通过**配置变更**完成，无需修改业务代码。
3. **引擎可适配**：算法底层引擎可灵活切换（云 API / 海康超脑 / 自建模型），算法注册表是路由与引擎的唯一真源。
4. **可查询**：每一条识别记录有唯一 ID、详细元数据、结构化结果，支持按时间、算法、位置、状态、资产等多维度查询。
5. **支持并发**：50–500 路并发上传、500–5 万条/天处理量，识别过程异步化、不阻塞上传。
6. **AI 增强分析**：基于 LLM 对识别记录做聚合统计、趋势分析、决策建议输出。
7. **本地可验证 / 云可部署**：先在本地 Docker Compose 跑通，云上可直接容器化部署。
8. **无鉴权模式**（V1.0 起）：本系统不实现用户级鉴权。API 端点由业务方分发的巡检员 App 内置写死，不由一线员工选择；安全边界由**网络层**（内网/VPN）与**App 分发渠道**（签名包、版本管控）共同保障。详细说明见 §13。
9. **定向返回完整结果**（V1.0 起）：对巡检员 App 的查询/上传响应，必须**一次性返回该图的完整识别结果 + LLM 总结与建议 + 完整元数据**，便于 App 解析后直接展示与归档，不要求 App 二次拼接。响应结构详见 §7.3.5。

### 1.4 非目标 (Non-Goals)

V1.0 版本**不包含**以下内容，避免范围蔓延：

- ❌ 实时视频流接入（RTSP/GB28181 拉流与抽帧）—— 后续版本考虑
- ❌ 摄像头/IoT 设备直接管理 —— 沿用现有海康超脑侧
- ❌ 巡检员移动端 App / 小程序 —— 沿用现有 App，本系统不重做
- ❌ 自研识别模型训练 —— 沿用云 API 或外接超脑
- ❌ 复杂的 RBAC / 多租户 —— V1.0 不实现用户鉴权（详见 §13）
- ❌ 视频内容审核 / 社交领域用法 —— 不在本系统范围

### 1.5 关键约束

| 约束 | 说明 |
|---|---|
| 技术栈要求 | 简单、稳定、生态成熟；优先 Python |
| 部署环境 | 本地 Docker Compose 验证 → 后续云部署 |
| 初期算法 | 1–2 个验证，后续扩到 40+ |
| LLM 接入 | 外部 API，OpenAI 兼容 chat 格式 |
| 开发平台 | Windows（开发机） |
| **不实现用户鉴权** | 端点由 App 内置，安全由网络边界 + App 分发保障（见 §13） |
| **响应必须自洽完整** | 巡检员 App 单次调用即可拿到该图的识别结果 + LLM 总结与建议 + 元数据，不依赖二次调用 |

### 1.6 V1.0 极简边界（新增，V1.2 评审决策）

V1.0 遵循"**先跑通、再完善**"原则，主动放弃以下特性以控制范围、保证 M0-M1 阶段 2 周可上线：

**不做（V1.0 边界外）**：
- ❌ 多用户/多租户/用户级鉴权（§13）
- ❌ 算法管理后台 UI、Prompt 模板版本化/灰度
- ❌ AI 对话（Function Calling）与流式响应
- ❌ 定时清理任务、灾备方案、冷存储归档
- ❌ Vue 之外的复杂前端方案（M0-M2 用 Vue 3 全家桶即可，详见 ADR-003）
- ❌ 缩略图自动生成、复杂文件签名 URL 机制
**Prompt 模板**：V1.0 硬编码在代码内（V1.2 简化，prompt_versions 表 V2.0 评估）。
- ❌ K8s Secret / KMS / mTLS / ELK / 文件杀毒
- ❌ 钉钉/邮件等告警通道（V1.0 只暴露 Prometheus 指标）

**原因**：
- 内部系统维护频率低，SQL/配置文件改一次的成本 < UI 建设成本
- 二阶段特性（M2 之后）的抽象层会让 V1.0 代码背负历史包袱
- 后续并入大系统时，这些横切关注点由大系统统一处理，本系统重做属于浪费

这些特性在 V2.0 或并入大系统时再统一评估。

### 1.7 V1.0 验收标准 SLO（新增）

| 指标 | 目标 | 测量方式 | 备注 |
|---|---|---|---|
| 单图识别 P95 延迟（含队列） | < 30s | Prometheus histogram | 视频按 N 帧聚合 |
| 上传接口 P95 延迟 | < 500ms | Prometheus histogram | 不含识别 |
| **系统层端到端成功率** | > 99.5% | `gevic_inspections_total{status}` | 不含引擎本身识别失败 |
| 系统可用性（工作时段 09:00-19:00） | > 99% | uptime 探针 | 约 6h/月停机可接受 |
| LLM 富化失败不影响主任务 | 100%（硬约束） | 集成测试断言 | `enrichment_status` 独立 |

**不做**：P99 / 99.9% / 多区域容灾 / 7×24 监控——内部系统负担不起云级 SLO。

---

## 2. 术语与缩略语

| 术语 | 解释 |
|---|---|
| 识别算法 (Algorithm) | 一种具体的图像识别能力，如"绝缘子破损识别" |
| 引擎 (Engine) | 识别算法底层的实现方式：云 API / 海康超脑 / 自建模型 |
| 算法注册表 (Algorithm Registry) | 数据库中存储"算法 ↔ 端点 ↔ 引擎 ↔ 配置"的表 |
| 巡检记录 (Inspection Record) | 一次上传+识别产生的完整数据，含原文件、识别结果、元数据 |
| 引擎适配器 (Engine Adapter) | 抽象不同识别引擎调用的统一接口层 |
| 海康超脑 (Hikvision Brain) | 海康威视边缘智能分析设备，部分识别可在其上完成 |
| LLM 报告 | 基于 LLM 对一段时间内识别记录的聚合分析输出 |

| 巡检员 (Inspector) | 现场使用 App 上传素材的工程人员 |
| 算法端点 (Algorithm Endpoint) | 系统为每个算法暴露的固定 HTTP API 路径 |

---

## 3. 系统概览

### 3.1 业务架构图

```
┌──────────────────────────────────────────────────────────────────┐
│                       巡检员 (Inspector)                          │
│                       使用现有 App 上传                            │
│              选算法 → POST 到对应 API 端点                        │
└──────────────────────┬───────────────────────────────────────────┘
                       │ HTTPS
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│                  GE-VIC 图像识别平台 (本系统)                     │
│                                                                  │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────────────┐  │
│  │  接入层 API  │──▶│  任务队列    │──▶│ 引擎适配器 (多引擎)  │  │
│  │ (FastAPI)    │   │  (Celery)    │   │ 云API / 海康超脑 /  │  │
│  └──────────────┘   └──────┬───────┘   │ 自建模型             │  │
│         │                  │            └──────────┬───────────┘  │
│         ▼                  ▼                       ▼              │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────────────┐  │
│  │ 对象存储     │   │  数据库      │   │ LLM 智能分析         │  │
│  │ (MinIO)      │   │ (PostgreSQL) │   │ (OpenAI 兼容 API)    │  │
│  └──────────────┘   └──────────────┘   └──────────────────────┘  │
│                       │                                           │
│                       ▼                                           │
│              ┌──────────────────┐                                 │
│              │  管理看板 (Web)  │  ◀── 统计 / 报告 / 详情        │
│              └──────────────────┘                                 │
└──────────────────────────────────────────────────────────────────┘
```

### 3.2 技术架构图（四层）

```
┌──────────────────────────────────────────────────────────────────┐
│ ① 接入层 (Ingest API) — FastAPI                                  │
│    - 固定通配路由 POST /api/v1/inspect/{algorithm_code}          │
│    - 算法注册表查询 + 文件校验（无鉴权, 见 §13）                            │
│    - 同步入库 + 异步投递 + 202 返回                              │
├──────────────────────────────────────────────────────────────────┤
│ ② 任务层 (Task Queue) — Celery + Redis                          │
│    - inspect_queue: 识别任务                                      │
│    - stats_queue: LLM 统计/分析任务（限速）                       │
│    - cleanup_queue: 定时清理/转储                                 │
│    - 支持重试、死信、状态追踪                                      │
├──────────────────────────────────────────────────────────────────┤
│ ③ 引擎层 (Engine Adapter) — 插件化                               │
│    - BaseEngine 抽象接口                                          │
│    - CloudVisionEngine (阿里云/腾讯云/百度/华为 视觉 API)         │
│    - HikvisionBrainEngine (海康超脑 HTTP/SDK)                     │
│    - LocalModelEngine (预留: 自建模型)                            │
│    - EngineFactory: 根据算法注册表 engine_type 实例化             │
├──────────────────────────────────────────────────────────────────┤
│ ④ 数据 + 智能层 (Storage + AI Stats)                              │
│    - PostgreSQL: 元数据 + 识别结果 + LLM 报告                     │
│    - MinIO: 原图/原视频对象存储                                   │
│    - LLM Service: OpenAI 兼容 chat API                           │
└──────────────────────────────────────────────────────────────────┘
```

### 3.3 端到端数据流（核心场景）

```
[巡检员 App]                                                        
   │  POST /api/v1/inspect/insulator-damage (file, meta)           
   ▼                                                             
[FastAPI 接入层]                                                 
   │  1. 查 algorithms 表 → 引擎配置（无鉴权, 见 §13）       
   │  2. 文件上传 MinIO → object_key                             
   │  3. inspections 表插入 PENDING 记录 → record_id             
   │  4. Celery 投递 inspect_queue{record_id, ...}                
   │  5. 202 Accepted {record_id, status: "PENDING"}             
   ▼                                                             
[Celery Worker]                                                  
   │  6. 从 MinIO 下载文件                                       
   │  7. engine.recognize() → 调 云API/超脑                      
   │  8. 更新 inspections: status=SUCCESS, result=JSONB          
   │  9. 失败 → 重试 3 次 → 死信 → status=FAILED               
   ▼                                                             
[管理看板 / 第三方系统]                                          
   │  GET /api/v1/records?algorithm=...&status=SUCCESS           
   │  GET /api/v1/records/{id}                                   
   │  POST /api/v1/stats/report (生成本周报告)                   

   ▼                                                             
[LLM Service]                                                    
   │  11. 聚合 SQL + 样本数据                                    
   │  12. 调 OpenAI 兼容 chat API                                
   │  13. 报告存 llm_reports / 流式响应给前端                     
   ▼                                                             
[看板 UI] — 图表 / 报告 / 详情                                
```

---

## 4. 核心设计理念

### 4.1 算法注册表驱动 (Algorithm-Registry-Driven)

系统所有"算法相关行为"完全由 `algorithms` 数据库表驱动：

- **端点路径**：`/api/v1/inspect/{code}` 中的 `{code}` 与 `algorithms.code` 严格对应
- **引擎选择**：`algorithms.engine_type` 决定调用哪个适配器
- **引擎配置**：`algorithms.engine_config` (JSONB) 传入适配器
- **请求 schema**：`algorithms.request_schema` (JSONB) 校验该算法的上传元数据

**新增算法 = 在 `algorithms` 表 INSERT 一行配置**。业务代码与 API 路由完全不变，下次启动/热加载即生效。

### 4.2 引擎适配器模式 (Engine Adapter Pattern)

所有识别引擎实现统一的 `BaseEngine` 抽象接口：

```python
class BaseEngine(ABC):
    @abstractmethod
    async def recognize(self, file: bytes, meta: dict, config: dict) -> RecognitionResult: ...
```

具体实现各自封装云 API / 海康超脑的调用细节。EngineFactory 根据 `engine_type` 实例化对应适配器。

**好处**：
- 新增引擎 = 实现 `BaseEngine` + 注册到 `ENGINE_REGISTRY`
- 测试时可替换为 MockEngine
- 同一算法可平滑从云 API 切换到超脑

### 4.3 异步任务化

上传与识别解耦：

- 上传接口只做"接文件 + 入队"，秒级返回 `202 Accepted`
- 识别在 Celery Worker 异步执行，客户端轮询或回调获取结果
- 上传与识别速度解耦 → 高并发不阻塞

### 4.4 数据/文件分离

| 关注点 | 存储 |
|---|---|
| 结构化数据（记录、结果、报告） | PostgreSQL |
| 二进制文件（原图/原视频） | MinIO（对象存储） |
| 临时缓存（Celery 队列状态） | Redis |

**好处**：
- PostgreSQL 不会被大文件拖慢
- MinIO 横向扩展容易，云上可平滑迁移到 S3/OSS/COS
- 文件去重（SHA256）天然支持

---


### 4.5 关键架构决策记录（ADR）

| 编号 | 决策 | 选择 | 备选 | 理由 |
|---|---|---|---|---|
| **ADR-001** | 任务队列 | Celery + Redis | RQ / Dramatiq | 生态成熟、文档全、招人易、坑少 |
| **ADR-002** | 对象存储 | MinIO（**单桶** `gevic`） | 本地盘 / 直接用云存储 | 后续易迁 S3/OSS，接口标准；子目录区分 |
| **ADR-003** | 前端技术栈 (M0-M2) | **Vue 3 + Vite + Element Plus + ECharts + Pinia + Vue Router** | FastAPI 模板 + HTMX | 用户决策：完整方案；再评估时机 = AI 对话(SSE)/复杂大屏需求出现时 |
| **ADR-004** | LLM 厂商 | **全环境变量配置**（`base_url` / `api_key` / `model` / `max_input_tokens` / `max_output_tokens`） | 硬编码单一厂商 | 用户决策：自行配置；任何 OpenAI 兼容 API；无任何默认值硬编码 |
| **ADR-005** | 富化触发位置 | Celery 任务内同步调用 | 独立队列 | 失败隔离、流程简单，后续可拆 |
| **ADR-006** | 算法注册表刷新 | 启动加载 + 滚动重启 | LISTEN/NOTIFY / Redis pub/sub | 内部改算法月级，省 2-3 天开发量 |
| **ADR-007** | 前端再评估时机 | AI 对话(SSE) / 复杂大屏需求出现时 | 仅业务量增长 | 触发条件与"前端能力边界"挂钩，与"算法数量"解耦 |

**ADR 变更规则**：任何对上述决策的修改需更新本表 + 重新评审。

---
## 5. 模块详细设计

### 5.1 接入层 (Ingest API)

**职责**：
- 接收上传请求（**无鉴权**，详见 §13）
- 校验算法 code 与元数据
- 落盘文件（MinIO）
- 写入 inspections 记录（status=PENDING）
- 投递 Celery 任务
- 同步返回 `record_id` 与初始元数据

**关键路径**：

| 方法 | 路径 | 用途 |
|---|---|---|
| POST | `/api/v1/inspect/{algorithm_code}` | **核心**：算法对应上传入口 |
| POST | `/api/v1/upload` | 简单验证上传（管理端/开发者） |
| GET | `/api/v1/algorithms` | 列出所有已注册算法 |
| GET | `/api/v1/records` | 多条件查询 |
| GET | `/api/v1/records/{id}` | 单条详情 |
| POST | `/api/v1/records/{id}/retry` | 失败重试 |
| GET | `/api/v1/health` | 健康检查 |

**请求格式**（multipart/form-data）：

```
POST /api/v1/inspect/insulator-damage
Headers:
  X-Inspector-Id: <inspector_id>      # 巡检员标识（必填, 用于结果回溯）
  X-Request-Id:   <uuid>              # 可选, 链路追踪
Body (multipart):
  file: <binary>                       # 必填, 1 张图或 1 个视频
  meta: <JSON string>                  # 可选, 业务元数据
        {
          "asset_id": "BJ-SUBSTATION-001",
          "location": {"lat": 39.9, "lng": 116.4},
          "remark": "雨后巡检"
        }
```

> **说明**：本系统**不实现用户鉴权**（详见 §13）。`X-Inspector-Id` 仅用于结果回溯与责任标识，不做权限校验。

**响应（成功 202）**：

```json
{
  "record_id": 1024,
  "algorithm_code": "insulator-damage",
  "status": "PENDING",
  "created_at": "2026-07-01T10:00:00Z",
  "status_url": "/api/v1/records/1024"
}
```

### 5.2 算法注册表 (Algorithm Registry)

详细结构见 §6.2 与 §8。本节强调行为：

- **查询时机**：每次 POST 上传前 + Celery 任务执行时
- **缓存**：启动时加载到内存字典（`{code: AlgorithmRow}`），`updated_at` 变更触发热刷新
- **版本**：`engine_config.version` 字段支持配置灰度

### 5.3 引擎适配器 (Engine Adapter)

接口定义见 §9.1。本节强调设计原则：

- **超时与重试**：适配器内部实现，统一 3 次重试 + 指数退避
- **错误归一化**：所有引擎返回 `RecognitionResult`，包含 `success / data / error_code / error_message`
- **可观测**：每次调用记录耗时、token/cost、HTTP status

### 5.4 任务队列 (Task Queue)

Celery 架构，三类队列：

| 队列 | 用途 | 并发 | 限速 |
|---|---|---|---|
| `inspect_queue` | 识别任务 | 4–16 worker（按 CPU/网络调整） | 无 |
| `stats_queue` | LLM 任务 | 2 worker | 10/min（防 LLM 限流） |
| `cleanup_queue` | 定时清理 | 1 worker | - |

**任务签名**：

```python
@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def run_inspection(self, record_id: int):
    ...
```

**重试策略**：指数退避 10s → 30s → 90s，超过 3 次入死信队列 + 标记 `FAILED`。



**临时文件策略**（V1.2 增补）：
- Worker 从 MinIO 下载文件到 `tempfile.NamedTemporaryFile(delete=False)` 创建的本地文件
- 任务完成后 `try/finally` 显式删除
- 失败重试时重新下载（简单可靠）
- **不引复杂的临时文件管理库**
### 5.5 数据持久层

- **ORM**：SQLAlchemy 2.x（异步）
- **迁移**：Alembic
- **连接池**：asyncpg，pool_size=20
- **事务边界**：单条记录写入用 `BEGIN ... COMMIT`，跨表操作放同一事务

### 5.6 LLM 智能分析模块

**两类输出**：

1. **结构化报告**（POST `/api/v1/stats/report`）
   - 输入：时间窗 + 算法范围 + 报告类型
   - 后端聚合 SQL + 抽取 10–30 条样本
   - 组装 Prompt → 调 LLM → 存 `llm_reports`
   - 输出：Markdown + 结构化 JSON（总结/分析/建议）


**Prompt 模板**：V1.0 硬编码在代码内（V1.2 简化，prompt_versions 表 V2.0 评估）。

### 5.7 管理看板 (Admin Web)

**Vue 3 + Vite + Element Plus + ECharts**

**页面**：

| 页面 | 功能 |
|---|---|
| 仪表盘 | 核心指标卡 + 趋势图 + 告警列表 |
| 记录查询 | 表格 + 筛选 + 详情抽屉（含原图预览、识别结果 JSON、LLM 总结） |
| 算法管理 | CRUD 算法注册表（暂用 SQL 脚本或简易管理界面） |
| 报告中心 | 报告列表 + 详情 + 触发新报告 |
| AI 助手 | 对话界面（SSE 流式 + Markdown 渲染） |
| 系统设置 | LLM 配置、队列状态、引擎健康 |

**简单上传**：单独页面，仅供验证用，含算法下拉 + 文件选择 + 提交。

---

## 6. 数据模型

### 6.1 ER 图

```
┌──────────────┐         ┌──────────────────┐
│  algorithms  │◀────────│   inspections    │
│              │  1:N    │                  │
│  id (PK)     │         │  id (PK)         │
│  code (UQ)   │         │  algorithm_code  │
│  name        │         │  status          │
│  category    │         │  object_key      │
│  engine_type │         │  file_hash       │
│  engine_cfg  │         │  request_meta    │
│  ...         │         │  result (JSONB)  │
└──────────────┘         │  asset_id        │
                         │  inspector_id    │
                         │  created_at      │
                         └────────┬─────────┘
                                  │
                                  │ 1:N
                                  ▼
                         ┌──────────────────┐
                         │  llm_reports     │
                         │  (按 scope 引用) │
                         └──────────────────┘

┌──────────────────┐    ┌────────────────────┐
```


#### 6.1.1 inspections 状态机（V1.2 新增）

```
主任务 (status):
  PENDING → RUNNING → SUCCESS
                   → FAILED (可重试, 自动重试 ≤ 3 次)
                   → DEAD   (超过 max_retries, 需手动干预)

LLM 富化 (enrichment_status, 独立流转):
  NONE → ENRICHING → ENRICHED
                 → ENRICH_FAILED (可单独重试)
```

**关键约束**：
- 重试期间 `status = RUNNING`（前端展示"识别中"，**不引入**独立的 `RETRYING` 状态）
- `status`（主任务）与 `enrichment_status`（LLM 富化）是**两个独立维度**
- 富化失败时，主 `status` 仍为 `SUCCESS`，`enrichment_status` 为 `ENRICH_FAILED`
- `DEAD` 状态记录 `error_message` 供排查，前端显示"重试"按钮调用 `/records/{id}/retry`
### 6.2 表结构 (PostgreSQL 16+)

```sql
-- 6.2.1 算法注册表
CREATE TABLE algorithms (
    id              BIGSERIAL PRIMARY KEY,
    code            VARCHAR(64) UNIQUE NOT NULL,
    name            VARCHAR(128) NOT NULL,
    category        VARCHAR(64),
    description     TEXT,
    engine_type     VARCHAR(32) NOT NULL,         -- 'cloud_api' | 'hikvision_brain' | 'local_model'
    engine_config   JSONB NOT NULL,               -- 引擎配置: API key/url/model, 超脑 ip/port/cred, ...
    request_schema  JSONB,                        -- 额外上传字段的 JSON Schema
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    version         INT NOT NULL DEFAULT 1,       -- 配置版本, 灰度
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_algorithms_active ON algorithms(is_active);
CREATE INDEX idx_algorithms_category ON algorithms(category);

-- 6.2.2 识别记录表
CREATE TABLE inspections (
    id              BIGSERIAL PRIMARY KEY,
    algorithm_code  VARCHAR(64) NOT NULL,
    category        VARCHAR(64),
    status          VARCHAR(16) NOT NULL,         -- 'PENDING' | 'RUNNING' | 'SUCCESS' | 'FAILED'
    object_key      VARCHAR(256),                 -- MinIO 路径
    file_hash       VARCHAR(64),                  -- SHA256
    file_size       BIGINT,
    file_type       VARCHAR(16),                  -- 'image' | 'video'
    request_meta    JSONB,                        -- 上传时附带的元数据
    result          JSONB,                        -- 识别结果 (结构化, 由引擎返回)
    summary         TEXT,                         -- 引擎生成的一句话总结 (可选)
    llm_enrichment  JSONB,                        -- LLM 富化: {summary, recommendations, model, prompt_version, token_used, generated_at}
    enrichment_status VARCHAR(16),                 -- 枚举: NONE / RUNNING / SUCCESS / FAILED
    error_message   TEXT,
    error_code      VARCHAR(64),
    retry_count     INT NOT NULL DEFAULT 0,
    inspector_id    VARCHAR(64),                  -- 巡检员标识
    location        JSONB,                        -- GPS / 资产位置
    asset_id        VARCHAR(64),                  -- 关联资产
    duration_ms     INT,                          -- 识别耗时
    cost_estimate   NUMERIC(10,6),                -- 单次识别估算成本 (云 API 调用等)
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_insp_alg ON inspections(algorithm_code);
CREATE INDEX idx_insp_status ON inspections(status);
CREATE INDEX idx_insp_created ON inspections(created_at DESC);
CREATE INDEX idx_insp_inspector ON inspections(inspector_id);
CREATE INDEX idx_insp_asset ON inspections(asset_id);
CREATE INDEX idx_insp_result_gin ON inspections USING GIN (result);
CREATE INDEX idx_insp_meta_gin ON inspections USING GIN (request_meta);

-- 6.2.3 LLM 报告表
CREATE TABLE llm_reports (
    id              BIGSERIAL PRIMARY KEY,
    title           VARCHAR(256) NOT NULL,
    report_type     VARCHAR(32) NOT NULL,         -- 'summary' | 'analysis' | 'recommendation' | 'comprehensive'
    scope           JSONB NOT NULL,               -- {algorithm_codes, start_at, end_at, asset_ids, ...}
    prompt_version  VARCHAR(32) NOT NULL,
    content_md      TEXT NOT NULL,                -- Markdown 报告
    content_json    JSONB,                        -- 结构化: {summary, analysis, recommendations, key_findings}
    sample_count    INT,                          -- 参与聚合的样本数
    token_used      INT,
    cost_usd        NUMERIC(10,6),
    duration_ms     INT,
    created_by      VARCHAR(64),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_reports_type ON llm_reports(report_type);
CREATE INDEX idx_reports_created ON llm_reports(created_at DESC);

-- 6.2.4 审计日志（V1.2 新增, 事后追责用, 取代原 chat_* 表）
CREATE TABLE audit_logs (
    id              BIGSERIAL PRIMARY KEY,
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    actor           VARCHAR(64) NOT NULL,
    action          VARCHAR(32) NOT NULL,
    resource_type   VARCHAR(32) NOT NULL,
    resource_id     VARCHAR(64),
    source_ip       INET,
    user_agent      VARCHAR(256),
    request_id      VARCHAR(64),
    request_meta    JSONB,
    result          VARCHAR(16) NOT NULL,
    error_code      VARCHAR(64)
);
CREATE INDEX idx_audit_actor ON audit_logs(actor, occurred_at DESC);
CREATE INDEX idx_audit_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX idx_audit_action ON audit_logs(action, occurred_at DESC);

-- 注: 原 §6.2.5 engine_calls 表保留（运维排障用, 区别于审计日志）

-- 6.2.5 引擎调用审计 (可选, V1.0 简化)
CREATE TABLE engine_calls (
    id              BIGSERIAL PRIMARY KEY,
    record_id       BIGINT REFERENCES inspections(id) ON DELETE CASCADE,
    engine_type     VARCHAR(32) NOT NULL,
    engine_endpoint VARCHAR(256),
    http_status     INT,
    latency_ms      INT,
    request_payload JSONB,
    response_payload JSONB,
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_engine_calls_record ON engine_calls(record_id);
```

### 6.3 索引策略

- **时间范围查询**：`created_at` 倒序索引
- **算法维度**：`(algorithm_code, created_at DESC)` 复合索引（V1.1 优化）
- **状态看板**：`status` 索引
- **结果模糊查询**：`result` / `request_meta` 用 GIN
- **资产/位置维度**：`asset_id` 索引

### 6.4 数据生命周期

| 数据 | 保留期 | 清理策略 |
|---|---|---|
| `inspections` 元数据 | 永久 | 不清理 |
| MinIO 原文件 | 至少 1 年（按合规） | 定时任务转储到冷存储 |
| `engine_calls` 审计 | 90 天 | 定时清理 |
| `audit_logs` | 永久 | 不清理（合规要求） |
| Celery 任务结果 | 不保留 | 无 result_backend，状态走 DB |

---

## 7. API 规范

### 7.1 设计原则

- RESTful 风格 + 统一前缀 `/api/v1`
- 全部 JSON 通信（除上传外）
- Pydantic 模型校验 + 自动 OpenAPI 文档 (`/docs`)
- 错误码统一格式（见 §7.4）
- 鉴权：Bearer Token (API Key) → 后续可升级 OAuth2/JWT

### 7.2 端点清单

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/health` | 健康检查（DB/Redis/MinIO） |
| POST | `/api/v1/inspect/{algorithm_code}` | **核心**：算法对应上传 |
| POST | `/api/v1/upload` | 简单验证上传 |
| GET | `/api/v1/algorithms` | 列出算法 |
| GET | `/api/v1/algorithms/{code}` | 算法详情 |
| GET | `/api/v1/records` | 多条件查询（分页） |
| GET | `/api/v1/records/{id}` | 单条详情 |
| POST | `/api/v1/records/{id}/retry` | 失败重试 |
| GET | `/api/v1/records/{id}/file` | 获取原文件签名 URL |
| POST | `/api/v1/stats/report` | 生成 LLM 报告 |
| GET | `/api/v1/stats/reports` | 报告列表 |
| GET | `/api/v1/stats/reports/{id}` | 报告详情 |
| GET | `/api/v1/stats/aggregate` | 纯统计聚合（看板用，不调 LLM） |
| POST | `/api/v1/records/{id}/enrich` | 触发 LLM 富化重试（V1.2 新增） |





### 7.3 核心端点详述

#### 7.3.1 POST /api/v1/inspect/{algorithm_code}

**Request**（multipart/form-data）：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| file | binary | 图片或视频 |
| meta | string (JSON) | 业务元数据，参考 `algorithms.request_schema` |
| inspector_id | string | 巡检员 ID（也可放 Header） |
| asset_id | string | 资产 ID（也可放 meta） |

**Response 202**：

```json
{
  "record_id": 1024,
  "algorithm_code": "insulator-damage",
  "status": "PENDING",
  "created_at": "2026-07-01T10:00:00Z",
  "status_url": "/api/v1/records/1024"
}
```

**Response 4xx**：

| 状态码 | 错误码 | 含义 |
|---|---|---|
| 400 | `INVALID_ALGORITHM` | algorithm_code 不存在或未启用 |
| 400 | `INVALID_FILE` | 文件类型/大小不符 |

| 413 | `FILE_TOO_LARGE` | 超过大小限制 |
| 429 | `RATE_LIMITED` | 触发限流 |
| 500 | `INTERNAL_ERROR` | 系统异常 |

#### 7.3.2 GET /api/v1/records

**Query Params**：

| 参数 | 类型 | 说明 |
|---|---|---|
| algorithm_code | string | 精确 |
| category | string | 精确 |
| status | string | 多选逗号分隔 |
| asset_id | string | 精确 |
| inspector_id | string | 精确 |
| start_at | ISO8601 | 起始时间 |
| end_at | ISO8601 | 结束时间 |
| keyword | string | 全文检索 (file_hash / asset_id / summary) |
| page | int | 默认 1 |
| page_size | int | 默认 20, 最大 200 |

**Response**：

```json
{
  "items": [
    {
      "id": 1024,
      "algorithm_code": "insulator-damage",
      "category": "供配电",
      "status": "SUCCESS",
      "asset_id": "BJ-SUBSTATION-001",
      "inspector_id": "INSP-001",
      "result": { "defects": [{"type": "破损", "confidence": 0.92, "bbox": [10,20,100,200]}] },
      "summary": "检测到 1 处绝缘子破损，置信度 92%",
      "created_at": "2026-07-01T10:00:00Z",
      "finished_at": "2026-07-01T10:00:08Z",
      "duration_ms": 8200,
      "file_url": "https://minio.../signature-url"
    }
  ],
  "total": 12345,
  "page": 1,
  "page_size": 20
}
```

#### 7.3.3 POST /api/v1/stats/report

**Request**：

```json
{
  "report_type": "comprehensive",
  "scope": {
    "algorithm_codes": ["insulator-damage", "transformer-overheat"],
    "category": "供配电",
    "start_at": "2026-06-24T00:00:00Z",
    "end_at": "2026-07-01T00:00:00Z",
    "asset_ids": null
  },
  "title": "本周供配电巡检报告"
}
```

**Response 200**（同步模式）：

```json
{
  "report_id": 88,
  "title": "本周供配电巡检报告",
  "content_md": "## 总结\n...",
  "content_json": {
    "summary": "...",
    "analysis": ["...", "..."],
    "recommendations": ["...", "..."],
    "key_findings": [{"asset_id": "...", "issue": "...", "severity": "high"}]
  },
  "token_used": 4280,
  "cost_usd": 0.0128,
  "duration_ms": 18500
}
```

**Response 202**（异步模式）：返回 `job_id`，前端轮询。

### 7.4 错误码统一格式

```json
{
  "error": {
    "code": "INVALID_ALGORITHM",
    "message": "算法 code 'foo' 不存在或未启用",
    "details": { "available_codes": ["insulator-damage", "pipe-leakage"] },
    "request_id": "uuid"
  }
}
```

---

## 8. 算法注册表与配置

### 8.1 新增算法流程

```
1. 准备引擎配置
   - 云 API: 申请/获取 API key, 选择模型, 记录 endpoint
   - 海康超脑: 确认超脑型号/IP/账号密码, 确认其支持的目标算法

2. 在 algorithms 表 INSERT 一行
   - code: 端点路径段, 短横线连接 (e.g. "insulator-damage")
   - name: 中文名
   - category: 供配电/供水/排水/建筑基础
   - engine_type: 'cloud_api' | 'hikvision_brain'
   - engine_config: 见 §8.3 示例
   - request_schema: 该算法需要的额外字段 (e.g. {"properties": {"voltage_level": {"type": "string"}}})
   - is_active: true

3. (可选) 验证
   - 调用 GET /api/v1/algorithms/{code} 确认能查到
   - 调用 POST /api/v1/inspect/{code} 上传一张测试图

4. 完工
   - 后续 API/前端无需任何改动, 新端点自动可用
```

**V1.1 增强**：通过管理看板的"算法管理"页面完成 CRUD，无需直接写 SQL。

### 8.2 配置示例

#### 8.2.1 阿里云视觉智能（绝缘子破损）

```json
{
  "code": "insulator-damage",
  "name": "绝缘子破损识别",
  "category": "供配电",
  "engine_type": "cloud_api",
  "engine_config": {
    "provider": "aliyun",
    "endpoint": "https://vision.aliyuncs.com",
    "action": "RecognizeInsulatorDamage",
    "access_key_id": "<from-secret>",
    "access_key_secret": "<from-secret>",
    "model_version": "v2",
    "timeout_sec": 30,
    "retry": 3
  },
  "request_schema": {
    "type": "object",
    "properties": {
      "voltage_level": { "type": "string", "enum": ["10kV", "35kV", "110kV", "220kV"] }
    }
  }
}
```

#### 8.2.2 海康超脑（安全帽佩戴）

```json
{
  "code": "helmet-detection",
  "name": "安全帽佩戴检测",
  "category": "建筑基础",
  "engine_type": "hikvision_brain",
  "engine_config": {
    "device_ip": "192.168.1.100",
    "device_port": 443,
    "username": "admin",
    "password": "<from-secret>",
    "protocol": "https",
    "api_path": "/ISAPI/Intelligent/analysisTask",
    "task_type": "file_upload",
    "poll_interval_sec": 2,
    "poll_timeout_sec": 60,
    "result_event_webhook": "https://ge-vic.local/api/v1/webhooks/hikvision"
  },
  "request_schema": null
}
```

---

## 9. 引擎适配器

### 9.1 接口规范

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Any

@dataclass
class RecognitionResult:
    success: bool
    data: Optional[dict]            # 引擎返回的结构化数据
    summary: Optional[str]          # 一句话总结
    error_code: Optional[str]
    error_message: Optional[str]
    raw_response: Optional[Any]     # 原始响应 (供审计/调试)
    cost_estimate: Optional[float]  # 估算成本
    duration_ms: Optional[int]

class BaseEngine(ABC):
    engine_type: str  # 子类指定

    @abstractmethod
    async def recognize(
        self,
        file_bytes: bytes,
        filename: str,
        meta: dict,
        config: dict,         # algorithms.engine_config
    ) -> RecognitionResult: ...

    @abstractmethod
    async def health_check(self, config: dict) -> bool: ...
```

### 9.2 CloudVisionEngine

**职责**：封装云厂商视觉 API（阿里云、腾讯云、百度、华为等）的调用。

**实现要点**：
- 通过 `config.provider` 分发到不同的云 SDK 适配器
- 统一签名、超时、错误归一化
- 把云返回的检测结果（`defects / labels / bbox / confidence`）归一为统一结构

**支持的 provider**（V1.0）：
- `aliyun` — 阿里云视觉智能开放平台
- `tencent` — 腾讯云 AI 视觉
- `baidu` — 百度智能云
- (V1.1+) `huawei`, `azure`, `aws`

### 9.3 HikvisionBrainEngine

**职责**：调用海康超脑对上传文件进行识别。

**实现要点**：
- 通过 HTTP/HTTPS 调海康 ISAPI（或 SDK）
- **关键点**：超脑主要设计用于"摄像头实时流"分析，**对任意文件做离线性分析的能力依赖具体型号**。本系统在 V1.0 阶段会预留该适配器，但实际可用性需在 M3 阶段针对实际超脑型号做 PoC 验证。
- 文件上传到超脑后，任务以**异步**方式执行：超脑返回 `task_id`，本系统轮询或接收 webhook 获取结果
- 错误码与超时由超脑侧定义，做归一化映射

**PoC 任务（M3）**：
- 在内网搭一台超脑（或使用已有超脑）
- 选取 1–2 个简单算法（如安全帽佩戴、烟火检测）验证文件级分析可行性
- 验证 webhook / 轮询两种取结果方式

### 9.4 LocalModelEngine (预留)

V1.0 仅保留接口，不做实现。后期可对接：
- ONNX Runtime 加载本地模型
- Triton Inference Server
- TorchServe

### 9.5 EngineFactory

```python
ENGINE_REGISTRY: dict[str, type[BaseEngine]] = {
    "cloud_api": CloudVisionEngine,
    "hikvision_brain": HikvisionBrainEngine,
    "local_model": LocalModelEngine,
}

def get_engine(engine_type: str) -> BaseEngine:
    cls = ENGINE_REGISTRY[engine_type]
    return cls()
```

---

## 10. 任务队列与并发

### 10.1 Celery 配置

```python
# celery_config.py (摘要)
broker_url = "redis://redis:6379/0"
# result_backend: V1.0 不需要（任务结果走 DB, 状态可查 inspections 表）

task_routes = {
    "app.tasks.run_inspection": {"queue": "inspect_queue"},
    "app.tasks.run_llm_report": {"queue": "stats_queue"},

    "app.tasks.cleanup":         {"queue": "cleanup_queue"},
}

task_annotations = {
    "app.tasks.run_inspection": {"rate_limit": "200/m"},
    "app.tasks.run_llm_report": {"rate_limit": "10/m"},

}
```

### 10.2 启动命令

```bash
# 单 worker 多队列 (V1.2 简化)
celery -A app.worker worker \
  -Q inspect_queue,stats_queue,cleanup_queue \
  --concurrency=8 \
  -l info

# V1.0 不需要 beat (无定时任务)
```

### 10.3 重试与死信

```python
@celery_app.task(
    bind=True,
    max_retries=3,
    autoretry_for=(EngineTimeoutError, EngineRateLimitError),
    retry_backoff=True,
    retry_backoff_max=90,
    retry_jitter=True,
)
def run_inspection(self, record_id: int):
    try:
        ...
    except (EngineTimeoutError, EngineRateLimitError) as e:
        raise self.retry(exc=e)
    except Exception as e:
        # 不可重试错误 → 直接标记 FAILED
        mark_failed(record_id, str(e))
```

**死信处理**：超过 `max_retries` 后投递到 `dlq` + 写 `inspections.error_message`，前端可见"重试"按钮。

### 10.4 并发与背压

- **上传端限速**：API 网关或 FastAPI 中间件，**按 IP 限速**（如 100 req/min, 与 §13.4 一致）
- **Worker 弹性**：Celery 进程数可调，K8s 部署时按 HPA 扩缩
- **队列堆积告警**：监控 `inspect_queue` 长度，超阈值告警

---

## 11. LLM 智能分析

### 11.1 LLM 选型（外部 API, OpenAI 兼容 chat）

- **接入方式**：OpenAI 兼容 chat completions API
- **可选厂商**（可配置切换）：
  - OpenAI（gpt-4o-mini / gpt-4o）
  - 通义千问（qwen-plus / qwen-max）
  - DeepSeek（deepseek-chat / deepseek-reasoner）
  - 智谱 GLM（glm-4-plus）
  - 字节豆包
- **V1.0 配置**：通过环境变量 `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` 切换
- **数据隐私**：本系统不向 LLM 发送原图/原视频，**只发送结构化数据 + 必要时的小样本文本描述**

### 11.2 Prompt 模板（V1.0 样例）

#### 11.2.1 报告生成模板（comprehensive）

```markdown
你是一名资深的城市基础设施巡检分析师。请基于以下巡检识别数据,产出结构化分析报告。

# 任务范围
- 报告类型: {{report_type}}
- 时间窗口: {{start_at}} 至 {{end_at}}
- 涉及算法: {{algorithm_codes}}
- 涉及分类: {{category}}
- 涉及资产: {{asset_ids}}

# 聚合统计
{{aggregated_stats}}

# 典型样本 (前 20 条)
{{sample_records}}

# 输出要求 (Markdown 格式)
## 一、总结 (200 字以内)
## 二、问题分析 (分点列出, 含趋势和异常)
## 三、处置建议 (按优先级排序, 给出具体行动)
## 四、关键发现 (高亮重点资产/隐患)

请用中文输出, 数字要有依据, 建议要可执行。
```

### 11.3 逐条记录 LLM 富化（实时，V1.0 必选）

**核心流程**：每条识别记录 `inspections` 在引擎识别成功后，**同一 Celery 任务内**再调用一次 LLM，对该单条结果生成"一句话总结 + 处置建议"，写入 `inspections.llm_enrichment`（JSONB）。

**触发位置**：`run_inspection` Celery 任务，识别成功后立即调用。

**输入 Prompt 模板（per_record_enrichment）**：

```markdown
你是一名资深的城市基础设施巡检员。基于以下**单条**识别结果，给出一句话总结和最多 3 条处置建议。

# 巡检背景
- 设施类型: {{category}}
- 识别算法: {{algorithm_name}}
- 巡检员: {{inspector_id}}
- 资产: {{asset_id}}
- 位置: {{location}}

# 识别结果
{{recognition_result_json}}

# 输出要求
## 一句话总结 (100 字以内)
## 处置建议 (1-3 条, 按优先级, 可执行)
```

**输出 Schema**（写入 `llm_enrichment` JSONB）：

```json
{
  "summary": "检测到 1 处绝缘子破损（高置信度 92%），位于图像右上区域。",
  "recommendations": [
    "建议立即安排现场核查并更换破损绝缘子",
    "对同类批次设备进行专项巡检"
  ],
  "model": "qwen-plus",
  "prompt_version": "per_record_v1.0",
  "token_used": 380,
  "generated_at": "2026-07-01T10:00:12Z"
}
```

**失败处理**：
- LLM 调用失败 → 重试 2 次（指数退避）
- 仍失败 → `enrichment_status = FAILED`，`llm_enrichment = null`，**不影响主任务 SUCCESS**
- App 端可通过 `enrichment_status` 字段感知"识别有结果但 LLM 富化失败"
- 提供独立接口 `POST /api/v1/records/{id}/enrich` 触发重试

**成本控制**：
- 输入 token 上限 1500，输出 token 上限 500
- 单次估算 ¥0.001-¥0.01（视厂商）
- 限速：与 `stats_queue` 共用 10 req/min

**与周期性报告的区别**：

| 维度 | 逐条富化（§11.3） | 周期性报告（§11.4） |
|---|---|---|
| 输入 | 单条记录 | 聚合统计 + 样本 |
| 触发 | 实时（识别成功后） | 按需 / 定时 |
| 用途 | App 直接展示给巡检员 | 管理决策 / 周报 |
| 频率 | 每条 1 次 | 周报/月报 |
| Prompt 长度 | 短（单条） | 长（聚合 + 多样本） |





### 11.4 报告生成流程（周期性 / 按需）

```
1. 用户在看板选择: 报告类型 + 时间窗 + 算法/分类/资产
2. POST /api/v1/stats/report (sync=true 立即返回 / async 投递)
3. 后端:
   a. 查 DB 聚合: 状态分布、问题分布、TOP 资产、TOP 巡检员
   b. 抽取 10–30 条代表性样本 (按 result 严重度 + 时间分布采样)
   c. 组装 Prompt
   d. 调 LLM API (限速 10/min, 超时 60s)
   e. 解析响应 (Markdown + 尝试解析 JSON)
   f. 存 llm_reports
4. 前端: 同步模式直接渲染 / 异步模式轮询
```

### 11.5 成本与限速

- **每日 token 上限**（环境变量 `LLM_DAILY_TOKEN_LIMIT`，默认 5M）
- **每分钟请求数**（Celery rate_limit，默认 10/m）
- **报告生成频率限制**（同一 scope 5 分钟内不重复生成）
- **每次报告预估**：输入 ~3K tokens，输出 ~2K tokens
- **成本追踪**：`llm_reports.cost_usd` + `inspections.llm_enrichment.token_used`

---

## 12. 存储策略（V1.2 简化）

### 12.1 MinIO 单桶设计

- **桶名**：`gevic`（V1.2 改为单桶，ADR-002）
- **访问策略**：私有，仅内网访问
- **目录结构**：`inspections/{yyyy}/{mm}/{dd}/{record_id}/{filename}`
- V1.0 不引冷存储 / 缩略图 / 多桶

### 12.2 文件命名

```
gevic/inspections/2026/07/01/1024/photo.jpg
```

**去重**：`file_hash` (SHA256) 唯一索引，重复上传直接复用。

### 12.3 文件访问

- V1.0 用 **Nginx 反向代理 + 简单 token**（不走 S3 签名 URL）
- Token 有效期 15 分钟
- 前端通过 `GET /api/v1/records/{id}/file` 获取访问 URL
- 不引复杂的签名 URL 机制

### 12.4 保留与清理

- 至少保留 1 年（合规要求）
- V1.0 **不引冷存储 / 定时清理**（手动清理即可）

---

## 13. 认证与授权 — 无鉴权模式

### 13.1 设计决策

**V1.0 起，本系统不实现用户级鉴权（API Key / OAuth / JWT 等均不做）**。

**依据**：
- 巡检员 App 的端点是**内置写死**的，不由一线员工选择
- 端点对外不可见，App 通过业务方自有渠道（应用市场、内部分发）下发
- 巡检员无能力直接访问 API，也无法选择调用哪个端点

### 13.2 安全假设

系统的安全边界由以下三层保障，**任一被突破均视为不可接受风险**：

| 层级 | 保障措施 | 责任方 |
|---|---|---|
| **网络层** | 部署在内网 / VPN / 仅办公网可达；不开公网 | 运维 / 网络 |
| **应用层** | 巡检员 App 由业务方打包签名、版本号管控、吊销机制 | App 业务方 |
| **传输层** | HTTPS（TLS 1.2+），证书由内部 CA 签发 | 运维 |

### 13.3 唯一标识 — `X-Inspector-Id`

- `X-Inspector-Id` 是**业务回溯标识**，**非鉴权**
- 来自巡检员 App，由 App 内登录态决定，不由系统校验
- 仅用于：日志关联、记录归属、统计回溯

### 13.4 限速（V1.0）

按**来源 IP** 限速（兜底，防止 App 端逻辑失控）：
- 单 IP：100 req/min（可调）
- 触发后返回 `429 RATE_LIMITED`

### 13.5 何时升级鉴权

下列任一情况出现，需重新评估并升级为 API Key + 鉴权方案：
- 巡检员 App 渠道开放（公网下载 / 多渠道分发）
- 出现多租户需求（不同巡检公司共用系统）
- API 被开放给第三方系统
- 出现安全事件（未授权访问）

### 13.6 不做什么（明确边界）

- ❌ 不实现用户注册/登录
- ❌ 不实现密码/OAuth/JWT
- ❌ 不实现 RBAC / 细粒度权限
- ❌ 不实现 API Key 签发管理界面
- ❌ 不实现租户隔离

---

## 14. 错误处理与可观测性

### 14.1 错误分类

| 类别 | 处理 |
|---|---|
| 4xx 客户端错误 | 直接返回，明确错误码 |
| 引擎 5xx / 超时 | Celery 重试 3 次，指数退避 |
| 引擎 4xx（如参数错）| 标记 FAILED，不重试 |
| LLM 429 / 5xx | Celery 重试 2 次 |
| LLM 4xx（Prompt 错）| 标记 FAILED |
| DB / MinIO 故障 | 立即标记 FAILED + 告警 |

### 14.2 日志

- **结构化日志**：JSON 格式，`request_id` 贯穿
- **日志库**：loguru / structlog
- **集中收集**：本地写文件，云上对接 ELK / Loki

**关键日志事件**：
- 上传接收 / 入队 / 任务开始 / 引擎调用 / 任务完成 / 失败重试

### 14.3 监控指标 (Prometheus, V1.2 简化为 3 项)

| 指标 | 类型 | 用途 |
|---|---|---|
| `gevic_inspections_total{algorithm, status}` | Counter | 计数 + 成功率 |
| `gevic_inspection_duration_seconds{algorithm, engine}` | Histogram | 延迟 P95 |
| `gevic_engine_call_errors_total{engine, error_code}` | Counter | 错误率 |

### 14.4 告警（V1.2 简化为 2 项）

| 告警 | 触发条件 | 处置 |
|---|---|---|
| 依赖不可达 | PG / Redis / MinIO 健康检查失败 | 立即人工介入 |
| Celery worker down | 所有 worker 进程消失 | 立即人工介入 + 自动重启 |

> V1.0 不做：富化失败率告警、队列堆积告警、引擎错误率告警。SLO 由 §1.7 保障。

## 15. 安全（V1.2 简化）

**内部系统下的真正安全需求**：`事后追责 > 事前拦截`。`n`n| 需求 | V1.0 实现 | 不做的事 |`n|---|---|---|`n| 文件类型校验 | MIME + 文件头 | 复杂文件杀毒 |`n| 凭据管理 | `.env` 文件（本地） | K8s Secret / KMS |`n| 数据脱敏 | LLM 输入字段白名单（代码层） | 人脸检测、自动化脱敏工具 |`n| 审计可追溯 | `audit_logs` 表（§6.2.4） | ELK 集中日志 |`n| 异常可发现 | Prometheus 指标 + 健康检查 | 复杂告警规则 |`n`n**关键判断**：`n- X-Inspector-Id 加最薄格式校验（`[A-Za-z0-9_-]{3,32}`）作为最薄护栏`n- "网络安全靠内网 + VPN"完全够；并入大系统时由大系统网关统一处理`n- 纵深防御（mTLS、设备指纹、请求签名）在 V1.0 阶段**完全不需要**`n`n（V1.2 简化）

**内部系统下的真正安全需求**："事后追责 > 事前拦截"。

| 需求 | V1.0 实现 | 不做的事 |
|---|---|---|
| 文件类型校验 | MIME + 文件头 | 复杂文件杀毒 |
| 凭据管理 | `.env` 文件（本地） | K8s Secret / KMS |
| 数据脱敏 | LLM 输入字段白名单（代码层） | 人脸检测、自动化脱敏工具 |
| 审计可追溯 | `audit_logs` 表（§6.2.4） | ELK 集中日志 |
| 异常可发现 | Prometheus 指标 + 健康检查 | 复杂告警规则 |

**关键判断**：
- X-Inspector-Id 加最薄格式校验（`[A-Za-z0-9_-]{3,32}`）作为最薄护栏
- "网络安全靠内网 + VPN"完全够；并入大系统时由大系统网关统一处理
- 纵深防御（mTLS、设备指纹、请求签名）在 V1.0 阶段**完全不需要**



### 15.1 文件上传安全

- 文件类型白名单（image/jpeg, image/png, image/webp, video/mp4, video/quicktime）
- 文件大小限制（图片 20MB，视频 500MB，可配置）
- 文件名清洗（防路径穿越）
- MIME 与文件头校验（防伪）

### 15.2 凭据管理

- **绝不入库明文**：所有密钥（云 API key、超脑密码、LLM key）放环境变量或 secret 管理
- 本地开发：`.env` 文件（不入 Git）
- 云上：K8s Secret / 云厂商 KMS

### 15.3 数据脱敏

- 发送给 LLM 的数据做最小化处理：去除人脸 / 隐私字段
- 日志中不打印 API key / 文件原内容
- 报告导出时可配置脱敏（V1.1 增强）

---

## 16. 部署

### 16.1 本地开发（Docker Compose，V1.2 精简为 6 服务）

`docker compose up -d` 起 6 个服务：

| 服务 | 端口 | 说明 |
|---|---|---|
| `postgres` | 5432 | 元数据库 |
| `redis` | 6379 | Celery broker（无 result_backend） |
| `minio` | 9000/9001 | 对象存储（单桶 `gevic`） |
| `minio-init` | - | 创建 `gevic` 桶的 init container |
| `backend` | 8000 | FastAPI + Celery 单 worker 多队列（V1.2 合并） |
| `frontend` | 5173 | Vue 3 dev server |

**对比 V1.1（9 服务）**：合并 3 个 Celery worker（inspect/stats/cleanup）为 1 个；删除 beat。

### 16.2 云部署

**容器镜像**：所有服务一个 Dockerfile，build 后 push 到镜像仓库。

**编排**：
- 简单：直接 docker-compose 部署到云主机
- 复杂：K8s manifest（Deployment + Service + Ingress + HPA + ConfigMap + Secret）

**托管服务映射**：

| 自管 | 云厂商 |
|---|---|
| PostgreSQL | 阿里云 RDS-PG / 腾讯云 PG |
| Redis | 阿里云 Redis / 腾讯云 Redis |
| MinIO | 阿里云 OSS / 腾讯云 COS / AWS S3 |
| FastAPI 镜像 | 阿里云 SAE / 腾讯云 Cloud Run / K8s |
| Celery Worker | 阿里云 SAE / K8s Deployment |
| Vue 静态站 | 阿里云 OSS 静态网站 / CDN |

### 16.3 迁移路径

V1.0 本地 → V1.0 云：
1. 写 Dockerfile + docker-compose
2. 把 MinIO 数据 dump/restore 或直接换 OSS/COS
3. 数据库用 PG dump/restore 或 DMS
4. 配置 K8s manifest 或选云厂商托管服务

---

## 17. 测试策略

### 17.1 单元测试 (pytest)

- 算法注册表查找
- 引擎适配器接口（Mock）
- Prompt 模板渲染
- DB 模型 (SQLAlchemy + 测试 PG)
- Pydantic 校验

覆盖率目标：核心模块 ≥ 80%

### 17.2 集成测试

- 端到端：上传 → 入队 → 识别（Mock 引擎）→ 入库 → 查询
- 引擎适配器集成：Mock 云 API / Mock 超脑 HTTP
- MinIO 集成：用 minio testcontainer
- Celery 集成：eager mode 或 test broker

### 17.3 端到端测试 (Playwright)

- 看板：访问 → 触发报告生成 → 查看报告


### 17.4 性能与并发

- **Locust**：模拟 50–500 并发上传
- **k6 / wrk**：HTTP 性能
- **Celery worker 压测**：单 worker 处理能力

---

## 18. 里程碑与交付计划（V1.2 重写：M0/M1/M2/M3+）

**总目标**：**2 周可上线 V1.0**（M0 + M1）。

### M0 — 脚手架 + 1 个算法端到端（1 周）

**目标**：1 个算法跑通"上传 → 入队 → 识别 → 富化 → 入库 → 查询"完整链路

- [ ] docker-compose 一键起 PG/Redis/MinIO/FastAPI/Celery/Vue（6 服务）
- [ ] `algorithms` / `inspections` / `audit_logs` 表 + Alembic 初始迁移 + 1 条种子算法
- [ ] FastAPI 通配路由 + MinIO 上传 + `inspections` 写入（PENDING）
- [ ] CloudVisionEngine 适配器（选 1 个云厂商）
- [ ] Celery `run_inspection` 任务（含 LLM 富化，硬编码 Prompt 模板）
- [ ] X-Inspector-Id 格式校验（`[A-Za-z0-9_-]{3,32}`） + `audit_logs` 写入
- [ ] Vue 3 看板：列表 + 详情 + 上传 + 重试 + 富化重试（最小可用）
- [ ] 端到端测试 5 条样本（覆盖正常/失败/重试/富化失败/格式校验拒绝）

**交付物**：能上传 1 张图 → 看到识别结果 + LLM 建议 + 元数据，5 分钟上手 demo

### M1 — 多算法 + 报告（1 周）

- [ ] 复制 M0 的适配器到 2-3 个算法（不同云厂商或同厂商不同接口）
- [ ] LLM 报告生成（异步任务 + 看板查看 + 看板触发）
- [ ] Vue 看板保留现状（不重构）
- [ ] 3 个核心 Prometheus 指标 + 2 个告警（§14 V1.2 简化）
- [ ] 极简监控（本地不部署 Grafana）

**交付物**：3 个算法跑通，可生成周报；**V1.0 上线**

### M2 — 海康超脑 PoC（1-2 周，风险驱动）

- [ ] 单独 PoC 任务（参见 §9.3 / §21.2）
- [ ] PoC 通过 → 进入 M3 规划
- [ ] PoC 不通过 → V1.0 保持 M1 状态，海康方案延后到 V2.0

### M3+ — 规模化与并入（按需，业务驱动）

**触发条件**（满足任一即启动）：
- 业务方真实提出 40+ 算法需求
- 出现 AI 对话（SSE 流式）/ 复杂大屏需求（前端再评估，ADR-007）
- 并入大系统（横切关注点迁移到大系统）

**M3+ 工作内容**：
- 算法管理后台 UI（SQL 已不够用时）
- AI 对话（Function Calling + SSE 流式）
- K8s 部署 / 监控告警 / 灾备

**总周期**：M0 + M1 = **2 周可上线 V1.0**。这是"高可落地"应有的节奏。

---

## 19. 风险与缓解

| 风险 | 等级 | 影响 | 缓解 |
|---|---|---|---|
| 海康超脑对"非摄像头流"文件分析能力有限 | 高 | 手动上传走超脑的方案不可行 | M3 阶段做 PoC；不可行则仅做"超脑事件订阅"模式 |
| 云 API 厂商调整价格/接口 | 中 | 成本上升 / 集成失效 | 适配器抽象 + 多 provider 支持；提前做成本监控 |
| LLM 幻觉 / 错误分析 | 中 | 报告不可信 | 结构化输出校验 + 引用原始数据；人在回路 |
| 大量视频文件占存储 | 中 | 存储成本 | 1 年后转冷存储；上传时强制文件大小限制 |
| 巡检 App 频繁上传导致瞬时峰值 | 中 | 队列堆积 | 限速 + Worker HPA + 队列长度告警 |
| LLM 厂商数据合规 | 中 | 隐私风险 | 不发送原图/原视频；只发送结构化数据；选择合规厂商 |

---

## 20. 待定问题 (Open Questions)

下列问题需在评审或后续阶段确认：

1. **Q-OPEN-1**：海康超脑具体型号与文件级分析能力 → 在 M3 阶段 PoC 后定
2. **Q-OPEN-2**：V1.0 选用的云视觉 API 厂商与具体算法清单 → 业务方提供
3. **Q-OPEN-3**：LLM 首选厂商（成本、效果、合规） → 评审决定
4. **Q-OPEN-4**：原文件保留期（1 年是否够？合规要求？） → 合规方确认
5. **Q-OPEN-5**：是否需要支持视频抽帧识别（上传 1 个长视频，按 N 秒抽 N 帧分别识别后聚合）？V1.0 暂只支持整视频识别，后续增强
6. **Q-OPEN-6（V1.1 已澄清）**：原计划升级到 OAuth2/JWT。**经评审决定 V1.0 不做用户鉴权**（见 §13），改为网络边界 + App 分发双层保障。如未来需要鉴权，参见 §13.5 触发条件。
7. **Q-OPEN-7**：40+ 算法的清单与优先级 → 业务方提供
8. **Q-OPEN-8（V1.2 已答复）**：**V1.0 不做**（与无鉴权模式一致）。并入大系统后由大平台统一 RBAC。

9. **Q-OPEN-9（V1.2 已答复）**：**告警阈值定 5% 持续 5 分钟**（§14.4）。SLO 100% 不影响主任务（§1.7 硬约束）。

---

## 22. 评审与签署

| 评审角色 | 姓名 | 日期 | 签字 | 备注 |
|---|---|---|---|---|
| 业务方代表 | | | | |
| 技术负责人 | | | | |
| 架构评审 | | | | |
| 安全/合规 | | | | |
| 运维/SRE | | | | |
| 产品经理 | | | | |

---

**文档结束。**

如对本规范有任何疑问或建议，请在评审记录表中填写，版本变更将通过变更记录表追溯。
