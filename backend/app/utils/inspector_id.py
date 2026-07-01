"""X-Inspector-Id 校验

V1.0 极简护栏: 只做格式校验,不做身份认证
"""
import re

from app.utils.exceptions import InvalidInspectorIdError

# 允许字母、数字、下划线、连字符, 长度 3-32
INSPECTOR_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{3,32}$")


def validate_inspector_id(inspector_id: str | None) -> str:
    """校验并返回 inspector_id, 失败抛 InvalidInspectorIdError"""
    if inspector_id is None or inspector_id == "":
        raise InvalidInspectorIdError("X-Inspector-Id is required")
    if not isinstance(inspector_id, str):
        raise InvalidInspectorIdError("X-Inspector-Id must be a string")
    if not INSPECTOR_ID_PATTERN.match(inspector_id):
        raise InvalidInspectorIdError(
            f"X-Inspector-Id format invalid: must match {INSPECTOR_ID_PATTERN.pattern}"
        )
    return inspector_id
