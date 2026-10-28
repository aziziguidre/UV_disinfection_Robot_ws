import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg = get_package_share_directory('uv_disinfection_robot')
    maps_dir = os.path.join(pkg, 'maps')
    candidates = ['world2map.yaml', 'merged_map.yaml', 'hospital_perfect.yaml', 'map.yaml']
    map_path = next((os.path.join(maps_dir, c) for c in candidates
                     if os.path.exists(os.path.join(maps_dir, c))),
                    os.path.join(maps_dir, 'hospital_map1.yaml'))
    print(f'[disinfection] using 2D map: {map_path}')
    rviz_cfg = os.path.join(pkg, 'rviz', 'disinfection.rviz')
    if not os.path.exists(rviz_cfg):
        rviz_cfg = os.path.join(pkg, 'launch', 'disinfection_view.rviz')
    urdf_path = os.path.join(pkg, 'urdf', 'main.urdf.xacro')

    launch_rviz_arg = DeclareLaunchArgument(
        'launch_rviz', default_value='false', description='Optionally launch RViz inside this process group (default: false)'
    )
    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time', default_value='true', description='Use simulation clock'
    )

    launch_rviz = LaunchConfiguration('launch_rviz')
    use_sim_time = LaunchConfiguration('use_sim_time')

    return LaunchDescription([
        launch_rviz_arg,
        use_sim_time_arg,

        # Robot model + TF chain
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='disinfection_rsp',
            output='screen',
            parameters=[{
                'robot_description': Command(['xacro ', urdf_path]),
                'use_sim_time': use_sim_time
            }]
        ),

        # 2D occupancy map
        Node(
            package='nav2_map_server',
            executable='map_server',
            name='disinfection_map_server',
            output='screen',
            parameters=[{
                'yaml_filename': map_path,
                'frame_id': 'odom',
                'topic_name': '/map_gt',
                'use_sim_time': use_sim_time
            }]
        ),
        Node(
            package='nav2_lifecycle_manager',
            executable='lifecycle_manager',
            name='disinfection_map_lcm',
            output='screen',
            parameters=[{
                'autostart': True,
                'node_names': ['disinfection_map_server'],
                'use_sim_time': use_sim_time
            }]
        ),

        # 1. Octomap Server
        Node(
            package='octomap_server',
            executable='octomap_server_node',
            name='octomap_server',
            output='screen',
            parameters=[{
                'resolution': 0.08,
                'frame_id': 'map',
                'sensor_model.max_range': 4.5,
                'sensor_model.hit': 0.51,
                'sensor_model.miss': 0.49,
                'filter_speckles': True,
                'use_sim_time': use_sim_time
            }],
            remappings=[('cloud_in', '/uv_points')]
        ),

        # 2. UV Irradiation Coverage (Dose Node)
        Node(
            package='uv_disinfection_robot',
            executable='uv_irradiation_coverage.py',
            name='uv_irradiation_coverage',
            output='screen',
            parameters=[{
                'use_sim_time': use_sim_time,
                'max_range': 4.5
            }]
        ),

        # Optional RViz (default false so START never opens windows)
        Node(
            package='rviz2',
            executable='rviz2',
            name='dose_rviz2',
            arguments=['-d', rviz_cfg],
            output='screen',
            condition=IfCondition(launch_rviz),
            parameters=[{'use_sim_time': use_sim_time}]
        ),
    ])
