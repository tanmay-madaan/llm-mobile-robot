import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument, RegisterEventHandler
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, Command
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue

def generate_launch_description():
    pkg_llm_gazebo = get_package_share_directory('llm_robot_gazebo')
    pkg_ros_gz_sim = get_package_share_directory('ros_gz_sim')
    pkg_llm_desc   = get_package_share_directory('llm_robot_description')

    world_file = os.path.join(pkg_llm_gazebo, 'worlds', 'empty.world.sdf')
    default_model_path = os.path.join(pkg_llm_desc, 'urdf', 'llm_robot.urdf.xacro')
    default_rviz_config_path = os.path.join(pkg_llm_desc, 'rviz', 'urdf.rviz')
    
    gz_args_arg = DeclareLaunchArgument(
        'gz_args', 
        default_value=f'-r -v 4 {world_file}', 
        description='Arguments for Gazebo Sim'
    )

    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_ros_gz_sim, 'launch', 'gz_sim.launch.py')
        ),
        launch_arguments={'gz_args': LaunchConfiguration('gz_args')}.items()
    )

    robot_description_content = Command(['xacro ', default_model_path])
    
    robot_state_publisher_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        parameters=[
            {'robot_description': ParameterValue(robot_description_content, value_type=str)},
            {'use_sim_time': True}
        ]
    )
    
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', default_rviz_config_path],
        parameters=[{'use_sim_time': True}]
    )

    lidar_bridge_node = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=['/scan@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan'],
        output='screen'
    )

    spawn_robot = Node(
        package='ros_gz_sim',
        executable='create',
        arguments=[
            '-topic', 'robot_description',
            '-name', 'llm_robot',
            '-x', '0.0',
            '-y', '0.0',
            '-z', '0.10'
        ],
        output='screen'
    )
    
    clock_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=['/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock'],
        output='screen'
    )

    jsb_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['joint_state_broadcaster'],
    )

    dd_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['diff_drive_base_controller'],
    )

    spawn_jsb_event = RegisterEventHandler(
        event_handler=OnProcessExit(
            target_action=spawn_robot,
            on_exit=[jsb_spawner, dd_spawner],
        )
    )

    return LaunchDescription([
        gz_args_arg,
        gazebo,
        robot_state_publisher_node,
        rviz_node,
        lidar_bridge_node,
        spawn_robot,
        clock_bridge,
        spawn_jsb_event
    ])
