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
import os
import subprocess
import tempfile
from typing import Any

from app.engines.base import BaseEngine, RecognitionResult
from app.services.llm_client import (
    LLMClient,
    get_shared_llm_client,
    make_strict_json_prompt,
    parse_json_response,
)
from app.config import Settings
from app.utils.exceptions import LLMError


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


def _get_ffmpeg_exe() -> str | None:
    """Return a usable ffmpeg binary path (bundled imageio-ffmpeg first, then PATH)."""
    try:
        import imageio_ffmpeg as iff
        return iff.get_ffmpeg_exe()
    except Exception:
        pass
    import shutil
    return shutil.which("ffmpeg")


def _probe_duration(ffmpeg: str, in_path: str) -> float | None:
    """Probe video duration in seconds via ffmpeg stderr."""
    import re as _re
    try:
        r = subprocess.run(
            [ffmpeg, "-hide_banner", "-i", in_path],
            capture_output=True, text=True, timeout=60,
        )
    except Exception:
        return None
    text = (r.stderr or "") + (r.stdout or "")
    m = _re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
    if not m:
        return None
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def _extract_video_frames(
    file_bytes: bytes,
    filename: str,
    n_frames: int = 3,
    max_long_edge: int = 1024,
    frame_fps: float = 2.0,
    max_frames: int = 16,
) -> list[bytes]:
    """Extract frames evenly across the WHOLE video duration.

    Density is `frame_fps` frames/second, capped at `max_frames`. For long
    videos the effective fps is lowered so samples still span the entire
    timeline (never just the first few seconds). Frames are downscaled so the
    long edge <= max_long_edge and returned as JPEG bytes.

    Uses the ffmpeg binary bundled with imageio-ffmpeg (no system ffmpeg
    needed). Returns [] on failure.
    """
    ffmpeg = _get_ffmpeg_exe()
    if ffmpeg is None:
        logger.error("ffmpeg not found; install imageio-ffmpeg: pip install imageio-ffmpeg")
        return []

    ext = ""
    name = (filename or "").lower()
    for e in (".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".ts"):
        if name.endswith(e):
            ext = e
            break
    in_fd, in_path = tempfile.mkstemp(suffix=ext or ".mp4")
    try:
        os.write(in_fd, file_bytes)
        os.close(in_fd)

        duration = _probe_duration(ffmpeg, in_path)
        if duration and duration > 0:
            eff_fps = min(frame_fps, max_frames / duration)
        else:
            eff_fps = frame_fps
        if eff_fps <= 0:
            eff_fps = 1.0 / 30.0

        with tempfile.TemporaryDirectory() as outdir:
            vf = (
                f"fps={eff_fps},"
                f"scale='if(gte(iw,ih),min({max_long_edge},iw),-2)':"
                f"'if(gte(iw,ih),-2,min({max_long_edge},ih))'"
            )
            out_pat = os.path.join(outdir, "f_%04d.jpg")
            proc = subprocess.run(
                [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", in_path,
                 "-vf", vf, "-frames:v", str(max_frames), "-q:v", "3",
                 "-f", "image2", out_pat],
                capture_output=True, text=True, timeout=300,
            )
            files = sorted(f for f in os.listdir(outdir) if f.endswith(".jpg"))
            result: list[bytes] = []
            for f in files:
                with open(os.path.join(outdir, f), "rb") as fh:
                    result.append(fh.read())
            if not result and proc.returncode != 0:
                logger.warning("ffmpeg frame extraction failed (%s): %s", filename, (proc.stderr or "")[-400:])
            return result[:max_frames]
    except Exception as e:
        logger.warning("video frame extraction failed (%s): %s", filename, e)
        return []
    finally:
        try:
            os.unlink(in_path)
        except OSError:
            pass


def _resize_image_bytes(
    file_bytes: bytes,
    mime: str,
    max_long_edge: int = 1536,
    quality: int = 85,
) -> tuple[bytes, str]:
    """Downscale an image so its long edge <= max_long_edge; return (jpeg_bytes, mime).

    Falls back to the original bytes if Pillow is missing or decoding fails.
    Cuts LLM input size / vision tokens dramatically for large photos.
    """
    try:
        import io
        from PIL import Image
        img = Image.open(io.BytesIO(file_bytes))
        img = img.convert("RGB")
        w, h = img.size
        if max(w, h) > max_long_edge:
            if w >= h:
                nw, nh = max_long_edge, round(h * max_long_edge / w)
            else:
                nw, nh = round(w * max_long_edge / h), max_long_edge
            img = img.resize((nw, nh), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        return buf.getvalue(), "image/jpeg"
    except Exception as e:
        logger.warning("image resize failed (%s): %s; sending original", mime, e)
        return file_bytes, mime


def _encode_data_url(data: bytes, mime: str) -> str:
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{b64}"



def _strip_think_tags(text: str) -> str:
    """移除 LLM 输出中的 <think>...</think> 块 (MiniMax, DeepSeek R1 等推理模型)"""
    if not text:
        return text
    import re as _re
    text = _re.sub(r"<think>.*?</think>", "", text, flags=_re.DOTALL)
    text = _re.sub(r"<think>.*$", "", text, flags=_re.DOTALL)
    return text.strip()


def _clean_description(text: str) -> str:
    """清理 description 字段: 去除 <think> 块、JSON 代码块标记, 截短"""
    if not text:
        return text
    text = _strip_think_tags(text)
    import re as _re
    text = _re.sub(r"^```[a-zA-Z]*\n", "", text)
    text = _re.sub(r"\n```\s*$", "", text)
    text = text.strip()
    if len(text) > 600:
        text = text[:600].rstrip() + "…"
    return text


def _parse_markdown_report(content):
    """Parse a Markdown inspection report (LLM output) into structured fields."""
    import re

    COLON_CLASS = r"[：:，,、]"
    out = {
        "summary": "",
        "description": "",  # 由下面填充: 标题后的第一个描述段
        "observations": [],
        "warnings": [],
        "_format": "markdown",
    }
    if not content:
        return out
    text = content

    # 描述: 提取标题后的第一个非标题非列表非表格段落 (最多 3 句, 400 字)
    desc_lines = []
    past_title = False
    for _line in text.split("\n"):
        _s = _line.strip()
        if not _s:
            continue
        if _s.startswith("#"):
            past_title = True
            continue
        if not past_title:
            continue
        # 排除列表 (以 - * • 开头后接空格) 和表格 (|) 和水平线 (---)
        is_list = bool(re.match(r"^[-*\u2022]\s+", _s))
        if is_list or _s.startswith("|") or _s.startswith("---"):
            if desc_lines:  # 如果已经积累了一些描述, 遇到列表就停止
                break
            continue
        # 去掉粗体/斜体标记
        _s = re.sub(r"\*\*([^*]+)\*\*", r"\1", _s)
        _s = re.sub(r"\*([^*]+)\*", r"\1", _s)
        _s = _s.replace("**", "")
        desc_lines.append(_s)
        if len(desc_lines) >= 3:
            break
    if desc_lines:
        out["description"] = " ".join(desc_lines)[:400]

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


def _clean_str(v) -> str:
    """Coerce to a trimmed string; None/NaN/dict -> '' or json."""
    if v is None:
        return ""
    if isinstance(v, (dict, list)):
        try:
            import json as _json
            return _json.dumps(v, ensure_ascii=False)
        except Exception:
            return str(v)
    s = str(v).strip()
    if s.lower() in ("nan", "none", "null"):
        return ""
    return s


def _to_confidence(v):
    """Coerce 0.9 / '90%' / '90' -> float in [0,1], else None."""
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        f = float(v)
    else:
        s = str(v).strip().rstrip("%").replace("\uff0c", ".").replace(",", ".")
        try:
            f = float(s)
        except ValueError:
            return None
    if f > 1.0:  # assume percentage (90 -> 0.9)
        f = f / 100.0
    if f < 0:
        return None
    return round(f, 4)


def _extract_confidence(text: str):
    """Pull a confidence value out of free text like '置信度90%' / 'confidence: 0.8'."""
    import re
    m = re.search(r"(?:置信度|confidence|可信度)[:：]?\s*(\d+(?:\.\d+)?%?)", text or "", re.IGNORECASE)
    return _to_confidence(m.group(1)) if m else None


def _extract_priority(text: str) -> str:
    """Pull a P0-P3 priority tag out of free text (ASCII boundaries only)."""
    import re
    m = re.search(r"(?<![A-Za-z0-9])(P[0-3])(?![A-Za-z0-9])", text or "")
    return m.group(1) if m else ""


# Canonical risk mapping (the frontend classifies by substring):
#   high   = severe / fault / urgent / red / P0
#   medium = warning / deviation / yellow / P1
#   low    = normal / green / P2 / P3
_RISK_HIGH = ("严重", "故障", "紧急", "危急", "高风险", "\U0001f534", "p0")
_RISK_MED = ("预警", "偏差", "较差", "较高", "异常", "中风险", "\U0001f7e1", "\U0001f7e0", "p1")
_RISK_LOW = ("正常", "良好", "低风险", "\U0001f7e2", "\u2705", "p2", "p3")


def _normalize_risk(v) -> str:
    """Map free-form risk/severity to a canonical label the frontend can classify."""
    s = _clean_str(v)
    if not s:
        return ""
    low = s.lower()
    if any(k in low for k in _RISK_HIGH):
        return "严重"
    if any(k in low for k in _RISK_MED):
        return "预警"
    if any(k in low for k in _RISK_LOW):
        return "正常"
    return ""


_NEG_KW = ("未检出", "未发现", "未见", "无明显异常", "无异常", "未观察到", "无缺陷", "未察觉")


def _is_negative_obs(label: str, note: str, risk: str, recommendation: str) -> bool:
    """True if this observation represents a no-finding (未检出/正常), to be shown
    in a separate 'undetected' section instead of mixed into findings/alarms."""
    hay = (f"{label} {note}").lower()
    if any(k in hay for k in _NEG_KW):
        return True
    # no priority recommendation + risk is explicitly normal => no-finding
    if not recommendation and risk == "正常":
        return True
    return False


def _normalize_parameters(v) -> list:
    if not isinstance(v, list):
        return []
    out = []
    for p in v:
        if not isinstance(p, dict):
            continue
        out.append({
            "key": _clean_str(p.get("key") or p.get("name") or p.get("参数")),
            "value": _clean_str(p.get("value") or p.get("值")),
            "unit": _clean_str(p.get("unit") or p.get("单位")),
            "deviation": _clean_str(p.get("deviation") or p.get("偏差")),
        })
    return out


def _normalize_observation(o) -> dict:
    """Coerce one observation (JSON/markdown/text) into the canonical schema.

    Missing confidence/risk/priority are re-extracted from the note text so
    that markdown/prose outputs (which often embed these inline) still yield
    structured fields.
    """
    import re as _re
    if not isinstance(o, dict):
        o = {"label": str(o)}
    label = _clean_str(o.get("label") or o.get("name") or o.get("device") or o.get("设备")) or "未命名"
    label = _re.sub(r"^#+\s*", "", label).strip(" :：")
    note = _strip_think_tags(_clean_str(o.get("note") or o.get("description") or o.get("detail") or o.get("描述")))
    confidence = _to_confidence(o.get("confidence") or o.get("置信度"))
    risk = _normalize_risk(o.get("risk") or o.get("severity") or o.get("风险") or o.get("风险等级"))
    recommendation = _clean_str(o.get("recommendation") or o.get("priority"))
    # fallback: pull structured bits out of the note text (smarter parsing)
    hay = f"{label} {note}"
    if confidence is None:
        confidence = _extract_confidence(hay)
    if not risk:
        risk = _normalize_risk(hay)
    if not recommendation:
        recommendation = _extract_priority(hay)
    is_neg = _is_negative_obs(label, note, risk, recommendation)
    return {
        "label": label,
        "type": _clean_str(o.get("type") or o.get("category") or o.get("类别")),
        "confidence": confidence,
        "status": _clean_str(o.get("status") or o.get("state") or o.get("运行状态")),
        "risk": risk,
        "note": note,
        "brand": _clean_str(o.get("brand") or o.get("model") or o.get("品牌型号")),
        "parameters": _normalize_parameters(o.get("parameters")),
        "recommendation": recommendation,
        "recommendation_detail": _clean_str(o.get("recommendation_detail") or o.get("recommendation_text") or o.get("建议")),
        "is_negative": is_neg,
    }


def _normalize_warnings(v) -> list:
    if isinstance(v, str):
        return [v.strip()] if v.strip() else []
    if not isinstance(v, list):
        return []
    out = []
    for w in v:
        if isinstance(w, dict):
            s = _clean_str(w.get("message") or w.get("text") or w.get("content"))
        else:
            s = _clean_str(w)
        if s:
            out.append(s)
    return out


def _normalize_recognition(parsed, media_type_hint: str, fmt: str) -> dict[str, Any]:
    """Normalization harness: ALWAYS return the canonical recognition schema.

    Guarantees the frontend gets stable fields + correct types even when the
    LLM returns markdown, prose, partial JSON, or odd value types.
    """
    if not isinstance(parsed, dict):
        parsed = {"description": str(parsed or "")}
    desc = _clean_description(_clean_str(parsed.get("description")))
    if not desc:
        desc = _clean_description(_clean_str(parsed.get("overview") or parsed.get("content")))
    obs_raw = parsed.get("observations")
    if not isinstance(obs_raw, list):
        obs_raw = []
    observations = [_normalize_observation(o) for o in obs_raw if o is not None]
    if not observations and desc:
        observations = [{
            "label": "整体分析", "type": "", "confidence": None, "status": "",
            "risk": "", "note": desc[:300], "brand": "", "parameters": [],
            "recommendation": "", "recommendation_detail": "",
        }]
    summary = _strip_think_tags(_clean_str(parsed.get("summary")))
    if not summary and desc:
        summary = desc.split("\n")[0][:200]
    return {
        "media_type": _clean_str(parsed.get("media_type")) or media_type_hint or "",
        "description": desc,
        "summary": summary,
        "observations": observations,
        "warnings": _normalize_warnings(parsed.get("warnings")),
        "_format": fmt or _clean_str(parsed.get("_format")),
    }


def _parse_structured_text(text: str) -> dict[str, Any]:
    """Smarter fallback for prose / bullet-list / key:value outputs.

    Handles models that ignore JSON and return plain text with sections,
    bullet lists, or 'label：value' lines. Produces observations[] + summary.
    """
    import re
    out: dict[str, Any] = {"summary": "", "description": "", "observations": [], "warnings": [], "_format": "text"}
    if not text:
        return out
    lines = [l.rstrip() for l in text.split("\n")]
    bullets: list[str] = []
    for raw in lines:
        s = raw.strip()
        if not s:
            continue
        bm = re.match(r"^([-*\u2022]|\d+[.)])\s+(.+)$", s)
        if bm:
            bullets.append(bm.group(2).strip())
        elif bullets and (raw.startswith("  ") or not re.match(r"^[-*\u2022\d#]", s)):
            if bullets:
                bullets[-1] = bullets[-1] + " " + s
    heads = [re.sub(r"^#+\s*", "", l.strip()).strip(" :：") for l in lines if l.strip().startswith("#")]
    items = bullets  # headings are section labels, not observations
    if items:
        for it in items:
            it = it.strip()
            if not it:
                continue
            # extract structured bits from free text (smarter parsing)
            conf = None
            cm = re.search(r"置信度[:：]?\s*(\d+(?:\.\d+)?%?)", it)
            if cm:
                conf = _to_confidence(cm.group(1))
            rec = ""
            rcm = re.search(r"\b(P[0-3])\b", it)
            if rcm:
                rec = rcm.group(1)
            risk = _normalize_risk(it)
            m = re.split(r"[\uff1a:]\s*", it, maxsplit=1)
            if len(m) == 2 and len(m[0]) < 24:
                label, note = m[0].strip(), m[1].strip()
            elif len(it) > 24:
                label, note = it[:24], it
            else:
                label, note = it, ""
            out["observations"].append({
                "label": label, "note": note[:300],
                "confidence": conf, "risk": risk, "recommendation": rec,
            })
    for l in lines:
        s = l.strip()
        if s and not s.startswith("#") and not re.match(r"^([-*\u2022]|\d+[.)])\s+", s):
            out["summary"] = s[:200]
            break
    if not out["summary"] and items:
        out["summary"] = items[0][:200]
    out["description"] = " ".join(l.strip() for l in lines if l.strip() and not l.strip().startswith("#"))[:400]
    return out


def _looks_unsupported_response_format(err: Exception) -> bool:
    """Heuristic: did the provider reject response_format (json_object)?"""
    msg = str(err).lower()
    return any(k in msg for k in ("response_format", "json_object", "json schema", "not support", "unsupported", "invalid"))


def _parse_llm_response(content: str, media_type_hint: str = "") -> dict[str, Any]:
    """Parse LLM output into the canonical recognition schema.

    Layered (harness + smarter parsing):
      1. strip think/fences + JSON (with repair)
      2. markdown report if JSON yielded no observations
      3. structured-text (prose / bullets / key:value) if still nothing
      4. normalize to canonical schema (always present, correct types)
    """
    raw = content or ""
    parsed = parse_json_response(raw)
    fmt = "json"
    obs = parsed.get("observations") if isinstance(parsed.get("observations"), list) else []
    if not obs and ("##" in raw or "###" in raw):
        md = _parse_markdown_report(raw)
        if md.get("observations"):
            for k in ("summary", "description", "media_type", "warnings"):
                if not md.get(k) and parsed.get(k):
                    md[k] = parsed[k]
            parsed = md
            fmt = "markdown"
            obs = md.get("observations") or []
    # if observations are thin (no note/confidence/risk), the bare-bullet
    # structured-text parser is usually richer -> prefer it
    thin = not obs or not any(
        _clean_str(o.get("note")) or _clean_str(o.get("confidence")) or _clean_str(o.get("risk"))
        for o in obs if isinstance(o, dict)
    )
    if thin:
        txt = _parse_structured_text(raw)
        if txt.get("observations"):
            for k in ("summary", "description", "media_type"):
                if not txt.get(k) and parsed.get(k):
                    txt[k] = parsed[k]
            if not txt.get("warnings") and parsed.get("warnings"):
                txt["warnings"] = parsed.get("warnings")
            parsed = txt
            fmt = "text"
    return _normalize_recognition(parsed, media_type_hint, fmt)


class MultimodalLLMEngine(BaseEngine):
    """多模态 LLM 引擎 - 用 LLM 直接识别图片/视频内容"""

    engine_type = "multimodal_llm"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = get_shared_llm_client(settings)

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
        frame_fps = float(config.get("frame_fps", 2.0) or 2.0)
        max_frames = int(config.get("max_frames", 16) or 16)
        max_frames = max(1, min(32, max_frames))
        n_frames = max(1, min(8, int(config.get("extract_frames", 3) or 3)))
        image_max_edge = int(config.get("image_max_long_edge", 1536) or 1536)

        meta_str = ", ".join(f"{k}={v}" for k, v in (meta or {}).items() if v is not None)
        user_prompt = user_prompt_template
        if meta_str:
            user_prompt = f"{user_prompt}\n\n文件: {filename} ({len(file_bytes)} bytes)\n元数据: {meta_str}"

        mime = None
        if isinstance(meta, dict):
            mime = meta.get("mime_type") or meta.get("content_type")

        try:
            if _is_video(filename, mime):
                frames = _extract_video_frames(
                    file_bytes, filename,
                    n_frames=n_frames, frame_fps=frame_fps, max_frames=max_frames,
                )
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
                img_bytes, img_mime_out = _resize_image_bytes(file_bytes, img_mime, max_long_edge=image_max_edge)
                data_urls = [_encode_data_url(img_bytes, img_mime_out)]
                media_type = "image"
            else:
                data_urls = [_encode_data_url(file_bytes, "image/jpeg")]
                media_type = "unknown"

            llm_overrides = _build_llm_overrides(config)
            client = get_shared_llm_client(self.settings, overrides=llm_overrides) if llm_overrides else self.client
            json_mode = bool(config.get("json_mode", True))
            rf = {"type": "json_object"} if json_mode else None
            try:
                response = await client.chat_with_images(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    image_data_urls=data_urls,
                    temperature=float(config.get("temperature", 0.3)),
                    response_format=rf,
                )
            except LLMError as _e:
                if rf is not None and _looks_unsupported_response_format(_e):
                    logger.warning("model rejected response_format, retrying without: %s", _e)
                    response = await client.chat_with_images(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        image_data_urls=data_urls,
                        temperature=float(config.get("temperature", 0.3)),
                        response_format=None,
                    )
                else:
                    raise
            parsed = _parse_llm_response(response.get("content", ""), media_type_hint=media_type)
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
        frame_fps = float(config.get("frame_fps", 2.0) or 2.0)
        max_frames = int(config.get("max_frames", 16) or 16)
        max_frames = max(1, min(32, max_frames))
        n_frames = max(1, min(8, int(config.get("extract_frames", 3) or 3)))
        image_max_edge = int(config.get("image_max_long_edge", 1536) or 1536)

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
                    frames = _extract_video_frames(
                        file_bytes, filename,
                        n_frames=n_frames, frame_fps=frame_fps, max_frames=max_frames,
                    )
                    if frames:
                        for fr in frames:
                            all_data_urls.append(_encode_data_url(fr, "image/jpeg"))
                elif _is_image(filename, mime):
                    img_mime = mime if (mime and mime.lower().startswith("image/")) else _guess_image_mime(filename)
                    ib, im = _resize_image_bytes(file_bytes, img_mime, max_long_edge=image_max_edge)
                    all_data_urls.append(_encode_data_url(ib, im))
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
            client = get_shared_llm_client(self.settings, overrides=llm_overrides) if llm_overrides else self.client
            meta_str = ", ".join(f"{k}={v}" for k, v in (meta or {}).items() if v is not None)
            user_prompt = user_prompt_template
            if meta_str:
                user_prompt = f"{user_prompt}\n\n{len(files)} 个文件: {meta_str}"

            json_mode = bool(config.get("json_mode", True))
            rf = {"type": "json_object"} if json_mode else None
            try:
                response = await client.chat_with_images(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    image_data_urls=all_data_urls,
                    temperature=float(config.get("temperature", 0.3)),
                    response_format=rf,
                )
            except LLMError as _e:
                if rf is not None and _looks_unsupported_response_format(_e):
                    logger.warning("batch: model rejected response_format, retrying without: %s", _e)
                    response = await client.chat_with_images(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        image_data_urls=all_data_urls,
                        temperature=float(config.get("temperature", 0.3)),
                        response_format=None,
                    )
                else:
                    raise
            parsed = _parse_llm_response(response.get("content", ""), media_type_hint="batch")
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
        client = get_shared_llm_client(self.settings, overrides=overrides) if overrides else self.client
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
        # Engine instances are cached/shared (see factory.get_engine). Do NOT
        # close the shared LLM client here; it would break connection reuse.
        pass
