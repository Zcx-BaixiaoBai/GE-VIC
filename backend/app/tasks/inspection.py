"""识别任务 - 调引擎 + 更新状态 + 富化调度"""
import logging
import time
from datetime import datetime, timezone

from celery import shared_task
from sqlalchemy import select

from app.config import get_settings
from app.database import get_global_sessionmaker
from app.engines import get_engine
from app.models import Algorithm, Inspection
from app.services.storage import StorageService

logger = logging.getLogger(__name__)


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
def run_inspection(self, record_id: int) -> dict[str, str | int]:
    """执行识别任务

    流程: PENDING → RUNNING → SUCCESS/FAILED
    成功后异步触发 LLM 富化 (enrich_inspection)
    """
    logger.info("Starting inspection for record_id=%s", record_id)
    settings = get_settings()
    sm = get_global_sessionmaker()

    async def _run() -> dict[str, str | int]:
        async with sm() as session:
            # 1. 加载记录
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

            # 2. 加载算法
            algo_stmt = select(Algorithm).where(Algorithm.code == inspection.algorithm_code)
            algo_result = await session.execute(algo_stmt)
            algorithm = algo_result.scalar_one_or_none()
            if algorithm is None or not algorithm.is_active:
                inspection.status = "FAILED"
                inspection.error_code = "ALGORITHM_UNAVAILABLE"
                inspection.error_message = f"Algorithm {inspection.algorithm_code} not available"
                await session.commit()
                return {"status": "failed", "record_id": record_id}

            # 3. 更新为 RUNNING
            inspection.status = "RUNNING"
            inspection.started_at = datetime.now(timezone.utc)
            inspection.retry_count = (inspection.retry_count or 0) + 1
            await session.commit()

            # 4. 下载文件
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

            # 5. 调引擎
            try:
                engine = get_engine(algorithm.engine_type)
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

            # 6. 处理结果
            now = datetime.now(timezone.utc)
            inspection.finished_at = now
            inspection.duration_ms = recognition.duration_ms

            if not recognition.success:
                if inspection.retry_count >= 3:
                    inspection.status = "DEAD"
                else:
                    inspection.status = "FAILED"
                inspection.error_code = recognition.error_code
                inspection.error_message = recognition.error_message
            else:
                inspection.status = "SUCCESS"
                inspection.result = recognition.data
                inspection.summary = recognition.summary
                inspection.cost_estimate = recognition.cost_estimate
                # 触发富化
                inspection.enrichment_status = "ENRICHING"

            await session.commit()

            # 7. 触发富化
            if inspection.status == "SUCCESS":
                from app.tasks.celery_app import celery_app
                celery_app.send_task(
                    "app.tasks.enrichment.enrich_inspection",
                    kwargs={"record_id": record_id},
                    queue="stats_queue",
                )

            return {"status": inspection.status, "record_id": record_id}

    import asyncio
    return asyncio.run(_run())


@shared_task(
    bind=True,
    name="app.tasks.enrichment.enrich_inspection",
    max_retries=2,
    default_retry_delay=30,
)
def enrich_inspection(self, record_id: int) -> dict[str, str | int]:
    """LLM 富化任务 (独立队列, 失败不影响主任务)"""
    logger.info("Enriching record_id=%s", record_id)
    settings = get_settings()
    sm = get_global_sessionmaker()

    async def _run() -> dict[str, str | int]:
        from app.services.llm_client import LLMClient
        from app.services.enrichment import EnrichmentService

        llm = LLMClient(settings)
        try:
            async with sm() as session:
                stmt = select(Inspection).where(Inspection.id == record_id)
                result = await session.execute(stmt)
                inspection = result.scalar_one_or_none()
                if inspection is None:
                    return {"status": "not_found", "record_id": record_id}
                if inspection.status != "SUCCESS":
                    return {"status": "skipped", "record_id": record_id}

                # 找算法名
                algo_stmt = select(Algorithm).where(Algorithm.code == inspection.algorithm_code)
                algo_result = await session.execute(algo_stmt)
                algorithm = algo_result.scalar_one_or_none()
                algo_name = algorithm.name if algorithm else inspection.algorithm_code

                recognition = inspection.result or {}

                enrichment = EnrichmentService(llm)
                try:
                    enriched = await enrichment.enrich(algo_name, recognition)
                    inspection.llm_enrichment = enriched
                    inspection.enrichment_status = "ENRICHED"
                except Exception as e:
                    logger.exception("Enrichment failed for record %s", record_id)
                    inspection.enrichment_status = "ENRICH_FAILED"
                    inspection.llm_enrichment = {
                        "error_code": "LLM_ERROR",
                        "error_message": str(e),
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                    }
                await session.commit()
                return {"status": "done", "record_id": record_id, "enrichment_status": inspection.enrichment_status}
        finally:
            await llm.close()

    import asyncio
    return asyncio.run(_run())
