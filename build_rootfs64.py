#!/usr/bin/env python3

import os, sys
import subprocess
import shutil
import crypt
from contextlib import contextmanager
import time
from pychroot import Chroot
import typing
from typing import Iterator
import linux_util
import argparse
import yaml
from datetime import datetime
from importlib.machinery import SourceFileLoader

customize_image = None

# mirror settings
default_ubuntu_mirror = "http://ports.ubuntu.com/"
local_ubuntu_mirror = "http://us-east-2.ec2.ports.ubuntu.com/ubuntu-ports/"
# local_ubuntu_mirror = "http://mirrors.mit.edu/ubuntu-ports/"
default_ros_mirror = "http://packages.ros.org/ros2/ubuntu"
local_ros_mirror = "http://packages.ros.org/ros2/ubuntu"

def apt_update():
    subprocess.run(["apt-get", "update"], check=True)

def apt_upgrade():
    subprocess.run(["apt-get", "-yy", "upgrade"], check=True)

def ssl_update():
    subprocess.run(["apt-get", "install", "ca-certificates", "-y"], check=True)
    subprocess.run(["update-ca-certificates"], check=True)

# Installing python2 because firmware upgrade still has not migrated to py3 and its a blocking feature
# TODO: When firmware upgrading migrates to py3, this can be removed
def install_python2():
    subprocess.run(["apt-get", "install", "python2", "-y"], check=True)
    subprocess.run(["curl", "https://bootstrap.pypa.io/pip/2.7/get-pip.py", "--output" , "get-pip.py"], check=False)
    subprocess.run(["python2", "get-pip.py"], check=True)
    subprocess.run(["pip2", "install", "requests"], check=True)
    subprocess.run(["pip2", "install", "pyserial"], check=True)

def apt_install_packages(
    package_list: typing.List[str],
    install_suggests: bool = False,
    install_recommends: bool = True,
):
    command = ["apt-get", "-yy"]
    if install_suggests:
        command.append("--install-suggests")
    if not install_recommends:
        command.append("--no-install-recommends")
    command.append("install")
    command.extend(package_list)
    subprocess.run(command, check=True)

def debootstrap(rootfs, use_local_mirror: bool = True):
    ubuntu_mirror = default_ubuntu_mirror
    if use_local_mirror:
        ubuntu_mirror = local_ubuntu_mirror
    subprocess.run(
        [
            "debootstrap",
            "--verbose",
            "--arch=arm64",
            "noble",
            rootfs,
            ubuntu_mirror,
        ],
        check=True,
    )


def ubuntu_apt_sources(release, use_local_mirror: bool = False):
    ubuntu_mirror = default_ubuntu_mirror
    if use_local_mirror:
        ubuntu_mirror = local_ubuntu_mirror

    sources = f"""deb {ubuntu_mirror} {release} main restricted universe multiverse
#deb-src {ubuntu_mirror} {release} main restricted universe multiverse

deb {ubuntu_mirror} {release}-updates main restricted universe multiverse
#deb-src {ubuntu_mirror} {release}-updates main restricted universe multiverse

deb {ubuntu_mirror} {release}-security main restricted universe multiverse
#deb-src {ubuntu_mirror} {release}-security main restricted universe multiverse

deb {ubuntu_mirror} {release}-backports main restricted universe multiverse
#deb-src {ubuntu_mirror} {release}-backports main restricted universe multiverse"""

    with open("/etc/apt/sources.list", "w+") as f:
        f.write(sources)


def ros_apt_sources(release, use_local_mirror: bool = False):
    shutil.copy(
        "/files/ros-archive-keyring.gpg",
        "/usr/share/keyrings/ros-archive-keyring.gpg",
    )

    ros_mirror = default_ros_mirror
    if use_local_mirror:
        ros_mirror = local_ros_mirror

    sources = f"deb {ros_mirror} {release} main"
    sources = f"""Types: deb
URIs:  {ros_mirror} 
Suites: {release}
Components: main 
Signed-By: /usr/share/keyrings/ros-archive-keyring.gpg
    """
    with open("/etc/apt/sources.list.d/ros-latest.sources", "w+") as f:
        f.write(sources)

