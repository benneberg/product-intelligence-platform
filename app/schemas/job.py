"""
Pydantic schemas for Product Intelligence Platform.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, field_validator

from app.db.models import JobStatus, SimulationOutcome, Persona


# Project Schemas
class ProjectBase(BaseModel):
    """Base project schema."""
    name: str = Field(..., min_length=1, max_length=200)
    target_url: str = Field(..., max_length=2048)
    description: Optional[str] = None


class ProjectCreate(ProjectBase):
    """Schema for creating a project."""
    pass


class ProjectResponse(ProjectBase):
    """Schema for project response."""
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# Job Schemas
class JobCreate(BaseModel):
    """Schema for creating a job."""
    url: str = Field(..., max_length=2048, description="Target URL to analyze")
    persona: str = Field(default="curious_beginner", description="Persona type for synthetic user")
    task_template: str = Field(default="explore_and_signup", description="Task to perform")
    max_steps: int = Field(default=50, ge=1, le=100, description="Maximum steps in simulation")
    max_duration: int = Field(default=900, ge=60, le=3600, description="Maximum duration in seconds")
    project_id: Optional[UUID] = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate URL format."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v


class JobUpdate(BaseModel):
    """Schema for updating a job."""
    status: Optional[JobStatus] = None
    outcome: Optional[SimulationOutcome] = None
    summary: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class JobResponse(BaseModel):
    """Schema for job response."""
    id: UUID
    project_id: Optional[UUID]
    url: str
    status: JobStatus
    persona: str
    task_template: str
    max_steps: int
    max_duration: int
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    outcome: Optional[SimulationOutcome]
    summary: Optional[str]
    error_message: Optional[str]
    metadata: Dict[str, Any]

    model_config = {"from_attributes": True}


class JobListResponse(BaseModel):
    """Schema for job list response."""
    jobs: List[JobResponse]
    total: int
    page: int
    page_size: int


# Session Schemas
class SessionResponse(BaseModel):
    """Schema for session response."""
    id: UUID
    job_id: UUID
    start_time: datetime
    end_time: Optional[datetime]
    logs: List[Dict[str, Any]]
    metrics: Dict[str, Any]

    model_config = {"from_attributes": True}


# Interaction Step Schemas
class InteractionStepBase(BaseModel):
    """Base interaction step schema."""
    step_number: int
    page_url: str
    page_title: Optional[str]
    action_type: str
    action_target: str
    action_value: Optional[str]
    action_mode: str
    agent_reasoning: Optional[str]
    pause_before_action: float
    screenshot_url: Optional[str]
    success: bool
    error_message: Optional[str]
    duration_ms: Optional[int]


class InteractionStepResponse(InteractionStepBase):
    """Schema for interaction step response."""
    id: UUID
    session_id: UUID
    job_id: UUID
    timestamp: datetime
    page_state_snapshot: Dict[str, Any]

    model_config = {"from_attributes": True}


# UX Insight Report Schemas
class FrictionPoint(BaseModel):
    """Schema for a friction point."""
    step_number: int
    description: str
    severity: str  # low, medium, high
    element: str
    recommendation: str


class Recommendation(BaseModel):
    """Schema for a recommendation."""
    priority: str  # high, medium, low
    category: str
    suggestion: str


class UXInsightReportBase(BaseModel):
    """Base UX insight report schema."""
    summary: str
    friction_points: List[FrictionPoint] = []
    positive_observations: List[str] = []
    recommendations: List[Recommendation] = []


class UXInsightReportResponse(UXInsightReportBase):
    """Schema for UX insight report response."""
    id: UUID
    job_id: UUID
    generated_at: datetime
    model_used: Optional[str]
    tokens_used: Optional[int]

    model_config = {"from_attributes": True}


# Metrics Schemas
class TaskMetrics(BaseModel):
    """Schema for task metrics."""
    steps_to_completion: int
    duration_seconds: float
    pages_visited: int


class NavigationMetrics(BaseModel):
    """Schema for navigation metrics."""
    loops: int
    dead_ends: int


class InteractionMetrics(BaseModel):
    """Schema for interaction metrics."""
    errors: int
    retries: int
    exploratory_actions: int


class EfficiencyMetrics(BaseModel):
    """Schema for efficiency metrics."""
    optimal_path_steps: int
    actual_steps: int
    efficiency: float


class MetricsResponse(BaseModel):
    """Schema for metrics response."""
    task_metrics: TaskMetrics
    navigation_metrics: NavigationMetrics
    interaction_metrics: InteractionMetrics
    efficiency_metrics: EfficiencyMetrics


# Health Check Schemas
class HealthCheckResponse(BaseModel):
    """Schema for health check response."""
    status: str
    services: Dict[str, str]
    version: str
