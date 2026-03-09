"""
Celery tasks for Product Intelligence Platform.
"""

import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import settings
from app.db.models import Job, Session as DBSession, JobStatus, SimulationOutcome
from app.worker.celery_app import celery_app
from app.core.engine import SimulationEngine

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create async engine for worker
worker_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
)
WorkerSessionLocal = async_sessionmaker(
    worker_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_worker_db():
    """Get database session for worker."""
    async with WorkerSessionLocal() as session:
        yield session


@celery_app.task(bind=True, name="app.worker.tasks.run_analysis_task")
def run_analysis_task(self, job_id: str):
    """
    Celery task to run the analysis simulation.

    This task:
    1. Fetches the job from the database
    2. Updates status to PROCESSING
    3. Runs the simulation engine
    4. Updates job with results
    """
    logger.info(f"Starting analysis task for job: {job_id}")

    # Run the async simulation
    import asyncio

    async def _run():
        async with WorkerSessionLocal() as db:
            try:
                # Fetch job
                result = await db.execute(
                    select(Job).where(Job.id == UUID(job_id))
                )
                job = result.scalar_one_or_none()

                if not job:
                    logger.error(f"Job not found: {job_id}")
                    return

                # Update status to processing
                job.status = JobStatus.PROCESSING
                job.started_at = datetime.utcnow()
                await db.commit()

                # Create session
                session = DBSession(
                    job_id=job.id,
                    start_time=datetime.utcnow(),
                )
                db.add(session)
                await db.commit()
                await db.refresh(session)

                # Run simulation engine
                logger.info(f"Running simulation for job: {job_id}, URL: {job.url}")

                engine = SimulationEngine(
                    job_id=job.id,
                    session_id=session.id,
                    db=db,
                )

                try:
                    # Run the simulation
                    result = await engine.run(
                        url=job.url,
                        persona=job.persona,
                        task_template=job.task_template,
                        max_steps=job.max_steps,
                        max_duration=job.max_duration,
                    )

                    # Update session with results
                    session.end_time = datetime.utcnow()
                    session.logs = result.get("logs", [])
                    session.metrics = result.get("metrics", {})
                    await db.commit()

                    # Update job with results
                    job.status = JobStatus.COMPLETED
                    job.completed_at = datetime.utcnow()
                    job.outcome = SimulationOutcome(result.get("outcome", "task_completed"))
                    job.summary = result.get("summary")
                    await db.commit()

                    logger.info(f"Simulation completed for job: {job_id}")

                except Exception as e:
                    logger.error(f"Simulation failed for job {job_id}: {str(e)}")

                    # Update job as failed
                    job.status = JobStatus.FAILED
                    job.completed_at = datetime.utcnow()
                    job.outcome = SimulationOutcome.ERROR
                    job.error_message = str(e)
                    await db.commit()

                    # Update session
                    session.end_time = datetime.utcnow()
                    await db.commit()

            except Exception as e:
                logger.error(f"Task failed for job {job_id}: {str(e)}")
                raise

    # Run async function
    asyncio.run(_run())

    return {"job_id": job_id, "status": "completed"}


@celery_app.task(name="app.worker.tasks.cleanup_old_jobs")
def cleanup_old_jobs():
    """
    Periodic task to clean up old jobs.
    """
    logger.info("Cleaning up old jobs...")
    # Implement cleanup logic
    pass
