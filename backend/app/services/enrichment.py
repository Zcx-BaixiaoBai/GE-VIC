"""LLM 富化服务 - 单条记录的结构化总结与建议

输入: 识别结果 JSON
输出: {summary, recommendations, raw, model, token_used, generated_at}
"""
import json
from datetime import datetime, timezone
from typing import Any

from app.services.llm_client import LLMClient, make_strict_json_prompt, parse_json_response
from app.utils.exceptions import LLMError

SYSTEM_PROMPT = """你是基础设施巡检领域的专家助手。
基于识别引擎返回的结构化结果, 用简洁准确的中文生成:
1. 一段不超过 80 字的总结
2. 2-4 条运维建议 (按优先级排序)

输出 JSON:
{
  "summary": "...",
  "recommendations": ["建议1", "建议2", "建议3"]
}
"""


def _build_user_prompt(
    algorithm_name: str,
    recognition: dict[str, Any],
    system_prompt: str | None = None,
) -> str:
    # 去掉 LLM 内部字段, 只传业务字段, 避免 token 浪费
    slim = {k: v for k, v in (recognition or {}).items()
            if k not in ("_raw_llm_content", "_model", "_usage", "_input", "files")}
    # observations 为空就丢掉
    if isinstance(slim.get("observations"), list) and not slim["observations"]:
        slim.pop("observations", None)
    base = f"""算法: {algorithm_name}
识别结果:
{json.dumps(slim, ensure_ascii=False, indent=2)}

请基于以上识别结果,生成简短总结与可执行建议。"""
    # 把 system 提示也透传给 LLM, 让它知道用谁的视角回答
    if system_prompt:
        base += "\n\n[系统角色]\n" + (system_prompt[:500] + ("..." if len(system_prompt) > 500 else ""))
    base += "\n\n请按系统角色的语气与格式输出, JSON 或 markdown 均可"
    return base


class EnrichmentService:
    """LLM 富化服务 - 失败不影响主任务"""

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    async def enrich(
        self,
        algorithm_name: str,
        recognition: dict[str, Any],
        engine_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """对单条记录做 LLM 富化 (会尊重算法的 enrichment_prompt 自定义系统提示)

        算法配置里可指定 enrichment_prompt 字段覆盖默认的"基础设施巡检"风格.
        """
        """对单条记录做 LLM 富化

        Returns:
            富化结果 dict, 含 summary / recommendations / model / token_used

        Raises:
            LLMError: 调用失败
        """
        engine_config = engine_config or {}
        # 算法可指定 enrichment_prompt 覆盖默认 SYSTEM_PROMPT
        custom = engine_config.get("enrichment_prompt")
        use_custom = bool(custom and str(custom).strip())
        system_prompt = str(custom).strip() if use_custom else SYSTEM_PROMPT
        user_prompt = _build_user_prompt(algorithm_name, recognition, system_prompt)
        # 如果算法配置里指定了 LLM 覆盖项, 用 per-call client
        from app.engines.multimodal_llm import _build_llm_overrides
        overrides = _build_llm_overrides(engine_config)
        client = self.llm
        if overrides:
            from app.config import get_settings as _gs
            client = LLMClient(_gs(), overrides=overrides)
        # 自定义 prompt 时不强求 JSON (允许 markdown 输出); 默认才走 json_object
        result = await client.chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_format=None if use_custom else {"type": "json_object"},
            temperature=0.3,
        )

        parsed = parse_json_response(result.get("content", ""))
        if "summary" not in parsed or not str(parsed.get("summary", "")).strip():
            # 解析失败或空: 取原文首行作为 summary, 不再返回 JSON 字符串
            raw_text = parsed.get("_raw_text", "") or result.get("content", "")
            first_line = raw_text.split("\n")[0].strip() if raw_text else "(空响应)"
            # 去掉 markdown 标题前缀
            import re
            first_line = re.sub(r"^#+\s*", "", first_line)
            parsed["summary"] = first_line[:200] if first_line else "(空响应)"
        if "recommendations" not in parsed or not isinstance(parsed.get("recommendations"), list):
            parsed["recommendations"] = []

        return {
            "summary": parsed.get("summary", ""),
            "recommendations": parsed.get("recommendations", []),
            "model": result.get("model", ""),
            "token_used": result.get("usage", {}).get("total_tokens", 0),
            "prompt_tokens": result.get("usage", {}).get("prompt_tokens", 0),
            "completion_tokens": result.get("usage", {}).get("completion_tokens", 0),
            "raw_content": result.get("content", ""),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
