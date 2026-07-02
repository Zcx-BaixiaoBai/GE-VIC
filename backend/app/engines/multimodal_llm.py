"""Multimodal LLM Engine - 把 LLM 本身作为识别器

适用场景: 直接用多模态 LLM (Qwen-VL / GPT-4V / Claude 3 等) 识别图片或视频内容,
       让 LLM 输出结构化的设备/缺陷/状态描述。

特点:
- 支持图片 (jpg/png/webp) 和视频 (mp4/mov/avi)
- 视频通过 imageio-ffmpeg 抽帧后送 LLM (可选依赖)
- 支持自定义 prompt + 自定义 frame 数量
- 输出统一为 JSON 结构: {media_type, description, observations[], summary}
"""
import base64
import json
import logging
import time
from typing import Any

from app.engines.base import BaseEngine, RecognitionResult
from app.services.llm_client import LLMClient, make_strict_json_prompt, parse_json_response
from app.config import Settings

logger = logging.getLogger(__name__)


DEFAULT_SYSTEM_PROMPT = """你是一名资深的电力/水务/工业设备巡检 AI 助手, 擅长从图像和视频中识别设备类型、评估运行状态、发现潜在缺陷。
请仔细观察输入的图像/视频帧, 然后以严格的 JSON 格式输出 (不要任何额外说明文字, 不要 markdown 围栏):
{
  "media_type": "image" 或 "video",
  "description": "对画面整体的中文描述, 200 字以内",
  "observations": [
    {
      "type": "类别 (设备识别/状态评估/异常发现/维护建议/其他)",
      "label": "简短标签",
      "confidence": 0 到 1 的小数,
      "note": "补充说明 (可省略)"
    }
  ],
  "summary": "一句话总结, 50 字以内"
}
observations 至少 1 条, 最多 8 条。如果没有明显异常也要在 observations 中给出 "未见明显异常" 的判断。"""


DEFAULT_USER_PROMPT = "请分析这张图/这段视频的内容, 识别设备并评估状态。"

_VIDEO_MIMES = {"video/mp4", "video/quicktime", "video/x-msvideo", "video/webm", "video/x-matroska"}
_VIDEO_EXTS = {".mp4", ".mov", ".avi", ".webm", ".mkv"}
_IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/bmp"}
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}


def _is_video(filename: str, mime_type: str | None) -> bool:
    name = (filename or "").lower()
    if any(name.endswith(ext) for ext in _VIDEO_EXTS):
        return True
    if mime_type and mime_type.lower() in _VIDEO_MIMES:
        return True
    return False


def _is_image(filename: str, mime_type: str | None) -> bool:
    name = (filename or "").lower()
    if any(name.endswith(ext) for ext in _IMAGE_EXTS):
        return True
    if mime_type and mime_type.lower() in _IMAGE_MIMES:
        return True
    return False


def _guess_image_mime(filename: str) -> str:
    name = (filename or "").lower()
    if name.endswith(".png"):
        return "image/png"
    if name.endswith(".webp"):
        return "image/webp"
    if name.endswith(".gif"):
        return "image/gif"
    if name.endswith(".bmp"):
        return "image/bmp"
    return "image/jpeg"


def _extract_video_frames(
    file_bytes: bytes,
    filename: str,
    n_frames: int = 3,
    max_long_edge: int = 1024,
) -> list[bytes]:
    """从视频中抽 N 帧 (均匀采样), 缩放到长边 <= max_long_edge, 返回 JPEG bytes 列表.

    Returns:
        list of JPEG bytes; 失败时返回空列表.
    """
    try:
        import imageio.v3 as iio
    except ImportError:
        logger.warning("imageio 未安装, 无法抽帧 (pip install imageio imageio-ffmpeg)")
        return []

    try:
        import io
        from PIL import Image
    except ImportError:
        logger.warning("Pillow 未安装, 无法处理视频帧")
        return []

    try:
        frames = []
        for i, frame in enumerate(iio.imiter(file_bytes, plugin="pyav")):
            if i >= 50:
                break
            frames.append(frame)
        if not frames:
            return []
        step = max(1, len(frames) // n_frames)
        sampled = frames[::step][:n_frames]

        result: list[bytes] = []
        for arr in sampled:
            img = Image.fromarray(arr)
            w, h = img.size
            if max(w, h) > max_long_edge:
                if w >= h:
                    nw, nh = max_long_edge, int(h * max_long_edge / w)
                else:
                    nw, nh = int(w * max_long_edge / h), max_long_edge
                img = img.resize((nw, nh), Image.LANCZOS)
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="JPEG", quality=85)
            result.append(buf.getvalue())
        return result
    except Exception as e:
        logger.warning("视频抽帧失败 (%s): %s", filename, e)
        return []


