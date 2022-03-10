import os
import shutil
import subprocess

def install():
	print("=============== INSTALLING GDM ===============")
	subprocess.run(["apt-get", "install", "gdm3", "-y"], check=True)
	print("installing gnome-terminal")
	subprocess.run(["apt-get", "install", "gnome-terminal", "-y"], check=True)

	# to get rid of mouse lag
	print("getting rid of mouse lag")
	with open("/boot/cmdline.txt", "a") as f:
		# the following is appended, an initial space is necessary to fit the file format
		f.write(" usbhid.mousepoll=4")
		f.close()

	print("setting up desktop environment")
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
	print("=============== INSTALLING GDM FINISHED =======")
	return