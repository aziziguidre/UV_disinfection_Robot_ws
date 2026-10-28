#!/usr/bin/env python3

import os

from ament_index_python.packages import get_package_share_directory, PackageNotFoundError
from launch import LaunchDescription
from launch.substitutions import Command
from launch_ros.actions import Node


def generate_launch_description():
    pkg_dir = get_package_share_directory('uv_disinfection_robot')

    # Process xacro to get robot description
    xacro_file = os.path.join(pkg_dir, 'urdf', 'main.urdf.xacro')
    robot_description_content = Command(['xacro ', xacro_file])
    robot_description = {'robot_description': robot_description_content}

    nav2_bringup_dir = get_package_share_directory('nav2_bringup')
    rviz_config = os.path.join(nav2_bringup_dir, 'rviz', 'nav2_default_view.rviz')

    # RViz2
    rviz2 = Node(
        package='rviz2',
        executable='rviz2',
        arguments=['-d', rviz_config],
        parameters=[{'use_sim_time': True}],
        output='screen',
    )

    return LaunchDescription([
        rviz2,
    ])
