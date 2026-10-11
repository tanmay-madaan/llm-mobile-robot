import os
import math
import yaml
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from action_msgs.msg import GoalStatus
from nav2_msgs.action import NavigateToPose
from ament_index_python.packages import get_package_share_directory, PackageNotFoundError

from .validator import validate_plan, PlanValidationError

def load_target_coordinates(targets_file: str = None) -> dict:
    """Load target definitions with coordinates from targets.yaml."""
    if targets_file and os.path.exists(targets_file):
        path = targets_file
    else:
        try:
            share_dir = get_package_share_directory('llm_robot_skills')
            path = os.path.join(share_dir, 'config', 'targets.yaml')
        except PackageNotFoundError:
            src_dir = os.path.expanduser('~/llm_robot_ws/src/llm_robot_skills/config/targets.yaml')
            if os.path.exists(src_dir):
                path = src_dir
            else:
                raise FileNotFoundError("Could not find targets.yaml in share or src directory")

    with open(path, 'r') as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict) or 'targets' not in data:
        raise ValueError("targets.yaml does not contain a 'targets' section")

    return data['targets']

class PlanExecutor(Node):
    """
    ROS 2 Task Executor that executes a validated plan step-by-step
    using Nav2 NavigateToPose action.
    """
    def __init__(self, node_name: str = 'plan_executor', targets_dict: dict = None, action_client=None):
        super().__init__(node_name)
        if targets_dict is not None:
            self._targets = targets_dict
        else:
            self._targets = load_target_coordinates()

        if action_client is not None:
            self._action_client = action_client
        else:
            self._action_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')

    def create_goal_msg(self, target_name: str) -> NavigateToPose.Goal:
        """Create a NavigateToPose goal from a target name."""
        if target_name not in self._targets:
            raise KeyError(f"Target '{target_name}' not found in target registry")

        data = self._targets[target_name]
        x = float(data.get('x', 0.0))
        y = float(data.get('y', 0.0))
        yaw = float(data.get('yaw', 0.0))

        goal_msg = NavigateToPose.Goal()
        goal_msg.pose.header.frame_id = 'map'
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
        goal_msg.pose.pose.position.x = x
        goal_msg.pose.pose.position.y = y
        goal_msg.pose.pose.position.z = 0.0

        goal_msg.pose.pose.orientation.x = 0.0
        goal_msg.pose.pose.orientation.y = 0.0
        goal_msg.pose.pose.orientation.z = math.sin(yaw / 2.0)
        goal_msg.pose.pose.orientation.w = math.cos(yaw / 2.0)

        return goal_msg

    def execute_navigation_step(self, target_name: str, timeout_sec: float = 60.0) -> bool:
        """
        Send a NavigateToPose goal synchronously from the node's perspective
        by spinning until the action finishes. Returns True on success, False on failure.
        """
        self.get_logger().info(f"Executing navigation step to '{target_name}'...")
        if not self._action_client.wait_for_server(timeout_sec=5.0):
            self.get_logger().error("NavigateToPose action server unavailable")
            return False

        goal_msg = self.create_goal_msg(target_name)
        send_goal_future = self._action_client.send_goal_async(goal_msg)
        rclpy.spin_until_future_complete(self, send_goal_future, timeout_sec=timeout_sec)

        if not send_goal_future.done():
            self.get_logger().error(f"Timeout waiting for goal acceptance for '{target_name}'")
            return False

        goal_handle = send_goal_future.result()
        if not goal_handle.accepted:
            self.get_logger().error(f"Goal for '{target_name}' was rejected by Nav2")
            return False

        self.get_logger().info(f"Goal for '{target_name}' accepted. Waiting for result...")
        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future, timeout_sec=timeout_sec)

        if not result_future.done():
            self.get_logger().error(f"Timeout waiting for result for '{target_name}'")
            return False

        status = result_future.result().status
        if status == GoalStatus.STATUS_SUCCEEDED:
            self.get_logger().info(f"Step '{target_name}' succeeded!")
            return True
        elif status == GoalStatus.STATUS_CANCELED:
            self.get_logger().warn(f"Step '{target_name}' was canceled")
            return False
        else:
            self.get_logger().error(f"Step '{target_name}' failed with status {status}")
            return False

    def execute_plan(self, plan_data) -> bool:
        """
        Validate plan and execute steps sequentially.
        Stops immediately on any failure or cancellation.
        """
        valid_targets = set(self._targets.keys())
        try:
            validated_steps = validate_plan(plan_data, valid_targets=valid_targets)
        except PlanValidationError as e:
            self.get_logger().error(f"Plan validation failed: {e}")
            return False

        total_steps = len(validated_steps)
        self.get_logger().info(f"Plan validated successfully ({total_steps} step(s)). Starting execution...")

        for idx, step in enumerate(validated_steps, start=1):
            action = step["action"]
            if action == "navigate_to_target":
                target = step["target"]
                self.get_logger().info(f"[{idx}/{total_steps}] Step: navigate_to_target -> '{target}'")
                success = self.execute_navigation_step(target)
                if not success:
                    self.get_logger().error(f"Plan aborted: step {idx} ('{target}') did not succeed")
                    return False

        self.get_logger().info("All plan steps completed successfully!")
        return True
