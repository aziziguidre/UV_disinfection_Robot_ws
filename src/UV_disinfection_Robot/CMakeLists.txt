cmake_minimum_required(VERSION 3.8)
project(uv_disinfection_robot)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# Find dependencies
find_package(ament_cmake REQUIRED)

# Install Python scripts
install(PROGRAMS
  scripts/odom.py
  scripts/teleop_keyboard_omni3.py
  scripts/cmd_vel_to_omni.py
  scripts/wheel_to_planar.py
  scripts/uv_irradiation_coverage.py
  scripts/human_detector.py
  DESTINATION lib/${PROJECT_NAME}
)

# Install resource directories
install(DIRECTORY
  launch
  urdf
  meshes
  rviz
  config
  worlds
  models
  maps
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
