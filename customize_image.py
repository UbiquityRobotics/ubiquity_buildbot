import subprocess

class customizeImage:
	# def __init__(self):
		# insert init actions here
		
	def execute_customizations(self):
		subprocess.run(["apt-get", "install", "sl"], check=True)
		return