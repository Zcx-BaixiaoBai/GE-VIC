# GE-VIC M2 实施计划 — 生产可用性 (断点续传 + 客户端压缩)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.
>
> **Goal:** 解决 cpolar 公网映射下的大文件上传失败 + 视频卡 20MB 限制 + 无进度反馈 三大问题, 让平台对外部用户真正可用。
>
> **M1 收尾**: [2026-07-01-gevic-m1-final.md](./2026-07-01-gevic-m1-final.md) — 5 算法, 13 Prometheus 指标
> **Spec 引用**: [../specs/2026-07-01-image-recognition-architecture-design.md](../specs/2026-07-01-image-recognition-architecture-design.md) V1.3 §18.2

## 1. M2 范围与不做

### 1.1 范围 (M2 必须做)

- [x] **客户端图片压缩**: Canvas 等比缩放 + JPEG 0.85
  - 长边 ≤ 1920px, 5MB iPhone 照片 → ~500KB
  - HEIC 透传 (Chrome/Firefox 透传, Safari 压缩)
  - GIF / 视频 / 已够小(< 800KB) 跳过
- [x] **TUS 1.0.0 断点续传**: 浏览器+后端全协议实现
  - 文件 ≥ 5MB 走 TUS (分片 5MB)
  - 文件 < 5MB 走原 multipart (cpolar 也能秒传)
  - 失败自动重试 5 次, 指数退避
  - localStorage 跨页面恢复 session
  - 进度条 (XHR upload.onprogress 真进度)
- [x] **修后端 max_size bug**: 不论 image/video 都用 max_image_size=20MB
  - 改成按 file_type 分支: image=20MB, video=500MB
  - 同步修 batch 上传端点
- [x] **alembic 006 迁移**: upload_sessions 表
- [x] **后端 GC**: 启动时清理 24h 过期 TUS 会话
- [x] **9 个 TUS 协议单元测试** + 9 个 E2E (含断点续传模拟)

### 1.2 不做 (留给 M3+)

- [ ] 客户端视频压缩/转码 (H.264 重编码太重, 上传由 TUS 解决)
- [ ] 直传 MinIO presigned URL (绕过 cpolar 复杂, 不值)
- [ ] tus-js-client 依赖 (自己写 ~250 行更可控, 0 依赖)
- [ ] S3 multipart (同上)

## 2. 技术栈新增

- **tus 1.0.0 protocol** (无服务端依赖, FastAPI + aiofiles 即可)
- **HTML5 Canvas** (浏览器原生, 0 依赖)
- **XMLHttpRequest upload.onprogress** (axios onUploadProgress 在 multipart 也支持)
- **localStorage** (跨页面 session 持久化)

## 3. 架构变更

### 3.1 上传流程

```
用户选文件
  ↓
图片? → Canvas 压缩 (1920px / JPEG 0.85)    ← 5MB → 500KB
  ↓
大小判断:
  < 5MB → multipart POST /inspect/{code}    ← 30s -> 30min 超时
  ≥ 5MB → TUS 流程:
            1) POST /uploads (init)
            2) PATCH /uploads/{id} (循环分片, XHR 进度)
            3) POST /inspect/{code}/from-upload/{id} (finalize)
  ↓
返回 record_id
```

### 3.2 后端 TUS 端点

| Method | Path | 作用 |
|---|---|---|
| OPTIONS | /api/v1/uploads | 协议能力声明 |
| POST | /api/v1/uploads | 创建会话 (含 Creation-With-Upload) |
| HEAD | /api/v1/uploads/{id} | 查询 offset (断点续传前提) |
| PATCH | /api/v1/uploads/{id} | 追加分片 (Upload-Offset 校验) |
| DELETE | /api/v1/uploads/{id} | 取消 |
| GET | /api/v1/uploads/{id}/status | JSON 状态 (前端用) |

### 3.3 新数据表

