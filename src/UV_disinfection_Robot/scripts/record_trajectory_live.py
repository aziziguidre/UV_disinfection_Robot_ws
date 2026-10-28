#!/usr/bin/env python3
"""
Script d'enregistrement et de tracé en direct de la trajectoire pour CHIRON-UV.
Écoute simultanément :
  - /odom_gt (nav_msgs/Odometry) : Vérité-terrain Gazebo
  - /amcl_pose (geometry_msgs/PoseWithCovarianceStamped) ou /pose (SLAM)
Génère automatiquement la figure haute résolution dans rapport_latex/figures/
"""

import os
import sys
import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry
from geometry_msgs.msg import PoseWithCovarianceStamped, PoseStamped
import numpy as np
import matplotlib.pyplot as plt

class TrajectoryRecorderNode(Node):
    def __init__(self):
        super().__init__('trajectory_recorder_node')
        
        self.gt_x, self.gt_y = [], []
        self.est_x, self.est_y = [], []
        
        # Souscription à la vérité terrain Gazebo P3D
        self.sub_gt = self.create_subscription(
            Odometry,
            '/odom_gt',
            self.gt_callback,
            10
        )
        
        # Souscription à la pose estimée AMCL
        self.sub_amcl = self.create_subscription(
            PoseWithCovarianceStamped,
            '/amcl_pose',
            self.amcl_callback,
            10
        )

        self.get_logger().info("="*60)
        self.get_logger().info("Enregistreur de Trajectoire CHIRON-UV Actif")
        self.get_logger().info("Téléopérez le robot ou lancez une navigation Nav2.")
        self.get_logger().info("Appuyez sur Ctrl+C pour arrêter et générer la figure.")
        self.get_logger().info("="*60)

    def gt_callback(self, msg):
        self.gt_x.append(msg.pose.pose.position.x)
        self.gt_y.append(msg.pose.pose.position.y)

    def amcl_callback(self, msg):
        self.est_x.append(msg.pose.pose.position.x)
        self.est_y.append(msg.pose.pose.position.y)

    def save_and_plot(self):
        if len(self.gt_x) < 5 or len(self.est_x) < 5:
            self.get_logger().warn("Pas assez de points enregistrés pour tracer la courbe.")
            return

        out_dir = os.path.expanduser('~/ros2_UV_disinfection_Robot_ws/rapport_latex/figures')
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, 'trajectory_comparison.png')

        fig, ax = plt.subplots(figsize=(10, 7), dpi=300)
        
        # Tracé vérité terrain
        ax.plot(self.gt_x, self.gt_y, color='#111111', linestyle='-', linewidth=2.0, label='Vérité-Terrain (Gazebo /odom_gt)')
        # Tracé estimation
        ax.plot(self.est_x, self.est_y, color='#0D9488', linestyle='--', linewidth=1.8, dashes=(4, 2), label='Estimation (SLAM / AMCL)')

        # Point de départ
        ax.scatter([self.gt_x[0]], [self.gt_y[0]], color='#1B365D', s=120, marker='s', label='Point de départ')

        ax.set_title("Comparaison de la Trajectoire Réelle vs Estimée (CHIRON-UV)", fontsize=13, fontweight='bold', color='#1B365D')
        ax.set_xlabel("X (mètres)", fontsize=11, fontweight='bold')
        ax.set_ylabel("Y (mètres)", fontsize=11, fontweight='bold')
        ax.grid(True, linestyle=':', color='gray', alpha=0.6)
        ax.set_facecolor('#F8FAFC')
        ax.legend(loc='upper right', frameon=True, facecolor='white', edgecolor='#1B365D')
        ax.set_aspect('equal', adjustable='box')

        plt.tight_layout()
        plt.savefig(out_path, dpi=300, bbox_inches='tight')
        self.get_logger().info(f"[SUCCÈS] Graphique généré dans : {out_path}")

def main():
    rclpy.init()
    node = TrajectoryRecorderNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("Arrêt de l'enregistrement. Génération du graphique...")
        node.save_and_plot()
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
