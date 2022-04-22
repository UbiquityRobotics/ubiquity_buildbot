import subprocess

def install():
    print("=============== INSTALLING UR50 ===============")
    # clone the driver for the ur50 lidar driver. 
    subprocess.run("git clone https://$GIT_TOKEN@github.com/UbiquityRobotics/ls_lidar_driver.git", 
                    shell=True, 
                    cwd = "/home/ubuntu/catkin_ws/src")

    # set static ip on ethernet port for lidar
    with open("/etc/systemd/network/11-eth-lidar.network", "w") as f:
        network_conf = """
[Match]
Name=eth*

[Network]
Address=192.168.42.125/24
"""
        f.write(network_conf)
        f.close()