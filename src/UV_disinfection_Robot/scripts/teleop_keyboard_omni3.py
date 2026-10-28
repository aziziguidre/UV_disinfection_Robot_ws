#!/usr/bin/env python3

import sys
import termios
import tty

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64MultiArray


MSG = """
Reading from the keyboard !
---------------------------
Moving around:
   u    i    o
   j    k    l
   m    ,    .

For Holonomic mode (strafing), hold down the shift key:
---------------------------
   U    I    O
   J    K    L
   M    <    >


anything else : stop

q/z : increase/decrease max speeds by 10%

CTRL-C to quit
"""

MOVE_BINDINGS = {
    'i': (-1, 0, 1),
    'o': (-1, 1, 0),
    'j': (1, 1, 1),
    'l': (-1, -1, -1),
    'u': (-1, 0, 1),
    ',': (1, 0, -1),
    '.': (0, 1, -1),
    'm': (1, -1, 0),
    'O': (-1, 1, 0),
    'I': (-1, 0, 1),
    'J': (1, -2, 1),
    'L': (-1, 2, -1),
    'U': (0, -1, 1),
    '<': (1, 0, -1),
    '>': (0, 1, -1),
    'M': (1, -1, 0),
}

SPEED_BINDINGS = {
    'q': (1.1, 1.1),
    'z': (0.9, 0.9),
}


class TeleopKeyboardOmni3Node(Node):
    def __init__(self):
        super().__init__('teleop_keyboard_omni3')

        # Publishers for ROS 2 controllers (/left_joint_velocity_controller/commands)
        self.pub_left_ros2 = self.create_publisher(
            Float64MultiArray, '/left_joint_velocity_controller/commands', 10)
        self.pub_back_ros2 = self.create_publisher(
            Float64MultiArray, '/back_joint_velocity_controller/commands', 10)
        self.pub_right_ros2 = self.create_publisher(
            Float64MultiArray, '/right_joint_velocity_controller/commands', 10)

        # Legacy publishers (/chiron_uv/left_joint_velocity_controller/command)
        self.pub_left_legacy = self.create_publisher(
            Float64MultiArray, '/chiron_uv/left_joint_velocity_controller/command', 10)
        self.pub_back_legacy = self.create_publisher(
            Float64MultiArray, '/chiron_uv/back_joint_velocity_controller/command', 10)
        self.pub_right_legacy = self.create_publisher(
            Float64MultiArray, '/chiron_uv/right_joint_velocity_controller/command', 10)

    def publish_vels(self, vl, vb, vr):
        msg_l = Float64MultiArray(data=[float(vl)])
        msg_b = Float64MultiArray(data=[float(vb)])
        msg_r = Float64MultiArray(data=[float(vr)])

        self.pub_left_ros2.publish(msg_l)
        self.pub_back_ros2.publish(msg_b)
        self.pub_right_ros2.publish(msg_r)

        self.pub_left_legacy.publish(msg_l)
        self.pub_back_legacy.publish(msg_b)
        self.pub_right_legacy.publish(msg_r)


def get_key(settings):
    tty.setraw(sys.stdin.fileno())
    key = sys.stdin.read(1)
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)
    return key


def vels(speed):
    return f'currently:\tspeed {speed} '


def main(args=None):
    settings = termios.tcgetattr(sys.stdin)

    rclpy.init(args=args)
    node = TeleopKeyboardOmni3Node()

    speed = 1.0
    x = 0
    y = 0
    z = 0
    status = 0

    try:
        print(MSG)
        print(vels(speed))
        while True:
            key = get_key(settings)
            if key in MOVE_BINDINGS:
                x = MOVE_BINDINGS[key][0]
                y = MOVE_BINDINGS[key][1]
                z = MOVE_BINDINGS[key][2]
            elif key in SPEED_BINDINGS:
                speed = speed * SPEED_BINDINGS[key][0]
                print(vels(speed))
                if status == 14:
                    print(MSG)
                status = (status + 1) % 15
            else:
                x = 0
                y = 0
                z = 0
                if key == '\x03':
                    break

            vell = x * speed
            velb = y * speed
            velr = z * speed

            node.publish_vels(vell, velb, velr)

    except Exception as e:
        print(e)

    finally:
        node.publish_vels(0.0, 0.0, 0.0)

        node.destroy_node()
        rclpy.try_shutdown()
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)


if __name__ == '__main__':
    main()
