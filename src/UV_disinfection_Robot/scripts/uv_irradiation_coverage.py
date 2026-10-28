#!/usr/bin/env python3

import math, struct, numpy as np
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Point, Vector3, PoseWithCovarianceStamped
from sensor_msgs.msg import PointCloud2, PointField
from nav_msgs.msg import OccupancyGrid, MapMetaData
from std_msgs.msg import Header, String, ColorRGBA, Empty, Bool
from visualization_msgs.msg import Marker, MarkerArray

# ── Viridis palette (9 stops, same as v4) ──────────────────────────────────
VIRIDIS = [
    (0.267, 0.004, 0.329), (0.282, 0.157, 0.471), (0.243, 0.286, 0.537),
    (0.192, 0.408, 0.557), (0.149, 0.510, 0.557), (0.122, 0.620, 0.537),
    (0.208, 0.718, 0.475), (0.431, 0.808, 0.345), (0.992, 0.906, 0.145),
]
# "Done" colour: orange-red (same as v4)
DONE_RGB = (0.94, 0.36, 0.14)

# Map viridis stop index → OccupancyGrid value (1-98), done → 99
# We'll encode dose → [1..99] in the OccupancyGrid and use a custom colour
# scheme in RViz (or publish a ColourOccupancyGrid via rviz_satellite / image).
# Strategy: OccupancyGrid stores a uint8 "dose index" (0=unknown/unseen,
# 1-98=viridis gradient, 99=target reached).  In RViz, set the colour scheme
# to "costmap" and tweak, OR subscribe to /uvrobot/dose_image (sensor_msgs/Image,
# RGBA8) which is the exact pixel-perfect heatmap shown in the GIF.

from sensor_msgs.msg import Image


def viridis_rgba(t: float):
    """t in [0,1] → (r,g,b,a) floats."""
    t = max(0.0, min(1.0, t))
    x = t * (len(VIRIDIS) - 1)
    i = int(x); f = x - i
    c0 = VIRIDIS[i]; c1 = VIRIDIS[min(i + 1, len(VIRIDIS) - 1)]
    return (c0[0] + (c1[0] - c0[0]) * f,
            c0[1] + (c1[1] - c0[1]) * f,
            c0[2] + (c1[2] - c0[2]) * f, 1.0)


def dose_color(dose, target):
    t = dose / target
    if t >= 1.0:
        return (*DONE_RGB, 1.0)
    return viridis_rgba(t)


