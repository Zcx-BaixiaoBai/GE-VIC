"""Inspection tasks - engine + state + enrichment"""
import asyncio
import logging
from datetime import datetime, timezone
from functools import lru_cache

from celery import shared_task
from sqlalchemy import select

from app.config import get_settings
from app.database import create_engine, get_sessionmaker
from app.engines import get_engine
from app.models import Algorithm, Inspection
from app.services.storage import StorageService
from app.services.metrics import (
    INSPECTIONS_TOTAL,
    INSPECTION_DURATION,
    ENGINE_CALL_ERRORS_TOTAL,
    ENRICHMENT_TOTAL,
    LLM_TOKENS_TOTAL,
)

logger = logging.getLogger(__name__)


def _get_engine_type_sync(algorithm_code: str) -> str:
    """同步查询算法的 engine_type (用于指标标签), 复用 task 的 engine"""
    from app.database import get_global_sessionmaker
    from sqlalchemy import select
    from app.models import Algorithm
    try:
        sm = get_global_sessionmaker()
        # 此函数实际在 async 上下文外调用, 用 run_sync
        import asyncio
        async def _query():
            async with sm() as session:
                stmt = select(Algorithm.engine_type).where(Algorithm.code == algorithm_code)
                result = await session.execute(stmt)
                return result.scalar_one_or_none()
        try:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(_query()) or "unknown"
        except RuntimeError:
            return asyncio.run(_query()) or "unknown"
    except Exception:
        return "unknown"


@lru_cache(maxsize=1)
def _make_task_sessionmaker():
    """Create a dedicated sessionmaker for task execution (separate engine from API)"""

    # Cached at module level so the asyncpg connection pool is reused across
    # Celery tasks instead of being recreated per task.
    return get_sessionmaker(create_engine(get_settings().database_url, pool_size=2))


async def _run_inspection_async(record_id: int) -> dict:
    """Core inspection logic (async) - called by both Celery task and sync mode"""
    settings = get_settings()
    sm = _make_task_sessionmaker()

    async with sm() as session:
        # 1. Load record
        stmt = select(Inspection).where(Inspection.id == record_id)
        result = await session.execute(stmt)
        inspection = result.scalar_one_or_none()
        if inspection is None:
            logger.error("Record %s not found", record_id)
            return {"status": "not_found", "record_id": record_id}

        if inspection.status not in {"PENDING", "FAILED", "DEAD"}:
            logger.warning(
                "Record %s already in status %s, skip", record_id, inspection.status
            )
            return {"status": "skipped", "record_id": record_id}

        # 2. Load algorithm
        algo_stmt = select(Algorithm).where(Algorithm.code == inspection.algorithm_code)
        algo_result = await session.execute(algo_stmt)
        algorithm = algo_result.scalar_one_or_none()
        if algorithm is None or not algorithm.is_active:
            inspection.status = "FAILED"
            inspection.error_code = "ALGORITHM_UNAVAILABLE"
            inspection.error_message = f"Algorithm {inspection.algorithm_code} not available"
            await session.commit()
            return {"status": "failed", "record_id": record_id}

        # 3. Update to RUNNING
        inspection.status = "RUNNING"
        inspection.started_at = datetime.now(timezone.utc)
        inspection.retry_count = (inspection.retry_count or 0) + 1
        await session.commit()

        # 4. Download file
        try:
            storage = StorageService.from_settings(settings)
            if not inspection.object_key:
                raise RuntimeError("No object_key on inspection")
            file_bytes = storage.download_file(inspection.object_key)
        except Exception as e:
            logger.exception("Download failed for record %s", record_id)
            inspection.status = "FAILED"
            inspection.error_code = "STORAGE_DOWNLOAD_ERROR"
            inspection.error_message = str(e)
            inspection.finished_at = datetime.now(timezone.utc)
            await session.commit()
            return {"status": "failed", "record_id": record_id}

        # 5. Call engine
        try:
            engine = get_engine(algorithm.engine_type)
            is_batch = bool(inspection.is_batch) and bool(inspection.batch_files)
            if is_batch:
                # 联合分析: 下载所有文件, 一次性发给引擎
                batch_files = []
                primary = {
                    "bytes": file_bytes,
                    "filename": inspection.request_meta.get("filename", "upload.bin") if inspection.request_meta else "upload.bin",
                    "mime": inspection.request_meta.get("mime_type") if inspection.request_meta else None,
                    "meta": inspection.request_meta or {},
                }
                batch_files.append(primary)
                for bf in inspection.batch_files or []:
                    try:
                        b_bytes = storage.download_file(bf["object_key"])
                        batch_files.append({
                            "bytes": b_bytes,
                            "filename": bf.get("filename", "batch.bin"),
                            "mime": bf.get("mime_type"),
                            "meta": bf.get("meta") or {},
                        })
                    except Exception as e:
                        logger.warning("Failed to download batch file %s: %s", bf.get("object_key"), e)
                recognition = await engine.recognize_batch(
                    files=batch_files,
                    meta=inspection.request_meta or {},
                    config=algorithm.engine_config or {},
                )
            else:
                recognition = await engine.recognize(
                    file_bytes=file_bytes,
                    filename=inspection.request_meta.get("filename", "upload.bin") if inspection.request_meta else "upload.bin",
                    meta=inspection.request_meta or {},
                    config=algorithm.engine_config or {},
                )
        except Exception as e:
            logger.exception("Engine call failed for record %s", record_id)
            inspection.status = "FAILED"
            inspection.error_code = "ENGINE_INIT_ERROR"
            inspection.error_message = str(e)
            inspection.finished_at = datetime.now(timezone.utc)
            await session.commit()
            return {"status": "failed", "record_id": record_id}

        # 6. Process result
        now = datetime.now(timezone.utc)
        inspection.finished_at = now
        inspection.duration_ms = recognition.duration_ms

        engine_type = algorithm.engine_type or "unknown"
        if not recognition.success:
            if inspection.retry_count >= 3:
                inspection.status = "DEAD"
            else:
                inspection.status = "FAILED"
            inspection.error_code = recognition.error_code
            inspection.error_message = recognition.error_message
            INSPECTIONS_TOTAL.labels(
                algorithm=inspection.algorithm_code,
                status=inspection.status,
            ).inc()
            if recognition.error_code:
                ENGINE_CALL_ERRORS_TOTAL.labels(
                    engine=engine_type,
                    error_code=recognition.error_code,
                ).inc()
        else:
            inspection.status = "SUCCESS"
            inspection.result = recognition.data
            inspection.summary = recognition.summary
            inspection.cost_estimate = recognition.cost_estimate
            inspection.enrichment_status = "ENRICHING"
            # 指标: 成功 + 耗时 (§14.3)
            INSPECTIONS_TOTAL.labels(
                algorithm=inspection.algorithm_code,
                status="SUCCESS",
            ).inc()
            if recognition.duration_ms:
                INSPECTION_DURATION.labels(
                    algorithm=inspection.algorithm_code,
                    engine=engine_type,
                ).observe(recognition.duration_ms / 1000.0)

        await session.commit()

        # 7. Trigger enrichment
        if inspection.status == "SUCCESS":
            if settings.task_sync_mode:
                try:
                    logger.info("Running enrichment in sync mode for record_id=%s", record_id)
                    await _run_enrichment_async(record_id)
                except Exception as e:
                    logger.exception("Sync enrichment failed")
            else:
                from app.tasks.celery_app import celery_app
                celery_app.send_task(
                    "app.tasks.enrichment.enrich_inspection",
                    kwargs={"record_id": record_id},
                    queue="stats_queue",
                )

        return {"status": inspection.status, "record_id": record_id}


