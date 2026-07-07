# GE-VIC 上传协议实现 (TUS 1.0.0)

> 文档日期: 2026-07-07 (M2)
> 适用版本: backend V1.3+, frontend V1.3+
> 协议标准: https://tus.io/

## 1. 为什么用 TUS

M1 部署到 cpolar 后, 大文件上传 100% 失败, 主因:
- 5-15MB 手机原图在 1-3Mbps 弱网下 30s 必超时
- 50-500MB 视频超过 20MB 后端限制
- 弱网抖断必须重传, 用户体验差

TUS 解决:
- 客户端分片 (5MB/片), 每片独立超时
- 失败自动重试 + 续传 (从服务端拿真实 offset)
- 跨页面恢复 (localStorage 持久化 session)
- 进度可见 (XHR upload.onprogress)

## 2. 协议端点

| Method | Path | 作用 |
|---|---|---|
| OPTIONS | /api/v1/uploads | 协议能力声明 (Tus-Resumable / Tus-Version / Tus-Extension / Tus-Max-Size) |
| POST | /api/v1/uploads | 创建会话 (返回 Location + Upload-Offset) |
| HEAD | /api/v1/uploads/{id} | 查询已写入字节 (断点续传前提) |
| PATCH | /api/v1/uploads/{id} | 追加一个分片 |
| DELETE | /api/v1/uploads/{id} | 取消上传, 清理临时文件 |
| GET | /api/v1/uploads/{id}/status | JSON 状态查询 (前端用, 非 TUS 协议) |