#I don't think we need this at the moment, since we don't have any packages for ros2 available through apt
def ubiquity_apt_sources(release):
    shutil.copy(
        "/files/ubiquity-archive-keyring.gpg",
        "/usr/share/keyrings/ubiquity-archive-keyring.gpg",
    )

    sources = f"""Types: deb
URIs:  https://packages.ubiquityrobotics.com/ubuntu/ubiquity-testing 
Suites: focal
Components: main pi
Signed-By: /usr/share/keyrings/ubiquity-archive-keyring.gpg
    """

    with open("/etc/apt/sources.list.d/ubiquity-latest.sources", "w+") as f:
        f.write(sources)


def chroot_cleanup(release):
    ubuntu_apt_sources(release, use_local_mirror=False)
    ros_apt_sources(release, use_local_mirror=False)
    subprocess.run(["rm", "-f", "/etc/apt/*.save"], check=False)
    subprocess.run(["rm", "-f", "/etc/apt/sources.list.d/*.save"], check=False)
    subprocess.run(["apt-get", "clean"], check=True)
    subprocess.run(["rm", "-rf", "/var/lib/apt/lists"], check=False)

def setup_networking(hostname: str):
    with open("/etc/hostname", "w+") as f:
        f.write(f"{hostname}\n")

    with open("/etc/hosts", "w+") as f:
        hosts = f"""127.0.0.1       localhost
::1             localhost ip6-localhost ip6-loopback
ff02::1         ip6-allnodes
ff02::2         ip6-allrouters

127.0.1.1       {hostname} {hostname}.local
"""
        f.write(hosts)

    with open("/etc/network/interfaces", "w+") as f:
        ifaces = """# interfaces(5) file used by ifup(8) and ifdown(8)
# Include files from /etc/network/interfaces.d:
source-directory /etc/network/interfaces.d

# The loopback network interface
auto lo
iface lo inet loopback

"""
        f.write(ifaces)

    with open("/etc/systemd/network/10-eth-dhcp.network", "w+") as f:
        network_conf = """ # Run as DHCP client on all ethernet ports by default
[Match]
Name=eth*

[Link]
RequiredForOnline=no

[Network]
DHCP=ipv4
LinkLocalAddressing=ipv6

[DHCP]
RouteMetric=100
UseMTU=true
"""
        f.write(network_conf)

