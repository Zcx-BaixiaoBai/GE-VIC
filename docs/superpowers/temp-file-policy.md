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
