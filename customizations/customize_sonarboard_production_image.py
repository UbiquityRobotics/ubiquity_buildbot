
import shutil
from common_img_mods import gdm3_mod, ubiquity_ros_packages_mod
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
			"hostname": "ubiquityrobot",
			"rootfs_extra_space_mb": 500,
			"rootfs": "/image-builds/PiFlavourMaker/focal-build",
			"flavour": "ubiquity-sonarboard-production-testing",
			"release": "focal",
			"imagedir": "/image-builds/final-images",
			"apt_get_packages": [
				"ros-noetic-pi-sonar",
				"python3-dev",
				"python3-rpi.gpio",
				"python3-matplotlib",
			]
		}
		
	def execute_customizations(self):
		gdm3_mod.install(disable_sleep_on_idle=True)
		ubiquity_ros_packages_mod.install_packages()
		ubiquity_ros_packages_mod.compile()
		
		# enable pigpiod
		subprocess.run("systemctl enable pigpiod", shell=True, check=True)

		# copy over the buzzer script
		shutil.copy("files/buzzer_check.py", "/home/ubuntu/buzzer_check.py")

		# copy over the sonar production start bash script
		shutil.copy("/files/sonarboard-test.sh", "/usr/sbin/sonarboard-test")

		shutil.copy("/files/sonarboard-test.service", "/lib/systemd/system/sonarboard_test.service")

		subprocess.run("sudo systemctl enable sonarboard_test.service", shell= True, check=True)

		return