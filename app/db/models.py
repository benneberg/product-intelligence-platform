"""
Database models for Product Intelligence Platform.
"""

import uuid
import enum
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import Column, String, DateTime, Text, Integer, Float, Boolean, Enum, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.db.session import Base


class JobStatus(str, enum.Enum):
    """Job status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SimulationOutcome(str, enum.Enum):
    """Simulation outcome enumeration."""
    TASK_COMPLETED = "task_completed"
    STUCK = "stuck"
    TIMEOUT = "timeout"
    ERROR = "error"


class ActionType(str, enum.Enum):
    """Action type enumeration."""
    CLICK = "click"
    TYPE = "type"
    SCROLL = "scroll"
    NAVIGATE = "navigate"
    HOVER = "hover"
    WAIT = "wait"


class ActionMode(str, enum.Enum):
    """Action mode enumeration."""
    GOAL_DIRECTED = "goal_directed"
    EXPLORATORY = "exploratory"


class Persona(str, enum.Enum):
    """Persona types for synthetic users."""
    CURIOUS_BEGINNER = "curious_beginner"
    IMPATIENT_SHOPPER = "impatient_shopper"
    CAREFUL_RESEARCHER = "careful_researcher"


class Project(Base):
    """Project model - groups related simulations."""
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    target_url = Column(String(2048), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    jobs = relationship("Job", back_populates="project", cascade="all, delete-orphan")


class Job(Base):
    """Job model - represents an analysis request."""
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True)
    url = Column(String(2048), nullable=False)
    status = Column(Enum(JobStatus), default=JobStatus.PENDING, nullable=False)
    persona = Column(String(50), default="curious_beginner", nullable=False)
    task_template = Column(Text, default="explore_and_signup", nullable=False)
    max_steps = Column(Integer, default=50, nullable=False)
    max_duration = Column(Integer, default=900, nullable=False)  # seconds

    # Timing
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Results
    outcome = Column(Enum(SimulationOutcome), nullable=True)
    summary = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)

    # Metadata
    metadata = Column(JSONB, default={})

    # Relationships
    project = relationship("Project", back_populates="jobs")
    sessions = relationship("Session", back_populates="job", cascade="all, delete-orphan")
    report = relationship("UXInsightReport", back_populates="job", uselist=False, cascade="all, delete-orphan")


class Session(Base):
    """Session model - represents a browser session."""
    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False)

    # Timing
    start_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    end_time = Column(DateTime, nullable=True)

    # Data
    logs = Column(JSONB, default=[])  # Raw interaction logs
    metrics = Column(JSONB, default={})  # Quantitative metrics

    # Relationships
    job = relationship("Job", back_populates="sessions")
    steps = relationship("InteractionStep", back_populates="session", cascade="all, delete-orphan")


class InteractionStep(Base):
    """InteractionStep model - represents a single action in the simulation."""
    __tablename__ = "interaction_steps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False)

    step_number = Column(Integer, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Page context
    page_url = Column(String(2048), nullable=False)
    page_title = Column(String(500), nullable=True)

    # Action details
    action_type = Column(Enum(ActionType), nullable=False)
    action_target = Column(Text, nullable=False)
    action_value = Column(Text, nullable=True)
    action_mode = Column(Enum(ActionMode), default=ActionMode.GOAL_DIRECTED, nullable=False)

    # Agent reasoning
    agent_reasoning = Column(Text, nullable=True)
    pause_before_action = Column(Float, nullable=False, default=0.0)

    # Screenshot
    screenshot_url = Column(String(2048), nullable=True)

    # Page state snapshot (compressed context)
    page_state_snapshot = Column(JSONB, default={})

    # Result
    success = Column(Boolean, default=True, nullable=False)
    error_message = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)

    # Relationships
    session = relationship("Session", back_populates="steps")


class UXInsightReport(Base):
    """UXInsightReport model - generated UX analysis report."""
    __tablename__ = "ux_insight_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False, unique=True)

    # Content
    summary = Column(Text, nullable=False)
    friction_points = Column(JSONB, default=[])  # Array of friction objects
    positive_observations = Column(JSONB, default=[])  # Array of strings
    recommendations = Column(JSONB, default=[])  # Array of recommendation objects

    # Metadata
    generated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    model_used = Column(String(100), nullable=True)
    tokens_used = Column(Integer, nullable=True)

    # Relationships
    job = relationship("Job", back_populates="report")
