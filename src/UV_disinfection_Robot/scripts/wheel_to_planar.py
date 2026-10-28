#!/usr/bin/env python3

"""
Wheel Commands to Planar Move Converter Node.
Subscribes to joint velocity controller commands for 3 omniwheels,
computes physical body Twist, and publishes to /cmd_vel_phys.
If no wheel command arrived within 0.3 s, sets wl=wb=wr=0 (publishes zero Twist).
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64MultiArray
from geometry_msgs.msg import Twist

class WheelToPlanarNode(Node):
    def __init__(self):
        super().__init__('wheel_to_planar', automatically_declare_parameters_from_overrides=True)
        
        self.w_left = 0.0
        self.w_back = 0.0
        self.w_right = 0.0

        self.last_left_time = self.get_clock().now()
        self.last_back_time = self.get_clock().now()
        self.last_right_time = self.get_clock().now()

        self.create_subscription(Float64MultiArray, '/left_joint_velocity_controller/commands', self.left_cb, 10)
        self.create_subscription(Float64MultiArray, '/back_joint_velocity_controller/commands', self.back_cb, 10)
        self.create_subscription(Float64MultiArray, '/right_joint_velocity_controller/commands', self.right_cb, 10)

        self.pub_cmd_vel_phys = self.create_publisher(Twist, '/cmd_vel_phys', 10)

        self.create_timer(0.02, self.timer_callback)
        self.get_logger().info('Wheel to Planar Move Converter Node initialized.')

    def left_cb(self, msg: Float64MultiArray):
        if msg.data:
            self.w_left = float(msg.data[0])
            self.last_left_time = self.get_clock().now()

    def back_cb(self, msg: Float64MultiArray):
        if msg.data:
            self.w_back = float(msg.data[0])
            self.last_back_time = self.get_clock().now()

    def right_cb(self, msg: Float64MultiArray):
        if msg.data:
            self.w_right = float(msg.data[0])
            self.last_right_time = self.get_clock().now()

    def timer_callback(self):
        now = self.get_clock().now()
        dt_left = (now - self.last_left_time).nanoseconds / 1e9
        dt_back = (now - self.last_back_time).nanoseconds / 1e9
        dt_right = (now - self.last_right_time).nanoseconds / 1e9

        if dt_left > 0.3 or dt_back > 0.3 or dt_right > 0.3:
            wl = 0.0
            wb = 0.0
            wr = 0.0
        else:
            wl = self.w_left
            wb = self.w_back
            wr = self.w_right

        r_wheel = 0.05
        L = 0.14

        vl = wl * r_wheel
        vb = wb * r_wheel
        vr = wr * r_wheel

        vx = (vr - vl) / 1.73205
        vy = (vl + vr - 2.0 * vb) / 3.0
        wz = (vl + vb + vr) / (3.0 * L)

        twist = Twist()
        twist.linear.x = float(-vy)
        twist.linear.y = float(vx)
        twist.linear.z = 0.0
        twist.angular.x = 0.0
        twist.angular.y = 0.0
        twist.angular.z = float(wz)

        self.pub_cmd_vel_phys.publish(twist)

def main(args=None):
    rclpy.init(args=args)
    node = WheelToPlanarNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()

if __name__ == '__main__':
    main()
