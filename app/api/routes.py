"""
API routes for Product Intelligence Platform.
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db, Job, Session as DBSession, Project, UXInsightReport, JobStatus
from app.schemas import (
    JobCreate,
    JobUpdate,
    JobResponse,
    JobListResponse,
    ProjectCreate,
    ProjectResponse,
    UXInsightReportResponse,
    HealthCheckResponse,
)
from app.worker.tasks import run_analysis_task
from app.config import settings

# Create router
router = APIRouter(prefix="/api/v1", tags=["API v1"])


# Health Check
@router.get("/health", response_model=HealthCheckResponse, tags=["Health"])
async def health_check():
    """
    Health check endpoint to verify services are running.
    """
    return HealthCheckResponse(
        status="ok",
        services={
            "api": "up",
            "database": "up",
        },
        version=settings.APP_VERSION,
    )


# Projects Endpoints
@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project: ProjectCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new project.
    """
    db_project = Project(
        name=project.name,
        target_url=project.target_url,
        description=project.description,
    )
    db.add(db_project)
    await db.commit()
    await db.refresh(db_project)
    return db_project


@router.get("/projects", response_model=List[ProjectResponse])
async def list_projects(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
):
    """
    List all projects.
    """
    result = await db.execute(
        select(Project).offset(skip).limit(limit)
    )
    projects = result.scalars().all()
    return projects


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific project by ID.
    """
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    return project


# Jobs Endpoints
@router.post("/analyze", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_analysis_job(
    job: JobCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new analysis job and enqueue it for processing.
    """
    # Create job record
    db_job = Job(
        project_id=job.project_id,
        url=job.url,
        persona=job.persona,
        task_template=job.task_template,
        max_steps=job.max_steps,
        max_duration=job.max_duration,
        status=JobStatus.PENDING,
    )
    db.add(db_job)
    await db.commit()
    await db.refresh(db_job)

    # Enqueue Celery task
    try:
        run_analysis_task.delay(str(db_job.id))
    except Exception as e:
        # Log error but don't fail the request
        db_job.status = JobStatus.FAILED
        db_job.error_message = f"Failed to enqueue task: {str(e)}"
        await db.commit()

    return db_job


@router.get("/jobs", response_model=JobListResponse)
async def list_jobs(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    status: Optional[JobStatus] = None,
):
    """
    List all jobs with optional status filter.
    """
    query = select(Job)
    if status:
        query = query.where(Job.status == status)

    # Get total count
    count_result = await db.execute(
        select(Job).where(Job.status == status) if status else select(Job)
    )
    total = len(count_result.scalars().all())

    # Get paginated results
    result = await db.execute(
        query.offset(skip).limit(limit).order_by(Job.created_at.desc())
    )
    jobs = result.scalars().all()

    return JobListResponse(
        jobs=jobs,
        total=total,
        page=skip // limit + 1,
        page_size=limit,
    )


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific job by ID.
    """
    result = await db.execute(
        select(Job).where(Job.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    return job


@router.patch("/jobs/{job_id}", response_model=JobResponse)
async def update_job(
    job_id: UUID,
    job_update: JobUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Update a job.
    """
    result = await db.execute(
        select(Job).where(Job.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )

    # Update fields
    update_data = job_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(job, field, value)

    await db.commit()
    await db.refresh(job)
    return job


# Reports Endpoints
@router.get("/jobs/{job_id}/report", response_model=UXInsightReportResponse)
async def get_job_report(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get the UX insight report for a job.
    """
    result = await db.execute(
        select(UXInsightReport).where(UXInsightReport.job_id == job_id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found for this job"
        )
    return report


# Sessions Endpoints
@router.get("/jobs/{job_id}/sessions")
async def get_job_sessions(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get all sessions for a job.
    """
    result = await db.execute(
        select(DBSession).where(DBSession.job_id == job_id)
    )
    sessions = result.scalars().all()
    return sessions
