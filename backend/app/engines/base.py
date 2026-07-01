"""引擎抽象基类"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class RecognitionResult:
    """识别结果 - 所有引擎统一返回"""
    success: bool
    data: dict[str, Any] | None
    summary: str | None
    error_code: str | None
    error_message: str | None
    raw_response: Any
    cost_estimate: float | None
    duration_ms: int | None


class EngineError(Exception):
    """引擎调用错误"""
    pass


class BaseEngine(ABC):
    """所有识别引擎的抽象基类

    识别引擎可以是云 API、海康超脑、或自建模型
    """

    engine_type: str = "base"

    @abstractmethod
    async def recognize(
        self,
        file_bytes: bytes,
        filename: str,
        meta: dict[str, Any],
        config: dict[str, Any],
    ) -> RecognitionResult:
        """对单张图/视频执行识别

        Args:
            file_bytes: 文件二进制内容
            filename: 文件名(用于推断类型)
            meta: 上传请求的元数据(asset_id, location 等)
            config: 算法注册表中的 engine_config

        Returns:
            RecognitionResult, success=True 表示识别成功
        """
        raise NotImplementedError

    @abstractmethod
    async def health_check(self, config: dict[str, Any]) -> bool:
        """健康检查 - 验证引擎可达"""
        raise NotImplementedError
