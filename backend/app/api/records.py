"""GET /api/v1/records - record query endpoints"""
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.deps import get_inspector_id
from app.models import Inspection
from app.schemas.inspection import (
    AlgorithmUsage,
    EnrichmentBreakdown,
    EnrichOut,
    InspectionListOut,
    InspectionOut,
    RecordStatsOut,
    RetryOut,
    StatusBreakdown,
)
from app.services.audit import AuditAction, AuditResult, AuditService
from app.config import get_settings
from app.tasks.celery_app import celery_app

router = APIRouter(prefix="/records", tags=["records"])


def _to_inspection_out(insp: Inspection, file_url: str | None = None) -> InspectionOut:
    """ORM to Pydantic conversion"""
    file_payload: dict[str, Any] | None = None
    if insp.object_key:
        file_payload = {
            "object_key": insp.object_key,
            "url": file_url or f"/api/v1/records/{insp.id}/file",
            "size": insp.file_size,
            "hash": insp.file_hash,
            "type": insp.file_type,
        }

    error_payload: dict[str, Any] | None = None
    if insp.error_code or insp.error_message:
        error_payload = {"code": insp.error_code, "message": insp.error_message}

    # 批次文件列表: 给每个文件生成可访问 URL
    batch_files_payload: list[dict[str, Any]] | None = None
    if getattr(insp, "is_batch", False) and getattr(insp, "batch_files", None):
        batch_files_payload = []
        for i, bf in enumerate(insp.batch_files or []):
            batch_files_payload.append({
                "index": i,
                "url": f"/api/v1/records/{insp.id}/file/{i}",
                "filename": bf.get("filename"),
                "mime_type": bf.get("mime_type"),
                "file_type": bf.get("file_type"),
                "size": bf.get("file_size"),
                "hash": bf.get("file_hash"),
            })

    return InspectionOut(
        id=insp.id,
        algorithm_code=insp.algorithm_code,
        category=insp.category,
        status=insp.status,
        enrichment_status=insp.enrichment_status,
        created_at=insp.created_at,
        started_at=insp.started_at,
        finished_at=insp.finished_at,
        duration_ms=insp.duration_ms,
        retry_count=insp.retry_count,
        inspector_id=insp.inspector_id,
        asset_id=insp.asset_id,
        request_meta=insp.request_meta,
        location=insp.location,
        file=file_payload,
        recognition=insp.result,
        summary=insp.summary,
        llm_enrichment=insp.llm_enrichment,
        error=error_payload,
        is_batch=bool(getattr(insp, "is_batch", False)),
        batch_size=len(insp.batch_files) if getattr(insp, "is_batch", False) and getattr(insp, "batch_files", None) else 0,
        batch_files=batch_files_payload,
    )


