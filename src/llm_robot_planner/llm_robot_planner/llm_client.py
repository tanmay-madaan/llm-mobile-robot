import os
import json
from google import genai
from google.genai import types
from google.genai.errors import APIError

from .validator import load_valid_targets, validate_plan, PlanValidationError

DEFAULT_MODEL = "gemini-3.8-flash"

SYSTEM_PROMPT_TEMPLATE = """You are an autonomous robot task planning assistant.
Your job is to convert natural language navigation commands into a structured sequence of actions.
The robot operates in a fixed environment and can only execute the 'navigate_to_target' action.

Valid targets:
{valid_targets}

Rules:
1. ONLY use the action 'navigate_to_target'.
2. ONLY use targets from the valid targets list.
3. Return a JSON object strictly matching this schema:
{{
  "plan": [
    {{"action": "navigate_to_target", "target": "<target_name>"}}
  ]
}}
4. If the user request cannot be fulfilled using the valid targets, return an empty plan: {{"plan": []}}.
"""

class LLMPlannerClient:
    """Client for generating validated robot plans using Gemini."""
    def __init__(self, api_key: str = None, model: str = DEFAULT_MODEL, client: genai.Client = None):
        self.model = model
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")

        if client is not None:
            self.client = client
        else:
            if not self.api_key:
                raise ValueError("GEMINI_API_KEY environment variable is not set and no API key was provided")
            self.client = genai.Client(api_key=self.api_key)

    def generate_plan(self, prompt: str, targets: set = None) -> list:
        """
        Send a natural language prompt to Gemini and return a validated plan.
        Raises PlanValidationError if validation fails or API errors occur.
        """
        if not prompt or not prompt.strip():
            raise PlanValidationError("Prompt cannot be empty")

        if targets is None:
            targets = load_valid_targets()

        system_instruction = SYSTEM_PROMPT_TEMPLATE.format(
            valid_targets=", ".join(sorted(list(targets)))
        )

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
        )

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            )
        except APIError as e:
            raise PlanValidationError(f"Gemini API error: {e}") from e
        except Exception as e:
            raise PlanValidationError(f"Unexpected error communicating with Gemini: {e}") from e

        response_text = getattr(response, "text", None)
        if not response_text:
            raise PlanValidationError("Gemini returned an empty response")

        try:
            plan_json = json.loads(response_text)
        except json.JSONDecodeError as e:
            raise PlanValidationError(f"Gemini returned invalid JSON: {e}") from e

        # Validate against the target registry and schema
        return validate_plan(plan_json, valid_targets=targets)
