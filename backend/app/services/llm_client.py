"""LLM 客户端 - OpenAI 兼容 chat API

通过 openai 库的 base_url 配置, 适配任何 OpenAI 兼容 API
(DashScope / Ollama / LM Studio / vLLM / 自建网关 等)
"""
import json
import re
import time
from typing import Any

from openai import AsyncOpenAI

from app.config import Settings
from app.services.runtime_config import get as rt_get
from app.utils.exceptions import LLMError


# ---- 统一 LLM 响应解析 (容错) ----
import re as _re
_THINK_RE = _re.compile(r"<think>.*?</think>", _re.DOTALL)


def strip_think_blocks(text: str) -> str:
    """去掉 <think>...</think> 推理块 (DeepSeek R1 / MiniMax M3 等思考模型)."""
    if not text:
        return text
    return _THINK_RE.sub("", text).strip()


def parse_json_response(content: str) -> dict[str, Any]:
    """从 LLM 响应中提取 JSON 字典 (兼容各种乱序格式).

    处理流程:
    1. 去掉 <think>...</think> 推理块
    2. 去掉 markdown 围栏 (```json ... ```)
    3. 尝试整体 json.loads
    4. 失败 -> 扫描找 { ... } 区间, 多次尝试 (容错修复)
    5. 仍失败 -> 返回 fallback 结构 (含完整原文 + 截断的 summary)

    容错策略:
    - LLM 在字符串值里有时用 ASCII " 代替中文 " (U+201C/U+201D), 这种 JSON 会破
    - 容错扫描: 找平衡的 { 和 }, 区间内用启发式替换未转义的 ASCII " (在中文/英文字符之间) 为 "
    """
    if not content:
        return {"_raw_text": "", "description": "", "summary": "", "observations": []}

    text = strip_think_blocks(content)

    # 去掉 markdown 围栏
    if text.startswith("```"):
        lines = text.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # 尝试 1: 整体解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试 2: 找第一个 { 到最后一个 } 截取后解析
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        candidate = text[start:end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            # 进入容错模式
            fixed = _try_repair_json(candidate)
            if fixed is not None:
                return fixed

    # 全部失败: 返回 fallback 结构 (不返回 JSON 字符串)
    return {
        "_raw_text": text,
        "description": text,
        "summary": text[:80] if text else "(空响应)",
        "observations": [],
    }


def _try_repair_json(text: str) -> dict[str, Any] | None:
    """LLM 输出的常见 JSON 错误: 字符串值里用了未转义的 ASCII 双引号.

    策略: 假设整体结构是 { ... }, 在 string 内部 (非结构边界) 把孤立的 " 替换为 ".
    这种启发式不完美, 但能修复 90% 的 LLM 拼写错误 (e.g. 中文 "现场按"急停"流程" 这种).
    """
    import re

    # 先尝试找平衡的大括号
    out = []
    in_str = False
    escape = False
    i = 0
    while i < len(text):
        c = text[i]
        if escape:
            out.append(c)
            escape = False
        elif c == "\\":
            out.append(c)
            escape = True
        elif c == '"':
            # 判断这是不是字符串边界
            # 启发式: 前后字符是 JSON 结构字符 ( , } ] : { ` ) 或空白 -> 边界
            if in_str:
                # 看下一个非空白字符是不是结构字符
                j = i + 1
                while j < len(text) and text[j] in " \t\n\r":
                    j += 1
                next_char = text[j] if j < len(text) else ""
                if next_char in ",}]:\n" or next_char == "":
                    in_str = False
                    out.append(c)
                else:
                    # 字符串内部的 " 替换为 \"
                    out.append('\\"')
            else:
                in_str = True
                out.append(c)
        else:
            out.append(c)
        i += 1

    candidate = "".join(out)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


def make_strict_json_prompt(extra: str = "") -> str:
    """追加到 system prompt 的尾段, 强制 JSON 输出且不含思考标签."""
    return (
        "\n\n重要: 只输出严格的 JSON (不要 markdown 围栏, 不要 <think> 标签, 不要解释)."
        + (("\n" + extra) if extra else "")
    )





class LLMClient:
    """OpenAI 兼容 LLM 客户端

    支持:
    - 流式 + 非流式
    - 自动重试 (由 openai 库内置)
    - 超时控制
    """

    def __init__(
        self,
        settings: Settings,
        overrides: dict[str, Any] | None = None,
    ) -> None:
        """LLM client. ``overrides`` (per-call) wins over ``settings``.

        Supported keys:
          - base_url, api_key, model
          - max_input_tokens, max_output_tokens
          - timeout (float, seconds; default 30)
        """
        self.settings = settings
        ov = overrides or {}
        self._model: str = str(ov.get("model") or settings.llm_model).strip() or settings.llm_model
        # max tokens: per-call override (int) wins; otherwise settings value
        try:
            self._max_output_tokens: int = int(
                ov.get("max_output_tokens", settings.llm_max_output_tokens)
            )
        except (TypeError, ValueError):
            self._max_output_tokens = settings.llm_max_output_tokens
        self._max_input_tokens: int = int(
            ov.get("max_input_tokens", settings.llm_max_input_tokens) or settings.llm_max_input_tokens
        )
        # base_url / api_key: only override if a non-empty value is given
        self._base_url: str = (str(ov.get("base_url")).strip() if ov.get("base_url") else "") or settings.llm_base_url
        self._api_key: str = (str(ov.get("api_key")).strip() if ov.get("api_key") else "") or settings.llm_api_key
        # timeout: per-call override (seconds); default 30
        try:
            self._timeout: float = float(ov.get("timeout", 30.0))
        except (TypeError, ValueError):
            self._timeout = 30.0
        self._shared: bool = False  # shared clients skip close()
        self.client = AsyncOpenAI(
            api_key=self._api_key,
            base_url=self._base_url,
            max_retries=2,
            timeout=self._timeout,
        )

    async def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: dict[str, str] | None = None,
        temperature: float = 0.3,
    ) -> dict[str, Any]:
        """调用 chat completion

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            response_format: {"type": "json_object"} 强制 JSON 输出
            temperature: 温度参数, 默认 0.3

        Returns:
            {"content": str, "model": str, "usage": dict}

        Raises:
            LLMError: 调用失败
        """
        try:
            kwargs: dict[str, Any] = {
                "model": self._model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": temperature,
                "max_tokens": int(rt_get("llm_max_output_tokens", self._max_output_tokens)),
            }
            if response_format is not None:
                kwargs["response_format"] = response_format

            assert self.client is not None
            response = await self.client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content or ""
            usage = response.usage
            return {
                "content": content,
                "model": response.model,
                "usage": {
                    "prompt_tokens": usage.prompt_tokens if usage else 0,
                    "completion_tokens": usage.completion_tokens if usage else 0,
                    "total_tokens": usage.total_tokens if usage else 0,
                },
            }
        except Exception as e:
            raise LLMError(f"LLM 调用失败: {e}") from e

    async def chat_with_images(
        self,
        system_prompt: str,
        user_prompt: str,
        image_data_urls: list[str],
        temperature: float = 0.3,
        response_format: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """多模态 chat: 同时发送文本 + 多张图片 (OpenAI image_url 格式)

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            image_data_urls: 图片 data URL 列表, 如 ["data:image/jpeg;base64,..."]
            temperature: 温度参数

        Returns:
            {"content": str, "model": str, "usage": dict}
        """
        try:
            content_parts: list[dict[str, Any]] = [
                {"type": "text", "text": user_prompt},
            ]
            for url in image_data_urls:
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": url},
                })
            response = await self.client.chat.completions.create(  # type: ignore[union-attr]
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": content_parts},
                ],
                temperature=temperature,
                max_tokens=int(rt_get("llm_max_output_tokens", self._max_output_tokens)),
                **({"response_format": response_format} if response_format is not None else {}),  # type: ignore[arg-type]
            )
            content = response.choices[0].message.content or ""
            usage = response.usage
            return {
                "content": content,
                "model": response.model,
                "usage": {
                    "prompt_tokens": usage.prompt_tokens if usage else 0,
                    "completion_tokens": usage.completion_tokens if usage else 0,
                    "total_tokens": usage.total_tokens if usage else 0,
                },
            }
        except Exception as e:
            raise LLMError(f"LLM 多模态调用失败: {e}") from e

    async def close(self) -> None:
        if self._shared:
            return  # shared clients are managed by the cache; do not close
        if self.client is not None:
            await self.client.close()