@router.get("", response_model=InspectionListOut)
async def list_records(
    request: Request,
    algorithm: Annotated[str | None, Query(description="Algorithm code filter")] = None,
    status_filter: Annotated[str | None, Query(alias="status", description="Status filter")] = None,
    asset_id: Annotated[str | None, Query()] = None,
    inspector_id_filter: Annotated[str | None, Query(alias="inspector_id", description="Inspector ID filter")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    inspector_id: Annotated[str, Depends(get_inspector_id)] = ...,  # type: ignore[assignment]
    session: AsyncSession = Depends(get_session),
) -> InspectionListOut:
    """List inspection records with multiple filters"""
    stmt = select(Inspection)
    count_stmt = select(func.count(Inspection.id))

    if algorithm:
        stmt = stmt.where(Inspection.algorithm_code == algorithm)
        count_stmt = count_stmt.where(Inspection.algorithm_code == algorithm)
    if status_filter:
        stmt = stmt.where(Inspection.status == status_filter)
        count_stmt = count_stmt.where(Inspection.status == status_filter)
    if asset_id:
        stmt = stmt.where(Inspection.asset_id == asset_id)
        count_stmt = count_stmt.where(Inspection.asset_id == asset_id)
    if inspector_id_filter:
        stmt = stmt.where(Inspection.inspector_id == inspector_id_filter)
        count_stmt = count_stmt.where(Inspection.inspector_id == inspector_id_filter)

    stmt = stmt.order_by(Inspection.created_at.desc()).offset(offset).limit(limit)

    result = await session.execute(stmt)
    items = [_to_inspection_out(r) for r in result.scalars().all()]

    total_result = await session.execute(count_stmt)
    total = total_result.scalar() or 0

    return InspectionListOut(items=items, total=total)


@router.get("/stats", response_model=RecordStatsOut)
async def get_record_stats(
    inspector_id: Annotated[str, Depends(get_inspector_id)],
    session: AsyncSession = Depends(get_session),
) -> RecordStatsOut:
    """Aggregate stats for the dashboard.

    Computes counts by status, by algorithm, average/p95 duration over SUCCESS
    records, today_count, success_rate, and enrichment coverage.
    """
    from datetime import datetime, timedelta, timezone
    from app.models import Algorithm

    # total
    total = (await session.execute(select(func.count(Inspection.id)))).scalar() or 0

    # today boundary
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # by status
    status_rows = (
        await session.execute(
            select(Inspection.status, func.count(Inspection.id)).group_by(Inspection.status)
        )
    ).all()
    by_status = StatusBreakdown()
    for st, cnt in status_rows:
        if st == "PENDING":
            by_status.pending = cnt
        elif st == "RUNNING":
            by_status.running = cnt
        elif st == "SUCCESS":
            by_status.success = cnt
        elif st == "FAILED":
            by_status.failed = cnt
        elif st == "DEAD":
            by_status.dead = cnt

    success_count = by_status.success
    failure_count = by_status.failed + by_status.dead
    success_rate = (success_count / total) if total > 0 else 0.0

    # today count
    today_count = (
        await session.execute(
            select(func.count(Inspection.id)).where(Inspection.created_at >= today_start)
        )
    ).scalar() or 0

    # avg / p95 duration (over SUCCESS records with duration_ms)
    duration_rows = (
        await session.execute(
            select(Inspection.duration_ms)
            .where(Inspection.status == "SUCCESS", Inspection.duration_ms.is_not(None))
            .order_by(Inspection.duration_ms)
        )
    ).scalars().all()
    avg_duration = None
    p95_duration = None
    if duration_rows:
        avg_duration = sum(duration_rows) / len(duration_rows)
        p95_idx = max(0, int(len(duration_rows) * 0.95) - 1)
        p95_duration = duration_rows[p95_idx]

    # enrichment stats (only over SUCCESS records)
    enrich_rows = (
        await session.execute(
            select(Inspection.enrichment_status, func.count(Inspection.id))
            .where(Inspection.status == "SUCCESS")
            .group_by(Inspection.enrichment_status)
        )
    ).all()
    by_enrichment = EnrichmentBreakdown()
    enriched = 0
    for es, cnt in enrich_rows:
        if es == "ENRICHED":
            by_enrichment.enriched = cnt
            enriched = cnt
        elif es == "ENRICHING":
            by_enrichment.enriching = cnt
        elif es == "ENRICH_FAILED":
            by_enrichment.failed = cnt
        else:
            by_enrichment.pending += cnt
    enrichment_rate = (enriched / success_count) if success_count > 0 else 0.0

    # by algorithm (top 10)
    algo_rows = (
        await session.execute(
            select(Inspection.algorithm_code, func.count(Inspection.id))
            .group_by(Inspection.algorithm_code)
            .order_by(func.count(Inspection.id).desc())
            .limit(10)
        )
    ).all()
    algo_codes = [r[0] for r in algo_rows]
    algo_names = {}
    if algo_codes:
        name_rows = (
            await session.execute(
                select(Algorithm.code, Algorithm.name).where(Algorithm.code.in_(algo_codes))
            )
        ).all()
        algo_names = {code: name for code, name in name_rows}
    by_algorithm = [
        AlgorithmUsage(code=code, name=algo_names.get(code), count=cnt)
        for code, cnt in algo_rows
    ]

    return RecordStatsOut(
        total=total,
        today_count=today_count,
        success_rate=success_rate,
        failure_count=failure_count,
        avg_duration_ms=avg_duration,
        p95_duration_ms=p95_duration,
        enrichment_rate=enrichment_rate,
        by_status=by_status,
        by_enrichment=by_enrichment,
        by_algorithm=by_algorithm,
        window_days=30,
    )


@router.get("/{record_id}", response_model=InspectionOut)
async def get_record(
    record_id: int,
    request: Request,
    inspector_id: Annotated[str, Depends(get_inspector_id)] = ...,  # type: ignore[assignment]
    session: AsyncSession = Depends(get_session),
) -> InspectionOut:
    """Get single record detail"""
    stmt = select(Inspection).where(Inspection.id == record_id)
    result = await session.execute(stmt)
    inspection = result.scalar_one_or_none()
    if inspection is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": f"Record {record_id} not found"},
        )
    return _to_inspection_out(inspection)


