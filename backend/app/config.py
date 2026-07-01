"""应用配置 - pydantic-settings 从环境变量加载"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 数据库
    database_url: str

    # LLM
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    llm_max_input_tokens: int = 4000
    llm_max_output_tokens: int = 1000
    # 演示模式: True 时 LLM 返回预设响应, 不调真实 API
    llm_mock_mode: bool = False

    # 对象存储
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "gevic_admin"
    minio_secret_key: str = "gevic_dev_password"
    minio_bucket: str = "gevic"
    minio_secure: bool = False

    # Celery
    celery_broker_url: str = "redis://redis:6379/0"

    # 应用
    app_env: str = "development"
    log_level: str = "INFO"

    # 文件上传限制
    max_image_size: int = 20 * 1024 * 1024  # 20MB
    max_video_size: int = 500 * 1024 * 1024  # 500MB

    # 任务同步模式: True 时 API 端点同步执行任务 (不依赖 Celery worker, 本地 dev 友好)
    task_sync_mode: bool = False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """获取单例设置 (缓存避免重复解析)"""
    return Settings()  # type: ignore[call-arg]