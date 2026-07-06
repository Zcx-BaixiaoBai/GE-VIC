"""Prometheus 指标定义与注册.

主规范 §14.3 3 个核心指标:
- gevic_inspections_total{algorithm, status}: 计数器
- gevic_inspection_duration_seconds{algorithm, engine}: 直方图
- gevic_engine_call_errors_total{engine, error_code}: 计数器

辅助指标:
- gevic_enrichment_total{status}: 富化结果
- gevic_llm_tokens_total{model, direction}: LLM token 用量
- gevic_algorithms_count: 活跃算法数
- gevic_upload_duration_seconds: 上传接口 P95 延迟 (§1.7 SLO)
- gevic_http_requests_total: HTTP 请求计数 (用于可用性统计)

V1.0 边界外 (M3+): Grafana 看板 / 告警通道
"""
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from app.middleware.metrics_middleware import UPLOAD_DURATION, HTTP_REQUESTS_TOTAL


# === §14.3 3 个核心指标 (主规范要求) ===

INSPECTIONS_TOTAL = Counter(
    "gevic_inspections_total",
    "识别任务总数 (按最终状态分组)",
    labelnames=("algorithm", "status"),
)

INSPECTION_DURATION = Histogram(
    "gevic_inspection_duration_seconds",
    "单次识别耗时 (秒, 包含 LLM 富化)",
    labelnames=("algorithm", "engine"),
    # 桶覆盖 0.5s ~ 5min, 与 SLO 单图 P95 < 30s 匹配
    buckets=(0.5, 1, 2, 5, 10, 20, 30, 60, 120, 300),
)

ENGINE_CALL_ERRORS_TOTAL = Counter(
    "gevic_engine_call_errors_total",
    "引擎调用错误次数 (按引擎与错误码)",
    labelnames=("engine", "error_code"),
)


# === §1.7 SLO 上传延迟 ===



# === 辅助指标 ===

ENRICHMENT_TOTAL = Counter(
    "gevic_enrichment_total",
    "LLM 富化总数 (按状态分组)",
    labelnames=("status",),  # ENRICHED | ENRICH_FAILED
)

LLM_TOKENS_TOTAL = Counter(
    "gevic_llm_tokens_total",
    "LLM token 用量 (按模型和方向)",
    labelnames=("model", "direction"),
)


ALGORITHMS_COUNT = Gauge(
    "gevic_algorithms_count",
    "当前活跃算法数 (is_active=true)",
)


DEPENDENCY_UP = Gauge(
    "gevic_dependency_up",
    "依赖健康状态 (1=ok, 0=down)",
    labelnames=("component",),  # postgres | redis | minio
)




def render_metrics() -> tuple[bytes, str]:
    """返回 Prometheus 抓取格式的 (body, content_type)"""
    return generate_latest(), CONTENT_TYPE_LATEST
