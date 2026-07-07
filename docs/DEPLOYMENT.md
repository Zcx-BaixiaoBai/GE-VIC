# GE-VIC 生产部署指南

> 文档日期: 2026-07-07 (M2)
> 适用版本: V1.3+

## 1. 部署方式选择

| 场景 | 推荐方式 | 复杂度 | 适用 |
|---|---|---|---|
| 个人/小团队 demo | **cpolar 内网穿透** | ⭐ | 1-10 人, 弱网测试 |
| 公司内网 | nginx 反代 + systemd | ⭐⭐ | 50 人内 |
| 公网正式服务 | nginx + 域名 + HTTPS (Let's Encrypt) | ⭐⭐⭐ | 真实生产 |
| Kubernetes | helm chart (未提供) | ⭐⭐⭐⭐ | 大规模 |

本文重点写 **cpolar 部署** (当前用户选择), 末尾补充其他方式要点。

## 2. cpolar 部署 (推荐用于 demo + 公网测试)

### 2.1 cpolar 简介

- 国内内网穿透服务, 免费版 1-3Mbps 带宽
- 注册: https://www.cpolar.com/
- 适合: 给外部用户/手机测试, 不自建服务器
- 限制: 免费版每月 1GB 流量, 公网延迟 ~50ms

### 2.2 部署架构

```
[手机/外部用户]
      ↓
[cpolar 公网域名] (如 https://abc123.r7.cpolar.cn)
      ↓
[cpolar 客户端] (本机, 监听 9200)
      ↓
[本机 8000 (backend) + 5173 (frontend)]
      ↓
[PostgreSQL / MinIO / Redis (本机或 Docker)]
```

### 2.3 前置条件

- 本机: Windows / Linux 任意, 已装 Docker Desktop 或本地服务
- cpolar: 注册 + 安装客户端 (https://www.cpolar.com/download)
- 本机防火墙: 放行 8000 / 5173 / 9200

### 2.4 启动顺序

```powershell
# 1) 启数据服务 (PG / Redis / MinIO)
cd C:\Users\Admin\Documents\GE-VIC
docker compose up -d postgres redis minio minio-init

# 2) 启后端 (生产模式)
cd backend
$env:APP_ENV="production"
$env:LLM_MOCK_MODE="false"   # 用真实 LLM
$env:TASK_SYNC_MODE="false"  # 用 Celery worker
alembic upgrade head         # 跑迁移
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 3) 另开终端: 启 Celery worker
cd backend
celery -A app.tasks.celery_app worker -Q inspect_queue,stats_queue -l info

# 4) 另开终端: 启前端 (生产 build 后用 nginx, 或 dev server)
cd frontend
npm run dev -- --host 0.0.0.0 --port 5173
# 生产建议: npm run build, 然后用 nginx serve dist/

# 5) 另开终端: 启 cpolar 隧道
cpolar http 5173             # 映射前端
cpolar http 8000             # 另开映射后端 (或在 cpolar.yml 配置)
```

### 2.5 cpolar 配置 (推荐: 用配置文件, 不占 9200 端口)

编辑 `~/.cpolar/cpolar.yml`:

```yaml
authtoken: <你的 cpolar authtoken>
tunnels:
  gevic-frontend:
    proto: http
    addr: 5173
    subdomain: gevic-frontend  # 自定义子域名, 需付费
    # 没付费: 用随机子域, 如 https://5819cf0d.r7.cpolar.cn
  gevic-backend:
    proto: http
    addr: 8000
    subdomain: gevic-backend
```

启动:
```bash
cpolar start gevic-frontend gevic-backend
```

### 2.6 验证

打开浏览器访问 cpolar 给的公网 URL (如 `https://abc.r7.cpolar.cn`):

- 应看到 GE-VIC 上传页
- 上传 1 张小图 → 几秒内 SUCCESS
- 上传 10MB 视频 → 看到进度条, 完成
- 故意关 WiFi 再开 → 进度从断点继续

### 2.7 cpolar 性能调优

| 问题 | 调优 |
|---|---|
| 上传慢 | 已用 M2 的 TUS + 压缩解决, 用户层无需调 |
| 频繁断流 | cpolar 免费版限制, 升级付费版 ($5/月) |
| 域名难记 | 付费自定义子域名 (gevic.r7.cpolar.top 之类) |
| 暴露后端端口 | 见 §2.8 安全 |

### 2.8 安全注意 (公网必须做)

- [ ] **HTTPS**: cpolar 默认 HTTPS, 不用自己配证书 ✅
- [ ] **不要直接暴露后端 8000**: 只暴露前端, 后端通过前端 nginx 反代
- [ ] **X-Inspector-Id 不要信**: 公网环境必须有 auth (大平台网关), 本系统 V1.0 假设内网
- [ ] **MinIO 控制台 9001**: 不要暴露公网
- [ ] **PostgreSQL 5432 / Redis 6379**: 不要暴露公网
- [ ] **LLM API Key**: 用环境变量, 不要写代码
- [ ] **审计日志**: M1 已加, 关注可疑上传

### 2.9 故障排查

| 现象 | 排查 |
|---|---|
| 外部访问 404 | cpolar 客户端没启, 或端口不对 |
| 看到页面上传失败 | 后端 8000 端口没起, 或跨域被拒 (检查 CORS) |
| 上传进度卡 0% | TUS 端点不可达, 试 `curl -X OPTIONS https://your-domain/api/v1/uploads` |
| 看到 'Connection was reset' | git 推 / TUS 推, 检查 cpolar 隧道状态 |
| 后端日志空 | 后端没在监听 0.0.0.0:8000 (检查 uvicorn --host 参数) |

## 3. nginx 反代 + systemd (内网生产)

适合: 公司内网, 50 人内, 不要公网。

```nginx
# /etc/nginx/conf.d/gevic.conf
server {
    listen 80;
    server_name gevic.internal;

    # 前端 dist
    location / {
        root /opt/gevic/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # 后端 API
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 600s;   # TUS 需要
        client_max_body_size 600m; # TUS 视频需要
    }
}
```

systemd 服务:
```ini
# /etc/systemd/system/gevic-backend.service
[Unit]
Description=GE-VIC Backend
After=network.target

[Service]
WorkingDirectory=/opt/gevic/backend
Environment="DATABASE_URL=postgresql+asyncpg://..."
Environment="LLM_API_KEY=..."
ExecStart=/opt/gevic/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

## 4. 公网正式部署 (HTTPS + 域名)

需要在 §3 基础上加:
- 域名 (gevic.example.com)
- Let's Encrypt 证书 (certbot --nginx)
- nginx 加 `listen 443 ssl`
- 后端强制 HTTPS (proxy_set_header X-Forwarded-Proto https)
- 大平台 / Cloudflare 做 DDoS 防护

## 5. 部署 checklist (M2 必须做)

新机器部署 / 升级到 M2 时, 必做:

```bash
# 1) 拉最新
git pull origin master

# 2) 后端依赖 + 迁移
cd backend
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
alembic upgrade head
# 预期最后一行: 006_tus_upload_sessions ... ok

# 3) 前端 build
cd ../frontend
npm ci
npm run build   # 生成 dist/

# 4) 重启所有服务
# (按你的部署方式)

# 5) 验证 TUS 端点
curl -X OPTIONS http://your-host:8000/api/v1/uploads -i | grep -i tus
# 预期: Tus-Resumable: 1.0.0

# 6) 端到端验证
# 浏览器上传 10MB 视频, 看进度条
# 关 WiFi 再开, 看从断点继续
```

## 6. 容量规划

| 场景 | PG | MinIO | Redis | 后端 CPU |
|---|---|---|---|---|
| 10 用户, 100 records/天 | 1 vCPU 1GB | 50GB | 256MB | 1 vCPU |
| 100 用户, 1000 records/天 | 2 vCPU 4GB | 500GB | 1GB | 2 vCPU |
| 1000 用户, 10k records/天 | 4 vCPU 16GB | 5TB | 4GB | 4 vCPU |

TUS 临时文件: 假设 10 个并发 × 500MB = 5GB 临时空间 (用独立卷)

## 7. 监控

- Prometheus 抓 `/metrics` (M1 已加)
- 告警: [alerts.md](./superpowers/alerts.md)
- 日志: 本地文件, 主规范假设大平台集中采集
- 健康检查: `GET /health/ready` 看 PG/MinIO/Redis 状态

## 8. 备份与恢复

| 数据 | 备份频率 | 保留 | 工具 |
|---|---|---|---|
| PostgreSQL | 每日 | 30 天 | pg_dump |
| MinIO | 每周 | 4 周 | mc mirror |
| Redis | 不备份 (可重建) | - | - |
| TUS 临时文件 | 不备份 | - | - |

## 9. 相关文档

- 📋 [M2 交付报告](./superpowers/plans/2026-07-01-gevic-m2-final.md)
- 🔌 [TUS 上传协议](./superpowers/upload-protocol.md)
- 📋 [架构决策 ADR](./superpowers/adr.md)
- 📊 [M2 实施计划](./superpowers/plans/2026-07-01-gevic-m2-implementation.md)
- 📊 [监控告警规则](./superpowers/alerts.md)
- 🏗️ [集成边界 (大平台)](./superpowers/integration-boundary.md)
