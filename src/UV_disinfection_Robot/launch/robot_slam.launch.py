#!/usr/bin/env python3

"""
Phase 1: SLAM Mapping Launch File for CHIRON-UV Robot.

Launches everything needed for manual mapping:
  - slam_toolbox (online async 2D SLAM)
  - cmd_vel_to_omni velocity converter
  - RViz2 with pre-configured SLAM display (map + laser + robot)

"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_dir = get_package_share_directory('uv_disinfection_robot')

    slam_config = os.path.join(pkg_dir, 'config', 'slam.yaml')
    rviz_config = os.path.join(pkg_dir, 'rviz', 'slam.rviz')

    # Process xacro to get robot description
    xacro_file = os.path.join(pkg_dir, 'urdf', 'main.urdf.xacro')
    robot_description_content = Command(['xacro ', xacro_file])
    robot_description = {'robot_description': robot_description_content}

    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time',
        default_value='true',
        description='Use simulation (Gazebo) clock if true'
    )

    use_sim_time = LaunchConfiguration('use_sim_time')

    # SLAM Toolbox Node
    slam_toolbox_node = Node(
        package='slam_toolbox',
        executable='async_slam_toolbox_node',
        name='slam_toolbox',
        output='screen',
        parameters=[
            slam_config,
            {'use_sim_time': use_sim_time}
        ],
    )

    # CmdVel to Omni Converter Node
    cmd_vel_converter_node = Node(
        package='uv_disinfection_robot',
        executable='cmd_vel_to_omni.py',
        name='cmd_vel_to_omni',
        output='screen',
    )

    # RViz2 with SLAM-specific config (map + laser + robot + TF)
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        arguments=['-d', rviz_config],
        output='screen',
        parameters=[robot_description, {'use_sim_time': use_sim_time}],
    )

    # Robot State Publisher: URDF -> static TF + /robot_description
    robot_state_publisher_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[robot_description, {'use_sim_time': use_sim_time}],
    )

    # Ground-truth odom -> TF (odom -> origin_link)
    odom_node = Node(
        package='uv_disinfection_robot',
        executable='odom.py',
        name='odom_pub',
        output='screen',
        parameters=[{'use_sim_time': use_sim_time}],
    )

    return LaunchDescription([
        use_sim_time_arg,
        slam_toolbox_node,
        cmd_vel_converter_node,
        rviz_node,
        robot_state_publisher_node,
        odom_node,
    ])
