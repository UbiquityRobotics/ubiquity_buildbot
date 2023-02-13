from common_img_mods import ubiquity_ros_packages_mod

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
			"flavour": "ubiquity-base",
			"release": "focal",
			"imagedir": "/image-builds/final-images",
			"apt_get_packages": [
				"ros-noetic-raspicam-node",
				"ros-noetic-pi-sonar",
				"ros-noetic-ubiquity-motor",
				"ros-noetic-oled-display-node",
				"ros-noetic-move-basic",
				"ros-noetic-fiducials",
				"ros-noetic-teleop-twist-keyboard",
				"ros-noetic-carrot-planner", # Required but not properly installed by magni-robot
				"cairosvg",  # Required but not properly installed by fiducals
			]
		}
		
	def execute_customizations(self):
		ubiquity_ros_packages_mod.install_packages()
		ubiquity_ros_packages_mod.compile()
		return