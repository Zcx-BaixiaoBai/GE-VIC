# 图像识别架构设计规范 V1.1

> **项目名称**：GE-VIC 图像识别平台
> **文档版本**：1.1
> **编制日期**：2026-07-01
> **状态**：待多方评审
> **保密级别**：内部

---

## 0. 文档元信息

### 0.1 变更记录

| 版本 | 日期 | 变更内容 | 作者 |
|---|---|---|---|
| 1.0 | 2026-07-01 | 初稿，提交评审 | - |
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
| AI 对话 (AI Chat) | 基于识别记录数据的自然语言问答交互 |
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
│              │  管理看板 (Web)  │  ◀── 统计 / 报告 / AI 对话      │
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
   │  POST /api/v1/chat (AI 对话)                                
   ▼                                                             
[LLM Service]                                                    
   │  11. 聚合 SQL + 样本数据                                    
   │  12. 调 OpenAI 兼容 chat API                                
   │  13. 报告存 llm_reports / 流式响应给前端                     
   ▼                                                             
[看板 UI] — 图表 / 报告 / 对话气泡                                
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

2. **流式对话**（POST `/api/v1/chat`）
   - SSE 流式响应
   - 工具调用：LLM 可通过 Function Calling 查询 DB（查记录、查统计）
   - 会话与消息存 `chat_sessions` / `chat_messages`

**Prompt 模板**：版本化（`prompt_versions` 表），可灰度切换。

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
│ chat_sessions    │◀──│  chat_messages     │
│  id (PK)         │1:N │  id (PK)           │
│  title           │    │  session_id (FK)   │
│  created_at      │    │  role              │
└──────────────────┘    │  content           │
                        │  tool_calls        │
                        │  created_at        │
                        └────────────────────┘
```

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

-- 6.2.4 LLM 对话会话
CREATE TABLE chat_sessions (
    id              BIGSERIAL PRIMARY KEY,
    title           VARCHAR(256),
    created_by      VARCHAR(64),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE chat_messages (
    id              BIGSERIAL PRIMARY KEY,
    session_id      BIGINT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role            VARCHAR(16) NOT NULL,         -- 'system' | 'user' | 'assistant' | 'tool'
    content         TEXT NOT NULL,
    tool_calls      JSONB,                        -- assistant 调用的工具
    tool_call_id    VARCHAR(64),                  -- 对应 tool 消息
    token_used      INT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_msg_session ON chat_messages(session_id, created_at);

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
| `chat_messages` | 180 天 | 定时清理 |
| Celery 结果 | 7 天 | Redis 自动过期 |

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
| POST | `/api/v1/chat/sessions` | 创建对话 |
| GET | `/api/v1/chat/sessions` | 对话列表 |
| GET | `/api/v1/chat/sessions/{id}/messages` | 历史消息 |
| POST | `/api/v1/chat/sessions/{id}/messages` | 发送消息（SSE 流式响应） |
| DELETE | `/api/v1/chat/sessions/{id}` | 删除对话 |

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

#### 7.3.4 POST /api/v1/chat/sessions/{id}/messages

**Request**：

```json
{ "content": "请分析最近一周的绝缘子破损趋势" }
```

**Response**：SSE 流式

```
event: message
data: {"delta": "根据", "done": false}

event: message
data: {"delta": "最近一周", "done": false}

...

