"""
Insights Generator - Analyzes session logs and generates UX reports.

Transforms raw interaction data into actionable UX insights.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class FrictionPoint:
    """Represents a UX friction point."""
    step_number: int
    description: str
    severity: str  # low, medium, high
    element: str
    recommendation: str
    page_url: str = ""


@dataclass
class Recommendation:
    """Represents a UX recommendation."""
    priority: str  # high, medium, low
    category: str
    suggestion: str


@dataclass
class UXReport:
    """Complete UX analysis report."""
    summary: str
    outcome: str
    friction_points: List[FrictionPoint] = field(default_factory=list)
    positive_observations: List[str] = field(default_factory=list)
    recommendations: List[Recommendation] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)


class InsightsGenerator:
    """
    Generates UX insights from session interaction logs.
    """

    # Common UX issues patterns
    ISSUE_PATTERNS = {
        "hidden_cta": {
            "keywords": ["scrolled", "looking for", "can't find", "where is"],
            "severity": "high",
            "category": "navigation",
        },
        "confusing_form": {
            "keywords": ["error", "failed", "wrong", "invalid"],
            "severity": "medium",
            "category": "forms",
        },
        "slow_loading": {
            "keywords": ["wait", "timeout", "slow", "loading"],
            "severity": "medium",
            "category": "performance",
        },
        "unclear_navigation": {
            "keywords": ["lost", "confused", "where", "back"],
            "severity": "medium",
            "category": "navigation",
        },
    }

    def __init__(self, use_llm: bool = True):
        self.use_llm = use_llm

    def generate(
        self,
        session_logs: List[Dict[str, Any]],
        metrics: Dict[str, Any],
        task: str = "explore_and_signup",
        llm_client=None,
    ) -> UXReport:
        """
        Generate UX insights report from session logs.

        Args:
            session_logs: List of interaction steps
            metrics: Quantitative metrics
            task: Task that was being performed
            llm_client: Optional LLM client for advanced analysis

        Returns:
            UXReport with insights
        """
        logger.info(f"Generating insights for {len(session_logs)} steps")

        # Analyze logs
        friction_points = self._detect_friction_points(session_logs)
        positive_observations = self._detect_positive_observations(session_logs)
        summary = self._generate_summary(session_logs, metrics, task)

        # Generate recommendations
        recommendations = self._generate_recommendations(
            friction_points,
            positive_observations,
            metrics,
        )

        # Determine outcome
        outcome = self._determine_outcome(session_logs, metrics)

        return UXReport(
            summary=summary,
            outcome=outcome,
            friction_points=friction_points,
            positive_observations=positive_observations,
            recommendations=recommendations,
            metrics=metrics,
        )

    def _detect_friction_points(
        self,
        session_logs: List[Dict[str, Any]],
    ) -> List[FrictionPoint]:
        """Detect friction points from logs."""
        friction_points = []

        # Check for failed actions
        for i, log in enumerate(session_logs):
            result = log.get("result", {})
            action = log.get("action", {})

            if not result.get("success", True):
                step_num = log.get("step_number", i + 1)
                error = result.get("error", "Unknown error")

                # Determine severity based on error type
                severity = "low"
                if "not found" in error.lower():
                    severity = "high"
                elif "timeout" in error.lower():
                    severity = "medium"

                friction_points.append(FrictionPoint(
                    step_number=step_num,
                    description=f"Action failed: {error}",
                    severity=severity,
                    element=action.get("target", "Unknown"),
                    recommendation=self._get_recommendation_for_error(error),
                ))

        # Check for loops (repeated actions)
        loop_steps = self._detect_loops(session_logs)
        for step_num in loop_steps:
            friction_points.append(FrictionPoint(
                step_number=step_num,
                description="User appears stuck in a loop, repeating same actions",
                severity="medium",
                element="Navigation",
                recommendation="Improve navigation clarity and provide clearer path to goal",
            ))

        # Check for excessive scrolling (potential hidden content)
        scroll_count = sum(
            1 for log in session_logs
            if log.get("action", {}).get("action_type") == "scroll"
        )
        if scroll_count > 10:
            # Find the step where excessive scrolling started
            friction_points.append(FrictionPoint(
                step_number=min(10, len(session_logs)),
                description=f"User scrolled {scroll_count} times - content may be hard to find",
                severity="medium",
                element="Page Layout",
                recommendation="Move important content higher or add navigation aids",
            ))

        return friction_points

    def _detect_positive_observations(
        self,
        session_logs: List[Dict[str, Any]],
    ) -> List[str]:
        """Detect positive UX observations."""
        observations = []

        # Check for smooth navigation
        successful_clicks = sum(
            1 for log in session_logs
            if log.get("action", {}).get("action_type") == "click"
            and log.get("result", {}).get("success", False)
        )
        if successful_clicks >= 5:
            observations.append(f"Navigation worked smoothly ({successful_clicks} successful clicks)")

        # Check for form completion
        type_actions = [
            log for log in session_logs
            if log.get("action", {}).get("action_type") == "type"
        ]
        if len(type_actions) >= 2:
            observations.append("Form fields were accessible and fillable")

        # Check for goal completion
        if self._check_goal_completion(session_logs):
            observations.append("User successfully completed the primary task")

        # Check for reasonable time
        if session_logs:
            # Check if not too many errors
            errors = sum(
                1 for log in session_logs
                if not log.get("result", {}).get("success", True)
            )
            if errors <= 2:
                observations.append("Minimal friction encountered during session")

        return observations

    def _detect_loops(self, session_logs: List[Dict[str, Any]]) -> List[int]:
        """Detect loops in user behavior."""
        loops = []
        recent_actions = []

        for log in session_logs:
            action = log.get("action", {})
            action_key = f"{action.get('action_type')}:{action.get('target')}"

            if action_key in recent_actions[-2:]:
                loops.append(log.get("step_number", 0))

            recent_actions.append(action_key)
            if len(recent_actions) > 5:
                recent_actions.pop(0)

        return loops

    def _generate_summary(
        self,
        session_logs: List[Dict[str, Any]],
        metrics: Dict[str, Any],
        task: str,
    ) -> str:
        """Generate overall summary."""
        steps = len(session_logs)
        errors = sum(
            1 for log in session_logs
            if not log.get("result", {}).get("success", True)
        )

        task_metrics = metrics.get("task_metrics", {})
        duration = task_metrics.get("duration_seconds", 0)
        pages_visited = task_metrics.get("pages_visited", 0)

        # Determine outcome
        completed = self._check_goal_completion(session_logs)

        if completed:
            summary = f"Successfully completed {task} in {steps} steps over {duration:.0f} seconds. "
        else:
            summary = f"Attempted {task} over {steps} steps and {duration:.0f} seconds. "

        if errors > 0:
            summary += f"Encountered {errors} errors along the way. "
        else:
            summary += "No major errors encountered. "

        summary += f"Visited {pages_visited} pages during the session."

        return summary

    def _generate_recommendations(
        self,
        friction_points: List[FrictionPoint],
        positive_observations: List[str],
        metrics: Dict[str, Any],
    ) -> List[Recommendation]:
        """Generate prioritized recommendations."""
        recommendations = []

        # Generate recommendations from friction points
        seen_categories = set()
        for fp in friction_points:
            category = self._get_category_for_severity(fp.severity)
            if category not in seen_categories:
                recommendations.append(Recommendation(
                    priority=fp.severity,
                    category=category,
                    suggestion=fp.recommendation,
                ))
                seen_categories.add(category)

        # Add efficiency recommendations
        efficiency = metrics.get("efficiency_metrics", {}).get("efficiency", 1.0)
        if efficiency < 0.5:
            recommendations.append(Recommendation(
                priority="medium",
                category="efficiency",
                suggestion="User took many steps - consider streamlining the user flow",
            ))

        # Sort by priority
        priority_order = {"high": 0, "medium": 1, "low": 2}
        recommendations.sort(key=lambda x: priority_order.get(x.priority, 2))

        return recommendations[:5]  # Limit to top 5

    def _determine_outcome(
        self,
        session_logs: List[Dict[str, Any]],
        metrics: Dict[str, Any],
    ) -> str:
        """Determine session outcome."""
        if self._check_goal_completion(session_logs):
            return "task_completed"

        # Check for stuck/loops
        if len(self._detect_loops(session_logs)) > 3:
            return "stuck"

        # Check for too many errors
        errors = sum(
            1 for log in session_logs
            if not log.get("result", {}).get("success", True)
        )
        if errors > 5:
            return "error"

        return "incomplete"

    def _check_goal_completion(self, session_logs: List[Dict[str, Any]]) -> bool:
        """Check if primary goal was completed."""
        # Look for completion indicators in final steps
        if not session_logs:
            return False

        # Check URLs for completion indicators
        final_urls = [
            log.get("page_url", "").lower()
            for log in session_logs[-3:]
        ]

        completion_indicators = [
            "success", "welcome", "dashboard", "complete",
            "confirmed", "account", "profile", "thank",
        ]

        for url in final_urls:
            if any(ind in url for ind in completion_indicators):
                return True

        # Check if final action was successful submit
        for log in reversed(session_logs):
            action = log.get("action", {})
            result = log.get("result", {})
            if (action.get("action_type") == "click" and
                "submit" in action.get("target", "").lower() and
                result.get("success")):
                return True

        return False

    def _get_recommendation_for_error(self, error: str) -> str:
        """Get recommendation based on error type."""
        error_lower = error.lower()

        if "not found" in error_lower:
            return "Ensure element is properly visible and accessible"
        elif "timeout" in error_lower:
            return "Optimize page load time or add loading indicators"
        elif "invalid" in error_lower:
            return "Improve form validation messaging"
        else:
            return "Review and fix the underlying issue"

    def _get_category_for_severity(self, severity: str) -> str:
        """Map severity to category."""
        mapping = {
            "high": "usability",
            "medium": "navigation",
            "low": "content",
        }
        return mapping.get(severity, "general")

    def to_dict(self, report: UXReport) -> Dict[str, Any]:
        """Convert UXReport to dictionary."""
        return {
            "summary": report.summary,
            "outcome": report.outcome,
            "friction_points": [
                {
                    "step_number": fp.step_number,
                    "description": fp.description,
                    "severity": fp.severity,
                    "element": fp.element,
                    "recommendation": fp.recommendation,
                }
                for fp in report.friction_points
            ],
            "positive_observations": report.positive_observations,
            "recommendations": [
                {
                    "priority": rec.priority,
                    "category": rec.category,
                    "suggestion": rec.suggestion,
                }
                for rec in report.recommendations
            ],
            "metrics": report.metrics,
        }
