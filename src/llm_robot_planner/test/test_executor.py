import pytest
import rclpy
from unittest.mock import MagicMock
from action_msgs.msg import GoalStatus
from action_msgs.srv import CancelGoal
from nav2_msgs.action import NavigateToPose

from llm_robot_planner.executor import PlanExecutor

TEST_TARGETS = {
    "home": {"x": 0.0, "y": 0.0, "yaw": 0.0},
    "red_box": {"x": 1.0, "y": 1.5, "yaw": 0.0},
    "blue_cylinder": {"x": -1.0, "y": -1.5, "yaw": 3.14159},
    "green_box": {"x": 1.0, "y": -1.0, "yaw": 0.0},
}

@pytest.fixture(scope="module")
def rclpy_init():
    rclpy.init()
    yield
    rclpy.shutdown()

def create_mock_future(result_value):
    future = rclpy.task.Future()
    future.set_result(result_value)
    return future

def test_goal_msg_creation(rclpy_init):
    executor = PlanExecutor(node_name='test_node_goal_msg', targets_dict=TEST_TARGETS)
    goal_msg = executor.create_goal_msg("red_box")
    assert goal_msg.pose.header.frame_id == 'map'
    assert goal_msg.pose.pose.position.x == 1.0
    assert goal_msg.pose.pose.position.y == 1.5
    assert goal_msg.pose.pose.orientation.w == 1.0
    executor.destroy_node()

def test_execute_plan_success(rclpy_init):
    mock_action_client = MagicMock()
    mock_action_client.wait_for_server.return_value = True

    # Goal handle mock
    goal_handle = MagicMock()
    goal_handle.accepted = True
    
    # Result mock
    result = MagicMock()
    result.status = GoalStatus.STATUS_SUCCEEDED
    goal_handle.get_result_async.return_value = create_mock_future(result)

    mock_action_client.send_goal_async.return_value = create_mock_future(goal_handle)

    executor = PlanExecutor(
        node_name='test_node_success',
        targets_dict=TEST_TARGETS,
        action_client=mock_action_client
    )

    plan = {
        "plan": [
            {"action": "navigate_to_target", "target": "home"},
            {"action": "navigate_to_target", "target": "red_box"}
        ]
    }

    assert executor.execute_plan(plan) is True
    assert mock_action_client.send_goal_async.call_count == 2
    executor.destroy_node()

def test_execute_plan_stops_on_rejection(rclpy_init):
    mock_action_client = MagicMock()
    mock_action_client.wait_for_server.return_value = True

    # First goal is rejected
    goal_handle = MagicMock()
    goal_handle.accepted = False
    mock_action_client.send_goal_async.return_value = create_mock_future(goal_handle)

    executor = PlanExecutor(
        node_name='test_node_rejection',
        targets_dict=TEST_TARGETS,
        action_client=mock_action_client
    )

    plan = [
        {"action": "navigate_to_target", "target": "blue_cylinder"},
        {"action": "navigate_to_target", "target": "green_box"}
    ]

    assert executor.execute_plan(plan) is False
    # Second goal must not be called after first fails
    assert mock_action_client.send_goal_async.call_count == 1
    executor.destroy_node()

def test_execute_plan_stops_on_failure(rclpy_init):
    mock_action_client = MagicMock()
    mock_action_client.wait_for_server.return_value = True

    # First goal accepted but aborted
    goal_handle = MagicMock()
    goal_handle.accepted = True

    result = MagicMock()
    result.status = GoalStatus.STATUS_ABORTED
    goal_handle.get_result_async.return_value = create_mock_future(result)

    mock_action_client.send_goal_async.return_value = create_mock_future(goal_handle)

    executor = PlanExecutor(
        node_name='test_node_abort',
        targets_dict=TEST_TARGETS,
        action_client=mock_action_client
    )

    plan = [
        {"action": "navigate_to_target", "target": "blue_cylinder"},
        {"action": "navigate_to_target", "target": "green_box"}
    ]

    assert executor.execute_plan(plan) is False
    assert mock_action_client.send_goal_async.call_count == 1
    executor.destroy_node()

