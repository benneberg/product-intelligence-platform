"""
Simulation Engine - Core component for running synthetic user simulations.

Phase 2 Enhanced Version with:
- Page State Processor for DOM compression
- Action Validator for safety checks
- Insights Generator for UX reports
- Enhanced LLM client with better prompts
"""

import asyncio
import logging
import random
import time
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.browser import BrowserManager
from app.core.llm import LLMClient
from app.core.llm_enhanced import EnhancedLLMClient
from app.core.page_processor import PageStateProcessor, ProcessedPageState
from app.core.validator import ActionValidator, RetryHandler
from app.core.insights import InsightsGenerator
from app.db.models import InteractionStep, ActionType, ActionMode, UXInsightReport

logger = logging.getLogger(__name__)


class RecentSteps:
    """
    Memory buffer for recent interaction steps.
    Used to detect loops and provide context to the agent.
    """

    def __init__(self, capacity: int = 10):
        self.capacity = capacity
        self.steps: List[Dict[str, Any]] = []

    def append(self, step: Dict[str, Any]):
        """Add a step to memory."""
        self.steps.append(step)
        if len(self.steps) > self.capacity:
            self.steps.pop(0)

    def recent(self, n: int = 5) -> List[Dict[str, Any]]:
        """Get the n most recent steps."""
        return self.steps[-n:]

    def __len__(self):
        return len(self.steps)


class MetricsCollector:
    """
    Collects quantitative metrics during simulation.
    """

    def __init__(self):
        self.steps: List[Dict[str, Any]] = []
        self.pages: set = set()
        self.errors: int = 0
        self.retries: int = 0
        self.loops: int = 0
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None

    def update(self, action: Dict[str, Any], result: Dict[str, Any]):
        """Update metrics with new action and result."""
        self.steps.append(action)
        if "page_url" in result:
            self.pages.add(result["page_url"])

        if not result.get("success", True):
            self.errors += 1
            if self._is_retry(action):
                self.retries += 1

        if self._is_loop_step(action):
            self.loops += 1

    def _is_retry(self, action: Dict[str, Any]) -> bool:
        """Check if action is a retry."""
        recent = self.steps[-5:]
        same_target = [s for s in recent if s.get("target") == action.get("target")]
        return len(same_target) >= 2

    def _is_loop_step(self, action: Dict[str, Any]) -> bool:
        """Check if action creates a loop."""
        recent = self.steps[-5:]
        same = [s for s in recent if s.get("action_type") == action.get("action_type") and
                s.get("target") == action.get("target")]
        return len(same) >= 3

    def finalize(self) -> Dict[str, Any]:
        """Get final metrics."""
        duration = (self.end_time - self.start_time).total_seconds() if self.start_time and self.end_time else 0

        return {
            "task_metrics": {
                "steps_to_completion": len(self.steps),
                "duration_seconds": duration,
                "pages_visited": len(self.pages),
            },
            "navigation_metrics": {
                "loops": self.loops,
                "errors": self.errors,
                "retries": self.retries,
            },
            "efficiency_metrics": {
                "actual_steps": len(self.steps),
                "efficiency": min(1.0, 20 / max(len(self.steps), 1)),
            },
        }


