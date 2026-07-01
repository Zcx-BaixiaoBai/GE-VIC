"""LLM 富化服务 - 单条记录的结构化总结与建议

输入: 识别结果 JSON
输出: {summary, recommendations, raw, model, token_used, generated_at}
"""
import json
from datetime import datetime, timezone
from typing import Any

from app.services.llm_client import LLMClient
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


def _build_user_prompt(algorithm_name: str, recognition: dict[str, Any]) -> str:
    return f"""算法: {algorithm_name}
识别结果:
{json.dumps(recognition, ensure_ascii=False, indent=2)}

请基于以上识别结果, 生成 JSON 格式的总结与建议。"""


class EnrichmentService:
    """LLM 富化服务 - 失败不影响主任务"""

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    async def enrich(
        self, algorithm_name: str, recognition: dict[str, Any]
    ) -> dict[str, Any]:
        """对单条记录做 LLM 富化

        Returns:
            富化结果 dict, 含 summary / recommendations / model / token_used

        Raises:
            LLMError: 调用失败
        """
        user_prompt = _build_user_prompt(algorithm_name, recognition)
        result = await self.llm.chat(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        try:
            parsed = json.loads(result["content"])
        except (json.JSONDecodeError, KeyError) as e:
            raise LLMError(f"LLM 输出非 JSON: {e}") from e

        return {
            "summary": parsed.get("summary", ""),
            "recommendations": parsed.get("recommendations", []),
            "model": result.get("model", ""),
            "token_used": result.get("usage", {}).get("total_tokens", 0),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
