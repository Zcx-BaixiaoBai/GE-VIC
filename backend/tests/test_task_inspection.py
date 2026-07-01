"""Celery 任务测试 - 验证任务可被导入和注册

M0: 任务逻辑测试在 E2E 中覆盖, 单元测试只验证模块加载与路由。
"""
import pytest

from app.tasks.celery_app import celery_app
from app.tasks.inspection import enrich_inspection, run_inspection


def test_celery_app_registered() -> None:
    """Celery 应用实例可访问"""
    assert celery_app.main == "gevic"


def test_tasks_registered() -> None:
    """任务已注册到 Celery"""
    tasks = list(celery_app.tasks.keys())
    assert "app.tasks.inspection.run_inspection" in tasks
    # enrich_inspection 可能在 inspection 模块或 enrichment 模块中, 都接受
    assert any("enrich_inspection" in t for t in tasks)


def test_task_max_retries_config() -> None:
    """run_inspection 配置了重试"""
    assert run_inspection.max_retries == 3
    assert enrich_inspection.max_retries == 2


def test_routes_config() -> None:
    """任务路由到正确的队列"""
    routes = celery_app.conf.task_routes
    assert routes["app.tasks.inspection.run_inspection"]["queue"] == "inspect_queue"
    # 找到 enrich 任务的路由
    enrich_route = next(v for k, v in routes.items() if "enrich" in k)
    assert enrich_route["queue"] == "stats_queue"
