#!/usr/bin/env python3

import os
from launch_ros.parameter_descriptions import ParameterValue
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, IncludeLaunchDescription, RegisterEventHandler, SetEnvironmentVariable
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_dir = get_package_share_directory('uv_disinfection_robot')
    parent_dir = os.path.dirname(pkg_dir)

    # Ensure Gazebo can resolve package://uv_disinfection_robot/... mesh URIs
    # and model://aws_robomaker_hospital_* URIs for the hospital world
    models_dir = os.path.join(pkg_dir, 'models')
    existing_model_path = os.environ.get('GAZEBO_MODEL_PATH', '')
    user_gazebo_models = os.path.expanduser('~/.gazebo/models')
    gazebo_model_path = f"{parent_dir}:{models_dir}:{user_gazebo_models}:{existing_model_path}" if existing_model_path else f"{parent_dir}:{models_dir}:{user_gazebo_models}"
    set_gazebo_model_path = SetEnvironmentVariable('GAZEBO_MODEL_PATH', gazebo_model_path)
    disable_gazebo_online_db = SetEnvironmentVariable('GAZEBO_MODEL_DATABASE_URI', '')

    # Hospital world from UVC-Disinfection-Robot
    default_world_file = os.path.join(pkg_dir, 'worlds', 'hospital.world')
    world_file = LaunchConfiguration('world', default=default_world_file)

    world_arg = DeclareLaunchArgument(
        'world',
        default_value=default_world_file,
        description='Full path to Gazebo world file to load'
    )

    samples_arg = DeclareLaunchArgument(
        'samples',
        default_value='180',
        description='Horizontal samples for 3D LIDAR'
    )
    vertical_samples_arg = DeclareLaunchArgument(
        'vertical_samples',
        default_value='8',
        description='Vertical samples for 3D LIDAR'
    )
    update_rate_arg = DeclareLaunchArgument(
        'update_rate',
        default_value='3',
        description='Update rate for 3D LIDAR'
    )

    samples = LaunchConfiguration('samples')
    vertical_samples = LaunchConfiguration('vertical_samples')
    update_rate = LaunchConfiguration('update_rate')

    # Process xacro to get robot description
    xacro_file = os.path.join(pkg_dir, 'urdf', 'main.urdf.xacro')
    robot_description_content = Command([
        'xacro ', xacro_file,
        ' samples:=', samples,
        ' vertical_samples:=', vertical_samples,
        ' update_rate:=', update_rate
    ])
    #robot_description = {'robot_description': robot_description_content} 
    robot_description = {'robot_description': ParameterValue(robot_description_content, value_type=str)}

    use_sim_time = LaunchConfiguration('use_sim_time', default='true')

    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time',
        default_value='true',
        description='Use simulation (Gazebo) clock'
    )
    # Robot State Publisher
    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[robot_description, {'use_sim_time': use_sim_time}],
    )

    # Build environment dictionary for Gazebo processes
    gazebo_env = dict(os.environ)
    gazebo_env['GAZEBO_MODEL_PATH'] = gazebo_model_path
    gazebo_env['GAZEBO_MODEL_DATABASE_URI'] = ''

    # Gazebo server & client (direct execution with explicit env to prevent online DB freeze)
    gzserver = ExecuteProcess(
        cmd=['gzserver', '-s', 'libgazebo_ros_init.so', '-s', 'libgazebo_ros_factory.so', '-s', 'libgazebo_ros_force_system.so', world_file],
        env=gazebo_env,
        output='screen'
    )
    gzclient = ExecuteProcess(
        cmd=['gzclient'],
        env=gazebo_env,
        output='screen'
    )

    # Initial spawn pose inside warehouse room
    x_pose_arg = DeclareLaunchArgument('x_pose', default_value='-7.7', description='Robot spawn X coordinate')
    y_pose_arg = DeclareLaunchArgument('y_pose', default_value='12.78', description='Robot spawn Y coordinate')
    # planar_support_collision has its bottom at origin_link z=0.0.
    z_pose_arg = DeclareLaunchArgument('z_pose', default_value='0.0', description='Robot spawn Z coordinate')
    yaw_pose_arg = DeclareLaunchArgument('yaw_pose', default_value='0.0', description='Robot spawn Yaw angle')

    x_pose = LaunchConfiguration('x_pose')
    y_pose = LaunchConfiguration('y_pose')
    z_pose = LaunchConfiguration('z_pose')
    yaw_pose = LaunchConfiguration('yaw_pose')

    # Spawn entity in Gazebo at designated pose
    spawn_entity = Node(
        package='gazebo_ros',
        executable='spawn_entity.py',
        arguments=[
            '-topic', 'robot_description',
            '-entity', 'chiron_uv',
            '-x', x_pose,
            '-y', y_pose,
            '-z', z_pose,
            '-Y', yaw_pose,
        ],
        output='screen',
    )

    # Joint State Broadcaster (spawned after entity is loaded)
    joint_state_broadcaster_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['joint_state_broadcaster'],
        output='screen',
    )

    # Velocity controllers for wheels
    left_vel_controller_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['left_joint_velocity_controller'],
        output='screen',
    )
    back_vel_controller_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['back_joint_velocity_controller'],
        output='screen',
    )
    right_vel_controller_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['right_joint_velocity_controller'],
        output='screen',
    )

    # Position controllers for tube height
    back_height_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['back_height_controller'],
        output='screen',
    )
    front_height_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['front_height_controller'],
        output='screen',
    )
    right_height_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['right_height_controller'],
        output='screen',
    )
    left_height_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['left_height_controller'],
        output='screen',
    )

    # Position controllers for tube angle
    back_angle_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['back_angle_controller'],
        output='screen',
    )
    front_angle_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['front_angle_controller'],
        output='screen',
    )
    right_angle_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['right_angle_controller'],
        output='screen',
    )
    left_angle_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['left_angle_controller'],
        output='screen',
    )

    # Odom publisher node
    odom_publisher = Node(
        package='uv_disinfection_robot',
        executable='odom.py',
        output='screen',
        parameters=[{
            'use_sim_time': use_sim_time,
            'spawn_x': x_pose,
            'spawn_y': y_pose,
            'spawn_yaw': yaw_pose,
        }],
    )
  # Wheel to planar converter node
    wheel_to_planar_node = Node(
        package='uv_disinfection_robot',
        executable='wheel_to_planar.py',
        name='wheel_to_planar',
        output='screen',
        parameters=[{'use_sim_time': use_sim_time}],
    )
    cmd_vel_to_omni_node = Node(
        package='uv_disinfection_robot',
        executable='cmd_vel_to_omni.py',
        name='cmd_vel_to_omni',
        output='screen',
        parameters=[{'use_sim_time': use_sim_time}],
    )
    # Sequence: spawn_entity -> joint_state_broadcaster -> other controllers
    delayed_joint_state_broadcaster = RegisterEventHandler(
        event_handler=OnProcessExit(
            target_action=spawn_entity,
            on_exit=[joint_state_broadcaster_spawner],
        )
    )

    delayed_controllers = RegisterEventHandler(
        event_handler=OnProcessExit(
            target_action=joint_state_broadcaster_spawner,
            on_exit=[
                left_vel_controller_spawner,
                back_vel_controller_spawner,
                right_vel_controller_spawner,
                 back_height_spawner,
                front_height_spawner,
                right_height_spawner,
                left_height_spawner,
                back_angle_spawner,
                front_angle_spawner,
                right_angle_spawner,
                left_angle_spawner
            ],
        )
    )

  
    return LaunchDescription([
        world_arg,
        samples_arg,
        vertical_samples_arg,
        update_rate_arg,
        use_sim_time_arg,
        x_pose_arg,
        y_pose_arg,
        z_pose_arg,
        yaw_pose_arg,
        set_gazebo_model_path,
        disable_gazebo_online_db,
        gzserver,
        gzclient,
        robot_state_publisher,
        spawn_entity,
        delayed_joint_state_broadcaster,
        delayed_controllers,
        odom_publisher,
        wheel_to_planar_node,
        cmd_vel_to_omni_node,
       
    ])
