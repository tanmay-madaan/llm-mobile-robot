import pytest
from unittest.mock import MagicMock

from llm_robot_planner.cli import run_interactive_planner
from llm_robot_planner.validator import PlanValidationError

def test_cli_exit_immediately():
    inputs = ["exit"]
    outputs = []

    ret = run_interactive_planner(
        input_func=lambda prompt: inputs.pop(0),
        print_func=outputs.append,
        llm_client=MagicMock(),
    )

    assert ret == 0
    assert any("Exiting task planner" in line for line in outputs)

def test_cli_plan_rejected_by_user():
    inputs = [
        "Go to red box then return home",  # task prompt
        "n",                               # user confirmation (reject)
    ]
    outputs = []

    mock_llm_client = MagicMock()
    mock_llm_client.generate_plan.return_value = [
        {"action": "navigate_to_target", "target": "red_box"},
        {"action": "navigate_to_target", "target": "home"},
    ]
    mock_executor = MagicMock()

    ret = run_interactive_planner(
        input_func=lambda prompt: inputs.pop(0),
        print_func=outputs.append,
        llm_client=mock_llm_client,
        executor=mock_executor,
    )

    assert ret == 0
    assert any("Plan rejected by user" in line for line in outputs)
    assert not mock_executor.execute_plan.called

def test_cli_plan_approved_and_executed_success():
    inputs = [
        "Go to the green box",  # task prompt
        "y",                    # user confirmation (approve)
    ]
    outputs = []

    mock_llm_client = MagicMock()
    mock_plan = [{"action": "navigate_to_target", "target": "green_box"}]
    mock_llm_client.generate_plan.return_value = mock_plan

    mock_executor = MagicMock()
    mock_executor.execute_plan.return_value = True

    ret = run_interactive_planner(
        input_func=lambda prompt: inputs.pop(0),
        print_func=outputs.append,
        llm_client=mock_llm_client,
        executor=mock_executor,
    )

    assert ret == 0
    assert mock_executor.execute_plan.called
    mock_executor.execute_plan.assert_called_once_with(mock_plan)
    assert any("All plan steps executed successfully" in line for line in outputs)

def test_cli_plan_approved_and_executed_failure():
    inputs = [
        "Go to blue cylinder",
        "yes",
    ]
    outputs = []

    mock_llm_client = MagicMock()
    mock_plan = [{"action": "navigate_to_target", "target": "blue_cylinder"}]
    mock_llm_client.generate_plan.return_value = mock_plan

    mock_executor = MagicMock()
    mock_executor.execute_plan.return_value = False

    ret = run_interactive_planner(
        input_func=lambda prompt: inputs.pop(0),
        print_func=outputs.append,
        llm_client=mock_llm_client,
        executor=mock_executor,
    )

    assert ret == 1
    assert any("Plan execution halted" in line for line in outputs)

def test_cli_llm_error_handling():
    inputs = ["invalid request"]
    outputs = []

    mock_llm_client = MagicMock()
    mock_llm_client.generate_plan.side_effect = PlanValidationError("Unknown target requested")
    mock_executor = MagicMock()

    ret = run_interactive_planner(
        input_func=lambda prompt: inputs.pop(0),
        print_func=outputs.append,
        llm_client=mock_llm_client,
        executor=mock_executor,
    )

    assert ret == 1
    assert any("Plan generation/validation failed" in line for line in outputs)
    assert not mock_executor.execute_plan.called
