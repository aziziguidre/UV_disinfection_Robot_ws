#!/usr/bin/env python3
"""
Launch file UV_Dashboard.launch.py for UV Disinfection Robot
Starts:
1. rosbridge_server (rosbridge_websocket + rosapi_node) on port 9090
2. disinfection_process ROS 2 node
3. Python HTTP server serving the Web Control UI on port 5173
4. web_video_server on port 8080
5. human_detector YOLO node
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_dashboard = get_package_share_directory('uv_web_dashboard')

    port_arg = DeclareLaunchArgument(
        'port', default_value='9090', description='Port for rosbridge websocket'
    )
    web_port_arg = DeclareLaunchArgument(
        'web_port', default_value='5173', description='Port for web frontend HTTP server'
    )
    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time', default_value='true', description='Use simulation (Gazebo) clock'
    )

    port = LaunchConfiguration('port')
    web_port = LaunchConfiguration('web_port')
    use_sim_time = LaunchConfiguration('use_sim_time')

    # 1. rosbridge_websocket node
    rosbridge_node = Node(
        package='rosbridge_server',
        executable='rosbridge_websocket',
        name='rosbridge_websocket',
        output='screen',
        parameters=[{
            'port': 9090,
            'use_sim_time': use_sim_time,
            'send_action_goals_in_new_thread': True,
            'call_services_in_new_thread': True
        }]
    )

    # 2. rosapi node
    rosapi_node = Node(
        package='rosapi',
        executable='rosapi_node',
        name='rosapi',
        output='screen',
        parameters=[{'use_sim_time': use_sim_time}]
    )

    # 3. disinfection_process node
    disinfection_process_node = Node(
        package='uv_web_dashboard',
        executable='disinfection_process',
        name='disinfection_process',
        output='screen',
        parameters=[{'use_sim_time': use_sim_time}]
    )

    # 4. Web UI static file server
    frontend_dist = os.path.join(pkg_dashboard, 'web_frontend', 'dist')
    if not os.path.exists(frontend_dist):
        src_frontend_dist = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'web_frontend', 'dist'
        )
        if os.path.exists(src_frontend_dist):
            frontend_dist = src_frontend_dist

    web_server = ExecuteProcess(
        cmd=['python3', '-m', 'http.server', web_port, '--directory', frontend_dist],
        output='screen'
    )

    # 5. Publish initial pose for AMCL (matching warehouse spawn at -11.883, 10.879, yaw=0.0)
    set_initial_pose = ExecuteProcess(
        cmd=['bash', '-c',
             'sleep 5; '
             'ros2 topic pub -1 /initialpose geometry_msgs/PoseWithCovarianceStamped '
             '\'{ header: { frame_id: "map" }, '
             'pose: { pose: { position: { x: -11.883, y: 10.879, z: 0.0 }, '
             'orientation: { x: 0.0, y: 0.0, z: 0.0, w: 1.0 } }, '
             'covariance: [0.25, 0.0, 0.0, 0.0, 0.0, 0.0, '
             '0.0, 0.25, 0.0, 0.0, 0.0, 0.0, '
             '0.0, 0.0, 0.0, 0.0, 0.0, 0.0, '
             '0.0, 0.0, 0.0, 0.0, 0.0, 0.0, '
             '0.0, 0.0, 0.0, 0.0, 0.0, 0.0, '
             '0.0, 0.0, 0.0, 0.0, 0.0, 0.068] } }\''],
        output='screen'
    )

    # 6. web_video_server node for MJPEG stream (port 8080)
    web_video_server_node = Node(
        package='web_video_server',
        executable='web_video_server',
        name='web_video_server',
        output='screen',
        parameters=[{
            'port': 8080,
            'use_sim_time': use_sim_time
        }]
    )

    # 7. human_detector node (running continuously with camera feed)
    human_detector_node = Node(
        package='uv_disinfection_robot',
        executable='human_detector.py',
        name='human_detector',
        output='screen',
        parameters=[{
            'image_topic': '/rs_color/image_raw',
            'use_sim_time': use_sim_time
        }]
    )

    return LaunchDescription([
        port_arg,
        web_port_arg,
        use_sim_time_arg,
        rosbridge_node,
        rosapi_node,
        disinfection_process_node,
        web_video_server_node,
        human_detector_node,
        web_server,
        set_initial_pose,
    ])
