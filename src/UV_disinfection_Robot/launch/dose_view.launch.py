import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg = get_package_share_directory('uv_disinfection_robot')
    rviz_cfg = os.path.join(pkg, 'rviz', 'disinfection.rviz')
    if not os.path.exists(rviz_cfg):
        rviz_cfg = os.path.join(pkg, 'launch', 'disinfection_view.rviz')

    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time', default_value='true', description='Use simulation (Gazebo) clock'
    )

    return LaunchDescription([
        use_sim_time_arg,
        Node(
            package='rviz2',
            executable='rviz2',
            name='dose_rviz2',
            arguments=['-d', rviz_cfg],
            parameters=[{'use_sim_time': LaunchConfiguration('use_sim_time')}],
            output='screen'
        )
    ])
