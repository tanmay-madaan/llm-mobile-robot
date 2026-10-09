import math
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from action_msgs.msg import GoalStatus
from nav2_msgs.action import NavigateToPose

class NavigateToNode(Node):
    def __init__(self):
        super().__init__('navigate_to')

        # Declare ROS 2 parameters
        self.declare_parameter('x', 1.0)
        self.declare_parameter('y', 0.0)
        self.declare_parameter('yaw', 0.0)

        # Create action client
        self._action_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')

    def send_goal(self):
        # Get parameters
        target_x = self.get_parameter('x').value
        target_y = self.get_parameter('y').value
        target_yaw = self.get_parameter('yaw').value

        self.get_logger().info('Waiting for navigate_to_pose action server...')
        self._action_client.wait_for_server()

        goal_msg = NavigateToPose.Goal()
        goal_msg.pose.header.frame_id = 'map'
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()

        goal_msg.pose.pose.position.x = float(target_x)
        goal_msg.pose.pose.position.y = float(target_y)
        goal_msg.pose.pose.position.z = 0.0
        
        goal_msg.pose.pose.orientation.x = 0.0
        goal_msg.pose.pose.orientation.y = 0.0
        goal_msg.pose.pose.orientation.z = math.sin(target_yaw / 2.0)
        goal_msg.pose.pose.orientation.w = math.cos(target_yaw / 2.0)

        self.get_logger().info(f'Sending goal to x={target_x}, y={target_y}, yaw={target_yaw}...')
        self._send_goal_future = self._action_client.send_goal_async(goal_msg)
        self._send_goal_future.add_done_callback(self.goal_response_callback)

    def goal_response_callback(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().info('Goal was rejected by server')
            rclpy.shutdown()
            return

        self.get_logger().info('Goal accepted by server, waiting for result...')
        self._get_result_future = goal_handle.get_result_async()
        self._get_result_future.add_done_callback(self.get_result_callback)

    def get_result_callback(self, future):
        status = future.result().status
        if status == GoalStatus.STATUS_SUCCEEDED:
            self.get_logger().info('Navigation succeeded!')
        elif status == GoalStatus.STATUS_CANCELED:
            self.get_logger().info('Navigation canceled.')
        elif status == GoalStatus.STATUS_ABORTED:
            self.get_logger().info('Navigation aborted/failed.')
        else:
            self.get_logger().info(f'Navigation finished with status code: {status}')

        rclpy.shutdown()

def main(args=None):
    rclpy.init(args=args)
    node = NavigateToNode()
    
    # Send the goal right after initialization
    node.send_goal()
    
    try:
        # Spin to process callbacks asynchronously
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info('Keyboard Interrupt (SIGINT)')
    finally:
        # Cleanup
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()