class BehavioralModel:
    """
    Adds human-like behavioral noise to agent decisions.
    """

    PERSONAS = {
        "curious_beginner": {
            "min_pause": 2.0,
            "max_pause": 5.0,
            "exploration_prob": 0.25,
            "mistake_prob": 0.10,
            "reading_speed": "slow",
        },
        "impatient_shopper": {
            "min_pause": 0.5,
            "max_pause": 1.5,
            "exploration_prob": 0.10,
            "mistake_prob": 0.15,
            "reading_speed": "fast",
        },
        "careful_researcher": {
            "min_pause": 4.0,
            "max_pause": 8.0,
            "exploration_prob": 0.40,
            "mistake_prob": 0.05,
            "reading_speed": "slow",
        },
    }

    def __init__(self, persona: str = "curious_beginner"):
        self.persona = self.PERSONAS.get(persona, self.PERSONAS["curious_beginner"])

    def should_explore(self) -> bool:
        """Determine if the agent should explore instead of goal-directed."""
        return random.random() < self.persona["exploration_prob"]

    def choose_exploration(self, page_state: ProcessedPageState) -> Dict[str, Any]:
        """Choose an exploratory action."""
        options = [
            {"action_type": "scroll", "value": "down", "reasoning": "Reading more content"},
            {"action_type": "hover", "target": "element", "reasoning": "Examining element"},
            {"action_type": "wait", "value": "2", "reasoning": "Reading content"},
        ]

        # Try to find clickable elements for exploration
        if page_state.primary_actions:
            action = page_state.primary_actions[0]
            options.append({
                "action_type": "click",
                "target": action.get("label", ""),
                "reasoning": f"Exploring: {action.get('label', '')}",
            })

        action = random.choice(options)
        action["mode"] = "exploratory"
        return action

    def calculate_pause(self, action: Dict[str, Any], page_state: ProcessedPageState) -> float:
        """Calculate human-like pause before action."""
        base = random.uniform(self.persona["min_pause"], self.persona["max_pause"])

        # Adjustments
        if action.get("action_type") == "submit":
            base *= 1.5

        # Adjust based on reading speed
        if self.persona["reading_speed"] == "slow":
            base *= 1.3

        if action.get("mode") == "exploratory":
            base *= 1.2

        return base

    def add_micro_actions(self, action: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Add realistic secondary actions."""
        actions = []

        # 30% chance: scroll to element before clicking
        if action.get("action_type") == "click" and random.random() < 0.3:
            actions.append({"action_type": "scroll", "value": "down", "reasoning": "Locating element"})

        # 20% chance: hover before clicking
        if action.get("action_type") == "click" and random.random() < 0.2:
            actions.append({"action_type": "hover", "target": action.get("target"), "reasoning": "Examining element"})

        actions.append(action)
        return actions


class SimulationEngine:
    """
    Core simulation engine that runs the observe → decide → act → record loop.

    Phase 2 Enhanced with:
    - PageStateProcessor for DOM compression
    - ActionValidator for safety checks
    - InsightsGenerator for UX reports
    - EnhancedLLMClient for intelligent decisions
    """

    def __init__(
        self,
        job_id: UUID,
        session_id: UUID,
        db: AsyncSession,
    ):
        self.job_id = job_id
        self.session_id = session_id
        self.db = db
        self.browser: Optional[BrowserManager] = None
        self.llm_client: Optional[EnhancedLLMClient] = None
        self.memory = RecentSteps(capacity=10)
        self.metrics = MetricsCollector()
        self.behavioral_model: Optional[BehavioralModel] = None

        # Phase 2 components
        self.page_processor = PageStateProcessor()
        self.action_validator: Optional[ActionValidator] = None
        self.retry_handler = RetryHandler()
        self.insights_generator = InsightsGenerator()

    async def run(
        self,
        url: str,
        persona: str = "curious_beginner",
        task_template: str = "explore_and_signup",
        max_steps: int = 50,
        max_duration: int = 900,
    ) -> Dict[str, Any]:
        """
        Run the simulation with Phase 2 enhancements.

        Args:
            url: Target URL to analyze
            persona: Persona type for synthetic user
            task_template: Task to perform
            max_steps: Maximum number of steps
            max_duration: Maximum duration in seconds

        Returns:
            Dict with logs, metrics, summary, and UX report
        """
        logger.info(f"Starting simulation for job {self.job_id}")
        logger.info(f"URL: {url}, Persona: {persona}, Max steps: {max_steps}")

        # Initialize components
        self.behavioral_model = BehavioralModel(persona)
        self.action_validator = ActionValidator(
            max_loop_count=3,
            target_domain=url.split("//")[-1].split("/")[0] if "//" in url else url.split("/")[0],
        )

        # Initialize LLM client
        self.llm_client = EnhancedLLMClient()
        await self.llm_client.initialize()

        self.metrics.start_time = datetime.utcnow()
        logs = []

        try:
            # Initialize browser
            self.browser = BrowserManager()
            await self.browser.launch()

            # Navigate to initial URL
            await self.browser.navigate_to(url)

            # Main simulation loop
            for step in range(max_steps):
                # Check timeout
                elapsed = (datetime.utcnow() - self.metrics.start_time).total_seconds()
                if elapsed > max_duration:
                    logger.info(f"Timeout reached after {elapsed:.0f} seconds")
                    break

                logger.info(f"Step {step + 1}/{max_steps}")

                # 1. OBSERVE - Capture raw page state
                raw_state = await self.browser.capture_state()

                # 2. PROCESS - Compress page state for LLM
                processed_state = self.page_processor.process(raw_state)
                page_dict = self.page_processor.to_dict(processed_state)

                # 3. DECIDE - Get next action from LLM or behavioral model
                if self.behavioral_model.should_explore():
                    action = self.behavioral_model.choose_exploration(processed_state)
                else:
                    # Use Enhanced LLM for goal-directed decision
                    action = await self.llm_client.decide(
                        page_state=page_dict,
                        task=task_template,
                        persona=persona,
                        memory=self.memory.recent(5),
                    )

                # Add behavioral noise
                action = self.behavioral_model.add_micro_actions(action)
                pause = self.behavioral_model.calculate_pause(action, processed_state)

                # Wait (simulate human pause)
                await asyncio.sleep(pause)

                # 4. VALIDATE - Check action safety
                validation = self.action_validator.validate(
                    action=action,
                    page_state=processed_state,
                    memory=self.memory.recent(10),
                )

                if not validation.valid:
                    logger.warning(f"Action validation failed: {validation.reason}")
                    if validation.corrected_action:
                        action = validation.corrected_action
                    else:
                        continue

                # 5. EXECUTE - Perform action(s)
                for act in (action if isinstance(action, list) else [action]):
                    start_time = time.time()
                    result = await self.browser.execute_action(act)
                    duration_ms = int((time.time() - start_time) * 1000)

                    # Handle retry on failure
                    if not result.get("success"):
                        retry_count = 0
                        while self.retry_handler.should_retry(act, result, retry_count):
                            retry_action = self.retry_handler.get_retry_action(
                                act,
                                result.get("error", ""),
                                processed_state,
                            )
                            result = await self.browser.execute_action(retry_action)
                            retry_count += 1
                            if result.get("success"):
                                break

                    # 6. RECORD - Log the step
                    step_record = await self._record_step(
                        step_number=step + 1,
                        page_url=raw_state.get("url", ""),
                        page_title=raw_state.get("title", ""),
                        action=act,
                        pause=pause,
                        result=result,
                        duration_ms=duration_ms,
                        page_state=raw_state,
                    )
                    logs.append(step_record)

                    # Update memory and metrics
                    self.memory.append({"action": act, "result": result, "step": step + 1})
                    self.metrics.update(act, result)

                    # Check for completion
                    if self._is_task_completed(raw_state, act, result):
                        logger.info("Task completed!")
                        break

                    # Check if stuck
                    if self._is_stuck():
                        logger.info("Stuck detected - ending simulation")
                        break

            self.metrics.end_time = datetime.utcnow()

        except Exception as e:
            logger.error(f"Simulation error: {str(e)}")
            raise

        finally:
            # Cleanup
            if self.browser:
                await self.browser.close()

        # 7. ANALYZE - Generate UX insights
        metrics = self.metrics.finalize()
        ux_report = self.insights_generator.generate(
            session_logs=logs,
            metrics=metrics,
            task=task_template,
            llm_client=self.llm_client,
        )

        # Save UX report to database
        await self._save_ux_report(ux_report)

        return {
            "logs": logs,
            "metrics": metrics,
            "outcome": ux_report.outcome,
            "summary": ux_report.summary,
            "friction_points": [
                {
                    "step_number": fp.step_number,
                    "description": fp.description,
                    "severity": fp.severity,
                    "element": fp.element,
                    "recommendation": fp.recommendation,
                }
                for fp in ux_report.friction_points
            ],
            "positive_observations": ux_report.positive_observations,
            "recommendations": [
                {
                    "priority": rec.priority,
                    "category": rec.category,
                    "suggestion": rec.suggestion,
                }
                for rec in ux_report.recommendations
            ],
        }

    async def _record_step(
        self,
        step_number: int,
        page_url: str,
        page_title: str,
        action: Dict[str, Any],
        pause: float,
        result: Dict[str, Any],
        duration_ms: int,
        page_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Record an interaction step to database."""
        # Map action type string to enum
        action_type_map = {
            "click": ActionType.CLICK,
            "type": ActionType.TYPE,
            "scroll": ActionType.SCROLL,
            "navigate": ActionType.NAVIGATE,
            "hover": ActionType.HOVER,
            "wait": ActionType.WAIT,
        }

        action_type = action_type_map.get(
            action.get("action_type", "click"),
            ActionType.CLICK
        )

        mode = ActionMode.EXPLORATORY if action.get("mode") == "exploratory" else ActionMode.GOAL_DIRECTED

        # Create database record
        step = InteractionStep(
            id=uuid.uuid4(),
            session_id=self.session_id,
            job_id=self.job_id,
            step_number=step_number,
            timestamp=datetime.utcnow(),
            page_url=page_url,
            page_title=page_title,
            action_type=action_type,
            action_target=action.get("target", ""),
            action_value=action.get("value"),
            action_mode=mode,
            agent_reasoning=action.get("reasoning", ""),
            pause_before_action=pause,
            success=result.get("success", True),
            error_message=result.get("error"),
            duration_ms=duration_ms,
            page_state_snapshot=page_state,
        )

        self.db.add(step)
        await self.db.commit()

        return {
            "step_number": step_number,
            "action": action,
            "result": result,
            "pause": pause,
        }

    async def _save_ux_report(self, report):
        """Save UX report to database."""
        report_obj = UXInsightReport(
            job_id=self.job_id,
            summary=report.summary,
            friction_points=[
                {
                    "step_number": fp.step_number,
                    "description": fp.description,
                    "severity": fp.severity,
                    "element": fp.element,
                    "recommendation": fp.recommendation,
                }
                for fp in report.friction_points
            ],
            positive_observations=report.positive_observations,
            recommendations=[
                {
                    "priority": rec.priority,
                    "category": rec.category,
                    "suggestion": rec.suggestion,
                }
                for rec in report.recommendations
            ],
        )
        self.db.add(report_obj)
        await self.db.commit()

    def _is_task_completed(
        self,
        page_state: Dict[str, Any],
        action: Dict[str, Any],
        result: Dict[str, Any],
    ) -> bool:
        """Check if task is completed."""
        url = page_state.get("url", "").lower()
        title = page_state.get("title", "").lower()

        completion_indicators = [
            "welcome", "dashboard", "success", "confirmed",
            "complete", "profile", "account created",
        ]

        for indicator in completion_indicators:
            if indicator in url or indicator in title:
                return True

        return False

    def _is_stuck(self) -> bool:
        """Detect if simulation is stuck in a loop."""
        recent = self.memory.recent(5)
        if len(recent) < 3:
            return False

        # Check for repeated actions
        targets = [s.get("action", {}).get("target") for s in recent]
        if len(set(targets)) == 1 and len(targets) >= 3:
            return True

        # Check for too many errors
        if self.metrics.errors >= 5:
            return True

        return False
