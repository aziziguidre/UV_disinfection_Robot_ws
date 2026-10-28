# 🐍 CHIRON-UV Core Nodes & Scripts (`scripts/`)

This directory contains the computational engines, AI perception models, kinematics converters, and odometry integrators powering the **CHIRON-UV** autonomous mobile robot.

---

## 📑 Scripts Directory Index

| Script | Purpose | Key Subsystem |
|---|---|---|
| **`human_detector.py`** | YOLOv8 real-time person detector & emergency fail-safe interlock | AI Perception & Safety |
| **`uv_irradiation_coverage.py`** | 3D OctoMap raytracing & 2D floor UV dose accumulation engine | Physics Dosimetry Engine |
| **`odom.py`** | Holonomic odometry integration from wheel encoder states | State Estimation |
| **`cmd_vel_to_omni.py`** | $v_x, v_y, \omega_z$ velocity mapping to 3-wheel Kiwi drive | Kinematics & ros2_control |
| **`teleop_keyboard_omni3.py`** | Interactive keyboard teleoperation for 3 omniwheels | Manual Control |
| **`wheel_to_planar.py`** | Planar joint state transform utility | Kinematics Utility |
| **`record_trajectory_live.py`** | Real-time path and trajectory logger | Evaluation & Benchmarking |

---

## 👁️ 1. YOLOv8 AI Human Detection (`human_detector.py`)

<p align="center">
  <img src="../../../docs/images/yolov8_detection.png" alt="YOLOv8 Human Detection" width="75%" />
</p>

### Overview
UV-C germicidal light (254 nm) destroys DNA/RNA in pathogens but is hazardous to human skin and eyes. `human_detector.py` acts as an autonomous zero-latency safety guardian that immediately halts radiation if any person enters the room.

### Technical Implementation
- **Neural Network**: Ultralytics **YOLOv8 Nano** (`yolov8n.pt`, 6.5 MB pre-trained on COCO dataset).
- **Class Filtering**: Isolates COCO Class 0 (`Person`) with confidence threshold tuning ($\text{conf} \ge 0.30$).
- **Multi-Threaded Asynchronous Inference**: Uses worker threads to prevent blocking ROS 2 camera frame ingestion callbacks.
- **Inference Optimization**: Downsamples frames to $320 \times 320$ and processes every $N$-th frame (`every_n_frames:=3`) to maintain high real-time FPS on edge hardware.

### ROS 2 Interface
- **Inputs**:
  - `/camera/image_raw` or `/rs_color/image_raw` (`sensor_msgs/Image`)
- **Outputs**:
  - `/uvrobot/human_detected` (`std_msgs/Bool`): Published as `True` whenever a person is in frame. Immediately stops the UV dose server and holds Nav2 navigation.
  - `/uvrobot/human_count` (`std_msgs/Int32`): Real-time count of detected individuals.
  - `/uvrobot/yolo_image` (`sensor_msgs/Image`): Bounding-box annotated stream delivered to `web_video_server`.

### Running Standalone
```bash
ros2 run uv_disinfection_robot human_detector.py --ros-args -p image_topic:=/rs_color/image_raw -p conf:=0.35
```

---

## ☀️ 2. UV Dosimetry & OctoMap Raycaster (`uv_irradiation_coverage.py`)

<p align="center">
  <img src="../../../docs/images/heatmap_dose.png" alt="UV-C Real-Time Heatmap" width="75%" />
</p>

### Overview
Simulates the germicidal dose emitted from 4 cylindrical UV lamps mounted symmetrically on the robot base.

### Physics Formulation
- **Inverse-Square Attenuation**:
  $$E(d) = \min\left(\frac{P_{\text{UV}}}{4\pi (d^2 + 0.25)}, 40.0\right) \quad [\text{W/m}^2]$$
- **Cumulative Dose**:
  $$\text{Dose}(x, y) = \sum_{k=1}^4 \int_0^T E(d_k) \, dt \quad [\text{J/m}^2]$$
- **Occlusion Handling**: Radial raycasting every $2^\circ$ up to 4.5 m, terminated whenever a wall or furniture voxel is struck.
- **Color Encoding**: Encodes accumulated dose values onto an 8-bit multi-stop **Viridis color gradient** published as `/uvrobot/dose_heatmap_2d` and `/uvrobot/dose_image`.

---

## 🛞 3. Holonomic Odometry & Kinematics (`odom.py` & `cmd_vel_to_omni.py`)

<p align="center">
  <img src="../../../docs/images/schema_cinematique_complet.png" alt="Kinematic Schema" width="60%" />
</p>

- Computes forward and inverse kinematics for the 3-wheel Kiwi omnidirectional base (spaced at $120^\circ$).
- Publishes smooth odometry transforms (`odom` $\rightarrow$ `base_link`) to the TF tree.
