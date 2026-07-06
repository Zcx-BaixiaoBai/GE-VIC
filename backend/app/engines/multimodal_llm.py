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


def _build_llm_overrides(config: dict) -> dict:
    """Extract per-algorithm LLM overrides from engine_config.

    Returns a dict of overrides usable by LLMClient.__init__(overrides=...).
    Empty values (None / "" / 0) are dropped so the global settings still apply.
    Also auto-derives a sensible timeout based on max_output_tokens so
    reasoning models / large-output calls don't get killed by the 30s default.
    """
    out: dict = {}
    base_url = config.get("llm_base_url")
    if isinstance(base_url, str) and base_url.strip():
        out["base_url"] = base_url.strip()
    api_key = config.get("llm_api_key")
    if isinstance(api_key, str) and api_key.strip():
        out["api_key"] = api_key.strip()
    model = config.get("llm_model")
    if isinstance(model, str) and model.strip():
        out["model"] = model.strip()
    for k_in, k_out in (("max_input_tokens", "max_input_tokens"), ("max_output_tokens", "max_output_tokens")):
        v = config.get(k_in)
        if v is not None and v != "":
            try:
                iv = int(v)
                if iv > 0:
                    out[k_out] = iv
            except (TypeError, ValueError):
                pass
    if "llm_mock_mode" in config:
        out["mock_mode"] = bool(config["llm_mock_mode"])

    # Auto-derive timeout: 60s base + max_output_tokens * 60ms/tok + reasoning buffer
    # Examples:
    #   max_output_tokens=20000 + reasoning model -> 60 + 1200 + 30 = 1290s (capped at 600)
    #   max_output_tokens=1000                  -> 60 + 60 = 120s
    explicit_timeout = config.get("llm_timeout")
    if explicit_timeout is not None:
        try:
            out["timeout"] = float(explicit_timeout)
        except (TypeError, ValueError):
            pass
    elif "max_output_tokens" in out:
        mo = out["max_output_tokens"]
        model_lower = (out.get("model") or "").lower()
        is_reasoning = any(t in model_lower for t in ("reasoning", "thinking", "nemotron", "o1", "o3", "qwq", "deepseek-r1"))
        reasoning_buf = 30.0 if is_reasoning else 0.0
        derived = 60.0 + (mo * 0.06) + reasoning_buf
        out["timeout"] = min(600.0, max(60.0, derived))
    return out

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



