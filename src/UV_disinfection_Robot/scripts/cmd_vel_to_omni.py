#!/usr/bin/env python3

"""
CmdVel to Omniwheel Velocity Converter Node.
Maps Nav2's X-forward commands to the robot's physical Y-forward axes.
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import Float64MultiArray

class CmdVelToOmniNode(Node):
    def __init__(self):
        super().__init__('cmd_vel_to_omni', automatically_declare_parameters_from_overrides=True)
        
        # Subscribe to Nav2 velocity commands
        self.create_subscription(Twist, '/cmd_vel', self.cmd_vel_callback, 10)
        
        # Wheel Velocity Controller Publishers
        self.pub_left_ros2 = self.create_publisher(Float64MultiArray, '/left_joint_velocity_controller/commands', 10)
        self.pub_back_ros2 = self.create_publisher(Float64MultiArray, '/back_joint_velocity_controller/commands', 10)
        self.pub_right_ros2 = self.create_publisher(Float64MultiArray, '/right_joint_velocity_controller/commands', 10)
        
        self.get_logger().info('CmdVel to Omniwheel Converter Node initialized.')

    def cmd_vel_callback(self, msg: Twist):
        vx = msg.linear.x
        vy = msg.linear.y
        wz = msg.angular.z

        # Omniwheel kinematic transformation
        scale = 100.0
        L = 0.14
        v_left = (-0.866025 * vx + 0.5 * vy + L * wz) * scale
        v_back = (-vy + L * wz) * scale
        v_right = (0.866025 * vx + 0.5 * vy + L * wz) * scale

        msg_l = Float64MultiArray(data=[float(v_left)])
        msg_b = Float64MultiArray(data=[float(v_back)])
        msg_r = Float64MultiArray(data=[float(v_right)])

        self.pub_left_ros2.publish(msg_l)
        self.pub_back_ros2.publish(msg_b)
        self.pub_right_ros2.publish(msg_r)

def main(args=None):
    rclpy.init(args=args)
    node = CmdVelToOmniNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()

if __name__ == '__main__':
    main()
