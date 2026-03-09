"""
Core package for Product Intelligence Platform.
"""

from app.core.browser import BrowserManager
from app.core.engine import SimulationEngine, MetricsCollector, BehavioralModel, RecentSteps
from app.core.llm import LLMClient
from app.core.page_processor import PageStateProcessor, ProcessedPageState
from app.core.validator import ActionValidator, ValidationResult, RetryHandler
from app.core.insights import InsightsGenerator, UXReport, FrictionPoint, Recommendation
from app.core.llm_enhanced import EnhancedLLMClient, LLMPromptBuilder, PersonaConfig

__all__ = [
    # Browser
    "BrowserManager",
    # Engine
    "SimulationEngine",
    "MetricsCollector",
    "BehavioralModel",
    "RecentSteps",
    # LLM
    "LLMClient",
    "EnhancedLLMClient",
    "LLMPromptBuilder",
    "PersonaConfig",
    # Page Processing
    "PageStateProcessor",
    "ProcessedPageState",
    # Validation
    "ActionValidator",
    "ValidationResult",
    "RetryHandler",
    # Insights
    "InsightsGenerator",
    "UXReport",
    "FrictionPoint",
    "Recommendation",
]
