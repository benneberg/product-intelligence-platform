"""
LLM client for AI-powered decision making with enhanced prompts.
"""

import json
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class DecisionPrompt:
    """Structured prompt for agent decision making."""
    system_prompt: str
    user_prompt: str
    expected_schema: Dict[str, Any]


class PersonaConfig:
    """Persona configurations for synthetic users."""

    PERSONAS = {
        "curious_beginner": {
            "description": "A first-time user who is curious and careful. They read content before acting and explore features.",
            "behavior": "Reads text, hovers before clicking, explores secondary links, takes time to understand UI.",
            "goals": "Understand the product, find signup, create account.",
            "frustrations": "Hidden CTAs, unclear labels, complex forms.",
        },
        "impatient_shopper": {
            "description": "A user in a hurry who wants to complete tasks quickly with minimal interaction.",
            "behavior": "Clicks quickly, scans for CTAs, skips reading, abandons if too complex.",
            "goals": "Complete purchase or signup as fast as possible.",
            "frustrations": "Long forms, slow loading, popups blocking content.",
        },
        "careful_researcher": {
            "description": "A thorough user who compares options and reads everything before deciding.",
            "behavior": "Reads all content, compares options, checks pricing, reviews terms.",
            "goals": "Make informed decision, understand all options.",
            "frustrations": "Missing information, hidden costs, pressure tactics.",
        },
    }

    @classmethod
    def get_prompt(cls, persona_name: str) -> Dict[str, Any]:
        """Get persona configuration."""
        return cls.PERSONAS.get(persona_name, cls.PERSONAS["curious_beginner"])