class UVDoseMapNode(Node):
    def __init__(self):
        super().__init__('uv_irradiation_coverage')

        # ── Parameters ────────────────────────────────────────────────────
        self.declare_parameter('voxel_size',   0.08)
        self.declare_parameter('uv_power',     800.0)
        self.declare_parameter('target_dose',  12.0)
        self.declare_parameter('frame_id',     'map')
        self.declare_parameter('max_range',    4.5)

        self.res         = max(0.02, self.get_parameter('voxel_size').value)
        self.uv_power    = self.get_parameter('uv_power').value
        self.target_dose = self.get_parameter('target_dose').value
        self.frame_id    = self.get_parameter('frame_id').value
        self.max_range   = float(self.get_parameter('max_range').value)

        # ── State ─────────────────────────────────────────────────────────
        self.robot_x = self.robot_y = self.robot_yaw = 0.0
        self.voxel_grid  = {}   # (ix,iy,iz) → dose  (3-D, walls + floor)
        self.floor_dose  = {}   # (ix,iy)    → dose  (2-D projection, heatmap)
        self.gmap        = None
        self.last_header_stamp = None
        self.human_detected    = False

        # ── Publishers ────────────────────────────────────────────────────
        self.pub_cloud   = self.create_publisher(PointCloud2,  '/uvrobot/irradiation_map',     10)
        self.pub_markers = self.create_publisher(MarkerArray,  '/uvrobot/irradiation_markers', 10)
        self.pub_stats   = self.create_publisher(String,       '/uvrobot/disinfection_stats',  10)
        # ★ NEW – 2-D heatmap topics
        self.pub_heatmap = self.create_publisher(OccupancyGrid, '/uvrobot/dose_heatmap_2d',   10)
        self.pub_image   = self.create_publisher(Image,         '/uvrobot/dose_image',         10)

        # ── Subscribers ───────────────────────────────────────────────────
        self.create_subscription(PointCloud2,              '/octomap_point_cloud_centers', self.centers_cb, 10)
        self.create_subscription(PoseWithCovarianceStamped, '/amcl_pose',                 self.pose_cb,    10)
        self.create_subscription(OccupancyGrid,            '/map_gt',                     self.map_cb,     10)
        self.create_subscription(Bool,                     '/uvrobot/human_detected',     self.human_cb,   10)
        self.create_subscription(Empty,                    '/disinfection/stop_server',   self.stop_empty_cb, 10)
        self.create_subscription(Bool,                     '/disinfection/stop',          self.stop_bool_cb,  10)

        self.create_timer(0.5, self.publish_loop)
        self.get_logger().info('SOCA Dose Server v5 (octomap walls + 2-D heatmap) ready.')

    # ── Callbacks ─────────────────────────────────────────────────────────
    def human_cb(self, msg):      self.human_detected = bool(msg.data)
    def stop_empty_cb(self, msg): rclpy.try_shutdown()
    def stop_bool_cb(self, msg):
        if msg.data: rclpy.try_shutdown()

    def pose_cb(self, msg):
        self.robot_x = msg.pose.pose.position.x
        self.robot_y = msg.pose.pose.position.y
        o = msg.pose.pose.orientation
        self.robot_yaw = math.atan2(
            2.0 * (o.w * o.z + o.x * o.y),
            1.0 - 2.0 * (o.y * o.y + o.z * o.z))

    def map_cb(self, msg):
        self.gmap = msg.data
        self.gw   = msg.info.width
        self.gh   = msg.info.height
        self.gres = msg.info.resolution
        self.gox  = msg.info.origin.position.x
        self.goy  = msg.info.origin.position.y
        self.get_logger().info('GT map loaded for floor painting.')

    # ── Helpers ───────────────────────────────────────────────────────────
    def _free(self, x, y):
        j = int((x - self.gox) / self.gres)
        i = int((y - self.goy) / self.gres)
        if not (0 <= i < self.gh and 0 <= j < self.gw):
            return False
        v = self.gmap[i * self.gw + j]
        return 0 <= v <= 40

    def get_sources(self):
        c, s = math.cos(self.robot_yaw), math.sin(self.robot_yaw)
        return [(self.robot_x + dx * c - dy * s,
                 self.robot_y + dx * s + dy * c,
                 0.05 + dz)
                for dx, dy, dz in [(0, 0.065, 0.65), (0, -0.065, 0.65),
                                   (0.065, 0, 0.65), (-0.065, 0, 0.65)]]

    def irr(self, d2):
        return min(self.uv_power / (4.0 * math.pi * (d2 + 0.25)), 40.0)

    # ── Floor dose (radial ray cast) ──────────────────────────────────────
    def dose_floor(self, dt):
        if self.human_detected or self.gmap is None:
            return
        rx, ry   = self.robot_x, self.robot_y
        sources  = self.get_sources()
        res      = self.res
        kz       = int(math.floor(0.06 / res))

        for a in range(0, 360, 2):
            ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
            t = 0.15
            while t <= self.max_range:
                x = rx + ca * t
                y = ry + sa * t
                if not self._free(x, y):
                    break
                add = sum(self.irr((x - sx)**2 + (y - sy)**2 + (0.06 - sz)**2)
                          for sx, sy, sz in sources)
                ix, iy = int(math.floor(x / res)), int(math.floor(y / res))
                key3   = (ix, iy, kz)
                dose_add = add * dt
                self.voxel_grid[key3]  = self.voxel_grid.get(key3, 0.0)  + dose_add
                # ★ accumulate into the 2-D floor dict as well
                self.floor_dose[(ix, iy)] = self.floor_dose.get((ix, iy), 0.0) + dose_add
                t += 0.06

    # ── Octomap callback (wall/object surfaces) ───────────────────────────
    def centers_cb(self, msg):
        if self.human_detected:
            return
        stamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        if not hasattr(self, 'last_stamp'):
            self.last_stamp = stamp
            self.last_header_stamp = msg.header.stamp
            return
        dt = stamp - self.last_stamp
        self.last_stamp = stamp
        self.last_header_stamp = msg.header.stamp
        if dt <= 0.0 or dt > 2.0:
            dt = 0.3

        sources = self.get_sources()
        res     = self.res
        off     = {f.name: f.offset for f in msg.fields}
        ox_, oy_, oz_ = off.get('x', 0), off.get('y', 4), off.get('z', 8)
        st, data = msg.point_step, msg.data
        cutoff   = 0.95 * self.max_range

        for i in range(0, len(data) - st + 1, st):
            wx = struct.unpack_from('f', data, i + ox_)[0]
            wy = struct.unpack_from('f', data, i + oy_)[0]
            wz = struct.unpack_from('f', data, i + oz_)[0]
            if not (math.isfinite(wx) and math.isfinite(wy) and math.isfinite(wz)):
                continue
            if math.hypot(wx - self.robot_x, wy - self.robot_y) >= cutoff:
                continue
            key = (int(math.floor(wx / res)),
                   int(math.floor(wy / res)),
                   int(math.floor(wz / res)))
            add = sum(self.irr((wx - sx)**2 + (wy - sy)**2 + (wz - sz)**2)
                      for sx, sy, sz in sources)
            self.voxel_grid[key] = self.voxel_grid.get(key, 0.0) + add * dt

    # ── Publish ───────────────────────────────────────────────────────────
    def publish_loop(self):
        self.dose_floor(0.5)

        header = Header()
        header.stamp    = self.last_header_stamp or self.get_clock().now().to_msg()
        header.frame_id = self.frame_id

        # ── 1. Stats ──────────────────────────────────────────────────────
        if not self.voxel_grid:
            msg = String(); msg.data = 'Disinfected: 0.0% (0/0)'
            self.pub_stats.publish(msg)
            return

        done  = sum(1 for v in self.voxel_grid.values() if v >= self.target_dose)
        total = len(self.voxel_grid)
        pct   = min(100.0, 100.0 * done / max(1, total))
        msg   = String(); msg.data = f'Disinfected: {pct:.1f}% ({done}/{total})'
        self.pub_stats.publish(msg)
        self.get_logger().info(
            f'Surface disinfected: {pct:.1f}% ({done}/{total} | target={self.target_dose} J/m²)')

        res = self.res

        # ── 2. 3-D PointCloud2 + MarkerArray (unchanged from v4) ─────────
        fields = [PointField(name='x',   offset=0,  datatype=PointField.FLOAT32, count=1),
                  PointField(name='y',   offset=4,  datatype=PointField.FLOAT32, count=1),
                  PointField(name='z',   offset=8,  datatype=PointField.FLOAT32, count=1),
                  PointField(name='rgb', offset=12, datatype=PointField.FLOAT32, count=1)]
        m       = Marker(); m.header = header; m.ns = 'uv_voxels'; m.id = 0
        m.type  = Marker.CUBE_LIST; m.action = Marker.ADD
        m.scale = Vector3(x=res * 0.95, y=res * 0.95, z=res * 0.95)
        m.pose.orientation.w = 1.0
        cb = []
        for (vx, vy, vz), dose in self.voxel_grid.items():
            px, py, pz = (vx + 0.5) * res, (vy + 0.5) * res, (vz + 0.5) * res
            rf, gf, bf, af = dose_color(dose, self.target_dose)
            rgb = (int(rf * 255) << 16) | (int(gf * 255) << 8) | int(bf * 255)
            cb.append(struct.pack('ffff', px, py, pz,
                                  struct.unpack('f', struct.pack('I', rgb))[0]))
            m.points.append(Point(x=px, y=py, z=pz))
            m.colors.append(ColorRGBA(r=rf, g=gf, b=bf, a=af))
        pc2 = PointCloud2(header=header, height=1, width=len(cb),
                          is_dense=True, is_bigendian=False,
                          fields=fields, point_step=16,
                          row_step=16 * len(cb), data=b''.join(cb))
        self.pub_cloud.publish(pc2)
        ma = MarkerArray(); ma.markers.append(m)
        self.pub_markers.publish(ma)

        # ── 3. ★ 2-D heatmap (OccupancyGrid + RGBA Image) ─────────────────
        self._publish_2d_heatmap(header)

    # ─────────────────────────────────────────────────────────────────────
    def _publish_2d_heatmap(self, header):
        """Build a flat 2-D heatmap from floor_dose and publish it as:
        a) OccupancyGrid  → /uvrobot/dose_heatmap_2d   (value 0-100)
        b) sensor_msgs/Image (RGBA8) → /uvrobot/dose_image  (exact colour)
        """
        if not self.floor_dose:
            return

        res  = self.res
        keys = list(self.floor_dose.keys())
        xs   = [k[0] for k in keys]
        ys   = [k[1] for k in keys]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        w = max_x - min_x + 1   # grid width  (cells)
        h = max_y - min_y + 1   # grid height (cells)

        # ── OccupancyGrid ─────────────────────────────────────────────────
        og             = OccupancyGrid()
        og.header      = header
        og.info.resolution     = res
        og.info.width          = w
        og.info.height         = h
        og.info.origin.position.x = min_x * res
        og.info.origin.position.y = min_y * res
        og.info.origin.orientation.w = 1.0

        data_occ = [-1] * (w * h)   # -1 = unknown
        for (ix, iy), dose in self.floor_dose.items():
            col = ix - min_x
            row = iy - min_y
            idx = row * w + col
            # Map dose to 0-100: 0=no dose, 100=target reached
            val = min(100, int(100.0 * dose / self.target_dose))
            data_occ[idx] = val
        og.data = data_occ
        self.pub_heatmap.publish(og)

        # ── RGBA Image (pixel-perfect viridis heatmap) ────────────────────
        # Each pixel = 4 bytes RGBA.  Row 0 = bottom of map (ROS convention).
        img_data = bytearray(h * w * 4)
        for (ix, iy), dose in self.floor_dose.items():
            col = ix - min_x
            row = iy - min_y          # row 0 = min_y (south)
            rf, gf, bf, af = dose_color(dose, self.target_dose)
            base = (row * w + col) * 4
            img_data[base]     = int(rf * 255)
            img_data[base + 1] = int(gf * 255)
            img_data[base + 2] = int(bf * 255)
            img_data[base + 3] = 220           # slight transparency

        img              = Image()
        img.header       = header
        img.height       = h
        img.width        = w
        img.encoding     = 'rgba8'
        img.is_bigendian = False
        img.step         = w * 4
        img.data         = bytes(img_data)
        self.pub_image.publish(img)


# ── Entry point ───────────────────────────────────────────────────────────
def main(args=None):
    rclpy.init(args=args)
    node = UVDoseMapNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        try:   node.destroy_node()
        except Exception: pass
        rclpy.try_shutdown()

if __name__ == '__main__':
    main()
