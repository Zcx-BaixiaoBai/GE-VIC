# GE-VIC 告警规则 (主规范 §14.4)

> V1.2 简化为 2 项告警, 由 Prometheus Alertmanager 触发。
> 本文档描述 PromQL 规则, 部署到 Alertmanager 时粘贴使用。

## 1. 依赖不可达 (PG / Redis / MinIO)

**触发条件**: 任一依赖健康检查连续 2 分钟失败。

```yaml
groups:
  - name: gevic.dependencies
    rules:
      - alert: GevicDependencyDown
        expr: |
          (
            up{job="gevic-backend"} == 0
          )
          or
          (
            gevic_dependency_up{component="postgres"} == 0
            or gevic_dependency_up{component="redis"} == 0
            or gevic_dependency_up{component="minio"} == 0
          )
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "GE-VIC 依赖不可达 ({{ $labels.component }})"
          description: "{{ $labels.component }} 健康检查连续 2 分钟失败, 立即人工介入。"
```

**当前实现**: `GET /health/ready` 检查 DB + MinIO, 暴露在 `gevic_dependency_up{component="..."}` gauge (M1 后置增强, M3 引入)。

---

## 2. Celery Worker Down

**触发条件**: 5 分钟内没有任务完成事件。

```yaml
  - name: gevic.worker
    rules:
      - alert: GevicWorkerDown
        expr: |
          (rate(gevic_inspections_total[5m]) > 0)
          and
          (rate(gevic_inspections_total{status="SUCCESS"}[5m]) == 0)
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "GE-VIC Worker 可能 down"
          description: "5 分钟内有任务但无 SUCCESS, worker 进程可能消失或卡死。"
```

**当前实现**: V1.0 用 sync 模式 (TASK_SYNC_MODE=true), 此告警主要针对 M2 切换到 async worker 后使用。

---

## 3. SLO 监控查询 (无告警, 用于看板上)

主规范 §1.7 V1.0 SLO 验收标准, 落地到 PromQL:

| 指标 | 目标 | PromQL |
|---|---|---|
| 单图识别 P95 延迟 | < 30s | `histogram_quantile(0.95, sum(rate(gevic_inspection_duration_seconds_bucket[5m])) by (le, algorithm))` |
| 上传接口 P95 延迟 | < 500ms | `histogram_quantile(0.95, sum(rate(gevic_upload_duration_seconds_bucket[5m])) by (le, algorithm))` |
| 端到端成功率 | > 99.5% | `1 - (sum(rate(gevic_inspections_total{status=~"FAILED|DEAD"}[5m])) / sum(rate(gevic_inspections_total[5m])))` |
| LLM 富化失败不影响主任务 | 100% | `sum(rate(gevic_inspections_total{status="SUCCESS", algorithm=~".*"}[5m])) >= sum(rate(gevic_enrichment_total{status=~".*"}[5m]))` |

**V1.0 不做**: P99 / 99.9% / 多区域容灾 / 7×24 监控。

---

## 4. 部署 (M3+ 评估)

1. V1.0 本地: 不部署 Alertmanager, SLO 通过手动查询验证。
2. V2.0 (云部署): 启用 Prometheus + Alertmanager, 钉钉告警通道由大系统统一提供。
3. M3+ (规模化): 评估 Grafana 看板 (主规范 ADR-007)。

## 5. 已知限制

- 当前 `gevic_dependency_up` gauge 尚未实现 (M1 范围外, M3 评估)
- `gevic_engine_call_errors_total` 已实现, 但 SLO 告警中未启用 (M1 简化)
- 富化失败率、队列堆积、引擎错误率告警均不做 (主规范 §14.4 明确)

## 6. 相关文件

- `backend/app/services/metrics.py` — 指标定义
- `backend/app/main.py` — `/health/live`, `/health/ready`, `/metrics` 端点
- `docs/superpowers/state-machine.md` — 状态流转定义