async def _run_enrichment_async(record_id: int) -> dict:
    """Core enrichment logic (async)"""
    from app.services.llm_client import get_shared_llm_client
    from app.services.enrichment import EnrichmentService

    settings = get_settings()
    sm = _make_task_sessionmaker()
    llm = get_shared_llm_client(settings)
    try:
        async with sm() as session:
            stmt = select(Inspection).where(Inspection.id == record_id)
            result = await session.execute(stmt)
            inspection = result.scalar_one_or_none()
            if inspection is None:
                return {"status": "not_found", "record_id": record_id}
            if inspection.status != "SUCCESS":
                return {"status": "skipped", "record_id": record_id}

            algo_stmt = select(Algorithm).where(Algorithm.code == inspection.algorithm_code)
            algo_result = await session.execute(algo_stmt)
            algorithm = algo_result.scalar_one_or_none()
            algo_name = algorithm.name if algorithm else inspection.algorithm_code

            recognition = inspection.result or {}

            enrichment = EnrichmentService(llm)
            try:
                enriched = await enrichment.enrich(algo_name, recognition, algorithm.engine_config)
                inspection.llm_enrichment = enriched
                inspection.enrichment_status = "ENRICHED"
                ENRICHMENT_TOTAL.labels(status="ENRICHED").inc()
                if enriched:
                    tok = enriched.get("token_used", 0) or 0
                    model = enriched.get("model", "unknown")
                    if tok:
                        LLM_TOKENS_TOTAL.labels(model=model, direction="prompt").inc(int(tok * 0.85))
                        LLM_TOKENS_TOTAL.labels(model=model, direction="completion").inc(int(tok * 0.15))
            except Exception as e:
                logger.exception("Enrichment failed for record %s", record_id)
                inspection.enrichment_status = "ENRICH_FAILED"
                ENRICHMENT_TOTAL.labels(status="ENRICH_FAILED").inc()
                inspection.llm_enrichment = {
                    "error_code": "LLM_ERROR",
                    "error_message": str(e),
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                }
            await session.commit()
            return {"status": "done", "record_id": record_id, "enrichment_status": inspection.enrichment_status}
    finally:
        pass  # shared LLM client is reused across tasks; do not close


@shared_task(
    bind=True,
    name="app.tasks.inspection.run_inspection",
    max_retries=3,
    default_retry_delay=10,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
)
def run_inspection(self, record_id: int) -> dict:
    """Celery task: sync wrapper for async function (worker process)"""
    logger.info("Celery task: Starting inspection for record_id=%s", record_id)
    return asyncio.run(_run_inspection_async(record_id))


@shared_task(
    bind=True,
    name="app.tasks.enrichment.enrich_inspection",
    max_retries=2,
    default_retry_delay=30,
)
def enrich_inspection(self, record_id: int) -> dict:
    """Celery task: sync wrapper for async function (worker process)"""
    logger.info("Celery task: Enriching record_id=%s", record_id)
    return asyncio.run(_run_enrichment_async(record_id))
