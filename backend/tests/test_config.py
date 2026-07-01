"""配置测试"""
import pytest
from pydantic import ValidationError

from app.config import Settings


def test_settings_load_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """从环境变量加载所有必填配置"""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/db")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.com/v1")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("LLM_MAX_INPUT_TOKENS", "4000")
    monkeypatch.setenv("LLM_MAX_OUTPUT_TOKENS", "1000")

    settings = Settings()

    assert settings.database_url == "postgresql+asyncpg://u:p@localhost:5432/db"
    assert settings.llm_base_url == "https://example.com/v1"
    assert settings.llm_api_key == "test-key"
    assert settings.llm_model == "gpt-4o-mini"
    assert settings.llm_max_input_tokens == 4000
    assert settings.llm_max_output_tokens == 1000


def test_settings_missing_required(monkeypatch: pytest.MonkeyPatch) -> None:
    """缺必填项应抛 ValidationError"""
    # 清空所有相关环境变量
    for k in [
        "DATABASE_URL",
        "LLM_BASE_URL",
        "LLM_API_KEY",
        "LLM_MODEL",
        "LLM_MAX_INPUT_TOKENS",
        "LLM_MAX_OUTPUT_TOKENS",
    ]:
        monkeypatch.delenv(k, raising=False)
    # 禁用 .env 读取
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_get_settings_singleton() -> None:
    """get_settings 返回单例 (lru_cache)"""
    from app.config import get_settings
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
