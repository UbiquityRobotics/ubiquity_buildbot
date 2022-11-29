
import shutil
from common_img_mods import gdm3_mod
import subprocess
import linux_util
import os

class customizeImage:
	def __init__(self):

		# there needs to exist a dictionary with name "conf" the following variables:
		# "hostname": hostname that the image is going to have setup.
		# "rootfs_extra_space_mb": how much more space will be allocated in rootfs in generated image.
		# "rootfs": absolute path on buildbot filesystem where generated rootfs will be saved (if unsure what this is, leave unchanged)
		# "flavour": flavour of generated image. The name of generated image will be: ${timestamp}-${flavour}-${release}-raspberry-pi.img
		# "release": release of the generated image. Currently only possible value is "focal".
		# "imagedir": absolute path on buildbot filesystem where generated image will be saved (if unsure what this is, leave unchanged)
		# "apt_get_packages": apt packages that need to be installed onto the image
		self.conf = {
			"hostname": "personfollower",
			"rootfs_extra_space_mb": 3000,
			"rootfs": "/image-builds/PiFlavourMaker/focal-build",
			"flavour": "ubiquity-person-follower",
			"release": "focal",
			"imagedir": "/image-builds/final-images",
			"apt_get_packages": [
				"zip",
				"sox",
				"cairosvg",  # Required but not properly installed by fiducals
				"poppler-utils",  # Required but not properly installed by fiducals
				"gedit",
				"python3-dev",
				"python3-rpi.gpio",
				"python3-matplotlib",
				"python3-vcstool",
				"python3-smbus",
				"python3-catkin-tools",
				"python3-osrf-pycommon",
				"python3-tk",
				"python3-pyqt5",
				"ros-noetic-gps-common",
				"ros-noetic-raspicam-node",
				"ros-noetic-pi-sonar",
				"ros-noetic-ubiquity-motor",
				"ros-noetic-oled-display-node",
				"ros-noetic-move-basic",
				"ros-noetic-fiducials",
				"ros-noetic-teleop-twist-keyboard",
				"ros-noetic-carrot-planner", # Required but not properly installed by magni-robot
				"ros-noetic-robot-localization",
				"ros-noetic-rosbridge-suite",
				"ros-noetic-tf2-web-republisher",
				"ros-noetic-tf-conversions",
				"ros-noetic-vision-msgs",
				"ros-noetic-rviz-visual-tools",
				"ros-noetic-map-server",
				"ros-noetic-nmea-navsat-driver",
				"libudev-dev",
				"ros-noetic-web-video-server",
				"ros-noetic-laser-filters",
				"ros-noetic-actionlib",
				"ros-noetic-tf2-sensor-msgs"
			]
		}
		
	def execute_customizations(self):
		gdm3_mod.install()

		print("=============== Swap ===============")
		subprocess.run("fallocate -l 1G /swapfile", shell=True, check=True, executable='/bin/bash')
		subprocess.run("chmod 600 /swapfile", shell=True, check=True, executable='/bin/bash')
		subprocess.run("mkswap /swapfile", shell=True, check=True, executable='/bin/bash')
		subprocess.run("swapon /swapfile", shell=True, check=True, executable='/bin/bash')

		print("=============== Tensorflow Lite ===============")
		linux_util.run_as_user(
			"ubuntu",
			["bash", "-c", "pip3 install --extra-index-url https://google-coral.github.io/py-repo/ tflite_runtime || true"],
			cwd="/home/ubuntu/catkin_ws",
			check=True,
		)

		print("=============== Coral TPU ===============")
		subprocess.run("echo \"deb https://packages.cloud.google.com/apt coral-edgetpu-stable main\" | sudo tee /etc/apt/sources.list.d/coral-edgetpu.list", shell=True, check=True, executable='/bin/bash')
		subprocess.run("curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key add -", shell=True, check=True, executable='/bin/bash')
		subprocess.run("sudo apt-get update", shell=True, check=True, executable='/bin/bash')
		subprocess.run("sudo apt-get install libedgetpu1-std -y", shell=True, check=True, executable='/bin/bash')
		subprocess.run("sudo apt-get install python3-pycoral -y", shell=True, check=True, executable='/bin/bash')
		subprocess.run("python3 -m pip install --extra-index-url https://google-coral.github.io/py-repo/ pycoral~=2.0", shell=True, check=True, executable='/bin/bash')

		print("=============== Installing Main Codebase ===============")
		subprocess.run("git config --global credential.helper 'cache --timeout=120'", shell=True, check=True, executable='/bin/bash')
		subprocess.run("rm -rf /home/ubuntu/catkin_ws/src/ubiquity_motor", shell=True, check=True, executable='/bin/bash')
		subprocess.run("rm /etc/ubiquity/robot.yaml", shell=True, check=True, executable='/bin/bash')

		os.chdir("/home/ubuntu/catkin_ws/src")

		subprocess.run("git clone https://github.com/UbiquityRobotics/person_following_robot.git", shell=True, check=True, executable='/bin/bash')

		os.chdir("/home/ubuntu/catkin_ws/src/person_following_robot")
		subprocess.run("vcs import < personfollower.repos", shell=True, check=True, executable='/bin/bash')

		os.chdir("/home/ubuntu/catkin_ws")
		subprocess.run("rosdep install --from-paths src --ignore-src --rosdistro=noetic -y  || true", shell=True, check=True, executable='/bin/bash')
		
		subprocess.run("chown -R ubuntu:ubuntu /home/ubuntu", shell=True, check=True, executable='/bin/bash')
		linux_util.run_as_user(
			"ubuntu",
			["bash", "-c", "source /opt/ros/noetic/setup.bash; catkin_make -j1"],
			cwd="/home/ubuntu/catkin_ws",
			check=True,
		)

		print("=============== Misc File Edits ===============")
		subprocess.run('echo \"SUBSYSTEM==\\\"tty\\\", ATTRS{idVendor}==\\\"10c4\\\", ATTRS{idProduct}==\\\"ea60\\\", SYMLINK+=\\\"lidar\\\"\" >> /etc/udev/rules.d/50-usb.rules', shell=True, check=True, executable='/bin/bash')
		subprocess.run('echo \"SUBSYSTEM==\\\"tty\\\", ATTRS{idVendor}==\\\"0403\\\", ATTRS{idProduct}==\\\"6015\\\", SYMLINK+=\\\"beacon\\\"\" >> /etc/udev/rules.d/50-usb.rules', shell=True, check=True, executable='/bin/bash')

		subprocess.run("bash -c \"echo '%sudo   ALL=NOPASSWD: /bin/systemctl reboot, /bin/systemctl poweroff' >> /etc/sudoers.d/nopasswd\"", shell=True, check=True, executable='/bin/bash')
		subprocess.run("bash -c \"echo 'source /home/ubuntu/catkin_ws/devel/setup.bash' >> /etc/ubiquity/ros_setup.bash\"", shell=True, check=True, executable='/bin/bash')	
		
		subprocess.run("sed --in-place 's/# Punch it./# Punch it.\nexport DISPLAY=:0\necho \"x\" >> $check_path/g' /usr/sbin/magni-base", shell=True, check=True, executable='/bin/bash')
		subprocess.run("sed --in-place 's/roslaunch --wait -v magni_bringup base.launch/roslaunch --wait -v ezmap_bringup base.launch/g' /usr/sbin/magni-base", shell=True, check=True, executable='/bin/bash')

		subprocess.run("chown -R ubuntu:ubuntu /etc/ubiquity", shell=True, check=True, executable='/bin/bash')
		subprocess.run("chown -R ubuntu:ubuntu /home/ubuntu", shell=True, check=True, executable='/bin/bash')
		
		return
