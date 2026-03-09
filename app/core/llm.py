"""
LLM client for AI-powered decision making.
"""

import json
import logging
from typing import Dict, Any, Optional, List

from app.config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Client for interacting with LLM APIs (OpenAI/Claude).
    """

    def __init__(
        self,
        provider: str = "openai",
        model: str = None,
        temperature: float = None,
        max_tokens: int = None,
    ):
        self.provider = provider
        self.model = model or settings.OPENAI_MODEL
        self.temperature = temperature or settings.OPENAI_TEMPERATURE
        self.max_tokens = max_tokens or settings.OPENAI_MAX_TOKENS
        self.client = None

    async def initialize(self):
        """Initialize the LLM client."""

        if self.provider == "openai" and settings.OPENAI_API_KEY:
            import openai
            openai.api_key = settings.OPENAI_API_KEY
            self.client = openai

        elif self.provider == "anthropic" and settings.ANTHROPIC_API_KEY:
            import anthropic
            self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

        elif self.provider == "groq" and settings.GROQ_API_KEY:
            from openai import AsyncOpenAI

            self.client = AsyncOpenAI(
                api_key=settings.GROQ_API_KEY,
                base_url="https://api.groq.com/openai/v1",
            )

            self.model = settings.GROQ_MODEL

        elif self.provider == "openrouter" and settings.OPENROUTER_API_KEY:
            from openai import AsyncOpenAI

            self.client = AsyncOpenAI(
                api_key=settings.OPENROUTER_API_KEY,
                base_url="https://openrouter.ai/api/v1",
                default_headers={
                    "HTTP-Referer": "http://localhost",
                    "X-Title": "Product Intelligence Platform",
                },
            )

            self.model = settings.OPENROUTER_MODEL

        logger.info(f"LLM provider initialized: {self.provider}")

    async def complete(
        self,
        prompt: str,
        system_prompt: str = None,
        temperature: float = None,
        max_tokens: int = None,
    ) -> Dict[str, Any]:
        """
        Get completion from LLM.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Override default temperature
            max_tokens: Override default max tokens

        Returns:
            Dict with response text and metadata
        """
        if not self.client:
            await self.initialize()

        temp = temperature or self.temperature
        tokens = max_tokens or self.max_tokens

        try:
            if self.provider == "openai" and self.client:
                response = await self.client.ChatCompletion.acreate(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt or self._default_system_prompt()},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=temp,
                    max_tokens=tokens,
                )

                return {
                    "text": response.choices[0].message.content,
                    "model": response.model,
                    "usage": {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens,
                    },
                }

            elif self.provider == "anthropic" and self.client:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=tokens,
                    temperature=temp,
                    system=system_prompt or self._default_system_prompt(),
                    messages=[{"role": "user", "content": prompt}],
                )

                return {
                    "text": response.content[0].text,
                    "model": response.model,
                    "usage": {
                        "input_tokens": response.usage.input_tokens,
                        "output_tokens": response.usage.output_tokens,
                    },
                }
            elif self.provider in ["groq", "openrouter"] and self.client:

                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt or self._default_system_prompt()},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=temp,
                    max_tokens=tokens,
                )

                return {
                    "text": response.choices[0].message.content,
                    "model": response.model,
                    "usage": response.usage.model_dump() if response.usage else {},
                }
            else:
                # Fallback - return a mock response for testing
                logger.warning("No LLM client available, returning mock response")
                return self._mock_response(prompt)

        except Exception as e:
            logger.error(f"LLM request failed: {str(e)}")
            return {"text": "", "error": str(e)}

    def _default_system_prompt(self) -> str:
        """Get default system prompt for the agent."""
        return """You are simulating a realistic first-time user exploring a website.

TASK: Explore and attempt signup
PERSONA: Curious beginner - careful, reads content, explores features

You are analyzing a web page and need to decide what action to take next.
Consider:
- Natural exploration vs. goal pursuit
- What catches attention
- What might be confusing

Respond in JSON format:
{
  "action": "click|type|scroll|wait",
  "target": "element description or selector",
  "value": "text to type (if applicable)",
  "reasoning": "why this makes sense for a real user"
}"""

    def _mock_response(self, prompt: str) -> Dict[str, Any]:
        """Generate a mock response for testing without API keys."""
        # Simple rule-based response
        if "signup" in prompt.lower() or "sign up" in prompt.lower():
            return {
                "text": json.dumps({
                    "action": "scroll",
                    "value": "down",
                    "reasoning": "Looking for signup option",
                }),
                "model": "mock",
                "usage": {"total_tokens": 100},
            }

        return {
            "text": json.dumps({
                "action": "click",
                "target": "button",
                "reasoning": "Exploring page",
            }),
            "model": "mock",
            "usage": {"total_tokens": 50},
        }

    async def analyze_session(
        self,
        session_logs: List[Dict[str, Any]],
        metrics: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Analyze session logs to generate UX insights.

        Args:
            session_logs: List of interaction steps
            metrics: Quantitative metrics

        Returns:
            Dict with analysis results
        """
        prompt = self._create_analysis_prompt(session_logs, metrics)
        response = await self.complete(prompt)

        try:
            # Parse JSON response
            return json.loads(response.get("text", "{}"))
        except json.JSONDecodeError:
            logger.error("Failed to parse LLM response as JSON")
            return {"error": "Failed to parse analysis"}

    def _create_analysis_prompt(
        self,
        session_logs: List[Dict[str, Any]],
        metrics: Dict[str, Any],
    ) -> str:
        """Create prompt for session analysis."""
        # Format logs for analysis
        log_summary = []
        for log in session_logs[-20:]:  # Last 20 steps
            step = log.get("step_number", 0)
            action = log.get("action", {})
            result = log.get("result", {})
            log_summary.append(
                f"Step {step}: {action.get('action_type')} on {action.get('target')} - "
                f"{'Success' if result.get('success') else 'Failed'}"
            )

        prompt = f"""
You are a UX expert analyzing a recorded user session.

TASK: Explore and attempt signup

INTERACTION LOG:
{chr(10).join(log_summary)}

QUANTITATIVE METRICS:
{json.dumps(metrics, indent=2)}

Analyze this session:

1. SUMMARY: What happened overall (2-3 sentences)

2. FRICTION POINTS: Where user struggled
   For each:
   - Step number
   - What went wrong
   - Why it's problematic
   - Severity (low/medium/high)
   - Specific recommendation

3. POSITIVE OBSERVATIONS: What worked well

4. RECOMMENDATIONS: Prioritized improvements

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
