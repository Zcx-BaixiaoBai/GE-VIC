# GE-VIC 与大系统集成边界 (主规范 §3.2 落地)

> V1.0 决策: 本系统是"业务核心能力模块", 横切关注点由大平台统一提供。
> 文档日期: 2026-07-06

## 1. 集成模型

```
┌─────────────────────────┐
│   大平台 (Gateway)      │
│  - SSO / OAuth         │
│  - API 网关 (限速/熔断) │
│  - 多租户隔离           │
│  - 告警通道 (钉钉/邮件) │
└────────┬────────────────┘
         │ 代理
         ▼
┌─────────────────────────┐
│   GE-VIC (本系统)       │
│  - 业务核心 (识别/富化) │
│  - X-Inspector-Id 业务标识│
│  - 自管 MinIO/PG/Redis  │
│  - 暴露 Prometheus 指标 │
└─────────────────────────┘
         │
         ▼ 指标采集
┌─────────────────────────┐
│   大平台 (Prometheus)   │
│  - 集中存储指标         │
│  - 跨系统告警           │
└─────────────────────────┘
```

## 2. 能力划分

| 能力 | 本系统状态 | 大系统职责 |
|---|---|---|
| 用户鉴权 (SSO/OAuth) | **不做** | 大系统 |
| API 网关 (限速/熔断) | **不做** | 大系统 |
| 多租户隔离 | **不做** | 大系统 |
| 审计日志收集 | 写本地文件 | 大系统集中采集 |
| 监控告警通道 (钉钉/邮件) | 只暴露指标 | 大系统统一告警 |
| 文件存储 (MinIO) | 本系统自管 | 并入时迁移到统一 OSS |
| 业务核心 (识别/富化/报告) | **本系统做** | - |
| 算法注册表 | **本系统做** | - |
| 看板 UI | **本系统做** | - |

## 3. 集成时变更清单

当本系统并入大平台时, 以下变更需要执行:

### 3.1 大平台侧

- [ ] 部署大平台网关, 代理到本系统 `/api/v1/*` 端点
- [ ] 在网关层注入 `X-Inspector-Id` (从用户身份映射为业务标识)
- [ ] 接入 Prometheus, 抓取本系统 `/metrics` 端点
- [ ] 配置告警规则 (参见 `docs/superpowers/alerts.md`)
- [ ] 接入审计日志 (从本系统本地文件收集)

### 3.2 本系统侧

- [ ] **保留**: `X-Inspector-Id` 校验逻辑 (防御性, 即使有网关也校验)
- [ ] **移除**: 任何未来添加的鉴权代码 (避免双层鉴权冲突)
- [ ] **保留**: `/health/live` 和 `/health/ready` 端点 (K8s 探针标准)
- [ ] **保留**: `/metrics` 端点 (Prometheus 抓取标准)
- [ ] **数据迁移**: MinIO 桶内容迁移到大平台统一 OSS
- [ ] **数据迁移**: PostgreSQL 数据库 (大平台可能有不同的 schema)

### 3.3 集成前 vs 集成后

| 项 | 集成前 (V1.0) | 集成后 (V2.0) |
|---|---|---|
| 用户身份 | `X-Inspector-Id` 字符串 | 用户认证 token + 网关注入 |
| API 入口 | 8000 端口直连 | 大平台网关代理 |
| 文件存储 | 本地 MinIO | 大平台统一 OSS |
| 数据库 | 本地 PostgreSQL | 大平台统一 DB |
| 监控 | 手动查 `/metrics` | 大平台 Prometheus 抓取 |
| 告警 | 人工介入 | 大平台 Alertmanager 推送 |
| 审计 | 本地文件 | 大平台日志系统 |

## 4. 大系统集成示例 (伪代码)

```python
# 大平台网关侧 (伪代码, 不是本系统)
@app.get("/api/v1/inspect/{code}")
async def gateway_proxy(code: str, request: Request):
    user_token = request.headers.get("Authorization")
    user_info = verify_jwt(user_token)  # 大系统做
    # 网关注入 X-Inspector-Id
    new_headers = {
        "X-Inspector-Id": map_user_to_inspector(user_info),
        "X-User-Id": user_info["user_id"],
        "X-Tenant-Id": user_info["tenant_id"],
    }
    # 代理到 GE-VIC
    response = await httpx_client.post(
        f"http://gevic-backend:8000/api/v1/inspect/{code}",
        headers=new_headers,
        files=request.files,
    )
    return JSONResponse(content=response.json(), status_code=response.status_code)
```

## 5. 不做清单 (验证 V1.0 边界)

主规范 §1.6 明确 V1.0 不做, 集成时大系统统一处理:

- ❌ 多用户/多租户/用户级鉴权
- ❌ API 网关 (限速/熔断)
- ❌ 多租户隔离
- ❌ K8s Secret / KMS 凭据管理
- ❌ ELK / Loki 集中日志
- ❌ 钉钉/邮件告警通道
- ❌ 灾备/多区域容灾
- ❌ mTLS / 设备指纹 / 请求签名

## 6. 关键约束

1. **本系统不存用户身份信息** - `X-Inspector-Id` 是业务标识 (如 "WEB-DEMO-USER", "WEB-XJ-OP-001"), 不是用户主键
2. **本系统不存租户信息** - 集成时由大平台网关注入租户 ID
3. **本系统的数据库是业务专用** - 识别记录/算法配置/审计日志, 集成时按业务规则迁移
4. **本系统的 MinIO 是业务专用** - 图像/视频文件, 集成时迁移到大平台 OSS

## 7. 决策时间表

| 阶段 | 决策 | 状态 |
|---|---|---|
| M0 (脚手架) | 极简边界, 不做用户/网关 | ✅ 已实现 |
| M1 (多算法) | 暴露 Prometheus 指标, 等待大系统接入 | ✅ 已实现 |
| M2 (海康 PoC) | 评估是否需要新接口 | 规划中 |
| M3+ (规模化) | 与大系统集成 | 待业务方需求 |