完整协议规范见 [tus.io/protocols/resumable-upload](https://tus.io/protocols/resumable-upload)。

## 3. 请求 / 响应示例

### 3.1 创建会话

```http
POST /api/v1/uploads HTTP/1.1
Host: api.example.com
Tus-Resumable: 1.0.0
Upload-Length: 52428800
Upload-Metadata: filename bWFnaWMtaGVhZGVyLmpwZw==,filetype aW1hZ2UvanBlZw==,file_type aW1hZ2U=

HTTP/1.1 201 Created
Location: /api/v1/uploads/a1b2c3d4e5f6...
Tus-Resumable: 1.0.0
Upload-Offset: 0
Upload-Expires: Wed, 08 Jul 2026 12:00:00 GMT
```

### 3.2 追加分片

```http
PATCH /api/v1/uploads/a1b2c3d4e5f6 HTTP/1.1
Host: api.example.com
Tus-Resumable: 1.0.0
Upload-Offset: 0
Content-Type: application/offset+octet-stream

<5242880 bytes of binary data>

HTTP/1.1 204 No Content
Tus-Resumable: 1.0.0
Upload-Offset: 5242880
```

### 3.3 断点续传 (HEAD 查询)

```http
HEAD /api/v1/uploads/a1b2c3d4e5f6 HTTP/1.1
Tus-Resumable: 1.0.0

HTTP/1.1 200 OK
Tus-Resumable: 1.0.0
Upload-Offset: 31457280
Upload-Length: 52428800
Upload-Expires: Wed, 08 Jul 2026 12:00:00 GMT
Cache-Control: no-store
```

### 3.4 错位 offset (409)

```http
PATCH /api/v1/uploads/a1b2c3d4e5f6 HTTP/1.1
Upload-Offset: 999    ← 客户端算错了

HTTP/1.1 409 Conflict
Tus-Resumable: 1.0.0
Upload-Offset: 31457280   ← 服务端真实 offset, 客户端应 HEAD 后重试
```

### 3.5 完成后, 转 Inspection

```http
POST /api/v1/inspect/insulator-damage/from-upload/a1b2c3d4e5f6 HTTP/1.1
X-Inspector-Id: INSP-001
Content-Type: multipart/form-data; boundary=...

--...
Content-Disposition: form-data; name="meta"

{"asset_id": "BJ-001", "filename": "magic-header.jpg"}
--...--

HTTP/1.1 202 Accepted
{
  "record_id": 1234,
  "algorithm_code": "insulator-damage",
  "status": "PENDING",
  "created_at": "2026-07-07T12:34:56Z",
  "status_url": "/api/v1/records/1234"
}
```

## 4. 实现细节

### 4.1 临时文件存储

- 路径: `{Settings.upload_tmp_dir}/{session_id}.bin` (默认 `./upload-tmp/{id}.bin`)
- 写入: 每次 PATCH 追加 (open `"ab"`)
- 读取: finalize 时一次性 read_bytes()
- 删除: 完成 / 取消 / 过期时

### 4.2 状态机

详见 [state-machine.md §8](./state-machine.md)。三态: `uploading` / `completed` / `cancelled`。

### 4.3 过期与 GC

- `expires_at` 默认创建时间 + 24h
- 应用启动时 `gc_expired_sessions()` 扫描过期, 删文件 + 删行
- 客户端 localStorage 也设 24h 过期

### 4.4 错误码

| 场景 | HTTP | 说明 |
|---|---|---|
| 创建时 Upload-Length 超过 TUS_MAX_SIZE (600MB) | 422 | 客户端应分片 / 拒绝 |
| PATCH 时 Upload-Offset 不匹配 | 409 | 客户端应 HEAD 拿真实 offset 后重试 |
| PATCH 错位导致总字节超 Upload-Length | 413 | 客户端应减小单片 |
| finalize 时 `offset < total_size` | 409 | UPLOAD_INCOMPLETE, 让客户端重传 |
| finalize 时临时文件丢失 | 410 | UPLOAD_FILE_MISSING, 让客户端重传 |
| Tus-Resumable 版本不对 | 412 | 客户端应升级或忽略 |

## 5. 客户端实现

详见 [`frontend/src/composables/useTusUpload.ts`](../../frontend/src/composables/useTusUpload.ts) (~250 行, 0 依赖)。

关键设计:
- **指纹**: `${file.size}-${file.name}-${file.lastModified}` 用于跨页面/刷新识别同一文件
- **存储**: `localStorage['gevic-tus-' + fingerprint]` 存 sessionId + endpoint + totalSize + filename
- **续传**: 上传前查 localStorage → 命中则 HEAD 拿 offset → 续传
- **重试**: try/catch 包每个分片, 失败指数退避 (1s/2s/4s/8s/15s, max 5 次)
- **进度**: XHR `upload.onprogress` (axios `onUploadProgress` 在 multipart 也能用)

## 6. 服务端实现

详见 [`backend/app/api/tus.py`](../../backend/app/api/tus.py) (~260 行)。

关键设计:
- 临时文件路径记在 DB, 启动时 GC 用
- `Upload-Metadata` header 用 base64 编码, 解析出 algorithm_code / inspector_id 等
- Creation-With-Upload 支持: 同一请求 body 即首个分片
- 并发安全: 当前为单写者, 多 PATCH 同 session 需客户端保证 (前端串行循环)

## 7. 测试覆盖

### 7.1 单元测试 (`tests/test_api_tus.py`)

```
tests/test_api_tus.py .........                  [100%]
============================== 9 passed
```

9 个 case 覆盖: OPTIONS / 创建 / Creation-With-Upload / HEAD / PATCH / PATCH 错位 / DELETE / 错版本 / 状态 JSON

### 7.2 E2E (`tests/e2e/09-tus-upload.spec.ts`)

9 个 case 覆盖: 同上 + 大文件 (100KB) 完整流程 + 断点续传模拟 + max_size 修复验证

## 8. 性能与限制

| 项 | 值 | 说明 |
|---|---|---|
| TUS_MAX_SIZE | 600MB | 单文件硬上限, config 可调 |
| TUS_CHUNK_SIZE (前端) | 5MB | 单片大小, 影响重试粒度 |
| TUS 触发阈值 (前端) | 5MB | < 此值走 multipart |
| 临时文件存活 | 24h | 过期 GC |
| 并发会话数 | 理论无限制 | 受磁盘空间限制 |
| 协议头固定 | ~200 字节 | 几乎无开销 |

## 9. 与未来工作的衔接

- M3+: 直传 MinIO presigned multipart URL (绕过 cpolar)
- M3+: 视频客户端转码 (H.264 重编码减小体积)
- M3+: S3 multipart 协议本地化 (dropbox-style 大文件)

详见 [decisions.md D-014](./decisions.md)。
