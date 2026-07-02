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


# 演示模式下的多模态响应（图片 / 视频分析）
MOCK_RESPONSES_MULTIMODAL = [
    {
        "media_type": "image",
        "description": "一张输电线路绝缘子串的特写照片。绝缘子由多个盘形瓷质单元串联组成, 安装在金属杆塔的横担上。整体表面较为洁净, 未见明显破损或闪络痕迹。背景为阴天, 远处可见同塔并架的其他线路。",
        "observations": [
            {"type": "设备识别", "label": "盘形悬式绝缘子", "confidence": 0.92, "note": "外观完好, 颜色正常"},
            {"type": "状态评估", "label": "运行正常", "confidence": 0.88, "note": "未发现破损/污秽/闪络"},
            {"type": "维护建议", "label": "常规巡检", "confidence": 0.85, "note": "按周期巡检即可, 无需特殊处理"},
        ],
        "summary": "识别为输电线路绝缘子, 运行状态良好, 无明显缺陷。",
    },
    {
        "media_type": "video",
        "description": "无人机巡检视频, 时长约 12 秒。摄像机沿输电线路缓慢飞行, 期间拍摄了 3 基杆塔。塔上绝缘子、导线和金具均清晰可见。第 2 基塔的中相绝缘子串末端有一处疑似锈蚀 (约 0:08 出现), 其余设备外观正常。",
        "observations": [
            {"type": "设备识别", "label": "杆塔 3 基, 绝缘子 9 串", "confidence": 0.94},
            {"type": "异常发现", "label": "第 2 基塔中相绝缘子串末端疑似锈蚀", "confidence": 0.76, "note": "建议现场复核"},
            {"type": "建议", "label": "对该基塔列入 7 日内复检计划", "confidence": 0.82},
        ],
        "summary": "无人机巡检 3 基杆塔, 1 处疑似锈蚀需现场复核, 其余设备正常。",
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

    async def chat_with_images(
        self,
        system_prompt: str,
        user_prompt: str,
        image_data_urls: list[str],
        temperature: float = 0.3,
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
        if self.settings.llm_mock_mode:
            # mock 模式: 从预设中根据图片数量选一个 (0 张 -> 文本响应, 1+ 张 -> 多模态响应)
            return self._mock_multimodal_chat(system_prompt, user_prompt, image_data_urls)

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
                model=self.settings.llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": content_parts},
                ],
                temperature=temperature,
                max_tokens=self.settings.llm_max_output_tokens,
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


    def _mock_multimodal_chat(
        self,
        system_prompt: str,
        user_prompt: str,
        image_data_urls: list[str],
    ) -> dict[str, Any]:
        """演示模式: 根据图片数量返回预设的多模态响应."""
        import json as _json
        # 选择响应的逻辑: 多张图(视频抽帧) -> 视频分析, 单张图 -> 图片分析
        if not image_data_urls or len(image_data_urls) == 0:
            response_data = MOCK_RESPONSES[self._mock_call_count % len(MOCK_RESPONSES)]
        elif len(image_data_urls) == 1:
            response_data = MOCK_RESPONSES_MULTIMODAL[0]
        else:
            response_data = MOCK_RESPONSES_MULTIMODAL[1]
        self._mock_call_count += 1
        time.sleep(0.08)
        return {
            "content": _json.dumps(response_data, ensure_ascii=False),
            "model": f"mock-multimodal-{self.settings.llm_model}",
            "usage": {
                "prompt_tokens": 250 + 80 * len(image_data_urls),
                "completion_tokens": 180,
                "total_tokens": 430 + 80 * len(image_data_urls),
            },
        }

    async def close(self) -> None:
        if self.client is not None:
            await self.client.close()
