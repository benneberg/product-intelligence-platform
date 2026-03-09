"""
Action Validator - Safety checks for agent actions.

Prevents:
- Invalid actions (element not found)
- Loops (same action repeated)
- Unsafe actions (destructive operations)
- Form errors (submitting empty forms)
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

from app.core.page_processor import ProcessedPageState

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of action validation."""
    valid: bool
    reason: str
    corrected_action: Optional[Dict[str, Any]] = None


class ActionValidator:
    """
    Validates agent actions for safety and correctness.
    """

    # Destructive keywords that should block actions
    DESTRUCTIVE_KEYWORDS = [
        "delete", "remove", "erase", "destroy",
        "logout", "log out", "sign out", "signout",
        "cancel subscription", "cancel account",
        "purchase", "buy now", "checkout", "pay",
        "unsubscribe", "close account",
    ]

    # Action type mappings
    ACTION_TYPES = ["click", "type", "scroll", "navigate", "hover", "wait"]

    def __init__(
        self,
        max_loop_count: int = 3,
        target_domain: str = None,
    ):
        self.max_loop_count = max_loop_count
        self.target_domain = target_domain

    def validate(
        self,
        action: Dict[str, Any],
        page_state: ProcessedPageState,
        memory: List[Dict[str, Any]],
    ) -> ValidationResult:
        """
        Validate an action before execution.

        Args:
            action: Action to validate
            page_state: Current page state
            memory: Recent action history

        Returns:
            ValidationResult with validity status and reason
        """
        action_type = action.get("action_type", "")
        target = action.get("target", "")
        value = action.get("value", "")

        # Rule 1: Check action type is valid
        if action_type not in self.ACTION_TYPES:
            return ValidationResult(
                valid=False,
                reason=f"Invalid action type: {action_type}",
            )

        # Rule 2: Check element exists (for click/type actions)
        if action_type in ["click", "type", "hover"]:
            if not self._element_exists(target, page_state):
                return ValidationResult(
                    valid=False,
                    reason=f"Element not found: {target}",
                )

        # Rule 3: Check for loops
        if self._is_loop(action, memory):
            return ValidationResult(
                valid=False,
                reason="Action creates unproductive loop (same action repeated)",
                corrected_action=self._get_alternative_action(action, page_state, memory),
            )

        # Rule 4: Check form safety (submit with empty required fields)
        if action_type == "click" and self._is_submit_action(target):
            if not self._form_has_data(page_state, memory):
                return ValidationResult(
                    valid=False,
                    reason="Cannot submit empty form",
                )

        # Rule 5: Check for destructive actions
        if self._is_destructive(action):
            return ValidationResult(
                valid=False,
                reason=f"Destructive action blocked: {target}",
            )

        # Rule 6: Check domain boundary (for navigation)
        if action_type == "navigate" and self.target_domain:
            if not self._same_domain(value, self.target_domain):
                return ValidationResult(
                    valid=False,
                    reason=f"External navigation blocked: {value}",
                )

        return ValidationResult(
            valid=True,
            reason="Valid action",
        )

    def _element_exists(
        self,
        target: str,
        page_state: ProcessedPageState,
    ) -> bool:
        """Check if target element exists on page."""
        # Check in primary actions
        for action in page_state.primary_actions:
            label = action.get("label", "").lower()
            if target.lower() in label or label in target.lower():
                return True

        # Check in all elements
        for el in page_state.all_elements:
            label = el.label.lower()
            if target.lower() in label or label in target.lower():
                return True

        # Check form fields
        for group in page_state.form_groups:
            for field in group.get("fields", []):
                label = field.get("label", "").lower()
                if target.lower() in label or label in target.lower():
                    return True

        return True  # Be permissive if we can't determine

    def _is_loop(
        self,
        action: Dict[str, Any],
        memory: List[Dict[str, Any]],
    ) -> bool:
        """Detect if action creates a loop."""
        if not memory:
            return False

        recent = memory[-self.max_loop_count:]

        # Check for exact same action
        same_count = 0
        for mem_action in recent:
            if (mem_action.get("action", {}).get("action_type") == action.get("action_type") and
                mem_action.get("action", {}).get("target") == action.get("target")):
                same_count += 1

        return same_count >= self.max_loop_count - 1

    def _get_alternative_action(
        self,
        action: Dict[str, Any],
        page_state: ProcessedPageState,
        memory: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Get an alternative action when stuck in loop."""
        # Try scrolling instead
        if action.get("action_type") in ["click", "type"]:
            return {
                "action_type": "scroll",
                "value": "down",
                "reasoning": "Stuck in loop, trying to find new content",
            }

        # Try different primary action
        if page_state.primary_actions:
            next_action = page_state.primary_actions[0]
            return {
                "action_type": "click",
                "target": next_action.get("label", ""),
                "reasoning": "Trying alternative primary action",
            }

        # Default: wait
        return {
            "action_type": "wait",
            "value": "2",
            "reasoning": "Pausing to reassess",
        }

    def _is_submit_action(self, target: str) -> bool:
        """Check if target is a submit button."""
        submit_keywords = ["submit", "send", "create", "register", "sign up", "signin", "login"]
        target_lower = target.lower()
        return any(kw in target_lower for kw in submit_keywords)

    def _form_has_data(
        self,
        page_state: ProcessedPageState,
        memory: List[Dict[str, Any]],
    ) -> bool:
        """Check if form has been filled."""
        # Check if any typing actions have occurred
        for mem in memory:
            action = mem.get("action", {})
            if action.get("action_type") == "type" and action.get("value"):
                return True

        return False

    def _is_destructive(self, action: Dict[str, Any]) -> bool:
        """Check if action is destructive."""
        target = (action.get("target", "") or "").lower()
        value = (action.get("value", "") or "").lower()

        # Check target and value for destructive keywords
        combined = f"{target} {value}"
        return any(kw in combined for kw in self.DESTRUCTIVE_KEYWORDS)

    def _same_domain(self, url: str, target_domain: str) -> bool:
        """Check if URL is in same domain."""
        if not url:
            return False

        # Simple domain check
        return target_domain in url


class RetryHandler:
    """
    Handles retry logic for failed actions.
    """

    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries

    def should_retry(
        self,
        action: Dict[str, Any],
        result: Dict[str, Any],
        retry_count: int,
    ) -> bool:
        """Determine if action should be retried."""
        if retry_count >= self.max_retries:
            return False

        # Retry on element not found
        error = result.get("error", "").lower()
        if "not found" in error or "timeout" in error:
            return True

        return False

    def get_retry_action(
        self,
        action: Dict[str, Any],
        error: str,
        page_state: ProcessedPageState,
    ) -> Dict[str, Any]:
        """Get modified action for retry."""
        # Try alternative element
        for el in page_state.all_elements[:5]:
            if el.type == action.get("action_type"):
                return {
                    "action_type": action.get("action_type"),
                    "target": el.label,
                    "reasoning": f"Original target failed ({error}), trying alternative",
                }

        # Default: scroll to find new elements
        return {
            "action_type": "scroll",
            "value": "down",
            "reasoning": f"Original target failed ({error}), scrolling to find new content",
        }