def common_ubiquity_customizations(release="noble", 
                                   hostname="ubuntu",
                                  git_token=""):
    ubuntu_apt_sources(release, use_local_mirror=True) #add ubuntu apt sources
    apt_update() # update ubuntu apt sources first and sync time
    ros_apt_sources(release) #add ros apt sources
    ubiquity_apt_sources(release) #add ubiquity apt sources
    ssl_update() #update ssl certificates if need be
    apt_update()
    apt_upgrade()

    # Do all of the apt installs upfront because it is slightly faster, and allows
    # us to potentially do something smarter in the future, like extract all the
    # packages before chrooting like debootstrap does.
    apt_install_packages(
        [
            # Base metapackages for ubuntu
            "ubuntu-minimal",
            # "ubuntu-standard",
            "ubuntu-server",
            # APT Keys, in a package for easy potential updates
            "ubiquity-archive-keyring",
            # Common utilities
            "vim",
            "nano",
            "emacs",
            "htop",
            "screen",
            "tmux",
            "at",
            "minicom",
            "curl",
            "git",
            "python3-pip",
            "chrony",
            "ethtool",
            "gnupg",
            "patch",
            "pollinate",
            "software-properties-common",
            "i2c-tools",
            "net-tools",
            "fake-hwclock",
            "hwclock-sync",
            "ssl-cert",
            # Raspberry Pi
            "libraspberrypi-bin",
            "libraspberrypi-dev",
            #"libraspberrypi-doc",
            "libraspberrypi0",
            #"raspberrypi-bootloader",
            "linux-firmware",
            "raspi-config",
            #"pigpiod",
            # Network Access
            "openssh-server",
            "libnss-mdns",
            "avahi-daemon",
            #"pifi", #pifi is not yet working with Ubuntu24 ARM64
            # ROS
            #"ros-noetic-ros-base",
            "ros-jazzy-ros-base",
            "python3-rosdep",
            #ROS2
            "python3-colcon-common-extensions",
            "ros-jazzy-controller-manager",
            "ros-jazzy-joint-state-publisher",
            "ros-jazzy-xacro",
            "python3-setuptools",
            # magni common,
            #ros-noetic-magni-robot is a package, that is currently being built for ros2 and will therfore be inside ros2_ws
            #"ros-noetic-magni-robot", #needed to enable magni-base.service,
            "bash-completion", # fixes autocompleteon problems
        ],
    )

    # Needed for lidars and others, its big but worth including, https://github.com/UbiquityRobotics/pi_image2/issues/40
    # Installed separately with --no-install-recommends because without it includes too many packages we don't need
    # along with gdm3
    subprocess.run("apt install -y ros-jazzy-pcl-ros --no-install-recommends", shell=True, check=True)

    # Installing python2 because firmware upgrade still has not migrated to py3 and its a blocking feature
    # TODO: When firmware upgrading migrates to py3, this can be removed
    #install_python2()

    groups = ["gpio", "i2c", "input", "spi", "bluetooth", "ssl-cert"]
    for group in groups:
        subprocess.run(["groupadd", "-f", "--system", group], check=True)

    shutil.copy("/files/adduser.local", "/usr/local/sbin/adduser.local")
    linux_util.make_executable("/usr/local/sbin/adduser.local")

    # set apt-daily.service to run after boot, not during it. This saves 30s of boot time
    os.makedirs("/etc/systemd/system/apt-daily.timer.d/", exist_ok=True)
    shutil.copy("/files/override.conf", "/etc/systemd/system/apt-daily.timer.d/override.conf")

    os.makedirs("/etc/ubiquity", exist_ok=True)
    with open("/etc/ubiquity/env.sh", "w+") as f:
        f.write("export ROS_HOSTNAME=$(hostname).local\n")
        f.write("export ROS_MASTER_URI=http://$(hostname):11311\n")
    with open("/etc/ubiquity/ros_setup.sh", "w+") as f:
        f.write(". /opt/ros/jazzy/setup.sh\n")
        f.write(
            "colcon_setup=/home/ubuntu/ros2_ws/install/setup.sh && test -f $colcon_setup && . $colcon_setup\n"
        )
        f.write(". /etc/ubiquity/env.sh\n")
    with open("/etc/ubiquity/ros_setup.bash", "w+") as f:
        f.write("source /opt/ros/jazzy/setup.bash\n")
        f.write(
            "colcon_setup=/home/ubuntu/ros2_ws/install/setup.bash && test -f $colcon_setup && . $colcon_setup\n"
        )
        f.write("source /etc/ubiquity/env.sh\n")
        # 1. Create group with fixed GID
    try:
        subprocess.run([
            "sudo", "groupadd", "-g", "1000", "ubuntu"
        ], check=True)
    except subprocess.CalledProcessError:
        print("Group 'ubuntu' already exists")
    
    # 2. Create user with fixed UID/GID
    subprocess.run([
        "sudo", "useradd",
        "--system",
        "--uid", "1000",
        "--gid", "1000",
        "--create-home",
        "--shell", "/bin/bash",
        "ubuntu"
    ], check=True)
    
    # 3. Configure sudoers safely
    with open("/tmp/ubuntu-sudoers", "w") as f:
        f.write("ubuntu ALL=(ALL) NOPASSWD: /usr/bin/rosdep fix-permissions\n")
    
    subprocess.run([
        "sudo", "install", "-o", "root", "-g", "root",
        "-m", "0440", "/tmp/ubuntu-sudoers", "/etc/sudoers.d/ubuntu"
    ], check=True)
    
    # 4. Create ROS workspace
    workspace_path = "/home/ubuntu/ros2_ws/src"
    os.makedirs(workspace_path, exist_ok=True)
    subprocess.run([
        "sudo", "chown", "-R", "ubuntu:ubuntu", "/home/ubuntu"
    ], check=True)

    # Make modifying the configs available to UI apps, and less of a hassle in general
    subprocess.run(["chown", "-R", "ubuntu:ubuntu", "/etc/ubiquity"])

    # Source ROS environment in the default bashrc for new users before creating the ubuntu user
    with open("/etc/skel/.bashrc", "a") as f:
        ros_source = "\n"
        ros_source += "source /etc/ubiquity/ros_setup.bash\n"
        f.write(ros_source)

    # 💡 Create ros2_ws directory with proper ownership
