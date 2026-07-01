"""LLM 客户端 - OpenAI 兼容 chat API

通过 openai 库的 base_url 配置, 适配任何 OpenAI 兼容 API
(DashScope / Ollama / LM Studio / vLLM / 自建网关 等)
"""
from typing import Any

from openai import AsyncOpenAI

from app.config import Settings
from app.utils.exceptions import LLMError


class LLMClient:
    """OpenAI 兼容 LLM 客户端

    支持:
    - 流式 + 非流式
    - 自动重试 (由 openai 库内置)
    - 超时控制
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = AsyncOpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            max_retries=2,
            timeout=30.0,
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
                "model": self.settings.llm_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": temperature,
                "max_tokens": self.settings.llm_max_output_tokens,
            }
            if response_format is not None:
                kwargs["response_format"] = response_format

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

    async def close(self) -> None:
        await self.client.close()
