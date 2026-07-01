"""LLM 客户端 - OpenAI 兼容 chat API

通过 openai 库的 base_url 配置, 适配任何 OpenAI 兼容 API
(DashScope / Ollama / LM Studio / vLLM / 自建网关 等)
"""
import time
from typing import Any

from openai import AsyncOpenAI

from app.config import Settings
from app.utils.exceptions import LLMError


# 演示模式下的固定响应
MOCK_RESPONSES = [
    {
        "summary": "检测到 1 处中等程度绝缘子伞裙破损, 位于线路中段。需在 7 天内安排现场检查并考虑补强。",
        "recommendations": [
            "立即派员现场复检, 使用高清摄像头或无人机近距离拍摄确认破损程度",
            "在 7 个工作日内安排带电修补作业 (如带电作业条件不具备则申请转检修)",
            "将该资产列入重点跟踪名单, 在后续 3 个月内每月巡检一次",
            "检查同线路相邻杆塔的绝缘子状况, 评估是否存在批次性缺陷",
        ],
    },
    {
        "summary": "识别到 1 处低风险表面污秽, 未见明显破损。整体状况尚可, 建议纳入定期维护计划。",
        "recommendations": [
            "安排在例行停电检修时进行表面清洁 (可考虑带电水冲洗)",
            "检测该区段线路的盐密与灰密, 评估是否需要调整清扫周期",
            "3 个月后复检确认污秽是否加重",
        ],
    },
    {
        "summary": "检测到 2 处缺陷, 其中 1 处高严重度 (闪络痕迹), 另 1 处为低风险破损。建议优先处理高严重度项。",
        "recommendations": [
            "高严重度闪络项: 48 小时内现场复检, 评估是否需紧急更换",
            "在抢修完成后对线路进行绝缘电阻测试, 确认整体绝缘性能",
            "中低风险项: 纳入下个月度检修计划统一处理",
        ],
    },
]


class LLMClient:
    """OpenAI 兼容 LLM 客户端

    支持:
    - 流式 + 非流式
    - 自动重试 (由 openai 库内置)
    - 超时控制
    - 演示模式 (LLM_MOCK_MODE=True): 返回预设响应, 不调真实 API
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._mock_call_count = 0
        if not settings.llm_mock_mode:
            self.client = AsyncOpenAI(
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
                max_retries=2,
                timeout=30.0,
            )
        else:
            self.client = None

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
        if self.settings.llm_mock_mode:
            return self._mock_chat(system_prompt, user_prompt)

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

    def _mock_chat(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        """演示模式: 返回预设响应 (循环使用)"""
        import json as _json

        response_data = MOCK_RESPONSES[self._mock_call_count % len(MOCK_RESPONSES)]
        self._mock_call_count += 1
        # 模拟一点延迟
        time.sleep(0.05)
        return {
            "content": _json.dumps(response_data, ensure_ascii=False),
            "model": f"mock-{self.settings.llm_model}",
            "usage": {
                "prompt_tokens": 200,
                "completion_tokens": 150,
                "total_tokens": 350,
            },
        }

    async def close(self) -> None:
        if self.client is not None:
            await self.client.close()