# Define paths
    ros2_ws = "/home/ubuntu/ros2_ws"
    ros2_ws_src = os.path.join(ros2_ws, "src")
    
    # Create directories with proper ownership
    os.makedirs(ros2_ws_src, exist_ok=True, mode=0o755)
    subprocess.run(["sudo", "chown", "-R", "ubuntu:ubuntu", "/home/ubuntu"], check=True)

    # 💡 Add ROS2 workspace build (uncomment and modify for ROS2)
    linux_util.run_as_user(
        "ubuntu",
        ["bash", "-c", "source /opt/ros/jazzy/setup.bash && colcon build --symlink-install"],
        cwd="/home/ubuntu/ros2_ws",
        check=True,
    )
                                      
    # 💡 Add rosdep fix before any rosdep commands
# Initialize rosdep
    subprocess.run(["sudo", "rosdep", "init"], check=True)
    
    # Fix permissions
    subprocess.run([
        "sudo", "chown", "-R", "ubuntu:ubuntu",
        "/home/ubuntu/.ros"
    ], check=True)

    # Update rosdep as ubuntu user
    linux_util.run_as_user(
        "ubuntu",
        ["rosdep", "update", "--include-eol-distros"],
        check=True
    )

except subprocess.CalledProcessError as e:
    print(f"Error during setup: {e}")
    exit(1)
