import subprocess
import os
import shutil
from common_img_mods import gdm3_mod
class customizeImage:
	def __init__(self):
		# there needs to exist a dictionary with name "conf" the following variables:
		# "hostname": hostname that the image is going to have setup.
		# "rootfs_extra_space_mb": how much more space will be allocated in rootfs in generated image.
		# "rootfs": absolute path on buildbot filesystem where generated rootfs will be saved
		# "flavour": flavour of generated image. The name of generated image will be: ${timestamp}-${flavour}-${release}-raspberry-pi.img
		# "release": release of the generated image. Currently only possible value is "focal".
		# "imagedir": absolute path on buildbot filesystem where generated image will be saved
		# "apt_get_packages":
		self.conf = {
			"hostname": "ubuntu",
			"rootfs_extra_space_mb": 500,
			"rootfs": "/image-builds/PiFlavourMaker/focal-build",
			"flavour": "ubiquity-gdm3-testing",
			"release": "focal",
			"imagedir": "/image-builds/final-images",
			"apt_get_packages": [
				"python2",
				"ros-noetic-raspicam-node",
				"ros-noetic-pi-sonar",
				"ros-noetic-ubiquity-motor",
				"ros-noetic-oled-display-node",
				"ros-noetic-move-basic",
				"ros-noetic-fiducials",
				"ros-noetic-teleop-twist-keyboard",
				"ros-noetic-carrot-planner", # Required but not properly installed by magni-robot
				"cairosvg",  # Required but not properly installed by fiducals
				"poppler-utils",  # Required but not properly installed by fiducals
				"gedit"
			]
		}
		
	def execute_customizations(self):
		gdm3_mod.install()
		return