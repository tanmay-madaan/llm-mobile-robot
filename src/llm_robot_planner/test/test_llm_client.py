import os
import json
import pytest
from unittest.mock import MagicMock
from google.genai.errors import APIError

from llm_robot_planner.llm_client import LLMPlannerClient
from llm_robot_planner.validator import PlanValidationError

TEST_TARGETS = {"home", "red_box", "blue_cylinder", "green_box"}

def test_missing_api_key_raises_error(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GEMINI_API_KEY environment variable is not set"):
        LLMPlannerClient()

def test_empty_prompt_raises_error():
    mock_genai_client = MagicMock()
    client = LLMPlannerClient(api_key="mock_key", client=mock_genai_client)
    with pytest.raises(PlanValidationError, match="Prompt cannot be empty"):
        client.generate_plan("")

def test_successful_plan_generation():
    mock_genai_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "plan": [
            {"action": "navigate_to_target", "target": "red_box"},
            {"action": "navigate_to_target", "target": "home"}
        ]
    })
    mock_genai_client.models.generate_content.return_value = mock_response

    client = LLMPlannerClient(api_key="mock_key", client=mock_genai_client)
    plan = client.generate_plan("Go to the red box then return home", targets=TEST_TARGETS)

    assert len(plan) == 2
    assert plan[0]["target"] == "red_box"
    assert plan[1]["target"] == "home"
    assert mock_genai_client.models.generate_content.called

def test_invalid_json_response_raises_error():
    mock_genai_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "This is not valid JSON"
    mock_genai_client.models.generate_content.return_value = mock_response

    client = LLMPlannerClient(api_key="mock_key", client=mock_genai_client)
    with pytest.raises(PlanValidationError, match="Gemini returned invalid JSON"):
        client.generate_plan("Go home", targets=TEST_TARGETS)

def test_empty_response_raises_error():
    mock_genai_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = None
    mock_genai_client.models.generate_content.return_value = mock_response

    client = LLMPlannerClient(api_key="mock_key", client=mock_genai_client)
    with pytest.raises(PlanValidationError, match="Gemini returned an empty response"):
        client.generate_plan("Go home", targets=TEST_TARGETS)

def test_unknown_target_in_llm_response_raises_error():
    mock_genai_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "plan": [
            {"action": "navigate_to_target", "target": "hallway"}
        ]
    })
    mock_genai_client.models.generate_content.return_value = mock_response

    client = LLMPlannerClient(api_key="mock_key", client=mock_genai_client)
    with pytest.raises(PlanValidationError, match="unknown target 'hallway'"):
        client.generate_plan("Go to the hallway", targets=TEST_TARGETS)

def test_unsupported_action_in_llm_response_raises_error():
    mock_genai_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "plan": [
            {"action": "pick_up_box", "target": "red_box"}
        ]
    })
    mock_genai_client.models.generate_content.return_value = mock_response

    client = LLMPlannerClient(api_key="mock_key", client=mock_genai_client)
    with pytest.raises(PlanValidationError, match="unsupported action 'pick_up_box'"):
        client.generate_plan("Pick up the red box", targets=TEST_TARGETS)

def test_api_error_handling():
    mock_genai_client = MagicMock()
    mock_genai_client.models.generate_content.side_effect = APIError(429, {"error": {"message": "Rate limit exceeded"}})

    client = LLMPlannerClient(api_key="mock_key", client=mock_genai_client)
    with pytest.raises(PlanValidationError, match="Gemini API error"):
        client.generate_plan("Go to blue cylinder", targets=TEST_TARGETS)