# Ensure required tools are installed
    subprocess.run([
        "apt-get", "install", "-y",
        "device-tree-compiler",  # For dtc
        "python3-rosdep",       # ROS2 dependency management
        "python3-colcon-common-extensions",
        "ros-jazzy-desktop",
        "build-essential"# Build system
    ], check=True)





    # Create catkin_ws
    os.makedirs("/home/ubuntu/ros2_ws/src")
    subprocess.run(["chown", "-R", "ubuntu:ubuntu", "/home/ubuntu/ros2_ws"])
    linux_util.run_as_user(
        "ubuntu",
        ["bash", "-c", "source /opt/ros/jazzy/setup.bash && colcon build"],
        cwd="/home/ubuntu/ros2_ws",
        check=True,
    )

    # clone the ubiquity_motor TODO - when apt update of this is figured out, cloning this can be removed
    linux_util.run_as_user(
        "ubuntu",
        ["bash", "-c", f"git clone https://{git_token}@github.com/UbiquityRobotics/ubiquity_motor_ros2"],
        cwd="/home/ubuntu/ros2_ws/src",
        check=True,
    )

    #clone Magni robot jazzy devel bracnh                                   
    linux_util.run_as_user(
        "ubuntu",
        ["bash", "-c", f"git clone https://{git_token}@github.com/UbiquityRobotics/magni_robot.git -b jazzy-devel"],
        cwd="/home/ubuntu/ros2_ws/src",
        check=True,
    )
    # 💡 Add Device Tree Overlay compilation step
    # 💡 Add Device Tree Overlay compilation from source
    overlay_src = "/home/ubuntu/ros2_ws/src/magni_robot/raspberrypi/overlays/ubiquity-led-buttons.dts"
    overlay_dest = "/boot/overlays/ubiquity-led-buttons.dtbo"
    
    # Compile if source exists
    if os.path.exists(overlay_src):
        subprocess.run([
            "dtc", "-@", "-I", "dts", "-O", "dtb",
            "-o", overlay_dest, overlay_src
        ], check=True)
        shutil.copy(overlay_dest, "/boot/overlays/")
    else:
        raise FileNotFoundError(f"Device Tree Source missing: {overlay_src}")
    

        # 💡 Modified copy command with existence check
    if os.path.exists(overlay_dest):
        shutil.copy(overlay_dest, "/boot/overlays/")
    else:
        raise FileNotFoundError("Failed to generate Device Tree Overlay")
        # 💡 Initialize ROS2 workspace properly
    linux_util.run_as_user(
        "ubuntu",
        ["bash", "-c", "mkdir -p /home/ubuntu/ros2_ws/src"],
        check=True
    )
    # 💡 Add ROS2 workspace build (uncomment and modify for ROS2)
    linux_util.run_as_user(
        "ubuntu",
        ["bash", "-c", "source /opt/ros/jazzy/setup.bash && colcon build --symlink-install"],
        cwd="/home/ubuntu/ros2_ws",
        check=True,
    )


    # compile and source
    # linux_util.run_as_user(
    #     "ubuntu",
    #     ["bash", "-c", "source /opt/ros/noetic/setup.bash && catkin_make -j1"],
    #     cwd="/home/ubuntu/catkin_ws",
    #     check=True,
    # )

    # placing robot.yaml into /etc/ubiquity/
    # default_robot.yaml which gets copied to /etc/ubiquity/robot.yaml lives in magni_bringup package.
    # magni_bringup package gets installed with either apt OR directly compiled in ~/catkin_ws/.
    # however installed, getting robot.yaml from one of them is handeled here with the ~/catkin_ws having
    # priority if both cases are true
    config_catkin_path = "/home/ubuntu/ros2_ws/src/magni_robot/magni_bringup/config/default_robot.yaml"
    #config_apt_path = "/opt/ros/jazzy/share/magni_bringup/config/default_robot.yaml" #while magni_robot jazzy isnt available as apt, this is not an option
    # if magni_robot is installed with apt compiled in ~catkin_ws:
    if os.path.isfile(config_catkin_path):
        shutil.copy(config_catkin_path, "/etc/ubiquity/robot.yaml")
    # if magni_robot is installed with apt:
    elif os.path.isfile(config_apt_path):
        shutil.copy(config_apt_path, "/etc/ubiquity/robot.yaml")
    # otherwise bring up warning and exit
    else:
        #print("Could not find config on paths: " + config_catkin_path + " OR " + config_apt_path)
        print("Could not find config on paths: " + config_catkin_path)
        return -1

    setup_networking(hostname)

    # Set up fstab
    with open("/etc/fstab", "w+") as f:
        fstab = """proc            /proc           proc    defaults          0       0
/dev/mmcblk0p2  /               ext4    defaults,noatime  0       1
/dev/mmcblk0p1  /boot/          vfat    defaults          0       2
"""
        f.write(fstab)

    shutil.copy("/files/config.txt", "/boot/config.txt")
    with open("/boot/cmdline.txt", "w") as f:
        cmdline = "dwc_otg.lpm_enable=0 console=tty1 root=/dev/mmcblk0p2 rootfstype=ext4 elevator=deadline fsck.repair=yes rootwait quiet splash plymouth.ignore-serial-consoles init=/usr/lib/raspi-config/init_resize.sh"
        f.write(cmdline)

    # Enable i2c module on boot
    with open("/etc/modules", "a") as f:
        f.write("\ni2c-dev\n\n")

    # Enable resizefs
    shutil.copy("/files/resize2fs_once", "/etc/init.d/resize2fs_once")
    subprocess.run(["systemctl", "enable", "resize2fs_once"], check=True)

    # These 2 firmware directories are large, and we are never going to use them on a Pi
    shutil.rmtree("/usr/lib/firmware/netronome")
    shutil.rmtree("/usr/lib/firmware/amdgpu")

    #shutil.copy("/files/pifi.conf", "/etc/pifi/pifi.conf") #until pifi works on ubuntu 24 ARM64 this is not necessary
    #shutil.copy("/files/default_ap.em", "/etc/pifi/default_ap.em") #until pifi works on ubuntu 24 ARM64 this is not necessary

    # Copy device tree overlay for pifi buttons
    shutil.copy(
        "/device-tree/ubiquity-led-buttons.dtbo",
        "/boot/overlays/ubiquity-led-buttons.dtbo",
    )

    # Enable pigpio daemon that we use for sonars
    subprocess.run(["systemctl", "enable", "pigpiod.service"], check=True)

    # Enable systemd-networkd that we use for ethernet
    subprocess.run(["systemctl", "enable", "systemd-networkd.service"], check=True)

    # Enable auto-starting magni-base
    #shutil.copy("/files/roscore.service", "/etc/systemd/system/roscore.service")
    #subprocess.run(["systemctl", "enable", "roscore.service"], check=True)
    shutil.copy("/files/magni-base.sh", "/usr/sbin/magni-base")
    linux_util.make_executable("/usr/sbin/magni-base")
    shutil.copy("/files/magni-base.service", "/lib/systemd/system/magni-base.service")
    subprocess.run(["systemctl", "enable", "magni-base.service"], check=True)

    # Customize Message of The Day that shows up at login
    # We don't want to link to Ubuntu's help documents (because we are heavily modified)
    subprocess.run(["chmod", "-x", "/etc/update-motd.d/10-help-text"], check=True)
    # We don't want to notify about LTS upgrades because running that upgrade usually breaks ROS
    subprocess.run(["chmod", "-x", "/etc/update-motd.d/91-release-upgrade"], check=True)
    with open("/etc/update-motd.d/50-ubiquity", "w+") as f:
        motd = """#!/bin/sh
echo ""
echo "Welcome to the Ubiquity Robotics Raspberry Pi Image"
echo "Learn more: https://learn.ubiquityrobotics.com"
echo "Like our image? Support us on PayPal: tips@ubiquityrobotics.com"
# echo ""
# echo "Wifi can be managed with pifi (pifi --help for more info)"
# echo ""

# it is known that timeout for rtc causes large boot delays. This usually happens if MCB is not connected
# if the error message is detected prompt the user to disable the hwclock-sync.service
# see bigger discussion about this in https://github.com/UbiquityRobotics/pi_image2/issues/33
if dmesg | grep -q "Timed out waiting for device /dev/rtc" >> /dev/null; then
echo "WARNING:"
echo "Detected message:"
dmesg | grep "Timed out waiting for device /dev/rtc"
echo "Waiting for non-existent /dev/rtc can cause large boot delays."
echo "Disable waiting for rtc with:"
echo "sudo systemctl disable hwclock-sync.service"
echo ""
fi

# if rtc device is found but rtc sync is not enabled, prompt the user to enable it.
if hwclock --show > /dev/null 2>&1; then
if systemctl is-active hwclock-sync.service |  grep -q "inactive"; then
echo "WARNING:"
echo "Hardware RTC detected but hwclock-sync.service is not enabled."
echo "Enable it with:"
echo "sudo systemctl enable hwclock-sync.service"
echo ""
fi
fi
"""
        f.write(motd)
    subprocess.run(["chmod", "+x", "/etc/update-motd.d/50-ubiquity"], check=True)

    # Locales, ugly shell to generate all English UTF-8 locales
    # We may choose to generate more/less locales in the future, but this seems like a good setupfor now
    subprocess.run(
        "grep 'en_.*\.UTF-8' /usr/share/i18n/SUPPORTED | awk '{print $1}' | xargs locale-gen",
        shell=True,
        check=True,
    )

    # SSH Key Regeneration
    # We want to make sure that SSH keys are unique per host, thats why 
    # we delete all old keys and enable sshdgenkeys.service which generates
    # new keys on first boot
    shutil.copy("/files/sshdgenkeys.service", "/lib/systemd/system/sshdgenkeys.service")
    os.makedirs("/etc/systemd/system/sshd.service.wants/", exist_ok=True)
    subprocess.run(["systemctl", "enable", "sshdgenkeys.service"], check=True)
    # forget all host keys from history to start from a clean slate
    # keys will be regenerated on first boot
    subprocess.run(["rm -f /etc/ssh/ssh_host_*key"], shell=True, check=True)
    subprocess.run(["rm -f /etc/ssh/ssh_host_*.pub"], shell=True, check=True)

    # The file is missing on Focal by default, compared to Xenial, so chroot throws weird errors
    # On the Xenial image the file's content is one entry: /usr/lib/arm-linux-gnueabihf/libarmmem.so
    # It's unclear what it does, if it should be added here as well or not, but leaving the file empty seems to be enough to clear up chroot errors
    subprocess.run(["touch", "/etc/ld.so.preload"], check=True)


