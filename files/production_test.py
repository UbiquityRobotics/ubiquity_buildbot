#!/usr/bin/env python3

# python script that is used for testing robots in production. Running this script
# successfully means that hardware and software work. This lives on firmware images
# and sends simple goals to robot to go forward and then turn

import rospy
import time
import math

from geometry_msgs.msg import PoseStamped, TransformStamped, Twist, Vector3Stamped
from nav_msgs.msg import Odometry
from tf.transformations import quaternion_from_euler, euler_from_quaternion

pub = rospy.Publisher('/move_base_simple/goal', PoseStamped, queue_size=1, latch=True)
rospy.init_node('test_motors', anonymous=False)
rospy.wait_for_message('/odom', Odometry)

goal = PoseStamped()
goal.pose.position.x = 0.5
goal.pose.position.y = 0.0
goal.pose.position.z = 0.0

q_rot = quaternion_from_euler(0, 0, -math.radians(180))
goal.pose.orientation.x = q_rot[0]
goal.pose.orientation.y = q_rot[1]
goal.pose.orientation.z = q_rot[2]
goal.pose.orientation.w = q_rot[3]
goal.header.frame_id = "base_link"
goal.header.stamp = rospy.Time.now()

print(goal)

pub.publish(goal)
rospy.sleep(10)