#!/usr/bin/env python3
"""
UV Disinfection Robot — Disinfection Process Coordinator Node
"""

import os
import signal
import math
import json
import re
import time
import threading
import subprocess
from collections import deque

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.executors import MultiThreadedExecutor
from rclpy.callback_groups import ReentrantCallbackGroup
from ament_index_python.packages import get_package_share_directory

from std_msgs.msg import String, Bool, Empty
from std_srvs.srv import Trigger
from geometry_msgs.msg import PoseStamped, Twist
from nav_msgs.msg import Odometry
from nav2_msgs.action import NavigateToPose, Spin
from action_msgs.msg import GoalStatus


def euler_to_quaternion(roll, pitch, yaw):
    cy = math.cos(yaw * 0.5)
    sy = math.sin(yaw * 0.5)
    cp = math.cos(pitch * 0.5)
    sp = math.sin(pitch * 0.5)
    cr = math.cos(roll * 0.5)
    sr = math.sin(roll * 0.5)

    qw = cr * cp * cy + sr * sp * sy
    qx = sr * cp * cy - cr * sp * sy
    qy = cr * sp * cy + sr * cp * sy
    qz = cr * cp * sy - sr * sp * cy
    return qx, qy, qz, qw


class DisinfectionProcessNode(Node):
    def __init__(self):
        super().__init__('disinfection_process')
        self.cb_group = ReentrantCallbackGroup()

        # ── State ──
        self.rooms = {}  # {name: {name, door:[x,y], center:[x,y]}}
        self.home_pose = (-11.883, 10.879, 0.0)  # Default Storage 2 (Robot House) spawn
        self.current_robot_pose = (-11.883, 10.879, 0.0)

        self.mission_id = 0  # Mission generation counter (increments on every dispatch & human hold)

        self.current_room = "IDLE"
        self.current_phase = "idle"  # idle, transit, sweeping, waiting, paused, stopped, held
        self.current_waypoint_idx = 0
        self.total_waypoints = 0
        self.progress = 0.0
        self.latest_coverage_pct = 0.0

        self.is_stopped = False
        self.is_paused = False
        self.is_tour_active = False
        self.goal_queue = deque()
        self.execution_thread = None
        self.thread_lock = threading.Lock()
        self.active_goal_handle = None

        self.disinfection_proc = None
        self.rviz_proc = None

        # Load static rooms.json at startup
        self._load_rooms_file()

        self.human_detected = False
        self.human_count = 0

        # ── Subscriptions ──
        self.create_subscription(
            PoseStamped, '/amcl_pose', self._pose_cb, 10, callback_group=self.cb_group)
        self.create_subscription(
            Odometry, '/odom', self._odom_cb, 10, callback_group=self.cb_group)
        self.create_subscription(
            Bool, '/uvrobot/human_detected', self._human_cb, 10, callback_group=self.cb_group)
        self.create_subscription(
            String, '/uvrobot/disinfection_stats', self._stats_cb, 10, callback_group=self.cb_group)
        self.create_subscription(
            String, '/room/goal', self._room_goal_cb, 10, callback_group=self.cb_group)
        self.create_subscription(
            String, '/room/command', self._room_cmd_cb, 10, callback_group=self.cb_group)
        self.create_subscription(
            Bool, '/disinfection/stop', self._estop_bool_cb, 10, callback_group=self.cb_group)
        self.create_subscription(
            Empty, '/disinfection/stop_empty', self._estop_empty_cb, 10, callback_group=self.cb_group)

        # Disinfection launch management
        self.create_subscription(
            Empty, '/disinfection/start', self._start_disinfection_msg_cb, 10, callback_group=self.cb_group)
        self.create_subscription(
            Empty, '/disinfection/stop_server', self._stop_disinfection_msg_cb, 10, callback_group=self.cb_group)

        self.srv_start = self.create_service(
            Trigger, '/start_disinfection', self._start_disinfection_srv_cb, callback_group=self.cb_group)
        self.srv_stop = self.create_service(
            Trigger, '/stop_disinfection', self._stop_disinfection_srv_cb, callback_group=self.cb_group)

        # ── Publishers ──
        self.status_pub = self.create_publisher(String, '/room/status', 10)
        self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)

        # ── Action Clients ──
        self.nav = ActionClient(
            self, NavigateToPose, 'navigate_to_pose', callback_group=self.cb_group)
        self.spin_client = ActionClient(
            self, Spin, 'spin', callback_group=self.cb_group)

        # ── Timers ──
        self.create_timer(0.5, self._publish_status, callback_group=self.cb_group)

        self.get_logger().info(f'Disinfection Process Node initialized with {len(self.rooms)} static rooms. Waiting for /amcl_pose...')

    def _bump_mission(self, reason="") -> int:
        self.mission_id += 1
        self.get_logger().info(f'[MISSION] Generation bumped -> {self.mission_id} ({reason})')
        return self.mission_id

    # ═══════════════════════════════════════════════════
    # Load static rooms.json file
    # ═══════════════════════════════════════════════════
    def _load_rooms_file(self):
        possible_paths = []
        try:
            pkg_desc = get_package_share_directory('uv_disinfection_robot')
            possible_paths.append(os.path.join(pkg_desc, 'config', 'rooms.json'))
            possible_paths.append(os.path.join(pkg_desc, 'maps', 'rooms.json'))
        except Exception:
            pass

        # Workspace relative fallbacks
        ws_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        possible_paths.extend([
            os.path.join(ws_root, 'src', 'UV_disinfection_Robot', 'config', 'rooms.json'),
            os.path.join(ws_root, 'src', 'uv_web_dashboard', 'web_frontend', 'public', 'rooms.json'),
            os.path.join(ws_root, 'src', 'UV_disinfection_Robot', 'maps', 'rooms.json'),
        ])

        try:
            pkg_coord = get_package_share_directory('uv_web_dashboard')
            possible_paths.append(os.path.join(pkg_coord, 'web_frontend', 'dist', 'rooms.json'))
        except Exception:
            pass

        for p in possible_paths:
            if os.path.exists(p):
                try:
                    with open(p, 'r') as f:
                        data = json.load(f)
                    if isinstance(data, list):
                        self.rooms = {r['name']: r for r in data}
                        self.get_logger().info(f'Successfully loaded {len(self.rooms)} rooms from {p}')
                        return
                except Exception as e:
                    self.get_logger().warn(f'Failed to read {p}: {e}')

        self.get_logger().error('Could not find rooms.json in any expected path!')

    # ═══════════════════════════════════════════════════
    # Pose & Stats Callbacks
    # ═══════════════════════════════════════════════════
    def _pose_cb(self, msg):
        p = msg.pose.position
        q = msg.pose.orientation
        yaw = math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))

        if abs(p.x) > 0.01 or abs(p.y) > 0.01:
            self.current_robot_pose = (p.x, p.y, yaw)
            if self.home_pose is None or (abs(self.home_pose[0] - (-11.883)) < 1e-4 and abs(self.home_pose[1] - 10.879) < 1e-4):
                self.home_pose = (p.x, p.y, yaw)
                self.get_logger().info(f'Set HOME pose from /amcl_pose: x={p.x:.3f}, y={p.y:.3f}, yaw={yaw:.3f}')

    def _odom_cb(self, msg):
        pass

    def _human_cb(self, msg):
        was_detected = self.human_detected
        self.human_detected = bool(msg.data)
        if self.human_detected and not was_detected:
            self.get_logger().error('HUMAN DETECTED on camera — UV radiation BANNED (safety interlock).')
            # 1. Instantly shut off UV dose server / ban UV radiation
            self._stop_disinfection_internal()
            if self.current_phase in ("idle", "waiting"):
                self.current_phase = "held"

    def _stats_cb(self, msg):
        match = re.search(r'([\d.]+)%', msg.data)
        if match:
            try:
                self.latest_coverage_pct = float(match.group(1))
            except ValueError:
                pass

    # ═══════════════════════════════════════════════════
    # Disinfection Process Controls
    # ═══════════════════════════════════════════════════
    def _start_disinfection_srv_cb(self, request, response):
        ok, message = self._start_disinfection_internal()
        response.success = ok
        response.message = message
        return response

    def _stop_disinfection_srv_cb(self, request, response):
        ok, message = self._stop_disinfection_internal()
        response.success = ok
        response.message = message
        return response

    def _start_disinfection_msg_cb(self, msg):
        self._start_disinfection_internal()

    def _stop_disinfection_msg_cb(self, msg):
        self._stop_disinfection_internal()

    def _start_disinfection_internal(self):
        # 0. Safety Interlock: Ban UV if human is present in the room
        if self.human_detected:
            self.get_logger().error('SAFETY INTERLOCK: Human detected in room! UV-C operation is strictly prohibited.')
            return False, "SAFETY INTERLOCK: Human detected in room. UV-C radiation is banned."

        # 1. Launch/ensure RViz2 is open for 3D room & heatmap inspection
        if self.rviz_proc is None or self.rviz_proc.poll() is not None:
            self.get_logger().info('Launching RViz2 dose & room heatmap view (dose_view.launch.py)...')
            self.rviz_proc = subprocess.Popen(
                ['ros2', 'launch', 'uv_disinfection_robot', 'dose_view.launch.py'],
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

        # 2. Clean up any stale compute processes before fresh start
        if self.disinfection_proc is not None and self.disinfection_proc.poll() is None:
            return True, "Disinfection stack already running"

        try:
            subprocess.run(['pkill', '-9', '-f', 'uv_irradiation_coverage.py'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(['pkill', '-9', '-f', 'octomap_server_node'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

        # 3. Launch disinfection compute stack (Octomap + Dose Server)
        self.get_logger().info('Starting disinfection compute stack (disinfection.launch.py)...')
        self.disinfection_proc = subprocess.Popen(
            ['ros2', 'launch', 'uv_disinfection_robot', 'disinfection.launch.py'],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return True, "Disinfection compute stack started (RViz2 active)"

    def _stop_disinfection_internal(self):
        # Stop disinfection compute nodes (Octomap, Dose Server) with zero orphans.
        # Keep RViz2 open so the operator can inspect the room heatmap.
        self.get_logger().info('Stopping disinfection stack (shutting down Octomap, Dose Server)...')
        if self.disinfection_proc is not None and self.disinfection_proc.poll() is None:
            try:
                pgid = os.getpgid(self.disinfection_proc.pid)
                os.killpg(pgid, signal.SIGTERM)
                try:
                    self.disinfection_proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(pgid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except Exception as e:
                self.get_logger().warn(f'Error killing disinfection process group: {e}')
            self.disinfection_proc = None

        # Clean up compute nodes so heatmap accumulation immediately stops
        for proc_pattern in ['uv_irradiation_coverage', 'octomap_server', 'disinfection.launch']:
            try:
                subprocess.run(['pkill', '-9', '-f', proc_pattern], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

        self.disinfection_proc = None
        return True, "Disinfection compute stack stopped (RViz2 view retained)"

    # ═══════════════════════════════════════════════════
    # Commands & Goals
    # ═══════════════════════════════════════════════════
    def _estop_bool_cb(self, msg):
        if msg.data:
            self._trigger_estop()

    def _estop_empty_cb(self, msg):
        self._trigger_estop()

    def _trigger_estop(self):
        with self.thread_lock:
            self._bump_mission("e-stop")
            self.is_stopped = True
            self.is_paused = False
            self.goal_queue.clear()
            self.current_phase = "stopped"
            if self.active_goal_handle is not None:
                try:
                    self.active_goal_handle.cancel_goal_async()
                except Exception:
                    pass
                self.active_goal_handle = None
            zero = Twist()
            self.cmd_vel_pub.publish(zero)
        # Stop UV radiation immediately on E-Stop for safety
        self._stop_disinfection_internal()
        self.get_logger().error('EMERGENCY STOP ACTIVATED — all motion and UV radiation locked.')

    def _room_cmd_cb(self, msg):
        cmd = msg.data.strip().lower()
        self.get_logger().info(f'Command received: {cmd}')
        if cmd in ('stop', 'estop'):
            self._trigger_estop()
        elif cmd == 'pause':
            if not self.is_stopped:
                self.is_paused = True
                self.current_phase = "paused"
                if self.active_goal_handle is not None:
                    try:
                        self.active_goal_handle.cancel_goal_async()
                    except Exception:
                        pass
                    self.active_goal_handle = None
                zero = Twist()
                self.cmd_vel_pub.publish(zero)
                self.get_logger().info('Navigation PAUSED — robot holding position.')
        elif cmd == 'resume':
            self.is_paused = False
            self.is_stopped = False
            if self.current_phase == "paused":
                self.current_phase = "transit"
            elif self.current_phase in ("stopped", "idle", "held"):
                self.current_phase = "idle"
            self.get_logger().info('Navigation RESUMED — continuing route.')
        elif cmd in ('start_tour', 'start_full_tour'):
            if self.is_stopped:
                self.get_logger().warn('Command ignored: EMERGENCY STOP active. Click Reset to clear safety lockout.')
                return
            self._start_full_tour()
        elif cmd == 'return_home':
            if self.is_stopped:
                self.get_logger().warn('Command ignored: EMERGENCY STOP active. Click Reset to clear safety lockout.')
                return
            self._start_room_goal('Home')

    def _room_goal_cb(self, msg):
        if self.is_stopped:
            self.get_logger().warn('Room goal rejected: EMERGENCY STOP is active! Click Reset to clear safety lockout before dispatching.')
            return

        goal_text = msg.data.strip()
        self.get_logger().info(f'Room goal requested: {goal_text}')

        room_name = goal_text
        if goal_text.startswith('{'):
            try:
                data = json.loads(goal_text)
                room_name = data.get('room', goal_text)
            except Exception:
                pass

        target_key = None
        if room_name in self.rooms or room_name == 'Home':
            target_key = room_name
        else:
            norm_target = room_name.lower().replace('_', ' ').strip()
            for k in self.rooms.keys():
                norm_key = k.lower().replace('_', ' ').strip()
                if norm_key == norm_target or norm_key.endswith(norm_target) or norm_target.endswith(norm_key):
                    target_key = k
                    break

        if target_key:
            self.get_logger().info(f'Executing room goal for: {target_key}')
            self._start_room_goal(target_key)
        else:
            self.get_logger().warn(f'Unknown room requested: {room_name}. Available: {list(self.rooms.keys())}')

    def _start_full_tour(self):
        if self.is_stopped:
            self.get_logger().warn('Full tour rejected: EMERGENCY STOP active. Click Reset first.')
            return

        with self.thread_lock:
            self.is_stopped = False
            self.is_paused = False
            self.is_tour_active = True
            mid = self._bump_mission("start_full_tour")
            if self.active_goal_handle is not None:
                try:
                    self.active_goal_handle.cancel_goal_async()
                except Exception:
                    pass
                self.active_goal_handle = None
            self.goal_queue.clear()
            for r in self.rooms.keys():
                self.goal_queue.append(r)
            if self.goal_queue:
                first = self.goal_queue.popleft()
                self._launch_thread(first, is_tour=True, mission_id=mid)

    def _start_room_goal(self, room_name):
        if self.is_stopped:
            self.get_logger().warn(f'Goal {room_name} rejected: EMERGENCY STOP active. Click Reset first.')
            return

        with self.thread_lock:
            self.is_stopped = False
            self.is_paused = False
            self.is_tour_active = False
            mid = self._bump_mission(f"dispatch_{room_name}")
            if self.active_goal_handle is not None:
                try:
                    self.active_goal_handle.cancel_goal_async()
                except Exception:
                    pass
                self.active_goal_handle = None
            self.goal_queue.clear()
            self._launch_thread(room_name, is_tour=False, mission_id=mid)

    def _launch_thread(self, room_name, is_tour=False, mission_id=None):
        if mission_id is None:
            mission_id = self.mission_id
        self.current_room = room_name
        self.current_phase = "transit"
        self.current_waypoint_idx = 0
        self.total_waypoints = 0
        self.progress = 0.0

        t = threading.Thread(
            target=self._run_room_pipeline, args=(room_name, is_tour, mission_id), daemon=True)
        self.execution_thread = t
        t.start()

    # ═══════════════════════════════════════════════════
    # Core Navigation go() function
    # ═══════════════════════════════════════════════════
    def go(self, x, y, yaw=None, target_tolerance=0.45, max_attempts=3):
        """
        Navigates to (x, y) enforcing:
        1. Mission ID check (aborts immediately if mission_id changed on new dispatch)
        2. Single-goal invariant (only 1 Nav2 goal active)
        3. Re-sends at most 1 Hz, max 3 attempts per waypoint (skips if unreachable)
        """
        my_mission_id = self.mission_id
        attempt = 0

        while attempt < max_attempts:
            # Check mission_id and estop
            if self.mission_id != my_mission_id or self.is_stopped:
                if self.active_goal_handle is not None:
                    try:
                        self.active_goal_handle.cancel_goal_async()
                    except Exception:
                        pass
                    self.active_goal_handle = None
                return False

            while self.is_paused and not self.is_stopped and self.mission_id == my_mission_id:
                time.sleep(0.3)

            if self.mission_id != my_mission_id or self.is_stopped:
                return False

            # Check if robot is already at the target point
            dist = math.hypot(self.current_robot_pose[0] - x, self.current_robot_pose[1] - y)
            if dist <= target_tolerance:
                self.get_logger().info(f'Robot reached goal ({x:.3f}, {y:.3f}) [dist={dist:.2f}m <= {target_tolerance}m]')
                return True

            if not self.nav.wait_for_server(timeout_sec=3.0):
                self.get_logger().error('Waiting for navigate_to_pose action server...')
                time.sleep(1.0)
                attempt += 1
                continue

            attempt += 1
            g = NavigateToPose.Goal()
            g.pose.header.frame_id = 'map'
            g.pose.header.stamp = self.get_clock().now().to_msg()
            g.pose.pose.position.x = float(x)
            g.pose.pose.position.y = float(y)
            g.pose.pose.position.z = 0.0

            if yaw is not None:
                qx, qy, qz, qw = euler_to_quaternion(0.0, 0.0, yaw)
                g.pose.pose.orientation.x = qx
                g.pose.pose.orientation.y = qy
                g.pose.pose.orientation.z = qz
                g.pose.pose.orientation.w = qw
            else:
                g.pose.pose.orientation.w = 1.0

            self.get_logger().info(f'Navigating to -> ({x:.3f}, {y:.3f}) [attempt={attempt}/{max_attempts}, mission_id={my_mission_id}, dist={dist:.2f}m]...')

            # Ensure any previous goal is cleared before sending
            if self.active_goal_handle is not None:
                try:
                    self.active_goal_handle.cancel_goal_async()
                except Exception:
                    pass
                self.active_goal_handle = None

            fh = self.nav.send_goal_async(g)

            # Wait for goal handle acceptance
            while not fh.done():
                if self.mission_id != my_mission_id or self.is_stopped:
                    return False
                time.sleep(0.05)

            gh = fh.result()
            if gh is None or not gh.accepted:
                self.get_logger().warn(f'Nav goal to ({x:.2f}, {y:.2f}) rejected by Nav2 (attempt {attempt}/{max_attempts}).')
                time.sleep(1.0)  # at most 1 Hz retry
                continue

            self.active_goal_handle = gh

            # Wait until goal is reached or aborted
            rr = gh.get_result_async()
            while not rr.done():
                if self.mission_id != my_mission_id or self.is_stopped:
                    try:
                        gh.cancel_goal_async()
                    except Exception:
                        pass
                    self.active_goal_handle = None
                    return False

                while self.is_paused and not self.is_stopped and self.mission_id == my_mission_id:
                    time.sleep(0.3)

                # Check if robot reached target while navigating
                current_dist = math.hypot(self.current_robot_pose[0] - x, self.current_robot_pose[1] - y)
                if current_dist <= target_tolerance:
                    self.get_logger().info(f'Robot reached ({x:.3f}, {y:.3f}) during motion [dist={current_dist:.2f}m <= {target_tolerance}m]')
                    try:
                        gh.cancel_goal_async()
                    except Exception:
                        pass
                    self.active_goal_handle = None
                    return True

                time.sleep(0.1)

            self.active_goal_handle = None
            result = rr.result()
            status = result.status if result else GoalStatus.STATUS_UNKNOWN

            dist = math.hypot(self.current_robot_pose[0] - x, self.current_robot_pose[1] - y)
            if status == GoalStatus.STATUS_SUCCEEDED or dist <= target_tolerance:
                self.get_logger().info(f'Goal reached: ({x:.3f}, {y:.3f}) [status={status}, dist={dist:.2f}m]')
                return True

            self.get_logger().warn(f'Nav attempt {attempt}/{max_attempts} ended (status={status}, dist={dist:.2f}m).')
            if attempt < max_attempts:
                # Rate limit re-send at most 1 Hz
                for _ in range(10):
                    if self.mission_id != my_mission_id or self.is_stopped:
                        return False
                    time.sleep(0.1)

        self.get_logger().warn(f'Waypoint ({x:.2f}, {y:.2f}) skipped after {max_attempts} attempts.')
        return False

    def spin(self, target_yaw=1.5708, timeout=30.0):
        my_mission_id = self.mission_id
        if not self.spin_client.wait_for_server(timeout_sec=3.0):
            return False

        if self.mission_id != my_mission_id or self.is_stopped:
            return False

        goal = Spin.Goal()
        goal.target_yaw = float(target_yaw)

        fh = self.spin_client.send_goal_async(goal)
        t0 = time.time()
        while not fh.done():
            if self.mission_id != my_mission_id or self.is_stopped:
                return False
            if time.time() - t0 > 5.0:
                return False
            time.sleep(0.05)

        gh = fh.result()
        if gh is None or not gh.accepted:
            return False

        self.active_goal_handle = gh
        rr = gh.get_result_async()
        t0 = time.time()
        while not rr.done():
            if self.mission_id != my_mission_id or self.is_stopped:
                try:
                    gh.cancel_goal_async()
                except Exception:
                    pass
                self.active_goal_handle = None
                return False
            if time.time() - t0 > timeout:
                try:
                    gh.cancel_goal_async()
                except Exception:
                    pass
                self.active_goal_handle = None
                return False
            time.sleep(0.1)

        self.active_goal_handle = None
        return rr.result().status == GoalStatus.STATUS_SUCCEEDED if rr.result() else False

    # ═══════════════════════════════════════════════════
    # Room Pipeline Execution (1: Door -> 2: Center -> 3..6: Tour Corners in order -> Waiting)
    # ═══════════════════════════════════════════════════
    def _run_room_pipeline(self, room_name, is_tour, mission_id):
        self.get_logger().info(f'[MISSION {mission_id}] Starting pipeline for target: {room_name}')

        # Handle RETURN HOME
        if room_name == 'Home':
            if self.home_pose is None:
                self.home_pose = (-11.883, 10.879, 0.0)

            hx, hy, hyaw = self.home_pose
            self.current_phase = "transit"
            self.total_waypoints = 1
            self.current_waypoint_idx = 1
            self.progress = 0.5
            self.get_logger().info(f'Navigating to HOME pose: ({hx:.2f}, {hy:.2f}, yaw={hyaw:.2f})...')

            ok = self.go(hx, hy, hyaw)
            if ok and self.mission_id == mission_id and not self.is_stopped:
                self.current_phase = "idle"
                self.progress = 1.0
                self.get_logger().info('Robot successfully returned to HOME.')
            return

        room_data = self.rooms.get(room_name)
        if not room_data:
            self.get_logger().warn(f'Room {room_name} not found in static definitions!')
            self.current_phase = "idle"
            return

        door = room_data.get('door', room_data.get('center'))
        center = room_data.get('center', door)
        tour = room_data.get('tour', [])

        door_x, door_y = float(door[0]), float(door[1])
        center_x, center_y = float(center[0]), float(center[1])

        num_tour_pts = len(tour)
        self.total_waypoints = 2 + num_tour_pts  # 1: Door, 2: Center, 3..2+N: Tour points
        self.current_waypoint_idx = 0
        self.progress = 0.0

        # ── 1. First Point: Door Point (Driving to room entrance) ──
        if self.mission_id != mission_id or self.is_stopped:
            return

        self.current_phase = "transit"
        self.current_waypoint_idx = 1
        self.progress = float(self.current_waypoint_idx) / self.total_waypoints
        self.get_logger().info(f'[{room_name}] STEP 1/{self.total_waypoints}: Navigating to DOOR ({door_x:.3f}, {door_y:.3f})...')

        ok = self.go(door_x, door_y)
        if not ok or self.mission_id != mission_id or self.is_stopped:
            return
        time.sleep(0.3)

        # ── Room Arrival Safety Check: Wait up to 30s if human is present before starting sweep ──
        if self.human_detected:
            self.get_logger().warn(f'[{room_name}] Arrived at room door, but human is present! Waiting up to 30s for area to clear (phase="held")...')
            self.current_phase = "held"
            t0 = time.time()
            while self.human_detected and not self.is_stopped and self.mission_id == mission_id:
                if time.time() - t0 > 30.0:
                    break
                time.sleep(0.5)

            if self.mission_id != mission_id or self.is_stopped:
                return

            if self.human_detected:
                self.get_logger().warn(f'[{room_name}] Human still present after 30s timeout — SKIPPING sweep step (UV BANNED). Proceeding...')
                self.current_phase = "waiting"
                self.progress = 1.0
                if is_tour:
                    time.sleep(1.5)
                    with self.thread_lock:
                        if self.goal_queue and self.mission_id == mission_id and not self.is_stopped:
                            next_room = self.goal_queue.popleft()
                            self._launch_thread(next_room, is_tour=True, mission_id=mission_id)
                        else:
                            self.is_tour_active = False
                return

        # ── 2. Second Point: Center Point ──
        if self.mission_id != mission_id or self.is_stopped:
            return

        self.current_phase = "sweeping"
        self.current_waypoint_idx = 2
        self.progress = float(self.current_waypoint_idx) / self.total_waypoints
        self.get_logger().info(f'[{room_name}] STEP 2/{self.total_waypoints}: Navigating to CENTER ({center_x:.3f}, {center_y:.3f})...')

        ok = self.go(center_x, center_y)
        if not ok or self.mission_id != mission_id or self.is_stopped:
            return
        time.sleep(0.3)

        # ── 3. Last Points: 4 Tour Points by order in rooms.json ──
        if num_tour_pts > 0:
            self.current_phase = "sweeping"
            for i, pt in enumerate(tour):
                if self.mission_id != mission_id or self.is_stopped:
                    return

                # If human enters during sweeping: hold and wait up to 30s
                if self.human_detected:
                    self.get_logger().warn(f'[{room_name}] Human entered during sweeping! Pausing sweep up to 30s (phase="held")...')
                    self.current_phase = "held"
                    self._stop_disinfection_internal()
                    t0 = time.time()
                    while self.human_detected and not self.is_stopped and self.mission_id == mission_id:
                        if time.time() - t0 > 30.0:
                            break
                        time.sleep(0.5)
                    if self.mission_id != mission_id or self.is_stopped:
                        return
                    if self.human_detected:
                        self.get_logger().warn(f'[{room_name}] Human still present during sweep — SKIPPING remaining sweep points.')
                        self.current_phase = "waiting"
                        self.progress = 1.0
                        if is_tour:
                            time.sleep(1.5)
                            with self.thread_lock:
                                if self.goal_queue and self.mission_id == mission_id and not self.is_stopped:
                                    next_room = self.goal_queue.popleft()
                                    self._launch_thread(next_room, is_tour=True, mission_id=mission_id)
                                else:
                                    self.is_tour_active = False
                        return

                self.current_phase = "sweeping"
                wx, wy = float(pt[0]), float(pt[1])
                self.current_waypoint_idx = 3 + i  # Waypoints 3, 4, 5, 6
                self.progress = float(self.current_waypoint_idx) / self.total_waypoints
                self.get_logger().info(f'[{room_name}] STEP {self.current_waypoint_idx}/{self.total_waypoints}: Navigating to tour corner {i+1}/{num_tour_pts} ({wx:.3f}, {wy:.3f})...')

                ok = self.go(wx, wy)
                if not ok or self.mission_id != mission_id or self.is_stopped:
                    return
                time.sleep(0.3)

        # ── Fallback Spin ONLY if room has NO tour points ──
        if num_tour_pts == 0:
            if self.mission_id != mission_id or self.is_stopped or self.human_detected:
                return
            self.current_phase = "sweeping"
            self.get_logger().info(f'[{room_name}] No tour points defined — executing fallback spin...')
            self.spin(6.2832, timeout=30.0)

        # ── 4. Set Phase to "waiting" ──
        if self.mission_id == mission_id and not self.is_stopped:
            self.current_phase = "waiting"
            self.progress = 1.0
            self.get_logger().info(f'[{room_name}] Room tour complete (door -> center -> {num_tour_pts} tour points). Phase -> waiting. Ready for next command.')

            if is_tour:
                time.sleep(1.5)
                with self.thread_lock:
                    if self.goal_queue and self.mission_id == mission_id and not self.is_stopped:
                        next_room = self.goal_queue.popleft()
                        self._launch_thread(next_room, is_tour=True, mission_id=mission_id)
                    else:
                        self.is_tour_active = False

    # ═══════════════════════════════════════════════════
    # Status Publisher
    # ═══════════════════════════════════════════════════
    def _publish_status(self):
        disinfection_running = False
        if self.disinfection_proc is not None:
            if self.disinfection_proc.poll() is None:
                disinfection_running = True

        data = {
            "room": self.current_room,
            "phase": self.current_phase,
            "progress": round(self.progress, 2),
            "waypoint": self.current_waypoint_idx,
            "total_waypoints": self.total_waypoints,
            "coverage": round(self.latest_coverage_pct, 1),
            "disinfection_running": disinfection_running,
            "home_x": round(self.home_pose[0], 3) if self.home_pose else -11.883,
            "home_y": round(self.home_pose[1], 3) if self.home_pose else 10.879,
            "home_yaw": round(self.home_pose[2], 3) if self.home_pose else 0.0
        }
        msg = String()
        msg.data = json.dumps(data)
        self.status_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = DisinfectionProcessNode()
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        if node.disinfection_proc is not None and node.disinfection_proc.poll() is None:
            try:
                pgid = os.getpgid(node.disinfection_proc.pid)
                os.killpg(pgid, signal.SIGTERM)
                try:
                    node.disinfection_proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(pgid, signal.SIGKILL)
            except Exception:
                pass
        if node.rviz_proc is not None and node.rviz_proc.poll() is None:
            try:
                pgid = os.getpgid(node.rviz_proc.pid)
                os.killpg(pgid, signal.SIGTERM)
                try:
                    node.rviz_proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(pgid, signal.SIGKILL)
            except Exception:
                pass
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