class LLMPromptBuilder:
    """
    Builds prompts for LLM decision making.
    """

    # JSON schema for action decisions
    ACTION_SCHEMA = {
        "type": "object",
        "properties": {
            "action_type": {
                "type": "string",
                "enum": ["click", "type", "scroll", "navigate", "hover", "wait"],
                "description": "The type of action to perform",
            },
            "target": {
                "type": "string",
                "description": "The element identifier (text, selector, or description)",
            },
            "value": {
                "type": "string",
                "description": "Value to type (only for type action)",
            },
            "reasoning": {
                "type": "string",
                "description": "Why this action makes sense for the user",
            },
            "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "Confidence in this action (0-1)",
            },
        },
        "required": ["action_type", "target", "reasoning"],
    }

    def build_decision_prompt(
        self,
        page_state: Dict[str, Any],
        task: str,
        persona: str,
        memory: List[Dict[str, Any]],
        include_schema: bool = True,
    ) -> DecisionPrompt:
        """
        Build prompt for action decision.

        Args:
            page_state: Compressed page state
            task: Task to complete
            persona: Persona name
            memory: Recent action history
            include_schema: Include JSON schema in prompt

        Returns:
            DecisionPrompt with system and user prompts
        """
        # Get persona config
        persona_config = PersonaConfig.get_prompt(persona)

        # Build system prompt
        system_prompt = self._build_system_prompt(persona_config, task)

        # Build user prompt
        user_prompt = self._build_user_prompt(
            page_state=page_state,
            task=task,
            persona_config=persona_config,
            memory=memory,
        )

        # Build schema
        schema = self.ACTION_SCHEMA if include_schema else {}

        return DecisionPrompt(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            expected_schema=schema,
        )

    def _build_system_prompt(self, persona_config: Dict[str, Any], task: str) -> str:
        """Build system prompt with persona context."""
        return f"""You are simulating a realistic human user exploring a website.

## TASK
{task}

## YOUR PERSONA
{persona_config['description']}

## BEHAVIOR
{persona_config['behavior']}

## GOALS
{persona_config['goals']}

## FRUSTRATIONS
{persona_config['frustrations']}

## INSTRUCTIONS
1. Analyze the current page state carefully
2. Consider what a real human with this persona would do next
3. Choose actions that match the persona's behavior style
4. Think about what might confuse or frustrate this user type
5. Balance goal-directed actions with natural exploration

## OUTPUT FORMAT
Respond with a JSON object describing your next action.
"""

    def _build_user_prompt(
        self,
        page_state: Dict[str, Any],
        task: str,
        persona_config: Dict[str, Any],
        memory: List[Dict[str, Any]],
    ) -> str:
        """Build user prompt with page context."""
        lines = []

        # Page info
        lines.append(f"Current Page: {page_state.get('url', 'Unknown')}")
        lines.append(f"Title: {page_state.get('title', 'Unknown')}")
        lines.append("")

        # Primary actions (CTAs)
        primary_actions = page_state.get("primary_actions", [])
        if primary_actions:
            lines.append("## AVAILABLE ACTIONS (Primary CTAs)")
            for action in primary_actions[:5]:
                lines.append(f"- [{action.get('id', '')}] {action.get('type', 'button').upper()}: \"{action.get('label', '')}\"")
            lines.append("")

        # Form fields
        form_groups = page_state.get("form_groups", [])
        if form_groups:
            lines.append("## FORM FIELDS")
            for group in form_groups[:3]:
                lines.append(f"### {group.get('name', 'Form')}")
                for field in group.get("fields", [])[:5]:
                    req = "(required)" if field.get("required") else ""
                    lines.append(f"- {field.get('label', '')} {req}")
            lines.append("")

        # Navigation
        nav = page_state.get("navigation", {})
        if nav.get("primary"):
            lines.append("## NAVIGATION")
            for item in nav["primary"][:8]:
                lines.append(f"- {item}")
            lines.append("")

        # Key content
        key_text = page_state.get("key_text", "")
        if key_text:
            lines.append("## PAGE CONTENT")
            lines.append(key_text[:300])
            lines.append("")

        # Recent actions (memory)
        if memory:
            lines.append("## RECENT ACTIONS")
            for mem in memory[-5:]:
                action = mem.get("action", {})
                result = mem.get("result", {})
                status = "✓" if result.get("success") else "✗"
                lines.append(
                    f"- Step {mem.get('step', '?')}: {action.get('action_type', '?')} "
                    f"{action.get('target', '')} {status}"
                )
            lines.append("")

        # What to do
        lines.append("## DECISION")
        lines.append(f"Task: {task}")
        lines.append(f"Persona: {persona_config['description'][:50]}...")
        lines.append("")
        lines.append("What should the user do next? Consider:")
        lines.append("- What would accomplish the task?")
        lines.append("- What might confuse this user?")
        lines.append("- What is natural exploration vs. goal pursuit?")
        lines.append("")
        lines.append("Respond with JSON:")

        return "\n".join(lines)

    def build_analysis_prompt(
        self,
        session_logs: List[Dict[str, Any]],
        metrics: Dict[str, Any],
        task: str,
    ) -> str:
        """Build prompt for session analysis and UX report."""
        # Format logs
        log_lines = []
        for log in session_logs[-20:]:
            step = log.get("step_number", 0)
            action = log.get("action", {})
            result = log.get("result", {})
            reasoning = action.get("reasoning", "")

            status = "✓" if result.get("success") else "✗"
            log_lines.append(
                f"Step {step}: {action.get('action_type', '?')} "
                f"'{action.get('target', '')}' - {reasoning} {status}"
            )

        prompt = f"""You are a UX expert analyzing a recorded user session.

TASK: {task}

INTERACTION LOG:
{chr(10).join(log_lines)}

METRICS:
{json.dumps(metrics, indent=2)}

Analyze this session and provide:

1. SUMMARY (2-3 sentences): What happened overall?

2. FRICTION POINTS: Where did the user struggle?
   For each:
   - Step number
   - What went wrong
   - Why it's problematic
   - Severity (low/medium/high)
   - Recommendation

3. POSITIVE OBSERVATIONS: What worked well?

4. RECOMMENDATIONS: Prioritized improvements?

Format as JSON:
{{
  "summary": "...",
  "friction_points": [
    {{
      "step_number": 12,
      "description": "...",
      "severity": "medium",
      "element": "...",
      "recommendation": "..."
    }}
  ],
  "positive_observations": ["...", "..."],
  "recommendations": [
    {{"priority": "high", "category": "forms", "suggestion": "..."}}
  ]
}}
"""
        return prompt