def _parse_markdown_report(content):
    """Parse a Markdown inspection report (LLM output) into structured fields."""
    import re

    COLON_CLASS = r"[：:，,、]"
    out = {
        "summary": "",
        "description": content.strip() if content else "",
        "observations": [],
        "warnings": [],
        "_format": "markdown",
    }
    if not content:
        return out

    def _clean(s):
        if not s:
            return s
        s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
        s = re.sub(r"\*([^*]+)\*", r"\1", s)
        s = s.replace("**", "")
        return s.strip()

    lines = content.split("\n")

    # === 1) WARNINGS ===
    warn_lines = []
    for i, line in enumerate(lines):
        # ## 段标题 (整段)
        if re.match(r"^#+\s+[^\n]*(?:安全|警示|⚠)", line):
            for j in range(i + 1, len(lines)):
                if lines[j].startswith("## "):
                    break
                t = lines[j].strip().lstrip("-*• ").strip()
                if t and not t.startswith("---") and not t.startswith("#") and not t.startswith("|"):
                    warn_lines.append(_clean(t)[:300])
            continue
        # 行内 bold 标题: **安全警示**：内容
        m = re.search(r"(\*\*(?:安全|警示|⚠)[^*]*\*\*)[ \t]*[:：]?\s*(.*)$", line)
        if m:
            inline = m.group(2).strip()
            if inline:
                warn_lines.append(_clean(inline)[:300])
    out["warnings"] = warn_lines

    # === 2) SUMMARY ===
    for i, line in enumerate(lines):
        if re.match(r"^#+\s+[^\n]*(?:整体评估|总体评估|总结|总评|总体)", line):
            for j in range(i + 1, len(lines)):
                t = lines[j].strip().lstrip("-*• ").strip()
                if t.startswith("## ") and not t.startswith("###"):
                    break
                if not t or t.startswith("#") or t.startswith("|") or t.startswith("---"):
                    continue
                out["summary"] = _clean(t)[:300]
                break
            break

    # === 3) DEVICE SECTIONS ===
    device_indices = [i for i, l in enumerate(lines) if re.match(r"^#{2,4}\s+[^\n]*设备[^\n]*" + COLON_CLASS, l)]
    for idx_i, start_i in enumerate(device_indices):
        heading = lines[start_i]
        name = re.sub(r"^#+\s+设备\s*\d+\s*" + COLON_CLASS + r"\s*", "", heading)
        name = _clean(name).strip()
        if not name:
            continue
        end_i = device_indices[idx_i + 1] if idx_i + 1 < len(device_indices) else len(lines)
        sec_lines = lines[start_i + 1:end_i]
        sec = "\n".join(sec_lines)

        obs = {
            "label": name, "type": "", "confidence": "", "status": "",
            "note": "", "risk": "", "parameters": [], "recommendation": "",
            "brand": "",
        }

        # 两列 key-value 表
        for k, v in re.findall(r"\|\s*([^|\n]+?)\s*\|\s*([^|\n]+?)\s*\|", sec):
            k = k.strip()
            v = v.strip()
            if re.match(r"^[-:\s]+$", k) or re.match(r"^[-:\s]+$", v):
                continue
            v = _clean(v)
            if any(x in k for x in ["类别", "Category", "category", "类型"]):
                obs["type"] = v
            elif any(x in k for x in ["品牌型号", "品牌", "Brand", "model"]):
                obs["brand"] = v
            elif k in ("运行状态", "status", "Status", "状态"):
                obs["status"] = v
            elif any(x in k for x in ["识别置信度", "confidence", "置信度"]):
                obs["confidence"] = v

        # 四列 参数/读数/单位/偏离 表
        for r in re.findall(r"\|\s*([^|\n]+?)\s*\|\s*([^|\n]+?)\s*\|\s*([^|\n]+?)\s*\|\s*([^|\n]+?)\s*\|", sec):
            k, v1, u, d = r[0].strip(), r[1].strip(), r[2].strip(), r[3].strip()
            if re.match(r"^[-:\s]+$", k) or re.match(r"^[-:\s]+$", v1):
                continue
            if k in ("参数", "Parameter", "param", "项目") or u in ("单位", "Unit"):
                continue
            if k and v1:
                obs["parameters"].append({
                    "key": k, "value": _clean(v1),
                    "unit": _clean(u), "deviation": _clean(d),
                })

        # 风险评级
        risk_m = re.search(
            r"风险评级[^\n]*?([🟢🟡🔴⚪✅❌])",
            sec,
        )
        if not risk_m:
            risk_m = re.search(
                r"风险评级[^\n]*?(正常运行|预警|故障|不明|较差|偏差)",
                sec,
            )
        if risk_m:
            obs["risk"] = risk_m.group(1)

        # 状态分析/描述 - 行内 + 后续列表
        for li, line in enumerate(sec_lines):
            m = re.search(r"\*\*状态(?:分析|描述)\*\*[ \t]*[:：]?\s*(.*)$", line)
            if m:
                inline = m.group(1).strip()
                if inline:
                    obs["note"] = _clean(inline)[:300]
                else:
                    for j in range(li + 1, len(sec_lines)):
                        t = sec_lines[j].strip()
                        if t.startswith("**") or t.startswith("#") or t.startswith("|"):
                            break
                        if t.startswith(("-", "*", "•")):
                            text = re.sub(r"^[-*•\s]+", "", t).strip()
                            if text:
                                obs["note"] = _clean(text)[:300]
                                break
                break

        # 巡检建议/提示 - 行内 + 后续列表
        for li, line in enumerate(sec_lines):
            m = re.search(r"\*\*巡检(?:建议|提示)\*\*[ \t]*[:：]?\s*(.*)$", line)
            if m:
                inline = m.group(1).strip()
                if inline:
                    pm = re.search(r"P[0-3]\s*(?:紧急|高|中|低)?", inline)
                    if pm:
                        obs["recommendation"] = pm.group(0).strip()
                    obs["recommendation_detail"] = _clean(inline)[:300]
                else:
                    for j in range(li + 1, len(sec_lines)):
                        t = sec_lines[j].strip()
                        if t.startswith("**") or t.startswith("#") or t.startswith("|"):
                            break
                        if t.startswith(("-", "*", "•")):
                            text = re.sub(r"^[-*•\s]+", "", t).strip()
                            if text:
                                pm = re.search(r"P[0-3]\s*(?:紧急|高|中|低)?", text)
                                if pm:
                                    obs["recommendation"] = pm.group(0).strip()
                                obs["recommendation_detail"] = _clean(text)[:300]
                                break
                break

        out["observations"].append(obs)

    if not out["observations"] and out["description"]:
        out["observations"].append({
            "label": "整体分析",
            "type": "", "confidence": "", "status": "",
            "note": out["description"][:300], "risk": "",
            "parameters": [], "recommendation": "",
        })

    return out


