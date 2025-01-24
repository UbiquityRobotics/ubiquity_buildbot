
import shutil
from common_img_mods import gdm3_mod, udev
import subprocess
import linux_util
import os

# This is a customization script used for generating base images and at the same time
# a minimal working example of a customization script. You can copy paste this
# for use as a starting point for custom projects

#NAME = "ezmap-lite"
#NAME = "ezmap-pro"
NAME = "ezmap"

LAMA_VER = "008"

class customizeImage:
	def __init__(self, git_token=None):

		# there needs to exist a dictionary with name "conf" the following variables:
		# "hostname": hostname that the image is going to have setup.
		# "rootfs_extra_space_mb": how much more space will be allocated in rootfs in generated image.
		# "rootfs": absolute path on buildbot filesystem where generated rootfs will be saved (if unsure what this is, leave unchanged)
		# "flavour": flavour of generated image. The name of generated image will be: ${timestamp}-${flavour}-${release}-raspberry-pi.img
		# "release": release of the generated image. Currently only possible value is "focal".
		# "imagedir": absolute path on buildbot filesystem where generated image will be saved (if unsure what this is, leave unchanged)
		# "apt_get_packages": apt packages that need to be installed onto the image
		self.git_token = git_token
		self.conf = {
			"hostname": "ezrobot",
			"rootfs_extra_space_mb": 2000,
			"rootfs": "/image-builds/PiFlavourMaker/focal-build",
			"flavour": NAME,
			"release": "focal",
			"imagedir": "/image-builds/final-images",
			"apt_get_packages": [
				"zip",
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
				"ros-noetic-laser-filters"
			]
		}
		
	def execute_customizations(self):
		gdm3_mod.install()

		subprocess.run("git config --global credential.helper 'cache --timeout=120'", shell=True, check=True, executable='/bin/bash')

		subprocess.run("export DEBIAN_FRONTEND=noninteractive; apt-get -y install iptables-persistent; unset DEBIAN_FRONTEND", shell=True, check=True, executable='/bin/bash')

		subprocess.run("iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 3000", shell=True, check=True, executable='/bin/bash')
		subprocess.run("iptables -t nat -I OUTPUT -p tcp -d 127.0.0.1 --dport 80 -j REDIRECT --to-ports 3000", shell=True, check=True, executable='/bin/bash')
		#subprocess.run("mkdir /etc/iptables", shell=True, check=True, executable='/bin/bash')
		subprocess.run("bash -c \"iptables-save > /etc/iptables/rules.v4\"", shell=True, check=True, executable='/bin/bash')
		
		# enable pigpiod
		subprocess.run("systemctl enable pigpiod", shell=True, check=True, executable='/bin/bash')
		subprocess.run("pip3 install pyyaml", shell=True, check=True, executable='/bin/bash')

		# Iris LaMA
		os.chdir("/home/ubuntu/")
		#subprocess.run("mkdir -p /home/ubuntu/iris_lama_ws/src", shell=True, check=True, executable='/bin/bash')

		#os.chdir("/home/ubuntu/iris_lama_ws/src")
		#subprocess.run("git clone https://github.com/UbiquityRobotics/iris_ur_lama.git", shell=True, check=True, executable='/bin/bash')
		#subprocess.run("git clone https://github.com/UbiquityRobotics/iris_ur_lama_ros.git", shell=True, check=True, executable='/bin/bash')

		subprocess.run("wget https://ubiquity-updates.sfo2.digitaloceanspaces.com/iris_lama_ws_"+LAMA_VER+".zip", shell=True, check=True, executable='/bin/bash')		
		subprocess.run("unzip iris_lama_ws_"+LAMA_VER+".zip", shell=True, check=True, executable='/bin/bash')
		subprocess.run("rm iris_lama_ws_"+LAMA_VER+".zip", shell=True, check=True, executable='/bin/bash')

		subprocess.run("chown -R ubuntu:ubuntu /home/ubuntu", shell=True, check=True, executable='/bin/bash')

		linux_util.run_as_user(
			"ubuntu",
			["bash", "-c", "source /opt/ros/noetic/setup.bash; rosdep update; rosdep install --from-paths src --ignore-src --rosdistro=noetic -y || true"],
			cwd="/home/ubuntu/iris_lama_ws",
			check=True,
		)

		linux_util.run_as_user(
			"ubuntu",
			["bash", "-c", "source /opt/ros/noetic/setup.bash; catkin config --extend /opt/ros/noetic; catkin build -j1"],
			cwd="/home/ubuntu/iris_lama_ws",
			check=True,
		)

		# EZ-Map
		repo = NAME.replace("-","_")

		github_username = "Luks24"
		github_token = self.git_token

		os.environ['GITHUB_USERNAME'] = github_username
		os.environ['GITHUB_TOKEN'] = github_token

		os.chdir("/home/ubuntu/catkin_ws/src")
		subprocess.run("git clone https://"+github_username+":"+github_token+"@github.com/UbiquityRobotics/"+repo+".git", shell=True, check=True, executable='/bin/bash')
		
		subprocess.run("git config --global credential.helper store", shell=True, check=True, executable='/bin/bash')
		
		os.chdir("/home/ubuntu/catkin_ws/src/"+repo)
		subprocess.run(f"GITHUB_USERNAME={github_username} GITHUB_TOKEN={github_token} vcs import < {repo}.repos --debug", shell=True, check=True, executable='/bin/bash')

		os.chdir("/home/ubuntu/catkin_ws")
		subprocess.run("rosdep install --from-paths src --ignore-src --rosdistro=noetic -y  || true", shell=True, check=True, executable='/bin/bash')
		#subprocess.run("source /opt/ros/noetic/setup.bash; source /home/ubuntu/iris_lama_ws/devel/setup.bash; catkin_make -j1", shell=True, check=True, executable='/bin/bash')

		subprocess.run("chown -R ubuntu:ubuntu /home/ubuntu", shell=True, check=True, executable='/bin/bash')
		linux_util.run_as_user(
			"ubuntu",
			["bash", "-c", "source /opt/ros/noetic/setup.bash; source /home/ubuntu/iris_lama_ws/devel/setup.bash; catkin_make -j1"],
			cwd="/home/ubuntu/catkin_ws",
			check=True,
		)

		# File edits
		udev.add_rules()

		subprocess.run("bash -c \"echo '%sudo   ALL=NOPASSWD: /bin/systemctl reboot, /bin/systemctl poweroff' >> /etc/sudoers.d/nopasswd\"", shell=True, check=True, executable='/bin/bash')		
		subprocess.run("bash -c \"echo 'source /home/ubuntu/iris_lama_ws/devel/setup.bash' >> /etc/ubiquity/ros_setup.bash\"", shell=True, check=True, executable='/bin/bash')	
		subprocess.run("bash -c \"echo 'source /home/ubuntu/catkin_ws/devel/setup.bash' >> /etc/ubiquity/ros_setup.bash\"", shell=True, check=True, executable='/bin/bash')	
		subprocess.run("bash -c \"echo 'source /home/ubuntu/catkin_ws/src/"+repo+"/ezmap_bringup/scripts/ros_log_clean.bash' >> /etc/ubiquity/env.sh\"", shell=True, check=True, executable='/bin/bash')	

		gps_config = '''stty -F /dev/ttyACM0 38400 raw
		echo -e -n '\\xB5\\x62\\x06\\x08\\x06\\x00\\xC8\\x00\\x01\\x00\\x01\\x00\\xDE\\x6A' >> /dev/ttyACM0
		source /etc/ubiquity/env.sh'''

		with open("/usr/sbin/magni-base", "r") as f:
		    content = f.read()

		content = content.replace("source /etc/ubiquity/env.sh", gps_config)
		content = content.replace("roslaunch --wait -v magni_bringup base.launch", "roslaunch --wait -v ezmap_bringup base.launch")

		with open("/usr/sbin/magni-base", "w") as f:
		    f.write(content)

		subprocess.run("chown -R ubuntu /etc/ubiquity/", shell=True, check=True, executable='/bin/bash')

		subprocess.run("""bash -c \"echo '[Match]
Name=eth*

[Network]
Address=192.168.42.125/24' > /etc/systemd/network/10-eth-dhcp.network\"""", shell=True, check=True, executable='/bin/bash')

		subprocess.run("chown -R ubuntu:ubuntu /etc/ubiquity", shell=True, check=True, executable='/bin/bash')
		subprocess.run("chown -R ubuntu:ubuntu /home/ubuntu", shell=True, check=True, executable='/bin/bash')
		
		return
