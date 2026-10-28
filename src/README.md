#  CHIRON-UV Workspace Source Directory (`src/`)

This directory houses the ROS 2 packages, web applications, communication bridges, and AI perception pipelines powering the **CHIRON-UV Autonomous Mobile Disinfection Robot**.

<p align="center">
  <img src="../docs/images/gazebo_hospital_world.png" alt="Gazebo Hospital Simulation" width="49%" />
  <img src="../docs/images/dashboard_web.png" alt="Mission Control Dashboard" width="49%" />
</p>

---

##  Packages & Subsystems in `src/`

| Package / Module | Type | Description | Documentation |
|---|---|---|---|
| **[`UV_disinfection_Robot`](UV_disinfection_Robot/)** | ROS 2 Package (`ament_cmake`) | Core robotics package: URDF/Xacro models, Gazebo hospital simulation, `ros2_control` velocity & position controllers, Nav2 configuration, and Inverse-Square UV dosimetry raytracing. | [Read Package Docs ➔](UV_disinfection_Robot/README.md) |
| **[`uv_web_dashboard`](uv_web_dashboard/)** | ROS 2 Package (`ament_python`) | Mission control web dashboard (React 18 + Vite + Tailwind) and multi-threaded ROS 2 room tour coordinator node (`disinfection_process.py`). | [Read Package Docs ➔](uv_web_dashboard/README.md) |
| **[`rosbridge_suite`](rosbridge_suite/)** | ROS 2 Package (`ament_python`) | Bidirectional WebSocket JSON bridge (`port 9090`) and ROS API services connecting the React web UI (`roslibjs`) to the robot navigation and telemetry stack. | [Read Bridge Docs ➔](rosbridge_suite/README.md) |
| **[`YOLOv8 AI Safety System`](UV_disinfection_Robot/scripts/)** | Computer Vision Module | Deep learning human detector running `yolov8n.pt` with real-time bounding box stream and zero-latency fail-safe emergency UV shutoff interlock. | [Read AI Vision Docs ➔](UV_disinfection_Robot/scripts/README.md#%EF%B8%8F-1-yolov8-ai-human-detection-human_detectorpy) |

---

## Visual Highlights

<p align="center">
  <img src="../docs/images/robot_uvc.png" alt="Chiron Robot Model" width="24%" />
  <img src="../docs/images/schema_cinematique_complet.png" alt="Kinematics Scheme" width="24%" />
  <img src="../docs/images/heatmap_dose.png" alt="UV Dose Heatmap" width="24%" />
  <img src="../docs/images/yolov8_detection.png" alt="YOLOv8 Detection" width="24%" />
</p>

---

##  Workspace Build Commands

Build all workspace packages from source using `colcon`:

```bash
cd /home/aziz/ros2_UV_disinfection_Robot_ws
source /opt/ros/humble/setup.bash

# Build all packages with symlinked install
colcon build --packages-select uv_disinfection_robot uv_web_dashboard rosbridge_suite rosbridge_server rosapi rosbridge_library rosbridge_msgs --symlink-install
source install/setup.bash
```

---

##  Running the Full Stack (4-Terminal Guide)

Open 4 separate terminal sessions:

```bash
# Terminal 1: Gazebo Simulation World & Robot Spawn
ros2 launch uv_disinfection_robot robot_gazebo.launch.py

# Terminal 2: Nav2 & AMCL Localization
ros2 launch uv_disinfection_robot robot_nav2.launch.py

# Terminal 3: UV Dosimetry Raycaster & OctoMap Engine
ros2 launch uv_disinfection_robot disinfection.launch.py

# Terminal 4: Web Dashboard, Rosbridge & Coordinator Node
ros2 launch uv_web_dashboard UV_Dashboard.launch.py
```

Then open your browser to **`http://localhost:5173`**.