event: message
data: {"delta": "", "done": true, "message_id": 1024, "tool_calls": [...]}
```


### 7.3.5 完整响应结构（识别结果 + LLM 富化 + 元数据）

**核心约定**：本系统对巡检员 App 的所有相关响应（上传、查询、单条详情），必须**自洽**地包含该图的：

1. **识别结果** — 算法引擎返回的结构化结果
2. **LLM 富化** — 在识别结果基础上由 LLM 生成的一句话总结 + 处置建议
3. **完整元数据** — 用于 App 与上传请求关联、回溯展示

App 单次调用即可完成解析、归档与展示，无需二次拼接。

#### 7.3.5.1 通用响应 Schema（GET `/api/v1/records/{id}` 或 `?wait=true` 同步返回）

```json
{
  "record_id": 1024,
  "algorithm_code": "insulator-damage",
  "algorithm_name": "绝缘子破损识别",
  "category": "供配电",

  "status": "SUCCESS",
  "created_at":  "2026-07-01T10:00:00Z",
  "started_at":  "2026-07-01T10:00:01Z",
  "finished_at": "2026-07-01T10:00:12Z",
  "duration_ms": 11000,

  "meta": {
    "inspector_id": "INSP-001",
    "asset_id":     "BJ-SUBSTATION-001",
    "location":     {"lat": 39.9, "lng": 116.4},
    "client_meta":  {"voltage_level": "110kV", "remark": "雨后巡检"}
  },

  "file": {
    "object_key": "inspections/2026/07/01/1024/photo.jpg",
    "file_url":   "https://minio.local/gevic-raw/.../photo.jpg?X-Amz-Signature=...",
    "file_hash":  "sha256:abc123...",
    "file_size":  1024000,
    "file_type":  "image/jpeg"
  },

  "recognition": {
    "defects": [
      {
        "type": "破损",
        "confidence": 0.92,
        "bbox": [10, 20, 100, 200],
        "severity": "high",
        "description": "绝缘子伞裙破损"
      }
    ],
    "raw": { /* 引擎原始返回 */ }
  },

  "llm_enrichment": {
    "summary": "检测到 1 处绝缘子破损（高置信度 92%），位于图像右上区域。",
    "recommendations": [
      "建议立即安排现场核查并更换破损绝缘子",
      "对同类批次设备进行专项巡检"
    ],
    "model":          "qwen-plus",
    "prompt_version": "v1.0",
    "token_used":     380,
    "generated_at":   "2026-07-01T10:00:12Z"
  },

  "error": null
}
```

#### 7.3.5.2 失败时响应

```json
{
  "record_id": 1024,
  "algorithm_code": "insulator-damage",
  "status": "FAILED",
  "created_at":  "2026-07-01T10:00:00Z",
  "finished_at": "2026-07-01T10:00:30Z",
  "duration_ms": 29000,
  "meta":   { "inspector_id": "INSP-001", "asset_id": "..." },
  "file":   { "object_key": "...", "file_url": "...", "file_hash": "...", "file_type": "image/jpeg" },
  "recognition": null,
  "llm_enrichment": null,
  "error": {
    "code": "ENGINE_TIMEOUT",
    "message": "云 API 调用超时（>30s）",
    "details": { "engine": "aliyun", "endpoint": "RecognizeInsulatorDamage" }
  }
}
```

#### 7.3.5.3 字段稳定性保证

- 所有字段命名采用 `snake_case`，保持稳定
- 任何字段的**新增**对旧版 App 是非破坏性的（App 忽略未知字段即可）
- 任何字段的**重命名/删除/类型变更**需走文档变更记录（§0.1）并提前通知 App 联调方
- App 解析策略：忽略未知字段；必填字段缺失视为该条数据不可用

#### 7.3.5.4 上传即返回完整结果（同步模式）

为简化 App 集成，可使用**同步等待**模式：

```
POST /api/v1/inspect/insulator-damage?wait=true&timeout=30
```

服务端在 `timeout` 秒内阻塞等待任务完成，超时则返回当前状态。响应结构与 §7.3.5.1 一致，但 `status` 可能是 PENDING/RUNNING/SUCCESS/FAILED 中任一。

> **App 推荐用法**：
> - **简单场景**（网络好、识别 < 30s）：用 `?wait=true&timeout=30` 一次拿到完整结果
> - **复杂场景**（弱网/视频）：用 202 异步模式 + 轮询 `GET /api/v1/records/{id}`

#### 7.3.5.5 列表查询响应

`GET /api/v1/records` 返回列表时，每条记录采用**精简版**响应（不含 `recognition.raw` 与 `file_url`），减少响应体积；如需完整响应，调 `GET /api/v1/records/{id}`。
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
result_backend = "redis://redis:6379/1"

task_routes = {
    "app.tasks.run_inspection": {"queue": "inspect_queue"},
    "app.tasks.run_llm_report": {"queue": "stats_queue"},
    "app.tasks.run_llm_chat":    {"queue": "stats_queue"},
    "app.tasks.cleanup":         {"queue": "cleanup_queue"},
}

task_annotations = {
    "app.tasks.run_inspection": {"rate_limit": "200/m"},
    "app.tasks.run_llm_report": {"rate_limit": "10/m"},
    "app.tasks.run_llm_chat":   {"rate_limit": "20/m"},
}
```

