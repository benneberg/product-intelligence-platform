"""
Web UI routes for serving HTML templates.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db, Job, UXInsightReport

# Create router
router = APIRouter(tags=["Web UI"])


@router.get("/")
async def root():
    """Redirect to dashboard."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/dashboard")


@router.get("/dashboard")
async def dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    """Dashboard page with stats and recent jobs."""
    # Get job stats
    result = await db.execute(select(Job))
    jobs = result.scalars().all()

    total_jobs = len(jobs)
    completed_jobs = len([j for j in jobs if j.status == "completed"])
    failed_jobs = len([j for j in jobs if j.status == "failed"])
    success_rate = int((completed_jobs / total_jobs * 100) if total_jobs > 0 else 0)

    # Calculate average duration
    completed_with_duration = [j for j in jobs if j.completed_at and j.started_at]
    avg_duration = 0
    if completed_with_duration:
        total_duration = sum(
            (j.completed_at - j.started_at).total_seconds()
            for j in completed_with_duration
        )
        avg_duration = int(total_duration / len(completed_with_duration))

    # Get recent jobs
    recent_jobs = sorted(jobs, key=lambda x: x.created_at, reverse=True)[:5]

    stats = {
        "total_jobs": total_jobs,
        "completed_jobs": completed_jobs,
        "success_rate": success_rate,
        "avg_duration": avg_duration,
    }

    return request.app.state.jinja_template.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "stats": stats,
            "recent_jobs": recent_jobs,
        }
    )


@router.get("/jobs")
async def jobs_list(
    request: Request,
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List all jobs with optional status filter."""
    query = select(Job).order_by(Job.created_at.desc())

    if status:
        query = query.where(Job.status == status)

    result = await db.execute(query)
    jobs = result.scalars().all()

    return request.app.state.jinja_template.TemplateResponse(
        "jobs.html",
        {
            "request": request,
            "jobs": jobs,
            "current_status": status,
        }
    )


@router.get("/jobs/new")
async def job_create(request: Request):
    """New analysis job form."""
    return request.app.state.jinja_template.TemplateResponse(
        "job_create.html",
        {"request": request}
    )


@router.get("/jobs/{job_id}")
async def job_detail(
    request: Request,
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Job detail page."""
    result = await db.execute(
        select(Job).where(Job.id == job_id)
    )
    job = result.scalar_one_or_none()

    if not job:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Job not found")

    return request.app.state.jinja_template.TemplateResponse(
        "job_detail.html",
        {
            "request": request,
            "job": job,
        }
    )


@router.get("/jobs/{job_id}/report")
async def job_report(
    request: Request,
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Job report page."""
    # Get job
    result = await db.execute(
        select(Job).where(Job.id == job_id)
    )
    job = result.scalar_one_or_none()

    if not job:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Job not found")

    # Get report
    result = await db.execute(
        select(UXInsightReport).where(UXInsightReport.job_id == job_id)
    )
    report = result.scalar_one_or_none()

    # Get metrics from job metadata
    metrics = job.metadata.get("metrics", {}) if job.metadata else {}

    return request.app.state.jinja_template.TemplateResponse(
        "report.html",
        {
            "request": request,
            "job": job,
            "report": report,
            "metrics": metrics,
        }
    )


@router.get("/projects")
async def projects_list(request: Request):
    """Projects list page (placeholder)."""
    return request.app.state.jinja_template.TemplateResponse(
        "projects.html",
        {"request": request, "projects": []}
    )
