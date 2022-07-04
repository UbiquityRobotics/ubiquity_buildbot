
import shutil
from common_img_mods import gdm3_mod
import subprocess

# This is a customization script used for generating base images and at the same time
# a minimal working example of a customization script. You can copy paste this
# for use as a starting point for custom projects

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
			"hostname": "ezmaprobot",
			"rootfs_extra_space_mb": 2000,
			"rootfs": "/image-builds/PiFlavourMaker/focal-build",
			"flavour": "ezmap",
			"release": "focal",
			"imagedir": "/image-builds/final-images",
			"apt_get_packages": [
				"cairosvg",  # Required but not properly installed by fiducals
				"poppler-utils",  # Required but not properly installed by fiducals
				"gedit",
				"python3-dev",
				"python3-rpi.gpio",
				"python3-matplotlib",
				"python3-vcstool",
				"python3-smbus",
				"python3-numpy",
				"python3-numba",
				"python3-scipy",
				"python3-catkin-tools",
				"python3-osrf-pycommon",
				"python3-tk",
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
				"ros-noetic-map-server",
				"ros-noetic-ublox",
				"libudev-dev",
				"ros-noetic-web-video-server",
				"ros-noetic-laser-filters",
				"iptables-persistent"
			]
		}
		
	def execute_customizations(self):
		gdm3_mod.install()
		
		# enable pigpiod
		subprocess.run("systemctl enable pigpiod", shell=True, check=True)

		# install quaternionic, hopefully we'll get rid of this soon
		subprocess.run("pip3 install pyyaml quaternionic", shell=True, check=True)

		# Iris LaMA
		subprocess.run("mkdir -p /home/ubuntu/iris_lama_ws/src", shell=True, check=True)
		os.chdir("/home/ubuntu/iris_lama_ws/src")

		subprocess.run("git clone https://github.com/UbiquityRobotics/iris_ur_lama.git", shell=True, check=True)
		subprocess.run("git clone https://github.com/UbiquityRobotics/iris_ur_lama_ros.git", shell=True, check=True)

		os.chdir("/home/ubuntu/iris_lama_ws")
		subprocess.run("rosdep update", shell=True, check=True)		
		subprocess.run("rosdep install --from-paths src --ignore-src -r -y", shell=True, check=True)
		subprocess.run("catkin config --extend /opt/ros/noetic", shell=True, check=True)
		subprocess.run("catkin build", shell=True, check=True)

		# EZ-Map
		os.chdir("/home/ubuntu/catkin_ws/src")
		subprocess.run("git clone https://github.com/UbiquityRobotics/ezmap.git", shell=True, check=True)

		os.chdir("/home/ubuntu/catkin_ws/src/ezmap")
		subprocess.run("vcs import < ezmap.repos", shell=True, check=True)

		os.chdir("/home/ubuntu/catkin_ws")
		subprocess.run("rosdep install --from-paths src --ignore-src --rosdistro=noetic -y", shell=True, check=True)
		subprocess.run("source /home/ubuntu/iris_lama_ws/devel/setup.bash; catkin_make", shell=True, check=True)

		# File edits
		subprocess.run("sudo bash -c \"echo '%sudo   ALL=NOPASSWD: /bin/systemctl reboot, /bin/systemctl poweroff' >> /etc/sudoers.d/nopasswd\"", shell=True, check=True)		
		subprocess.run("sudo bash -c \"echo 'source /home/ubuntu/iris_lama_ws/devel/setup.bash' >> /etc/ubiquity/ros_setup.bash\"", shell=True, check=True)	
		subprocess.run("sudo bash -c \"echo 'source /home/ubuntu/catkin_ws/devel/setup.bash' >> /etc/ubiquity/ros_setup.bash\"", shell=True, check=True)	
		subprocess.run("sudo bash -c \"echo 'source /home/ubuntu/catkin_ws/src/ezmap/ezmap_bringup/scripts/ros_log_clean.bash' >> /etc/ubiquity/env.sh\"", shell=True, check=True)	

		subprocess.run("sudo sed --in-place 's/roslaunch --wait -v magni_bringup base.launch/roslaunch --wait -v ezmap_bringup base.launch/g' /usr/sbin/magni-base", shell=True, check=True)
		subprocess.run("sudo sed --in-place 's/oled_display: {'controller': None}/oled_display: {'controller': SH1106}/g' /etc/ubiquity/robot.yaml", shell=True, check=True)

		subprocess.run("sudo chown -R ubuntu /etc/ubiquity/", shell=True, check=True)
		subprocess.run("sudo sed --in-place 's/oled_display: {'controller': None}/oled_display: {'controller': SH1106}/g' /etc/ubiquity/robot.yaml", shell=True, check=True)

		subprocess.run("""sudo bash -c \"echo '[Match]
Name=eth*

[Network]
Address=192.168.42.125/24' > /etc/systemd/network/10-eth-dhcp.network\"""", shell=True, check=True)


		subprocess.run("sudo iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 3000", shell=True, check=True)
		subprocess.run("sudo iptables -t nat -I OUTPUT -p tcp -d 127.0.0.1 --dport 80 -j REDIRECT --to-ports 3000", shell=True, check=True)
		subprocess.run("sudo mkdir /etc/iptables", shell=True, check=True)
		subprocess.run("sudo bash -c \"iptables-save > /etc/iptables/rules.v4\"", shell=True, check=True)

		subprocess.run("sudo sed --in-place 's/dtparam=i2c_arm=on/#dtparam=i2c_arm=on/g' /boot/config.txt", shell=True, check=True)
		subprocess.run("sudo bash -c "echo "" >> /boot/config.txt"", shell=True, check=True)
		subprocess.run("sudo bash -c "echo "" >> /boot/config.txt"", shell=True, check=True)
		subprocess.run("sudo bash -c "echo 'dtoverlay=i2c-gpio,i2c_gpio_sda=2,i2c_gpio_scl=3,bus=1' >> /boot/config.txt"", shell=True, check=True)

		return