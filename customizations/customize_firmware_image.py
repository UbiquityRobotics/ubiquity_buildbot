import imp
import subprocess
import shutil
import linux_util

class customizeImage:
	def __init__(self):
		# there needs to exist a dictionary with name "conf" the following variables:
		# "hostname": hostname that the image is going to have setup.
		# "rootfs_extra_space_mb": how much more space will be allocated in rootfs in generated image.
		# "rootfs": absolute path on buildbot filesystem where generated rootfs will be saved
		# "flavour": flavour of generated image. The name of generated image will be: ${timestamp}-${flavour}-${release}-raspberry-pi.img
		# "release": release of the generated image. Currently only possible value is "focal".
		# "imagedir": absolute path on buildbot filesystem where generated image will be saved
		# "apt_get_packages": apt packages that need to be installed onto the image
		self.conf = {
			"hostname": "ubiquityrobot",
			"rootfs_extra_space_mb": 500,
			"rootfs": "/image-builds/PiFlavourMaker/focal-build",
			"flavour": "ubiquity-firmware-load",
			"release": "focal",
			"imagedir": "/image-builds/final-images",
			"apt_get_packages": [
				"ros-noetic-raspicam-node",
				"ros-noetic-pi-sonar",
				"ros-noetic-ubiquity-motor",
				"ros-noetic-oled-display-node",
				"ros-noetic-move-basic",
			]
		}
		
	def execute_customizations(self):
		print("Copied /files/production_test.py -> /home/ubuntu/production_test.py")
		shutil.copy("/files/production_test.py", "/home/ubuntu/production_test.py")
		linux_util.make_executable("/home/ubuntu/production_test.py")
		
		print("Cloning ubiquity_motor")
		subprocess.run("git clone https://github.com/UbiquityRobotics/ubiquity_motor.git", shell= True, check=True, cwd="/home/ubuntu/catkin_ws/src/")

		# TODO copy over the correct firmware file
		shutil.copy("files/v43_20210829_enc.cyacd", "/home/ubuntu/v43_20210829_enc.cyacd")

		# overwrite the magni-base file with the production one
		shutil.copy("/files/magni-base-production-test.sh", "/usr/sbin/magni-base")
		# TODO maybe rather do with sed then separate magni-base file in the future?
		#subprocess.run(["sed", "-i", '/^.*base.launch.*/a rosrun ubiquity_motor upgrade_firmware.py --file /home/ubuntu/v43.cyacd', "/usr/sbin/magni-base"], check=True)
		
		return