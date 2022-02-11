import subprocess
import os
import shutil


class customizeImage:
	# def __init__(self):
		# insert init actions here
		
	def execute_customizations(self):
		# to get rid of mouse lag
		with open("/boot/cmdline.txt", "w+") as f:
			f.write("usbhid.mousepoll=4 ")
			f.close()

		# setup the desktop to not logout on idle
		os.makedirs("/usr/share/glib-2.0/schemas/", exist_ok=True)
		# in chroot "gsettings set" commands don't work, thats why we change default desktop settings
		# https://answers.launchpad.net/cubic/+question/696919
		shutil.copy("files/org.gnome.desktop.screensaver.gschema.xml", "/usr/share/glib-2.0/schemas/org.gnome.desktop.screensaver.gschema.xml")
		shutil.copy("files/org.gnome.settings-daemon.plugins.power.gschema.xml", "/usr/share/glib-2.0/schemas/org.gnome.settings-daemon.plugins.power.gschema.xml")
		# schemas must be recompiled after every change
		subprocess.run(["glib-compile-schemas", "/usr/share/glib-2.0/schemas"], check=True)
			
		# enable automatic login for user ubuntu by setting AutomaticLoginEnable and AutomaticLogin to true
		subprocess.run(["sed", "-i", '/AutomaticLoginEnable.*/c\AutomaticLoginEnable = true', "/etc/gdm3/custom.conf"], check=True)
		subprocess.run(["sed", "-i", '/AutomaticLogin .*/c\AutomaticLogin = ubuntu', "/etc/gdm3/custom.conf"], check=True)

		return