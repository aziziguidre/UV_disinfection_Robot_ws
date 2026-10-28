# 🌐 Rosbridge Suite — Web & ROS 2 Bridge for CHIRON-UV

[![ROS 2](https://img.shields.io/badge/ROS%202-Humble-22314E?logo=ros&logoColor=white)](https://docs.ros.org/en/humble/)
[![WebSocket](https://img.shields.io/badge/Transport-WebSockets%20%7C%20JSON-blue)](https://github.com/RobotWebTools/rosbridge_suite)
[![Dashboard](https://img.shields.io/badge/Connected%20To-uv__web__dashboard-61DAFB)](../uv_web_dashboard/)

`rosbridge_suite` provides the bidirectional JSON WebSocket communication bridge between the **CHIRON-UV ROS 2 robotics stack** and the **Mission Control Web Dashboard** (`uv_web_dashboard`).

<p align="center">
  <img src="../../docs/images/dashboard_web.png" alt="Connected Web Dashboard HUD" width="85%" />
</p>

---

## ⚡ Role in the CHIRON-UV Architecture

In this project, `rosbridge_server` (WebSocket on port `9090`) and `rosapi` enable the React 18 browser client (`roslibjs`) to communicate seamlessly with ROS 2 nodes without needing a native ROS installation on the client device:

### 1. Topics Bridged
- **Robot Pose & Odometry**: Subscribes to `/amcl_pose` (`PoseStamped`) and `/odom` (`Odometry`) for real-time map canvas rendering.
- **UV Dosimetry Heatmap**: Subscribes to `/uvrobot/dose_heatmap_2d` (`OccupancyGrid`) to render live Viridis radiation coverage over room floors.
- **Perception & Safety**: Subscribes to `/uvrobot/human_detected` (`Bool`) and `/uvrobot/human_count` (`Int32`) to trigger immediate browser HUD alerts.
- **Disinfection Telemetry**: Subscribes to `/uvrobot/disinfection_stats` (`String`) for coverage percentage, elapsed time, and status.
- **Operator Commands**: Publishes to `/room/goal` (room selection) and `/room/command` (`start`, `pause`, `resume`, `stop`, `home`).
- **Manual Teleoperation**: Publishes velocity commands directly to `/cmd_vel` (`geometry_msgs/Twist`).

### 2. Services & Actions Bridged
- **Trigger Services**: Calls `/start_disinfection` and `/stop_disinfection` (`std_srvs/Trigger`) to spin up or cleanly shut down the OctoMap and dosimetry computation engine.
- **Action Client Goals**: Dispatches `/navigate_to_pose` and `/spin` actions to Navigation2 in a dedicated background worker thread.

---

## 🚀 How to Run in CHIRON-UV

Launched automatically via the dashboard launch file:
```bash
ros2 launch uv_web_dashboard UV_Dashboard.launch.py
```

Or run standalone on port 9090:
```bash
ros2 launch rosbridge_server rosbridge_websocket_launch.xml port:=9090
```

---

## 📦 Upstream Rosbridge Suite Details

#### Server Implementations of the rosbridge v2 Protocol

rosbridge provides a JSON interface to ROS, allowing any client to send JSON to publish or subscribe to ROS topics, call ROS services, and more. rosbridge supports a variety of transport layers, including WebSockets and TCP. For information on the protocol itself, see the [rosbridge protocol specification](ROSBRIDGE_PROTOCOL.md).

For full documentation, see [the ROS wiki](http://ros.org/wiki/rosbridge_suite).

This project is released as part of the [Robot Web Tools](https://robotwebtools.github.io/) effort.

### Included Packages
* **`rosbridge_suite`**: Meta-package including all subpackages.
* **`rosbridge_library`**: Python API receiving JSON-formatted strings and invoking ROS publishers/subscribers/services.
* **`rosbridge_server`**: WebSocket server implementation exposing `rosbridge_library` over port 9090.
* **`rosapi`**: Service calls for introspecting ROS topics, services, parameters, and nodes.

### License
rosbridge_suite is released under the BSD license. See [LICENSE](LICENSE) for details.
