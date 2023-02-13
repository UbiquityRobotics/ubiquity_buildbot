import linux_util
import shutil

def install_packages():

	linux_util.run_as_user(
		"ubuntu",
		["bash", "-c", "git clone https://github.com/UbiquityRobotics/magni_robot.git"],
		cwd="/home/ubuntu/catkin_ws/src",
		check=True,
	)

	shutil.copy("/home/ubuntu/catkin_ws/src/magni_robot/magni_bringup/config/default_robot.yaml", "/etc/ubiquity/robot.yaml")

	linux_util.run_as_user(
		"ubuntu",
		["bash", "-c", "git clone https://github.com/UbiquityRobotics/ubiquity_motor.git"],
		cwd="/home/ubuntu/catkin_ws/src",
		check=True,
	)

	linux_util.run_as_user(
		"ubuntu",
		["bash", "-c", "git clone https://github.com/UbiquityRobotics/oled_display_node.git"],
		cwd="/home/ubuntu/catkin_ws/src",
		check=True,
	)

	return

def compile():

	linux_util.run_as_user(
		"ubuntu",
		["bash", "-c", "source /opt/ros/noetic/setup.bash && catkin_make -j1"],
		cwd="/home/ubuntu/catkin_ws",
		check=True,
	)

	return