def _encode_data_url(data: bytes, mime: str) -> str:
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _parse_llm_response(content: str) -> dict[str, Any]:
    """Compat wrapper - delegates to shared parse_json_response."""
    return parse_json_response(content)


class MultimodalLLMEngine(BaseEngine):
    """多模态 LLM 引擎 - 用 LLM 直接识别图片/视频内容"""

    engine_type = "multimodal_llm"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = LLMClient(settings)

    async def recognize(
        self,
        file_bytes: bytes,
        filename: str,
        meta: dict[str, Any],
        config: dict[str, Any],
    ) -> RecognitionResult:
        start = time.monotonic()
        system_prompt = config.get("prompt") or DEFAULT_SYSTEM_PROMPT
        user_prompt_template = config.get("user_prompt") or DEFAULT_USER_PROMPT
        n_frames = int(config.get("extract_frames", 3))
        if n_frames < 1:
            n_frames = 1
        if n_frames > 8:
            n_frames = 8

        meta_str = ", ".join(f"{k}={v}" for k, v in (meta or {}).items() if v is not None)
        user_prompt = user_prompt_template
        if meta_str:
            user_prompt = f"{user_prompt}\n\n文件: {filename} ({len(file_bytes)} bytes)\n元数据: {meta_str}"

        mime = None
        if isinstance(meta, dict):
            mime = meta.get("mime_type") or meta.get("content_type")

        try:
            if _is_video(filename, mime):
                frames = _extract_video_frames(file_bytes, filename, n_frames=n_frames)
                if not frames:
                    return RecognitionResult(
                        success=False,
                        data=None,
                        summary="视频抽帧失败, 可能是格式不支持或缺少 imageio/imageio-ffmpeg 依赖",
                        error_code="VIDEO_FRAME_EXTRACTION_FAILED",
                        error_message="请安装 imageio + imageio-ffmpeg 后重试, 或改用图片上传",
                        raw_response=None,
                        cost_estimate=0.0,
                        duration_ms=int((time.monotonic() - start) * 1000),
                    )
                data_urls = [_encode_data_url(f, "image/jpeg") for f in frames]
                media_type = "video"
            elif _is_image(filename, mime):
                img_mime = mime if (mime and mime.lower().startswith("image/")) else _guess_image_mime(filename)
                data_urls = [_encode_data_url(file_bytes, img_mime)]
                media_type = "image"
            else:
                data_urls = [_encode_data_url(file_bytes, "image/jpeg")]
                media_type = "unknown"

            response = await self.client.chat_with_images(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                image_data_urls=data_urls,
                temperature=float(config.get("temperature", 0.3)),
            )
            parsed = _parse_llm_response(response.get("content", ""))
            parsed["media_type"] = parsed.get("media_type") or media_type
            parsed["_input"] = {
                "filename": filename,
                "size_bytes": len(file_bytes),
                "frames_sent": len(data_urls),
                "media_kind": media_type,
            }
            parsed["_usage"] = response.get("usage", {})

            return RecognitionResult(
                success=True,
                data=parsed,
                summary=parsed.get("summary") or parsed.get("description", "")[:80],
                error_code=None,
                error_message=None,
                raw_response=response,
                cost_estimate=0.0,
                duration_ms=int((time.monotonic() - start) * 1000),
            )
        except Exception as e:
            logger.exception("MultimodalLLMEngine 识别失败")
            return RecognitionResult(
                success=False,
                data=None,
                summary=f"多模态识别失败: {e}",
                error_code="MULTIMODAL_LLM_ERROR",
                error_message=str(e),
                raw_response=None,
                cost_estimate=0.0,
                duration_ms=int((time.monotonic() - start) * 1000),
            )

    async def health_check(self, config: dict[str, Any]) -> bool:
        return True

    async def aclose(self) -> None:
        await self.client.close()
