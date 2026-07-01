"""GET /api/v1/records - record query endpoints"""
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.deps import get_inspector_id
from app.models import Inspection
from app.schemas.inspection import (
    EnrichOut,
    InspectionListOut,
    InspectionOut,
    RetryOut,
)
from app.services.audit import AuditAction, AuditResult, AuditService
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