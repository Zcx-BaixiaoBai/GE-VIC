"""GET /api/v1/settings/llm - LLM 配置与连接测试"""
import logging
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings
from app.services.llm_client import LLMClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])


class LLMConfigOut(BaseModel):
    """LLM 配置 (脱敏)"""
    base_url: str
    model: str
    max_input_tokens: int
    max_output_tokens: int
    mock_mode: bool


class LLMTestResult(BaseModel):
    """LLM 连接测试结果"""
    success: bool
    message: str
    model: str | None = None
    content_preview: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    duration_ms: int | None = None


@router.get("/llm", response_model=LLMConfigOut)
async def get_llm_config() -> LLMConfigOut:
    """获取当前 LLM 配置 (脱敏)"""
    settings = get_settings()
    return LLMConfigOut(
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        max_input_tokens=settings.llm_max_input_tokens,
        max_output_tokens=settings.llm_max_output_tokens,
        mock_mode=settings.llm_mock_mode,
    )


@router.post("/llm/test", response_model=LLMTestResult)
async def test_llm_connection() -> LLMTestResult:
    """测试 LLM 连接 (发一个最小 prompt)"""
    import time
    settings = get_settings()
    client = LLMClient(settings)
    start = time.monotonic()
    try:
        result = await client.chat(
            system_prompt="You are a test assistant.",
            user_prompt="Reply with the single word: OK",
            temperature=0.0,
        )
        duration = int((time.monotonic() - start) * 1000)
        return LLMTestResult(
            success=True,
            message="LLM connection successful",
            model=result.get("model"),
            content_preview=(result.get("content") or "")[:200],
            prompt_tokens=result.get("usage", {}).get("prompt_tokens"),
            completion_tokens=result.get("usage", {}).get("completion_tokens"),
            total_tokens=result.get("usage", {}).get("total_tokens"),
            duration_ms=duration,
        )
    except Exception as e:
        return LLMTestResult(
            success=False,
            message=f"LLM call failed: {e}",
        )
    finally:
        await client.close()
