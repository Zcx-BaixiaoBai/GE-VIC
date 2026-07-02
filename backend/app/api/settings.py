"""GET /api/v1/settings/llm - LLM 配置与连接测试"""
import logging
from typing import Any
from pydantic import Field

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings
from app.services.llm_client import LLMClient
from app.services.runtime_config import get_all as rc_get_all, update as rc_update

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])


class LLMConfigOut(BaseModel):
    """LLM 配置 (脱敏)"""
    base_url: str
    model: str
    max_input_tokens: int
    max_output_tokens: int
    mock_mode: bool
    runtime_max_output_tokens: int | None = None
    runtime_max_input_tokens: int | None = None
    runtime_overrides: dict[str, bool] = Field(default_factory=dict, description="哪些值当前被 runtime 覆盖了")


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
    """获取当前 LLM 配置 (脱敏). runtime_* 显示被运行时配置覆盖的值."""
    settings = get_settings()
    rc = rc_get_all()
    rt_out = rc.get("llm_max_output_tokens")
    rt_in = rc.get("llm_max_input_tokens")
    return LLMConfigOut(
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        max_input_tokens=rt_in if isinstance(rt_in, int) else settings.llm_max_input_tokens,
        max_output_tokens=rt_out if isinstance(rt_out, int) else settings.llm_max_output_tokens,
        mock_mode=settings.llm_mock_mode,
        runtime_max_output_tokens=rt_out if isinstance(rt_out, int) else None,
        runtime_max_input_tokens=rt_in if isinstance(rt_in, int) else None,
        runtime_overrides={
            "max_output_tokens": isinstance(rt_out, int),
            "max_input_tokens": isinstance(rt_in, int),
        },
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


class LLMConfigUpdateIn(BaseModel):
    """LLM 运行时配置更新 (仅 max tokens 可热更新)"""
    max_input_tokens: int | None = Field(None, ge=128, le=128000)
    max_output_tokens: int | None = Field(None, ge=16, le=32000)


@router.patch("/llm", response_model=LLMConfigOut)
async def update_llm_config(body: LLMConfigUpdateIn) -> LLMConfigOut:
    """更新运行时 LLM 配置 (立即生效, 持久化到 .runtime-config.json).

    注意: 只能改 max tokens. base_url/model/mock_mode 来自环境变量, 改需重启.
    """
    updates: dict[str, int] = {}
    if body.max_input_tokens is not None:
        updates["llm_max_input_tokens"] = body.max_input_tokens
    if body.max_output_tokens is not None:
        updates["llm_max_output_tokens"] = body.max_output_tokens
    if updates:
        rc_update(updates)
    return await get_llm_config()
