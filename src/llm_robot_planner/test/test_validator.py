import pytest
from llm_robot_planner.validator import validate_plan, PlanValidationError

VALID_TARGETS = {"home", "red_box", "blue_cylinder", "green_box"}

def test_valid_dict_plan():
    plan = {
        "plan": [
            {"action": "navigate_to_target", "target": "home"},
            {"action": "navigate_to_target", "target": "blue_cylinder"},
        ]
    }
    result = validate_plan(plan, valid_targets=VALID_TARGETS)
    assert len(result) == 2
    assert result[0]["target"] == "home"
    assert result[1]["target"] == "blue_cylinder"

def test_valid_list_plan():
    plan = [
        {"action": "navigate_to_target", "target": "green_box"}
    ]
    result = validate_plan(plan, valid_targets=VALID_TARGETS)
    assert len(result) == 1
    assert result[0]["target"] == "green_box"

def test_empty_plan_dict():
    with pytest.raises(PlanValidationError, match="Plan is empty"):
        validate_plan({"plan": []}, valid_targets=VALID_TARGETS)

def test_empty_plan_list():
    with pytest.raises(PlanValidationError, match="Plan is empty"):
        validate_plan([], valid_targets=VALID_TARGETS)

def test_malformed_plan_type():
    with pytest.raises(PlanValidationError, match="Malformed plan"):
        validate_plan("navigate to red box", valid_targets=VALID_TARGETS)

def test_malformed_plan_missing_plan_key():
    with pytest.raises(PlanValidationError, match="must contain a 'plan' key"):
        validate_plan({"actions": [{"action": "navigate_to_target", "target": "home"}]}, valid_targets=VALID_TARGETS)

def test_unsupported_action():
    plan = [
        {"action": "pick_up_object", "target": "red_box"}
    ]
    with pytest.raises(PlanValidationError, match="unsupported action"):
        validate_plan(plan, valid_targets=VALID_TARGETS)

def test_unknown_target():
    plan = [
        {"action": "navigate_to_target", "target": "kitchen_table"}
    ]
    with pytest.raises(PlanValidationError, match="unknown target"):
        validate_plan(plan, valid_targets=VALID_TARGETS)

def test_missing_target_key():
    plan = [
        {"action": "navigate_to_target"}
    ]
    with pytest.raises(PlanValidationError, match="requires a 'target' key"):
        validate_plan(plan, valid_targets=VALID_TARGETS)

def test_unexpected_keys_rejected():
    plan = [
        {"action": "navigate_to_target", "target": "home", "velocity": 1.5}
    ]
    with pytest.raises(PlanValidationError, match="unexpected keys"):
        validate_plan(plan, valid_targets=VALID_TARGETS)
