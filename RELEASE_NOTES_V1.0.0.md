# GE-VIC V1.0.0

首个正式版本, 包含 M0 + M1 + M2 三个里程碑全部功能。已在 cpolar 公网映射下给真实用户使用, 通过端到端验证。

## 🎯 核心能力

- **5 个识别算法**: insulator-damage (cloud_api) / insulator-demo (mock) / multimodal-inspector / nvidia-mistral / minimax-test (multimodal_llm)
- **多文件联合识别**: 一次上传多张图, LLM 一次性交叉分析
- **TUS 1.0.0 断点续传**: 5MB/分片, 自动重试 5 次, 跨页面恢复 session
- **客户端图片压缩**: Canvas 1920px / JPEG 0.85, 5MB iPhone 照片 → 500KB
- **实时进度条**: TUS + direct 双重进度回调, 200ms 轮询兜底
- **LLM 富化报告**: 异步任务, 看板查看, 76/77 records 已富化
- **13 个 Prometheus 指标**: 3 核心 (主规范 §14.3) + 7 辅助 (§1.7 SLO + §14.4 告警) + 3 应用
- **审计日志**: 所有上传/识别/富化操作可追溯

## 🏗️ 架构

- **接入层**: FastAPI 0.110+ (Python 3.11+)
- **任务层**: Celery 5.3+ + Redis
- **引擎层**: 插件化适配器 (Mock / CloudVision / MultimodalLLM)
- **数据层**: PostgreSQL 16 + MinIO
- **前端**: Vue 3.4 + Vite 5 + Element Plus + Pinia + Vue Router
- **LLM**: OpenAI 兼容 chat API (DashScope / OpenAI / 自建网关)
- **上传协议**: TUS 1.0.0 (断点续传) + Canvas 客户端压缩

## 📊 性能数据 (M2 修复后)

| 场景 | 修复前 | 修复后 |
|---|---|---|
| 1KB 照片 | 5-10s | < 1s |
| 5MB iPhone 照片 | 30s 超时失败 | 压缩 500KB, 1-2s |
| 100MB 视频 | 413 拒绝 | TUS 进度可见, 2-5 分钟 |
| cpolar 抖断 | 重头再来 | 从断点继续 |
| 失败重试 | 手动 | 自动 5 次, 指数退避 |

## 🧪 测试覆盖

- **后端 55+ 单元测试**, 9 项 TUS 协议测试 (无需 DB/服务)
- **前端 9 项 Playwright E2E** (TUS 完整流程 + 断点续传 + max_size 修复)
- **vue-tsc 类型检查**: 0 错误
- **npm run build**: 通过

## 📦 部署

详见 [DEPLOYMENT.md](./DEPLOYMENT.md) (含 cpolar 专篇 + nginx + 公网 HTTPS + 上线 checklist)

```bash
# 1) 拉 V1.0.0
git clone https://github.com/Zcx-BaixiaoBai/GE-VIC.git
cd GE-VIC && git checkout v1.0.0

# 2) 后端
cd backend
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
alembic upgrade head   # 6 个迁移
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 3) Celery worker
celery -A app.tasks.celery_app worker -Q inspect_queue,stats_queue -l info

# 4) 前端
cd ../frontend && npm ci && npm run build
# 把 dist/ 部署到 nginx 或任何静态服务器
```

## 🔐 文件大小限制

| 类型 | 限制 |
|---|---|
| 图片 (jpg/png/webp/heic) | 20MB (raw) / 实际 500KB (压缩后) |
| 视频 (mp4/mov/avi/mkv/webm) | 500MB |
| TUS 单文件硬上限 | 600MB |
| TUS 临时文件 24h 过期自动清理 | yes |

## 📚 文档

- [README.md](./README.md) - 入口
- [DEPLOYMENT.md](./DEPLOYMENT.md) - 部署指南
- [docs/superpowers/plans/2026-07-01-gevic-m2-final.md](./docs/superpowers/plans/2026-07-01-gevic-m2-final.md) - M2 交付报告
- [docs/superpowers/upload-protocol.md](./docs/superpowers/upload-protocol.md) - TUS 协议
- [docs/superpowers/adr.md](./docs/superpowers/adr.md) - 16 个架构决策
- [docs/superpowers/specs/2026-07-01-image-recognition-architecture-design.md](./docs/superpowers/specs/2026-07-01-image-recognition-architecture-design.md) - V1.3 设计规范

## ⚠️ 已知限制 (M3+ 改进)

- HEIC 压缩: iPhone Safari OK, Chrome/Firefox 透传
- 客户端视频压缩: 不做 (H.264 重编码太重)
- 直传 MinIO presigned: 不做 (复杂度过高)
- 跨会话秒传 (hash 去重): 不做

## 📝 升级说明

从 master 直接 git pull 即可:
```bash
git pull
cd backend && alembic upgrade head
cd ../frontend && npm run build
```

数据库迁移 006 是 V1.0.0 新增的 (upload_sessions 表), 必须跑。

## 👥 贡献

V1.0.0 由 single dev (Zcx-BaixiaoBai) 在 2026-07 完成。

---

完整 commit 历史: 7 个 commit, 从 M0 端到端 → M1 多算法+监控 → M2 生产可用性。
