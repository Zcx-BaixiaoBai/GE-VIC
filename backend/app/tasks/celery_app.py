"""Celery 应用实例 - M0 阶段

- 3 队列: inspect_queue, stats_queue, cleanup_queue
- 无 result_backend (V1.0 简化, 状态从 DB 查)
"""
import os

from celery import Celery

# V1.0: 默认 broker (测试与本地开发时使用), 生产由环境变量覆盖
DEFAULT_BROKER = "redis://localhost:6379/0"

celery_app = Celery(
    "gevic",
    broker=os.environ.get("CELERY_BROKER_URL", DEFAULT_BROKER),
    include=[
        "app.tasks.inspection",
    ],
)

celery_app.conf.update(
    task_default_queue="inspect_queue",
    task_routes={
        "app.tasks.inspection.run_inspection": {"queue": "inspect_queue"},
        "app.tasks.inspection.enrich_inspection": {"queue": "stats_queue"},
    },
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=200,
    task_acks_late=True,
    timezone="Asia/Shanghai",
    enable_utc=True,
)
