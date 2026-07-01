"""LLM 客户端测试 - mock openai API"""
from unittest.mock import AsyncMock, MagicMock

import pytest
from openai import OpenAIError

from app.config import Settings
from app.services.llm_client import LLMClient
from app.utils.exceptions import LLMError


def _make_settings() -> Settings:
    return Settings(
        database_url="postgresql+asyncpg://u:p@localhost:5432/db",
        llm_base_url="https://example.com/v1",
        llm_api_key="test",
        llm_model="gpt-4o-mini",
        llm_max_input_tokens=4000,
        llm_max_output_tokens=1000,
    )


def _fake_response(content: str = "hello", model: str = "gpt-4o-mini") -> MagicMock:
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = content
    resp.model = model
    resp.usage = MagicMock()
    resp.usage.prompt_tokens = 5
    resp.usage.completion_tokens = 3
    resp.usage.total_tokens = 8
    return resp


@pytest.mark.asyncio
async def test_chat_success() -> None:
    """成功调用"""
    settings = _make_settings()
    client = LLMClient(settings)
    mock_response = _fake_response()
    client.client = MagicMock()
    client.client.chat.completions.create = AsyncMock(return_value=mock_response)
    client.client.close = AsyncMock()

    result = await client.chat(system_prompt="sys", user_prompt="hi")
    assert result["content"] == "hello"
    assert result["model"] == "gpt-4o-mini"
    assert result["usage"]["total_tokens"] == 8
    await client.close()


@pytest.mark.asyncio
async def test_chat_raises_llm_error_on_failure() -> None:
    """调用失败抛 LLMError"""
    settings = _make_settings()
    client = LLMClient(settings)
    client.client = MagicMock()
    client.client.chat.completions.create = AsyncMock(side_effect=OpenAIError("api error"))
    client.client.close = AsyncMock()

    with pytest.raises(LLMError):
        await client.chat(system_prompt="sys", user_prompt="hi")
    await client.close()