def test_execute_plan_stops_on_cancellation(rclpy_init):
    mock_action_client = MagicMock()
    mock_action_client.wait_for_server.return_value = True

    goal_handle = MagicMock()
    goal_handle.accepted = True

    result = MagicMock()
    result.status = GoalStatus.STATUS_CANCELED
    goal_handle.get_result_async.return_value = create_mock_future(result)

    mock_action_client.send_goal_async.return_value = create_mock_future(goal_handle)

    executor = PlanExecutor(
        node_name='test_node_cancel',
        targets_dict=TEST_TARGETS,
        action_client=mock_action_client
    )

    plan = [
        {"action": "navigate_to_target", "target": "home"},
        {"action": "navigate_to_target", "target": "red_box"}
    ]

    assert executor.execute_plan(plan) is False
    assert mock_action_client.send_goal_async.call_count == 1
    executor.destroy_node()

def test_execute_plan_rejects_invalid_plan(rclpy_init):
    mock_action_client = MagicMock()
    executor = PlanExecutor(
        node_name='test_node_invalid',
        targets_dict=TEST_TARGETS,
        action_client=mock_action_client
    )

    # Unknown target
    plan = [
        {"action": "navigate_to_target", "target": "unknown_location"}
    ]

    assert executor.execute_plan(plan) is False
    assert mock_action_client.send_goal_async.call_count == 0
    executor.destroy_node()

def test_navigation_timeout_cancels_goal_confirmed(rclpy_init):
    mock_action_client = MagicMock()
    mock_action_client.wait_for_server.return_value = True

    goal_handle = MagicMock()
    goal_handle.accepted = True

    # Uncompleted future to simulate navigation timeout
    result_future = rclpy.task.Future()
    goal_handle.get_result_async.return_value = result_future

    # Cancel response setup
    cancel_resp = CancelGoal.Response()
    cancel_resp.return_code = CancelGoal.Response.ERROR_NONE
    cancel_future = create_mock_future(cancel_resp)

    def on_cancel():
        # When cancel is called, result completes with STATUS_CANCELED
        res = MagicMock()
        res.status = GoalStatus.STATUS_CANCELED
        result_future.set_result(res)
        return cancel_future

    goal_handle.cancel_goal_async.side_effect = on_cancel
    mock_action_client.send_goal_async.return_value = create_mock_future(goal_handle)

    executor = PlanExecutor(
        node_name='test_node_timeout',
        targets_dict=TEST_TARGETS,
        action_client=mock_action_client
    )

    success = executor.execute_navigation_step("home", timeout_sec=0.01)
    assert success is False
    assert goal_handle.cancel_goal_async.called is True
    executor.destroy_node()

def test_execute_plan_timeout_aborts_subsequent_steps(rclpy_init):
    mock_action_client = MagicMock()
    mock_action_client.wait_for_server.return_value = True

    goal_handle = MagicMock()
    goal_handle.accepted = True

    result_future = rclpy.task.Future()
    goal_handle.get_result_async.return_value = result_future

    cancel_resp = CancelGoal.Response()
    cancel_resp.return_code = CancelGoal.Response.ERROR_NONE
    cancel_future = create_mock_future(cancel_resp)

    def on_cancel():
        res = MagicMock()
        res.status = GoalStatus.STATUS_CANCELED
        result_future.set_result(res)
        return cancel_future

    goal_handle.cancel_goal_async.side_effect = on_cancel
    mock_action_client.send_goal_async.return_value = create_mock_future(goal_handle)

    executor = PlanExecutor(
        node_name='test_node_timeout_abort',
        targets_dict=TEST_TARGETS,
        action_client=mock_action_client
    )

    plan = [
        {"action": "navigate_to_target", "target": "home"},
        {"action": "navigate_to_target", "target": "red_box"}
    ]

    assert executor.execute_plan(plan, step_timeout_sec=0.01) is False
    # Only 1 step was sent; step 2 was aborted!
    assert mock_action_client.send_goal_async.call_count == 1
    executor.destroy_node()