### 10.2 启动命令

```bash
# Worker
celery -A app.worker worker -Q inspect_queue --concurrency=8 -l info
celery -A app.worker worker -Q stats_queue --concurrency=2 -l info
celery -A app.worker worker -Q cleanup_queue --concurrency=1 -l info

# Beat (定时任务)
celery -A app.worker beat -l info
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

#### 11.2.2 AI 对话系统提示词

```markdown
你是 GE-VIC 巡检数据 AI 助手, 可访问以下工具:
- query_inspections(filters, limit)  // 查询识别记录
- get_aggregate_stats(scope)         // 获取聚合统计
- get_recent_reports(limit)          // 获取历史报告

回答时:
1. 优先调用工具获取真实数据, 不要凭印象回答
2. 数据结论要给出具体数字和依据
3. 建议要可执行
4. 不知道的请说"没有相关数据"
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

### 11.5 AI 对话（Function Calling）

- 维护一组工具函数（DB 查询、统计聚合、报告查询）
- LLM 决定调用哪个工具 → 后端执行 → 结果回传 LLM → LLM 组织自然语言回答
- 工具调用结果存 `chat_messages.tool_calls`

### 11.6 成本与限速

- **每日 token 上限**（环境变量 `LLM_DAILY_TOKEN_LIMIT`，默认 5M）
- **每分钟请求数**（Celery rate_limit，默认 10/m）
- **报告生成频率限制**（同一 scope 5 分钟内不重复生成）
- **每次报告预估**：输入 ~3K tokens，输出 ~2K tokens
- **成本追踪**：`llm_reports.cost_usd` + `chat_messages.token_used`

---

## 12. 存储策略

### 12.1 MinIO 桶设计

| 桶 | 用途 | 访问策略 |
|---|---|---|
| `gevic-raw` | 原始上传文件 | 私有，通过签名 URL 访问 |
| `gevic-thumb` | 缩略图 (V1.1 增强) | 私有 |
| `gevic-export` | 导出文件 (V1.1 增强) | 私有 |

### 12.2 文件命名

```
gevic-raw/
  inspections/
    {yyyy}/{mm}/{dd}/{record_id}/{filename}
```

**去重**：`file_hash` (SHA256) 唯一索引，重复上传直接复用。

### 12.3 签名 URL

- 默认有效期 15 分钟
- 前端通过 `GET /api/v1/records/{id}/file` 获取签名 URL

### 12.4 保留与清理

- 至少保留 1 年（合规要求）
- 长期归档：V1.1 增强，可对接冷存储（如 AWS Glacier / 阿里云归档存储）

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

### 14.3 监控指标 (Prometheus)

| 指标 | 类型 |
|---|---|
| `gevic_inspections_total{algorithm, status}` | Counter |
| `gevic_inspection_duration_seconds{algorithm, engine}` | Histogram |
| `gevic_queue_length{queue}` | Gauge |
| `gevic_llm_token_used_total{operation}` | Counter |
| `gevic_llm_cost_usd_total` | Counter |
| `gevic_engine_call_errors_total{engine, error_type}` | Counter |

### 14.4 告警

- 队列堆积 > 阈值
- 引擎调用错误率 > 5%
- LLM 调用失败率 > 10%
- MinIO / PG / Redis 不可达
- Celery worker 全部 down

---

## 15. 安全

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

### 16.1 本地开发（Docker Compose）

```
.
├── docker-compose.yml          # 一键起全部服务
├── .env.example                # 环境变量模板
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── app/
└── frontend/
    ├── Dockerfile
    └── package.json
```

`docker compose up -d` 起：
- `postgres` (5432)
- `redis` (6379)
- `minio` (9000/9001)
- `minio-init` (创建桶)
- `backend` (FastAPI, 8000)
- `worker-inspect` (Celery worker)
- `worker-stats` (Celery worker)
- `worker-cleanup` (Celery worker)
- `beat` (Celery beat)
- `frontend` (Vue dev server, 5173)

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
- 看板：AI 对话多轮

