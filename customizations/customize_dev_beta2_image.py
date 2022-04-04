import subprocess
import os
import shutil

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
			"hostname": "ubuntu",
			"rootfs_extra_space_mb": 500,
			"rootfs": "/image-builds/PiFlavourMaker/focal-build",
			"flavour": "ubiquity-gdm3-beta2-testing",
			"release": "focal",
			"imagedir": "/image-builds/final-images",
			"apt_get_packages": [
				"python2",
				"gdm3",
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
				"gnome-terminal", # otherwise there is no terminal on desktop environment
				"gedit"
			]
		}
		
	def execute_customizations(self):
		# to get rid of mouse lag
		with open("/boot/cmdline.txt", "a") as f:
			# the following is appended, an initial space is necessary to fit the file format
			f.write(" usbhid.mousepoll=4")
			f.close()

		os.makedirs("/usr/share/glib-2.0/schemas/", exist_ok=True)
		# in chroot "gsettings set" commands don't work, thats why we change default desktop settings
		# https://answers.launchpad.net/cubic/+question/696919
		# setup the desktop to not logout on idle
		shutil.copy("files/org.gnome.desktop.screensaver.gschema.xml", "/usr/share/glib-2.0/schemas/org.gnome.desktop.screensaver.gschema.xml")
		shutil.copy("files/org.gnome.settings-daemon.plugins.power.gschema.xml", "/usr/share/glib-2.0/schemas/org.gnome.settings-daemon.plugins.power.gschema.xml")
		# set the default desktop background
		shutil.copy("files/branding/magni_wallpaper.png", "/usr/share/magni_wallpaper.png")
		shutil.copy("files/org.gnome.desktop.background.gschema.xml", "/usr/share/glib-2.0/schemas/org.gnome.desktop.background.gschema.xml")
		# TODO in the future here also plymouth logo can be added
		# schemas must be recompiled after every change
		subprocess.run(["glib-compile-schemas", "/usr/share/glib-2.0/schemas"], check=True)
			
		# enable automatic login for user ubuntu by setting AutomaticLoginEnable and AutomaticLogin to true
		subprocess.run(["sed", "-i", '/AutomaticLoginEnable.*/c\AutomaticLoginEnable = true', "/etc/gdm3/custom.conf"], check=True)
		subprocess.run(["sed", "-i", '/AutomaticLogin .*/c\AutomaticLogin = ubuntu', "/etc/gdm3/custom.conf"], check=True)

		beta_text = 'echo "This is a beta2 release. Please report any problems to Ubiquity Robotics Discourse"'
		subprocess.run("echo '" + beta_text + "' >> /etc/update-motd.d/50-ubiquity", check=True, shell=True)

		return