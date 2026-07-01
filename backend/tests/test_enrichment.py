"""LLM 富化服务测试 - mock LLM client"""
from unittest.mock import AsyncMock

import pytest

from app.services.enrichment import EnrichmentService
from app.utils.exceptions import LLMError


@pytest.mark.asyncio
async def test_enrich_success() -> None:
    """成功富化: 解析 JSON 并入库"""
    mock_llm = AsyncMock()
    mock_llm.chat = AsyncMock(
        return_value={
            "content": '{"summary": "检测到 1 处破损", "recommendations": ["建议1", "建议2"]}',
            "model": "qwen-plus",
            "usage": {"total_tokens": 200, "prompt_tokens": 100, "completion_tokens": 100},
        }
    )

    service = EnrichmentService(mock_llm)
    result = await service.enrich(
        algorithm_name="绝缘子破损识别",
        recognition={"defects": [{"type": "破损", "confidence": 0.9}]},
    )

    assert result["summary"] == "检测到 1 处破损"
    assert len(result["recommendations"]) == 2
    assert result["model"] == "qwen-plus"
    assert result["token_used"] == 200
    assert "generated_at" in result


@pytest.mark.asyncio
async def test_enrich_invalid_json_raises() -> None:
    """LLM 返回非 JSON 应抛 LLMError"""
    mock_llm = AsyncMock()
    mock_llm.chat = AsyncMock(
        return_value={"content": "not a json", "model": "x", "usage": {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0}}
    )

    service = EnrichmentService(mock_llm)
    with pytest.raises(LLMError):
        await service.enrich(algorithm_name="x", recognition={})
