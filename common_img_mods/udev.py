import subprocess

def add_rules():

	# Lidar LD-19
	subprocess.run('echo \"SUBSYSTEM==\\\"tty\\\", ATTRS{idVendor}==\\\"10c4\\\", ATTRS{idProduct}==\\\"ea60\\\", SYMLINK+=\\\"ldlidar\\\"\" >> /etc/udev/rules.d/50-usb.rules', shell=True, check=True, executable='/bin/bash')

	# Ublox Bluetooth AoA Receiver
	subprocess.run('echo \"SUBSYSTEM==\\\"tty\\\", ATTRS{idVendor}==\\\"0403\\\", ATTRS{idProduct}==\\\"6015\\\", SYMLINK+=\\\"beacon\\\"\" >> /etc/udev/rules.d/50-usb.rules', shell=True, check=True, executable='/bin/bash')

	return