#!/usr/bin/env python3
"""human_detector.py — YOLOv8 person detector (robot-mania style).
Subscribes camera image, publishes:
  /uvrobot/human_detected (Bool), /uvrobot/human_count (Int32),
  /uvrobot/yolo_image (annotated image with person boxes)."""
import threading
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import Bool, Int32
from cv_bridge import CvBridge
import cv2
from ultralytics import YOLO

class YoloHumanDetector(Node):
    def __init__(self):
        super().__init__('human_detector')
        self.declare_parameter('image_topic', '/camera/image_raw')
        self.declare_parameter('model', 'yolov8n.pt')
        self.declare_parameter('conf', 0.30)
        self.declare_parameter('imgsz', 320)
        self.declare_parameter('every_n_frames', 3)
        topic = self.get_parameter('image_topic').value
        self.conf = float(self.get_parameter('conf').value)
        self.imgsz = int(self.get_parameter('imgsz').value)
        self.every_n = int(self.get_parameter('every_n_frames').value)
        self.model = YOLO(self.get_parameter('model').value)   # downloads once
        self.bridge = CvBridge()
        self.frame_i = 0
        self.busy = False
        self.create_subscription(Image, topic, self.cb, 10)
        self.pub_det = self.create_publisher(Bool, '/uvrobot/human_detected', 10)
        self.pub_cnt = self.create_publisher(Int32, '/uvrobot/human_count', 10)
        self.pub_img = self.create_publisher(Image, '/uvrobot/yolo_image', 10)
        self.get_logger().info(f'YOLOv8 human detector on {topic} ready.')

    def cb(self, msg):
        self.frame_i += 1
        if self.frame_i % self.every_n != 0 or self.busy:
            return
        self.busy = True
        threading.Thread(target=self.infer, args=(msg,), daemon=True).start()

    def infer(self, msg):
        try:
            cv_img = self.bridge.imgmsg_to_cv2(msg, 'bgr8')
            r = self.model(cv_img, conf=self.conf, imgsz=self.imgsz, verbose=False)[0]
            n = 0
            for box in r.boxes:
                if int(box.cls[0]) == 0:                      # COCO class 0 = person
                    n += 1
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    cv2.rectangle(cv_img, (x1, y1), (x2, y2), (0, 0, 255), 2)
                    cv2.putText(cv_img, f'person {float(box.conf[0]):.2f}',
                                (x1, max(12, y1 - 6)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            det = Bool(); det.data = n > 0; self.pub_det.publish(det)
            cnt = Int32(); cnt.data = n; self.pub_cnt.publish(cnt)
            out = self.bridge.cv2_to_imgmsg(cv_img, 'bgr8')
            out.header = msg.header
            self.pub_img.publish(out)
            if n: self.get_logger().info(f'PERSONS DETECTED: {n}')
        except Exception as e:
            self.get_logger().warn(f'yolo error: {e}')
        finally:
            self.busy = False

def main():
    rclpy.init()
    node = YoloHumanDetector()
    try: rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally:
        node.destroy_node(); rclpy.try_shutdown()

if __name__ == '__main__':
    main()
