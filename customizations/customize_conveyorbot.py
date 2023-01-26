import shutil
from common_img_mods import gdm3_mod
import subprocess
import linux_util
import os

class customizeImage:
	def __init__(self):

		self.conf = {
			"hostname": "conveyorbot",
			"rootfs_extra_space_mb": 2000,
			"rootfs": "/image-builds/PiFlavourMaker/focal-build",
			"flavour": "conveyorbot",
			"release": "focal",
			"imagedir": "/image-builds/final-images",
			"apt_get_packages": [
				'nodejs',
				'npm',
				'unclutter',
				'zip',
				'cairosvg',
				'poppler-utils',
				'gedit',
				'python3-dev',
				'python3-rpi.gpio',
				'python3-matplotlib',
				'python3-vcstool',
				'python3-smbus',
				'python3-catkin-tools',
				'python3-osrf-pycommon',
				'python3-tk',
				'python-xmltodict',
				'ros-noetic-gps-common',
				'ros-noetic-raspicam-node',
				'ros-noetic-pi-sonar',
				'ros-noetic-ubiquity-motor',
				'ros-noetic-oled-display-node',
				'ros-noetic-move-basic',
				'ros-noetic-fiducials',
				'ros-noetic-teleop-twist-keyboard',
				'ros-noetic-carrot-planner',
				'ros-noetic-robot-localization',
				'ros-noetic-rosbridge-suite',
				'ros-noetic-tf2-web-republisher',
				'ros-noetic-tf-conversions',
				'ros-noetic-vision-msgs',
				'ros-noetic-rviz-visual-tools',
				'ros-noetic-map-server',
				'ros-noetic-nmea-navsat-driver',
				'libudev-dev',
				'ros-noetic-web-video-server',
				'ros-noetic-laser-filters',
				'ros-noetic-twist-mux'
			]
		}
		
	def execute_customizations(self):
		gdm3_mod.install()
		subprocess.run('sleep 5; snap install chromium; sleep 5; snap install chromium || true', shell=True, check=True, executable='/bin/bash')
		subprocess.run("git config --global credential.helper 'cache --timeout=120'", shell=True, check=True, executable='/bin/bash')
		subprocess.run('systemctl enable pigpiod', shell=True, check=True, executable='/bin/bash')
		subprocess.run('pip3 install pyyaml', shell=True, check=True, executable='/bin/bash')
		subprocess.run('bash -c "echo \'LC_ALL=en_US.UTF-8\' | sudo tee -a /etc/environment > /dev/null"', shell=True, check=True, executable='/bin/bash')
		subprocess.run('bash -c "echo \'en_US.UTF-8 UTF-8\' | sudo tee -a /etc/locale.gen > /dev/null"', shell=True, check=True, executable='/bin/bash')
		subprocess.run('bash -c "echo \'LANG=en_US.UTF-8\' | sudo tee /etc/locale.conf > /dev/null"', shell=True, check=True, executable='/bin/bash')
		subprocess.run('locale-gen en_US.UTF-8', shell=True, check=True, executable='/bin/bash')
		subprocess.run('rm -rf /home/ubuntu/catkin_ws/src/ubiquity_motor', shell=True, check=True, executable='/bin/bash')
		subprocess.run('rm /etc/ubiquity/robot.yaml', shell=True, check=True, executable='/bin/bash')
		os.chdir('/home/ubuntu/catkin_ws/src')
		subprocess.run('git clone https://github.com/UbiquityRobotics/breadcrumb.git --branch repos', shell=True, check=True, executable='/bin/bash')
		os.chdir('/home/ubuntu/catkin_ws/src/breadcrumb')
		subprocess.run('vcs import < breadcrumb.repos', shell=True, check=True, executable='/bin/bash')
		subprocess.run('rm -rf /home/ubuntu/catkin_ws/src/breadcrumb/fiducials', shell=True, check=True, executable='/bin/bash')
		os.chdir('/home/ubuntu/catkin_ws')
		subprocess.run('rosdep install --from-paths src --ignore-src --rosdistro=noetic -y || true', shell=True, check=True, executable='/bin/bash')
		subprocess.run('chown -R ubuntu:ubuntu /home/ubuntu', shell=True, check=True, executable='/bin/bash')
		linux_util.run_as_user('ubuntu',
			[
		 'bash', '-c', 'npm install; npm run build'],
			cwd='/home/ubuntu/catkin_ws/src/breadcrumb/breadcrumb_touchscreen/web_app',
			check=True)
		linux_util.run_as_user('ubuntu',
			[
		 'bash', '-c', 'source /opt/ros/noetic/setup.bash; catkin_make -j1'],
			cwd='/home/ubuntu/catkin_ws',
			check=True)
		subprocess.run('bash -c "echo \'%sudo   ALL=NOPASSWD: /usr/bin/apt, /usr/bin/apt-get, /bin/systemctl poweroff, /bin/systemctl reboot, /bin/systemctl restart roscore, /usr/bin/rm /etc/ubiquity/IS_DEBUG, /usr/bin/pifi set-hostname, /usr/bin/touch /etc/ubiquity/IS_DEBUG\' >> /etc/sudoers.d/nopasswd"', shell=True, check=True, executable='/bin/bash')
		subprocess.run('bash -c "echo \'source /home/ubuntu/catkin_ws/devel/setup.bash\' >> /etc/ubiquity/ros_setup.bash"', shell=True, check=True, executable='/bin/bash')
		subprocess.run('touch /etc/ubiquity/IS_FIRST_BOOT', shell=True, check=True, executable='/bin/bash')
		subprocess.run('echo \'DEBUG_ON_FILE=/etc/ubiquity/IS_DEBUG\nALWAYS_DEBUG_ON_FILE=/etc/ubiquity/IS_DEBUG_ALWAYS\nif test -f ""$DEBUG_ON_FILE"" || test -f ""$ALWAYS_DEBUG_ON_FILE""\nthen\n    export ROS_HOSTNAME=$(hostname).local\n    export ROS_MASTER_URI=http://$(hostname):11311\nelse\n    export ROS_HOSTNAME=localhost\n    export ROS_MASTER_URI=http://localhost:11311\nfi\n\nsource /home/ubuntu/catkin_ws/src/breadcrumb/breadcrumb_bringup/scripts/ros_log_clean.bash\n\nexport DISPLAY=:0\' >> /etc/ubiquity/env.sh', shell=True,
			check=True,
			executable='/bin/bash')
		subprocess.run("sed --in-place 's/roslaunch --wait -v magni_bringup base.launch/roslaunch --wait -v breadcrumb_bringup base.launch/g' /usr/sbin/magni-base", shell=True, check=True, executable='/bin/bash')
		subprocess.run('chown -R ubuntu /etc/ubiquity/', shell=True, check=True, executable='/bin/bash')
		subprocess.run('bash -c "echo \'[Match]\nName=eth*\n\n[Network]\nAddress=192.168.42.125/24\' > /etc/systemd/network/10-eth-dhcp.network"', shell=True,
			check=True,
			executable='/bin/bash')
		subprocess.run('mkdir /home/ubuntu/.config/autostart/', shell=True, check=True, executable='/bin/bash')
		subprocess.run('chown -R ubuntu:ubuntu /etc/ubiquity', shell=True, check=True, executable='/bin/bash')
		subprocess.run('chown -R ubuntu:ubuntu /home/ubuntu', shell=True, check=True, executable='/bin/bash')
		subprocess.run('bash -c "echo \'#!/bin/bash\nsleep 5\n\nunclutter -idle 0.01 -root & \n\nsource /opt/ros/noetic/setup.bash;\nsource /home/ubuntu/catkin_ws/devel/setup.bash;\nsource /etc/ubiquity/env.sh;\n\nroslaunch breadcrumb_touchscreen touchscreen.launch\n\n# Fix for Chromium wont start after changing hostname\nrm -rf ~/snap/chromium/common/chromium/Singleton*\' > /home/ubuntu/breadcrumb_touchscreen.bash"', shell=True,
			check=True,
			executable='/bin/bash')
		subprocess.run('bash -c "echo \'[Desktop Entry]\nEncoding=UTF-8\nType=Application\nName=breadcrumb_touchscreen\nExec=/home/ubuntu/breadcrumb_touchscreen.bash\nStartupNotify=false\nTerminal=false\nHidden=false\' > /home/ubuntu/.config/autostart/breadcrumb_touchscreen.desktop"', shell=True,
			check=True,
			executable='/bin/bash')
		subprocess.run('bash -c "echo \'[Unit]\nDescription=your description\n\n[Service]\nExecStart=/home/ubuntu/catkin_ws/src/breadcrumb/triggered_logging/scripts/create_ramdisk.bash \n\n[Install]\nWantedBy=multi-user.target\' > /etc/systemd/system/ramdisk.service"', shell=True,
			check=True,
			executable='/bin/bash')
		subprocess.run('systemctl enable ramdisk.service', shell=True, check=True, executable='/bin/bash')
		subprocess.run('echo \'FIRST_BOOT_FILE=/etc/ubiquity/IS_FIRST_BOOT\nif test -f "$FIRST_BOOT_FILE"; then\n    # If we are booting for the first time\n    echo "First boot."\n    sudo rm $FIRST_BOOT_FILE\n\n    until [[ $(cut -d" " -f9 <<< $(ip addr show wlan0 | head -1 | tail -1)) = "UP" ]];\n    do\n        echo "wlan0 is not up yet. Waiting..."\n        sleep 2\n    done\n\n    line=$(ip addr show wlan0 | head -5 | tail -1)\n    suffix=$(cut -d"/" -f1 <<< $(cut -d":" -f6 <<< $line))\n    new_hostname="conveyorbot${suffix^^}"\n    sudo pifi set-hostname $new_hostname\n    sudo systemctl reboot\nfi\' > /etc/ubiquity/before_ros.sh', shell=True,
			check=True,
			executable='/bin/bash')
		subprocess.run('bash -c "echo \'[Unit]\n\n[Service]\nType=oneshot\nUser=root\nExecStart=/bin/bash /etc/ubiquity/before_ros.sh\n\n[Install]\nWantedBy=multi-user.target\' > /lib/systemd/system/before-ros.service"', shell=True,
			check=True,
			executable='/bin/bash')
		subprocess.run('systemctl enable before-ros.service', shell=True, check=True, executable='/bin/bash')
		subprocess.run("sed --in-place 's/After=NetworkManager.service time-sync.target/After=NetworkManager.service time-sync.target before-ros.service/g' /etc/systemd/system/roscore.service", shell=True, check=True, executable='/bin/bash')

		return
