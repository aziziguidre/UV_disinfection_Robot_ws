#!/usr/bin/env python3
"""Ground-truth odometry from gazebo_ros_p3d (/odom_gt). Exact, no drift."""
import math
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import TransformStamped, Quaternion
from nav_msgs.msg import Odometry
import tf2_ros

SPAWN_X, SPAWN_Y, SPAWN_YAW = -11.883, 10.879, 0.0

class GTOdom(Node):
    def __init__(self):
        super().__init__('odom_pub')
        self.spawn_x = float(self.declare_parameter('spawn_x', SPAWN_X).value)
        self.spawn_y = float(self.declare_parameter('spawn_y', SPAWN_Y).value)
        self.spawn_yaw = float(self.declare_parameter('spawn_yaw', SPAWN_YAW).value)
        self.tf = tf2_ros.TransformBroadcaster(self)
        self.odom_pub = self.create_publisher(Odometry, '/odom', 10)
        self.create_subscription(Odometry, '/odom_gt', self.gt_cb, 10)
        self.create_timer(0.02, self.timer_cb)
        self.have = False
        self.last_t = None

    def gt_cb(self, msg):
        p = msg.pose.pose.position
        q = msg.pose.pose.orientation
        yaw = math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))
        now = self.get_clock().now()
        if self.have and self.last_t is not None:
            dt = (now - self.last_t).nanoseconds / 1e9
            if dt > 1e-4:
                self.vx_w = (p.x - self.x_w) / dt
                self.vy_w = (p.y - self.y_w) / dt
                self.wz = (yaw - self.yaw_w) / dt
        else:
            self.vx_w = self.vy_w = self.wz = 0.0
        self.x_w, self.y_w, self.yaw_w = p.x, p.y, yaw
        self.last_t = now
        self.x = p.x - self.spawn_x
        self.y = p.y - self.spawn_y
        self.yaw = yaw - self.spawn_yaw
        self.have = True

    def timer_cb(self):
        if not self.have:
            return
        now = self.get_clock().now()
        q = Quaternion(x=0.0, y=0.0, z=math.sin(self.yaw / 2), w=math.cos(self.yaw / 2))
        t = TransformStamped()
        t.header.stamp = now.to_msg()
        t.header.frame_id = 'odom'
        t.child_frame_id = 'origin_link'
        t.transform.translation.x = self.x
        t.transform.translation.y = self.y
        t.transform.rotation = q
        self.tf.sendTransform(t)

        nose = (-math.sin(self.yaw), math.cos(self.yaw))
        left = (-math.cos(self.yaw), -math.sin(self.yaw))
        o = Odometry()
        o.header = t.header
        o.child_frame_id = 'origin_link'
        o.pose.pose.position.x = self.x
        o.pose.pose.position.y = self.y
        o.pose.pose.orientation = q
        o.twist.twist.linear.x = self.vx_w * nose[0] + self.vy_w * nose[1]
        o.twist.twist.linear.y = self.vx_w * left[0] + self.vy_w * left[1]
        o.twist.twist.angular.z = self.wz
        self.odom_pub.publish(o)

def main():
    rclpy.init()
    n = GTOdom()
    try:
        rclpy.spin(n)
    except KeyboardInterrupt:
        pass
    finally:
        n.destroy_node()
        rclpy.try_shutdown()

if __name__ == '__main__':
    main()
