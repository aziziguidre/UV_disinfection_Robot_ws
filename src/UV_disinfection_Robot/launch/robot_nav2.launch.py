#!/usr/bin/env python3
"""
ROS 2 Nav2 Launch for CHIRON-UV Robot — AMCL version (nav2 bringup).
NOTE: odom.py / cmd_vel_to_omni.py / wheel_to_planar.py are auto-started by

"""
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch.conditions import IfCondition
from launch_ros.actions import Node


def generate_launch_description():
    pkg_dir = get_package_share_directory('uv_disinfection_robot')
    nav2_bringup_dir = get_package_share_directory('nav2_bringup')

    nav2_params_file = os.path.join(pkg_dir, 'config', 'nav2_params.yaml')
    default_map_path = os.path.join(pkg_dir, 'maps', 'map.yaml')
    default_rviz_config = os.path.join(nav2_bringup_dir, 'rviz', 'nav2_default_view.rviz')

    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    map_yaml_file = LaunchConfiguration('map', default=default_map_path)
    autostart = LaunchConfiguration('autostart', default='true')
    include_gazebo = LaunchConfiguration('include_gazebo', default='false')
    use_rviz = LaunchConfiguration('use_rviz', default='true')
    rviz_config_file = LaunchConfiguration('rviz_config', default=default_rviz_config)

    declare_use_sim_time_cmd = DeclareLaunchArgument(
        'use_sim_time', default_value='true', description='Use simulation (Gazebo) clock if true')
    declare_map_yaml_cmd = DeclareLaunchArgument(
        'map', default_value=default_map_path, description='Full path to map yaml file to load for navigation')
    declare_autostart_cmd = DeclareLaunchArgument(
        'autostart', default_value='true', description='Automatically startup the nav2 stack')
    declare_include_gazebo_cmd = DeclareLaunchArgument(
        'include_gazebo', default_value='false', description='Include robot_gazebo.launch.py when true')
    declare_use_rviz_cmd = DeclareLaunchArgument(
        'use_rviz', default_value='true', description='Whether to launch RViz2 alongside Nav2')
    declare_rviz_config_file_cmd = DeclareLaunchArgument(
        'rviz_config', default_value=default_rviz_config, description='Full path to the RViz config file to use')

    nav2_bringup_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(nav2_bringup_dir, 'launch', 'bringup_launch.py')),
        launch_arguments={
            'use_sim_time': use_sim_time,
            'map': map_yaml_file,
            'params_file': nav2_params_file,
            'autostart': autostart,
            'use_composition': 'False',
        }.items(),
    )

    gazebo_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_dir, 'launch', 'robot_gazebo.launch.py')),
        condition=IfCondition(include_gazebo),
    )

    rviz_node = Node(
        package='rviz2', executable='rviz2', name='rviz2',
        arguments=['-d', rviz_config_file],
        parameters=[{'use_sim_time': use_sim_time}],
        output='screen',
        condition=IfCondition(use_rviz),
    )

    return LaunchDescription([
        declare_use_sim_time_cmd,
        declare_map_yaml_cmd,
        declare_autostart_cmd,
        declare_include_gazebo_cmd,
        declare_use_rviz_cmd,
        declare_rviz_config_file_cmd,
        nav2_bringup_launch,
        gazebo_launch,
        rviz_node,
    ])