### 17.4 性能与并发

- **Locust**：模拟 50–500 并发上传
- **k6 / wrk**：HTTP 性能
- **Celery worker 压测**：单 worker 处理能力

---

## 18. 里程碑与交付计划

### M1 — 核心链路（1–2 周）

**目标**：1 个算法跑通端到端

- [ ] 项目脚手架（docker-compose, FastAPI, Celery, PG, MinIO, Redis）
- [ ] 数据库迁移（Alembic）+ 初始算法注册
- [ ] FastAPI 接入层 + 单通配路由
- [ ] MinIO 文件上传
- [ ] Celery inspect_queue + run_inspection 任务
- [ ] CloudVisionEngine 适配器（至少 1 个云 provider）
- [ ] 算法注册表管理 SQL/脚本
- [ ] 看板：仪表盘 + 记录查询 + 简单上传页
- [ ] 基础日志 + 健康检查
- [ ] 端到端测试 1 条

**交付**：能上传 1 张图 → 看识别结果 → 在看板查到

### M2 — 多算法 + 报告（1–2 周）

- [ ] 增加 1–2 个算法（不同云 provider）
- [ ] 算法管理后台 CRUD
- [ ] 看板：报表中心 + 触发 LLM 报告
- [ ] LLM 报告生成（同步 + 异步两种模式）
- [ ] Prompt 模板 v1
- [ ] 限速 + 成本统计

**交付**：可管理 2–3 个算法，可生成本周报告

### M3 — 海康超脑接入（1–2 周）

- [ ] 海康超脑 PoC（确认文件级分析能力）
- [ ] HikvisionBrainEngine 适配器
- [ ] webhook 接收超脑结果（如支持）
- [ ] 至少 1 个算法在超脑上跑通
- [ ] 双引擎切换演示（云 API ↔ 超脑）

**交付**：手动上传可走超脑识别

### M4 — 规模化 + AI 对话（2–4 周）

- [ ] 批量注册 40+ 算法（脚本 + 管理后台）
- [ ] 看板：算法管理 + 配置版本灰度
- [ ] AI 对话（SSE 流式 + Function Calling）
- [ ] 多用户/多 API Key
- [ ] 监控告警 + 性能优化
- [ ] 文档（API/运维/用户）

**交付**：40+ 算法在线，多用户可对话查询

### M5+ — 云部署与生产化（按需）

- [ ] K8s manifest / 云厂商托管服务
- [ ] CI/CD
- [ ] 灾备 / 多区域
- [ ] 合规与审计

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
8. **Q-OPEN-8**：看板是否需要权限分级（管理员/普通用户/只读）？**V1.0 简化不做**（与无鉴权模式一致），V2.0 考虑

9. **Q-OPEN-9**：LLM 富化失败重试的 SLA 与告警阈值 — 是否需要「富化失败率超 X% 触发告警」？ 默认：失败率 > 5% 持续 5 分钟告警

---

## 21. 附录

### 21.1 完整 API 端点列表

见 §7.2。

### 21.2 海康超脑接入说明（PoC 任务清单）

1. 准备内网测试超脑（与生产同型号或系列）
2. 准备 5–10 张不同场景图片
3. 尝试调用超脑的"文件分析"接口（如 `POST /ISAPI/Intelligent/analysisTask`），上传图片
4. 观察：是否能返回识别结果？响应时间？支持哪些算法？
5. 评估：能力、成本、稳定性、文档支持度
6. 输出：PoC 报告，决定 M3 范围

### 21.3 LLM Prompt 模板示例

见 §11.2。

### 21.4 术语表

见 §2。

### 21.5 参考资料

- FastAPI 文档：https://fastapi.tiangolo.com/
- Celery 文档：https://docs.celeryq.dev/
- SQLAlchemy 2.x 异步：https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- MinIO 文档：https://min.io/docs/minio/linux/index.html
- OpenAI API 兼容：https://platform.openai.com/docs/api-reference/chat

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
