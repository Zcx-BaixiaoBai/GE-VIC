# GE-VIC 临时文件策略 (主规范 §5.4 补充)

> V1.0 决策: 临时文件管理保持极简, 不引入复杂库。

## 1. 策略

```
1. worker 处理前下载到 tempfile.NamedTemporaryFile 创建的本地文件
2. 任务完成后立即删除 (try/finally)
3. 失败重试时重新下载 (简单可靠)
4. 不引复杂的临时文件管理库
5. Celery result_backend 可省, 只保留 broker_url
```

## 2. 当前实现

### 多模态 LLM 引擎 (multimodal_llm.py)

视频抽帧**完全在内存**中完成 (不写临时文件):

```python
def _extract_video_frames(file_bytes, filename, n_frames=3, max_long_edge=1024):
    """从视频中抽 N 帧, 缩放到长边 <= max_long_edge, 返回 JPEG bytes 列表."""
    frames = []
    for i, frame in enumerate(iio.imiter(file_bytes, plugin="pyav")):
        if i >= 50: break
        frames.append(frame)
    # 采样 + PIL resize + io.BytesIO() 编码 JPEG
    # 返回 list[bytes], 整个过程无磁盘 I/O
    return result
```

`_extract_video_frames` 接收 `file_bytes: bytes`, 用 `imageio.imiter(file_bytes, ...)` 直接从内存读取视频流, 用 `PIL.Image` 缩放, 用 `io.BytesIO()` 编码为 JPEG 字节, 整个过程**不创建任何磁盘临时文件**。

### 其他引擎

- **CloudVisionEngine** (cloud_api): 接收 file_bytes, 直接 POST 给云厂商 API, 无临时文件。
- **MockEngine** (mock): 同步 mock 返回, 无文件 I/O。

## 3. 未来需要临时文件的场景

如果未来要支持本地模型推理 (如 ONNX / PyTorch) 或大文件分片上传, 才需要:

```python
import tempfile
import os

async def recognize(self, file_bytes, ...):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
    try:
        tmp.write(file_bytes)
        tmp.close()
        # 调用本地模型
        result = model.predict(tmp.name)
        return result
    finally:
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)
```

`tempfile.NamedTemporaryFile(delete=False)` + `try/finally` + `os.unlink()` 是 V1.0 推荐的极简方案。

## 4. Celery 决策

- `result_backend` **不配置** (主规范 §10.1 用 result_backend, 实际不需要)。
- 状态查询走 DB (`inspections` 表) 而非 Celery result store。
- broker_url 用 Redis, 仅做队列。
﻿

## 4. 临时文件总览 (V1.3 更新)

| 用途 | 路径 | 生命周期 | 谁来清理 | 大小估算 |
|---|---|---|---|---|
| worker 视频处理 | 无 (完全内存) | - | - | 0 |
| **TUS 断点续传分片** | `./upload-tmp/{session_id}.bin` | 会话完成或 24h 过期 | 完成时 finalize 删除; 过期由 `gc_expired_sessions` 启动清理 | 500MB/会话, 并发数个 |
| 客户端预览 (ObjectURL) | 浏览器内存 (URL.createObjectURL) | 用户移除文件或页面卸载 | 组件 `onUnmounted` revoke | 0 (不写盘) |
| Element Plus 上传临时 | 浏览器内存 | 同上 | - | 0 |

### 4.1 TUS 临时文件管理细节 (V1.3 新增)

- 位置: `Settings.upload_tmp_dir` (默认 `./upload-tmp/`)
- 命名: `{session_id}.bin`, 32 字符 hex
- 写入: 服务端 `PATCH /uploads/{id}` 追加, 客户端发送的每个分片落到此文件
- 清理触发:
  1. **正常完成**: `POST /inspect/{code}/from-upload/{id}` 把文件内容读出后 `Path.unlink()`
  2. **主动取消**: `DELETE /uploads/{id}` 清理
  3. **过期 (24h)**: 应用启动时 `gc_expired_sessions()` 扫描 `expires_at < NOW()`, 删除文件 + 删行
- 监控: `SELECT status, COUNT(*) FROM upload_sessions GROUP BY status;` 看积压

### 4.2 容量与并发

- 单会话最大 `TUS_MAX_SIZE = 600MB` (config 可调)
- 假设 100 个并发会话 × 600MB = 60GB 临时空间
- 建议生产环境 `upload_tmp_dir` 挂独立卷 (如 `/data/gevic-uploads`), 不与 backend 代码混在一起
- `df -h` 监控, 接近 80% 时告警 (alerts.md 应新增一条)

## 5. V1.3 决策总结

- ✅ 任务处理: 完全无临时文件 (内存)
- ✅ TUS 断点续传: 用临时文件, 24h 过期 + 完成即清理
- ❌ 不引入: 临时文件管理库 (over-engineered)
- ❌ 不引入: S3 multipart 协议本地化 (直传 MinIO 由 M3+ 评估)
