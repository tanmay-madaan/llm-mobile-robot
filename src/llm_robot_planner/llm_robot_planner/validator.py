import os
import yaml
from ament_index_python.packages import get_package_share_directory, PackageNotFoundError

SUPPORTED_ACTIONS = {"navigate_to_target"}

def load_valid_targets(targets_file: str = None) -> set:
    """
    Load valid target names from targets.yaml.
    If no file is provided, attempts to load from llm_robot_skills package share or src.
    """
    if targets_file and os.path.exists(targets_file):
        path = targets_file
    else:
        try:
            share_dir = get_package_share_directory('llm_robot_skills')
            path = os.path.join(share_dir, 'config', 'targets.yaml')
        except PackageNotFoundError:
            # Fallback to source directory if workspace not built yet
            src_dir = os.path.expanduser('~/llm_robot_ws/src/llm_robot_skills/config/targets.yaml')
            if os.path.exists(src_dir):
                path = src_dir
            else:
                raise FileNotFoundError("Could not find targets.yaml in share or src directory")

    with open(path, 'r') as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict) or 'targets' not in data:
        raise ValueError("targets.yaml does not contain a 'targets' section")

    return set(data['targets'].keys())

class PlanValidationError(Exception):
    """Raised when a plan fails schema or target validation."""
    pass

def validate_plan(plan_data, valid_targets: set = None) -> list:
    """
    Validate a task plan.

    Expected format:
    {
        "plan": [
            {"action": "navigate_to_target", "target": "<target_name>"},
            ...
        ]
    }
    or directly a list of action dictionaries:
    [
        {"action": "navigate_to_target", "target": "<target_name>"},
        ...
    ]

    Returns the validated list of action dictionaries.
    Raises PlanValidationError if invalid.
    """
    if valid_targets is None:
        valid_targets = load_valid_targets()

    if isinstance(plan_data, dict):
        if "plan" not in plan_data:
            raise PlanValidationError("Plan object must contain a 'plan' key")
        actions = plan_data["plan"]
    elif isinstance(plan_data, list):
        actions = plan_data
    else:
        raise PlanValidationError(f"Malformed plan: expected dict or list, got {type(plan_data).__name__}")

    if not isinstance(actions, list):
        raise PlanValidationError(f"Malformed plan: 'plan' must be a list, got {type(actions).__name__}")

    if len(actions) == 0:
        raise PlanValidationError("Plan is empty: must contain at least one action")

    validated_actions = []
    for idx, step in enumerate(actions):
        if not isinstance(step, dict):
            raise PlanValidationError(f"Step {idx}: expected dictionary, got {type(step).__name__}")

        if "action" not in step:
            raise PlanValidationError(f"Step {idx}: missing required key 'action'")

        action = step["action"]
        if not isinstance(action, str):
            raise PlanValidationError(f"Step {idx}: 'action' must be a string")

        if action not in SUPPORTED_ACTIONS:
            raise PlanValidationError(f"Step {idx}: unsupported action '{action}'. Supported: {sorted(list(SUPPORTED_ACTIONS))}")

        if action == "navigate_to_target":
            if "target" not in step:
                raise PlanValidationError(f"Step {idx}: 'navigate_to_target' action requires a 'target' key")
            
            target = step["target"]
            if not isinstance(target, str):
                raise PlanValidationError(f"Step {idx}: 'target' must be a string")

            if target not in valid_targets:
                raise PlanValidationError(
                    f"Step {idx}: unknown target '{target}'. Valid targets from targets.yaml: {sorted(list(valid_targets))}"
                )

        # Disallow extra unexpected parameters to prevent arbitrary commands
        allowed_keys = {"action", "target"}
        extra_keys = set(step.keys()) - allowed_keys
        if extra_keys:
            raise PlanValidationError(f"Step {idx}: unexpected keys in step: {sorted(list(extra_keys))}")

        validated_actions.append(step)

    return validated_actions