def _parse_llm_response(content: str) -> dict[str, Any]:
    """智能解析 LLM 响应: 先尝试 JSON, 失败则尝试 Markdown 报告.

    1. 尝试 JSON 解析 (parse_json_response + 容错修复)
    2. JSON 失败 或 observations 为空, 尝试 Markdown 报告解析
    3. 都失败则用 fallback (整段文本塞 description)
    """
    parsed = parse_json_response(content)
    # 判断是否需要尝试 markdown 解析:
    # - JSON 解析失败 (没有 _input 字段) 或 observations 为空 + 文本含 ## 标题
    looks_like_markdown = "##" in content or "###" in content
    is_structured = isinstance(parsed.get("observations"), list) and len(parsed["observations"]) > 0
    if not is_structured and looks_like_markdown:
        md_parsed = _parse_markdown_report(content)
        # 优先用 markdown 解析的结构, 但保留 JSON 解析的 summary (如果有)
        if md_parsed.get("observations"):
            # 合并: markdown 为主, 缺失字段从 JSON 拿
            for k in ("summary", "description", "media_type"):
                if not md_parsed.get(k) and parsed.get(k):
                    md_parsed[k] = parsed[k]
            parsed = md_parsed
    return parsed


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

            llm_overrides = _build_llm_overrides(config)
            client = LLMClient(self.settings, overrides=llm_overrides) if llm_overrides else self.client
            response = await client.chat_with_images(
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
            parsed["_model"] = response.get("model", "")
            parsed["_usage"] = response.get("usage", {})
            # 保存 LLM 原始响应 (含 <think> 等), 便于前端调试
            parsed["_raw_llm_content"] = response.get("content", "")

            return RecognitionResult(
                success=True,
                data=parsed,
                summary=parsed.get("summary") or (parsed.get("description", "").split("\n")[0] if parsed.get("description") else "")[:200],
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

    async def recognize_batch(
        self,
        files: list,
        meta: dict[str, Any],
        config: dict[str, Any],
    ) -> "RecognitionResult":
        """联合识别: 一次调用 LLM, 把所有图片一起发给模型做交叉分析.

        对每个文件做: 抽帧 (视频) -> base64 编码 -> 拼成 data_urls
        所有 data_urls 在一个 chat_with_images() 调用里发给 LLM
        """
        import time
        from app.engines.base import BatchFileItem

        start = time.monotonic()
        system_prompt = config.get("prompt") or DEFAULT_SYSTEM_PROMPT
        user_prompt_template = config.get("user_prompt") or DEFAULT_USER_PROMPT
        n_frames = int(config.get("extract_frames", 3))
        if n_frames < 1: n_frames = 1
        if n_frames > 8: n_frames = 8

        # 在 user_prompt 里明确告诉 LLM 这是联合分析
        if len(files) > 1:
            user_prompt_template = (
                user_prompt_template
                + f"\n\n本次共 {len(files)} 张图/视频, 请联合分析 (cross-reference) 它们的共同特征、设备状态、异常情况, 给出整体结论。"
            )

        try:
            all_data_urls: list[str] = []
            per_file_meta: list[dict] = []
            for idx, f in enumerate(files):
                file_bytes = f["bytes"]
                filename = f.get("filename", f"file_{idx}.bin")
                mime = f.get("mime")

                if _is_video(filename, mime):
                    frames = _extract_video_frames(file_bytes, filename, n_frames=n_frames)
                    if frames:
                        for fr in frames:
                            all_data_urls.append(_encode_data_url(fr, "image/jpeg"))
                elif _is_image(filename, mime):
                    img_mime = mime if (mime and mime.lower().startswith("image/")) else _guess_image_mime(filename)
                    all_data_urls.append(_encode_data_url(file_bytes, img_mime))
                else:
                    all_data_urls.append(_encode_data_url(file_bytes, "image/jpeg"))

                per_file_meta.append({
                    "index": idx,
                    "filename": filename,
                    "mime": mime,
                    "size_bytes": len(file_bytes),
                })

            if not all_data_urls:
                return RecognitionResult(
                    success=False,
                    data=None,
                    summary=None,
                    error_code="BATCH_NO_IMAGES",
                    error_message="No images extracted from batch",
                    raw_response=None,
                    cost_estimate=0.0,
                    duration_ms=int((time.monotonic() - start) * 1000),
                )

            # per-call LLM client
            from app.engines.multimodal_llm import _build_llm_overrides
            llm_overrides = _build_llm_overrides(config)
            client = LLMClient(self.settings, overrides=llm_overrides) if llm_overrides else self.client
            if client.mock_mode:
                return RecognitionResult(
                    success=True,
                    data={"_mock": True, "_batch_size": len(files)},
                    summary=f"Mock 联合识别 {len(files)} 个文件",
                    error_code=None,
                    error_message=None,
                    raw_response=None,
                    cost_estimate=0.0,
                    duration_ms=0,
                )

            meta_str = ", ".join(f"{k}={v}" for k, v in (meta or {}).items() if v is not None)
            user_prompt = user_prompt_template
            if meta_str:
                user_prompt = f"{user_prompt}\n\n{len(files)} 个文件: {meta_str}"

            response = await client.chat_with_images(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                image_data_urls=all_data_urls,
                temperature=float(config.get("temperature", 0.3)),
            )
            parsed = _parse_llm_response(response.get("content", ""))
            parsed["media_type"] = "batch"
            parsed["batch_size"] = len(files)
            parsed["files"] = per_file_meta
            parsed["_input"] = {
                "files": per_file_meta,
                "total_data_urls_sent": len(all_data_urls),
            }
            parsed["_model"] = response.get("model", "")
            parsed["_usage"] = response.get("usage", {})
            parsed["_raw_llm_content"] = response.get("content", "")

            return RecognitionResult(
                success=True,
                data=parsed,
                summary=parsed.get("summary") or (parsed.get("description", "").split("\n")[0] if parsed.get("description") else "")[:200],
                error_code=None,
                error_message=None,
                raw_response=response,
                cost_estimate=0.0,
                duration_ms=int((time.monotonic() - start) * 1000),
            )
        except Exception as e:
            logger.exception("MultimodalLLMEngine batch recognition failed")
            return RecognitionResult(
                success=False,
                data=None,
                summary=f"联合识别失败: {e}",
                error_code="BATCH_LLM_ERROR",
                error_message=str(e),
                raw_response=None,
                cost_estimate=0.0,
                duration_ms=int((time.monotonic() - start) * 1000),
            )

    async def health_check(self, config: dict[str, Any]) -> dict[str, Any]:
        """真实测一次 LLM (用 per-algorithm overrides).

        Returns:
            {ok: bool, message: str, model?: str, prompt_tokens?: int,
             completion_tokens?: int, total_tokens?: int, duration_ms?: int,
             error_code?: str}
        """
        import time
        overrides = _build_llm_overrides(config)
        client = LLMClient(self.settings, overrides=overrides) if overrides else self.client
        # mock 模式: 走 mock 路径也能算"通"
        if client.mock_mode:
            return {"ok": True, "message": "mock 模式 (未发起真实调用)", "duration_ms": 0}
        start = time.monotonic()
        try:
            r = await client.chat(
                system_prompt="You are a connectivity test assistant.",
                user_prompt="Reply with the single word: OK",
                temperature=0.0,
            )
            duration = int((time.monotonic() - start) * 1000)
            return {
                "ok": True,
                "message": "LLM 调用成功",
                "model": r.get("model", ""),
                "prompt_tokens": r.get("usage", {}).get("prompt_tokens", 0),
                "completion_tokens": r.get("usage", {}).get("completion_tokens", 0),
                "total_tokens": r.get("usage", {}).get("total_tokens", 0),
                "duration_ms": duration,
            }
        except Exception as e:
            return {
                "ok": False,
                "message": f"LLM 调用失败: {e}",
                "error_code": "LLM_TEST_FAILED",
                "duration_ms": int((time.monotonic() - start) * 1000),
            }

    async def aclose(self) -> None:
        await self.client.close()