```sql
CREATE TABLE upload_sessions (
  id VARCHAR(32) PRIMARY KEY,  -- UUID hex, 32 字符
  total_size BIGINT NOT NULL,
  offset BIGINT NOT NULL DEFAULT 0,
  filename VARCHAR(256),
  content_type VARCHAR(128),
  metadata_json JSONB,
  tmp_path VARCHAR(512) NOT NULL,
  file_type VARCHAR(16),  -- image / video / other
  status VARCHAR(16) NOT NULL DEFAULT 'uploading',  -- uploading / completed / cancelled
  expires_at TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '24 hours',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_upload_sessions_status ON upload_sessions(status);
CREATE INDEX ix_upload_sessions_expires_at ON upload_sessions(expires_at);
```

## 4. 任务分解 (历史实施记录)

> 以下按提交顺序记录, 全部完成 ✅

### Task 1: 后端基础设施
- `backend/app/models/upload_session.py` (新) — UploadSession 模型
- `backend/app/models/__init__.py` — 导出新模型
- `backend/alembic/versions/006_tus_upload_sessions.py` (新) — 迁移
- `backend/app/config.py` — 加 tus_threshold / tus_chunk_size / upload_tmp_dir
- `backend/app/main.py` — 启动时 GC 过期 TUS 会话

### Task 2: 后端 TUS 端点
- `backend/app/api/tus.py` (新) — 5 个 TUS 端点 + helpers (gc_expired_sessions)
- `backend/app/api/__init__.py` — 注册 tus router
- `backend/app/api/inspect.py` — 修 max_size 分支 + 加 from-upload finalization
- `backend/tests/test_api_tus.py` (新) — 9 个协议测试 (全过)

### Task 3: 前端 composables
- `frontend/src/composables/useImageCompress.ts` (新) — Canvas 压缩 + HEIC 透传
- `frontend/src/composables/useTusUpload.ts` (新) — TUS 客户端 + 断点续传 + localStorage

### Task 4: 前端集成
- `frontend/src/api/client.ts` — upload timeout 30s → 30min, 加 finalizeFromTus
- `frontend/src/stores/records.ts` — 暴露 uploadFile (带 onUploadProgress) + finalizeFromTus
- `frontend/src/views/UploadView.vue` — 压缩 → TUS 路径 → 进度条 UI
- `frontend/tests/e2e/09-tus-upload.spec.ts` (新) — 9 个 E2E

### Task 5: 工程
- `.gitignore` — 忽略 upload-tmp/ 和 scripts/*.py
- `vue-tsc --noEmit` 0 错误
- `npm run build` 成功
- 18/18 后端单元测试通过

## 5. 风险与缓解

| 风险 | 缓解 |
|---|---|
| HEIC 在 Chrome/Firefox 不能 canvas 解码 | 透传原文件, 后端 worker 处理; 进度条仍可用 |
| TUS 临时文件占用磁盘 | 24h 过期 + 启动时 GC; completed 后立即清理 |
| localStorage quota 满 | try/catch 静默失败, 不影响主流程 |
| 多窗口同时上传同一文件 | 各窗口独立 session (localStorage key 相同会复用, 但并发风险低) |
| 用户关浏览器 / 切换网络 | localStorage 持久化 session, 重新选同一文件自动续 |

## 6. 上线步骤

```bash
# 1) 拉最新
cd GE-VIC && git pull

# 2) 后端: 跑迁移
cd backend && alembic upgrade head
# 预期: 006_tus_upload_sessions ... ok

# 3) 重启 backend
# (start-app.ps1 或 docker compose restart)

# 4) 前端: 重新 build
cd ../frontend && npm run build
# 替换 dist/ 到 web 服务器

# 5) 验证
curl -X OPTIONS https://your-domain/api/v1/uploads -i | grep -i tus
# 预期: Tus-Resumable: 1.0.0
```

## 7. 验收清单

- [x] 1KB 图片立即上传 (秒回 record_id)
- [x] 5MB 图片自动压缩到 500KB
- [x] 30MB 视频通过 TUS 上传成功
- [x] 故意断网后, 重连能从断点继续
- [x] 进度条实时显示百分比
- [x] 失败自动重试 5 次
- [x] 24h 过期 session 启动时清理
- [x] HEIC 透传不崩溃
- [x] 18/18 后端测试 + 9/9 E2E 通过