def build_rootfs_from_params(rootfs="/image-builds/PiFlavourMaker/noble-build",
                            release="noble", 
                            hostname="ubuntu",
                            git_token=""):
    print("=========================================")
    print("Output rootfs: " + str(rootfs))
    print("Release: " + str(release))
    print("Hostname: " + str(hostname))
    print("=========================================")

    # always delete rootfs if already exists on path
    if os.path.isdir(rootfs):
        print("Found an old rootfs at "+rootfs+". Deleting it.")
        shutil.rmtree(rootfs)
    
    # if there is a backup minimal rootfs, copy it on the current rootfs path
    restored_from_backup = False
    if os.path.isdir(rootfs+"-backup"):
        print("Found a backup at "+rootfs+"-backup, copying it over to use it.")
        subprocess.run("sudo rsync -axHAX --delete "+ rootfs+"-backup/" + " " + rootfs+"/", check=True, shell=True)
        restored_from_backup=True
    # otherwise debootstrap fresh rootfs and copy it to backup folder as well
    else:
        debootstrap(rootfs)

    # define chroot mountpoints
    chroot_mountpoints = {
        "/dev": {"recursive": True},
        "/proc:/proc": {},
        "/sys:/sys": {},
        "/dev/shm:/dev/shm": {},
        "/etc/resolv.conf": {},
        "./files:/files": {},
        "./device-tree:/device-tree": {},
    }

    with Chroot(rootfs, mountpoints=chroot_mountpoints):
        apt_update()

        # set git token as temporary global variable so external apt packages can easily authenticate 
        # git actions using command "git clone https://$GIT_TOKEN@github.com/repolik.git"
        if git_token != "":
            os.environ["GIT_TOKEN"] = git_token
        # we assume that the backup already has common ur customizations
        # that is why if restored from backup, we simply skip this step again
        if not restored_from_backup:
            common_ubiquity_customizations(release, hostname, git_token)

    

        # if the customization script path was given, execute customizations
        if customize_image != None:

            print("========== now installing external apt packages ==============")
            try:
                apt_install_packages(customize_image.conf["apt_get_packages"])
            except Exception as e:
                print(str(e))
                exit(0)

            
            print("========== now running external customizations ===============")
            customize_image.execute_customizations()
            print("========== end of external customizations ====================")

            # again compile anything in /home/ubuntu/catkin_ws. This allows that each customization does
            # not have to compile everything separately which would take longer time 
            linux_util.run_as_user(
                "ubuntu",
                #not sure yet if this build will build everything in the ~/ros2_ws/src/
                ["bash", "-c", "source /opt/ros/jazzy/setup.bash && colcon build --base-paths src/ubiquity_motor_ros2 src/ubiquity_motor_ros2/ubiquity_motor_ros2_msgs --cmake-args --event-handlers console_direct+"],
                cwd="/home/ubuntu/ros2_ws",
                check=True,
            )

        chroot_cleanup(release)

    print("Built rootfs at: " + rootfs)

    # writing into rootfs the date of its gerenation
    with open(rootfs+"/home/ubuntu/build_info.yaml", 'w+') as f:
        d = {"rootfs_build_date": datetime.today().date()}
        d = yaml.dump(d, f)