@router.post("/{record_id}/retry", response_model=RetryOut)
async def retry_record(
    record_id: int,
    request: Request,
    inspector_id: Annotated[str, Depends(get_inspector_id)],
    session: AsyncSession = Depends(get_session),
) -> RetryOut:
    """Retry a FAILED/DEAD record"""
    stmt = select(Inspection).where(Inspection.id == record_id)
    result = await session.execute(stmt)
    inspection = result.scalar_one_or_none()
    if inspection is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": f"Record {record_id} not found"},
        )

    if inspection.status not in {"FAILED", "DEAD"}:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_STATUS",
                "message": f"Cannot retry record with status {inspection.status}",
            },
        )

    inspection.status = "PENDING"
    inspection.error_code = None
    inspection.error_message = None
    inspection.retry_count = 0

    celery_app.send_task(
        "app.tasks.inspection.run_inspection",
        kwargs={"record_id": record_id},
        queue="inspect_queue",
    )

    audit = AuditService(session)
    await audit.log(
        actor=inspector_id,
        action=AuditAction.RETRY,
        resource_type="inspection",
        resource_id=str(record_id),
        source_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        result=AuditResult.SUCCESS,
    )

    await session.commit()

    return RetryOut(record_id=record_id, status="PENDING")


@router.post("/{record_id}/enrich", response_model=EnrichOut)
async def enrich_record(
    record_id: int,
    request: Request,
    inspector_id: Annotated[str, Depends(get_inspector_id)],
    session: AsyncSession = Depends(get_session),
) -> EnrichOut:
    """Trigger LLM enrichment for a SUCCESS record"""
    stmt = select(Inspection).where(Inspection.id == record_id)
    result = await session.execute(stmt)
    inspection = result.scalar_one_or_none()
    if inspection is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": f"Record {record_id} not found"},
        )

    if inspection.status != "SUCCESS":
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_STATUS",
                "message": f"Can only enrich SUCCESS records, current: {inspection.status}",
            },
        )

    inspection.enrichment_status = "ENRICHING"

    settings_obj = get_settings()
    if settings_obj.task_sync_mode:
        # sync 模式: 直接 await (无 Celery worker 也跑得通)
        from app.tasks.inspection import _run_enrichment_async
        try:
            await _run_enrichment_async(record_id)
        except Exception as e:
            logger.exception("Sync enrichment failed for record %s", record_id)
    else:
        celery_app.send_task(
            "app.tasks.inspection.enrich_inspection",
            kwargs={"record_id": record_id},
            queue="stats_queue",
        )

    audit = AuditService(session)
    await audit.log(
        actor=inspector_id,
        action=AuditAction.ENRICH,
        resource_type="inspection",
        resource_id=str(record_id),
        source_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        result=AuditResult.SUCCESS,
    )

    await session.commit()

    return EnrichOut(record_id=record_id, enrichment_status="ENRICHING")