def test_cancel_active_goal_unconfirmed_on_rejection(rclpy_init):
    mock_action_client = MagicMock()
    executor = PlanExecutor(
        node_name='test_node_cancel_rej',
        targets_dict=TEST_TARGETS,
        action_client=mock_action_client
    )

    goal_handle = MagicMock()
    cancel_resp = CancelGoal.Response()
    cancel_resp.return_code = CancelGoal.Response.ERROR_REJECTED
    cancel_resp.goals_canceling = []
    goal_handle.cancel_goal_async.return_value = create_mock_future(cancel_resp)

    confirmed = executor.cancel_active_goal(goal_handle, timeout_sec=0.1)
    # Cancellation must NOT be reported as confirmed when rejected
    assert confirmed is False
    executor.destroy_node()

def test_cancel_active_goal_unconfirmed_on_timeout(rclpy_init):
    mock_action_client = MagicMock()
    executor = PlanExecutor(
        node_name='test_node_cancel_timeout',
        targets_dict=TEST_TARGETS,
        action_client=mock_action_client
    )

    goal_handle = MagicMock()
    # Uncompleted cancel future to simulate cancel timeout
    uncompleted_cancel_fut = rclpy.task.Future()
    goal_handle.cancel_goal_async.return_value = uncompleted_cancel_fut

    confirmed = executor.cancel_active_goal(goal_handle, timeout_sec=0.01)
    assert confirmed is False
    executor.destroy_node()

def test_cancel_active_goal_unconfirmed_when_status_not_canceled(rclpy_init):
    mock_action_client = MagicMock()
    executor = PlanExecutor(
        node_name='test_node_cancel_wrong_status',
        targets_dict=TEST_TARGETS,
        action_client=mock_action_client
    )

    goal_handle = MagicMock()
    cancel_resp = CancelGoal.Response()
    cancel_resp.return_code = CancelGoal.Response.ERROR_NONE
    goal_handle.cancel_goal_async.return_value = create_mock_future(cancel_resp)

    # Result completes with STATUS_ABORTED instead of STATUS_CANCELED
    result = MagicMock()
    result.status = GoalStatus.STATUS_ABORTED
    result_future = create_mock_future(result)
    goal_handle.get_result_async.return_value = result_future

    confirmed = executor.cancel_active_goal(goal_handle, result_future=result_future, timeout_sec=0.1)
    assert confirmed is False
    executor.destroy_node()

def test_execute_plan_interrupted_by_ctrl_c(rclpy_init, monkeypatch):
    mock_action_client = MagicMock()
    mock_action_client.wait_for_server.return_value = True

    goal_handle = MagicMock()
    goal_handle.accepted = True

    result_future = rclpy.task.Future()
    goal_handle.get_result_async.return_value = result_future

    cancel_resp = CancelGoal.Response()
    cancel_resp.return_code = CancelGoal.Response.ERROR_NONE
    cancel_future = create_mock_future(cancel_resp)

    def on_cancel():
        res = MagicMock()
        res.status = GoalStatus.STATUS_CANCELED
        result_future.set_result(res)
        return cancel_future

    goal_handle.cancel_goal_async.side_effect = on_cancel
    mock_action_client.send_goal_async.return_value = create_mock_future(goal_handle)

    executor = PlanExecutor(
        node_name='test_node_interrupt',
        targets_dict=TEST_TARGETS,
        action_client=mock_action_client
    )

    original_spin = rclpy.spin_until_future_complete
    interrupted_once = False

    def mock_spin(node, future, timeout_sec=None):
        nonlocal interrupted_once
        if future == result_future and not interrupted_once:
            interrupted_once = True
            raise KeyboardInterrupt()
        return original_spin(node, future, timeout_sec=timeout_sec)

    monkeypatch.setattr(rclpy, 'spin_until_future_complete', mock_spin)

    plan = [
        {"action": "navigate_to_target", "target": "home"},
        {"action": "navigate_to_target", "target": "red_box"}
    ]

    success = executor.execute_plan(plan)
    assert success is False
    assert executor._interrupted is True
    assert goal_handle.cancel_goal_async.called is True
    # Second step aborted!
    assert mock_action_client.send_goal_async.call_count == 1
    executor.destroy_node()
