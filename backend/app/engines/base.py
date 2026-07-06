"""引擎抽象基类"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from typing import TypedDict


class BatchFileItem(TypedDict, total=False):
    """一个批量文件项"""
    bytes: bytes
    filename: str
    mime: str | None
    meta: dict[str, Any]



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

    async def recognize_batch(
        self,
        files: list[BatchFileItem],
        meta: dict[str, Any],
        config: dict[str, Any],
    ) -> "RecognitionResult":
        """联合识别 (多文件一起看).

        默认实现: 仅处理第一个文件（向下兼容）。
        多模态 LLM 引擎需要覆写此方法以同时看到多张图。
        """
        if not files:
            return RecognitionResult(
                success=False,
                data=None,
                summary=None,
                error_code="NO_FILES",
                error_message="Batch recognition requires at least one file",
                raw_response=None,
                cost_estimate=0.0,
                duration_ms=0,
            )
        first = files[0]
        return await self.recognize(
            file_bytes=first["bytes"],
            filename=first["filename"],
            meta={**(first.get("meta") or {}), **meta, "_batch_size": len(files)},
            config=config,
        )

    @abstractmethod
    async def health_check(self, config: dict[str, Any]) -> dict[str, Any]:
        """健康检查 - 验证引擎可达"""
        raise NotImplementedError