class EnhancedLLMClient:
    """
    Enhanced LLM client with better prompts and retry logic.
    """

    def __init__(self, provider: str = "openai", model: str = None):
        self.provider = provider
        self.model = model or settings.OPENAI_MODEL
        self.prompt_builder = LLMPromptBuilder()
        self.client = None

    async def initialize(self):
        """Initialize the LLM client."""
        if self.provider == "openai" and settings.OPENAI_API_KEY:
            try:
                import openai
                openai.api_key = settings.OPENAI_API_KEY
                self.client = openai
            except ImportError:
                logger.warning("OpenAI package not installed")

    async def decide(
        self,
        page_state: Dict[str, Any],
        task: str,
        persona: str,
        memory: List[Dict[str, Any]],
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """
        Get next action decision from LLM.

        Args:
            page_state: Compressed page state
            task: Task to complete
            persona: Persona name
            memory: Recent action history
            max_retries: Max retry attempts

        Returns:
            Action decision dict
        """
        if not self.client:
            await self.initialize()

        # Build prompt
        prompt = self.prompt_builder.build_decision_prompt(
            page_state=page_state,
            task=task,
            persona=persona,
            memory=memory,
        )

        # Try to get valid response
        for attempt in range(max_retries):
            try:
                response = await self._make_request(
                    system=prompt.system_prompt,
                    user=prompt.user_prompt,
                )

                # Parse response
                decision = self._parse_decision(response)
                if decision:
                    return decision

            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")

        # Fallback
        return self._fallback_decision(page_state)

    async def _make_request(self, system: str, user: str) -> str:
        """Make request to LLM."""
        if not self.client:
            return self._mock_response(user)

        try:
            if self.provider == "openai":
                response = await self.client.ChatCompletion.acreate(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    temperature=0.7,
                    max_tokens=500,
                )
                return response.choices[0].message.content

        except Exception as e:
            logger.error(f"LLM request failed: {str(e)}")
            return self._mock_response(user)

    def _parse_decision(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse LLM response into decision dict."""
        try:
            # Try to extract JSON from response
            # Handle potential markdown code blocks
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            if response.startswith("```"):
                response = response[3:]

            data = json.loads(response.strip())

            return {
                "action_type": data.get("action_type", "click"),
                "target": data.get("target", ""),
                "value": data.get("value", ""),
                "reasoning": data.get("reasoning", ""),
                "confidence": data.get("confidence", 0.5),
            }

        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM response as JSON")
            return None

    def _fallback_decision(self, page_state: Dict[str, Any]) -> Dict[str, Any]:
        """Generate fallback decision when LLM fails."""
        # Try to find a primary action
        primary_actions = page_state.get("primary_actions", [])
        if primary_actions:
            action = primary_actions[0]
            return {
                "action_type": "click",
                "target": action.get("label", ""),
                "reasoning": "Fallback: clicking primary action",
                "confidence": 0.3,
            }

        # Default to scrolling
        return {
            "action_type": "scroll",
            "value": "down",
            "reasoning": "Fallback: scrolling to find content",
            "confidence": 0.3,
        }

    def _mock_response(self, prompt: str) -> str:
        """Generate mock response for testing."""
        return json.dumps({
            "action_type": "scroll",
            "value": "down",
            "reasoning": "Mock: exploring page",
            "confidence": 0.5,
        })

    async def analyze_session(
        self,
        session_logs: List[Dict[str, Any]],
        metrics: Dict[str, Any],
        task: str,
    ) -> Dict[str, Any]:
        """Analyze session and generate UX report."""
        if not self.client:
            return {"error": "No LLM client available"}

        prompt = self.prompt_builder.build_analysis_prompt(
            session_logs=session_logs,
            metrics=metrics,
            task=task,
        )

        try:
            response = await self._make_request(
                system="You are a UX expert.",
                user=prompt,
            )
            return json.loads(response)
        except Exception as e:
            logger.error(f"Analysis failed: {str(e)}")
            return {"error": str(e)}
