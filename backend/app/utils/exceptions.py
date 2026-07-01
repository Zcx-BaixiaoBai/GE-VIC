"""自定义异常"""


class GevicError(Exception):
    """基础异常"""
    pass


class InvalidInspectorIdError(GevicError):
    """X-Inspector-Id 格式不合法"""
    pass


class AlgorithmNotFoundError(GevicError):
    """算法 code 不存在或未启用"""
    pass


class FileTooLargeError(GevicError):
    """文件超过大小限制"""
    pass


class EngineError(GevicError):
    """识别引擎调用失败"""
    pass


class LLMError(GevicError):
    """LLM 调用失败"""
    pass


class NotFoundError(GevicError):
    """资源未找到"""
    pass