def build_rootfs_from_script(customization_script_path="",
                            git_token=""):
    global customize_image
    # import of customize image script from specified path
    if customization_script_path != "":
        try:
            print("Importing customize image script from "+customization_script_path)
            ci = SourceFileLoader("customize_image", customization_script_path).load_module()
            customize_image = ci.customizeImage()
        except Exception as e:
            print("Importing of customization script failed.")
            print(e)
            return
    else:
        sys.exit("Customization script path was not defined. This can be done with --customization_script_path argument. Exiting")

    build_rootfs_from_params(customize_image.conf["rootfs"],
                            customize_image.conf["release"],
                            customize_image.conf["hostname"],
                            git_token)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--release",
        default="noble",
        help="Release",
    )
    parser.add_argument(
        "--rootfs",
        default="/image-builds/PiFlavourMaker/noble-build",
        help="The path of generated rootfs",
    )
    parser.add_argument(
        "--hostname",
        default="ubiquityrobot",
        help="Network hostname of the generated rootfs",
    )
    parser.add_argument(
        "--git_token",
        default="",
        help="Git token that is going to be temporary set as GIT_TOKEN in chroot session. Users can invoke that to authenticate git actions. Leave empty if not needed",
    )
    parser.add_argument(
        "--customization_script_path",
        default="",
        help="Customization script path",
    )
    py_arguments, unknown = parser.parse_known_args()

    if py_arguments.customization_script_path == "":
        build_rootfs_from_params(py_arguments.rootfs, 
                                py_arguments.release, 
                                py_arguments.hostname, 
                                py_arguments.git_token)
    else:
        build_rootfs_from_script(py_arguments.customization_script_path,
                                py_arguments.git_token)
