"""X-Inspector-Id 校验测试"""
import pytest

from app.utils.exceptions import InvalidInspectorIdError
from app.utils.inspector_id import INSPECTOR_ID_PATTERN, validate_inspector_id


def test_pattern_compiles() -> None:
    """正则能编译"""
    assert INSPECTOR_ID_PATTERN.pattern == r"^[A-Za-z0-9_-]{3,32}$"


def test_valid_inspector_ids() -> None:
    """合法 ID 通过"""
    for valid in ["INSP-001", "abc", "user_name", "A1B2C3", "x" * 32, "abc-123_xyz"]:
        assert validate_inspector_id(valid) == valid


def test_invalid_too_short() -> None:
    """过短抛错"""
    with pytest.raises(InvalidInspectorIdError):
        validate_inspector_id("ab")


def test_invalid_too_long() -> None:
    """过长抛错"""
    with pytest.raises(InvalidInspectorIdError):
        validate_inspector_id("x" * 33)


def test_invalid_chars() -> None:
    """非法字符抛错"""
    for invalid in ["abc!", "abc def", "abc@def", "abc/def", "<script>"]:
        with pytest.raises(InvalidInspectorIdError):
            validate_inspector_id(invalid)


def test_none_or_empty() -> None:
    """None/空字符串抛错"""
    for invalid in [None, ""]:
        with pytest.raises(InvalidInspectorIdError):
            validate_inspector_id(invalid)  # type: ignore[arg-type]