# ---- shared (cached) LLM clients for connection-pool reuse ----
_CLIENT_CACHE: dict[str, LLMClient] = {}
_CLIENT_CACHE_MAX = 32


def _client_cache_key(settings: Settings, overrides: dict[str, Any] | None) -> str:
    import hashlib
    ov = overrides or {}
    base_url = (str(ov.get("base_url")).strip() if ov.get("base_url") else "") or settings.llm_base_url
    model = (str(ov.get("model")).strip() if ov.get("model") else "") or settings.llm_model
    api_key = (str(ov.get("api_key")).strip() if ov.get("api_key") else "") or settings.llm_api_key
    try:
        timeout = float(ov.get("timeout", 30.0))
    except (TypeError, ValueError):
        timeout = 30.0
    try:
        mo = int(ov.get("max_output_tokens", settings.llm_max_output_tokens))
    except (TypeError, ValueError):
        mo = settings.llm_max_output_tokens
    try:
        mi = int(ov.get("max_input_tokens", settings.llm_max_input_tokens) or settings.llm_max_input_tokens)
    except (TypeError, ValueError):
        mi = settings.llm_max_input_tokens
    raw = f"{base_url}|{model}|{hashlib.sha256(api_key.encode()).hexdigest()[:16]}|{mo}|{mi}|{timeout}"
    return hashlib.sha1(raw.encode()).hexdigest()


def get_shared_llm_client(settings: Settings, overrides: dict[str, Any] | None = None) -> LLMClient:
    """Return a process-wide cached LLMClient for the given config.

    Reuses the underlying AsyncOpenAI/httpx connection pool across tasks and
    engine calls instead of creating a new one each time. Callers must NOT
    close() the returned client.
    """
    key = _client_cache_key(settings, overrides)
    c = _CLIENT_CACHE.get(key)
    if c is None:
        c = LLMClient(settings, overrides=overrides)
        c._shared = True
        if len(_CLIENT_CACHE) >= _CLIENT_CACHE_MAX:
            _CLIENT_CACHE.pop(next(iter(_CLIENT_CACHE)))
        _CLIENT_CACHE[key] = c
    return c


def invalidate_llm_client_cache() -> None:
    """Drop all cached LLM clients (e.g. when algorithm configs change)."""
    _CLIENT_CACHE.clear()
