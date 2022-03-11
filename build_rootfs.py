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

py_arguments = None

# mirror settings
default_ubuntu_mirror = "http://ports.ubuntu.com/"
local_ubuntu_mirror = "http://us-east-2.ec2.ports.ubuntu.com/ubuntu-ports/"
# local_ubuntu_mirror = "http://mirrors.mit.edu/ubuntu-ports/"
default_ros_mirror = "http://packages.ros.org/ros/ubuntu"
local_ros_mirror = "http://packages.ros.org/ros/ubuntu"

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
            "--arch=armhf",
            "focal",
            rootfs,
            ubuntu_mirror,
        ],
        check=True,
    )


def ubuntu_apt_sources(use_local_mirror: bool = False):
    ubuntu_mirror = default_ubuntu_mirror
    if use_local_mirror:
        ubuntu_mirror = local_ubuntu_mirror

    sources = f"""deb {ubuntu_mirror} {py_arguments.release} main restricted universe multiverse
#deb-src {ubuntu_mirror} {py_arguments.release} main restricted universe multiverse

deb {ubuntu_mirror} {py_arguments.release}-updates main restricted universe multiverse
#deb-src {ubuntu_mirror} {py_arguments.release}-updates main restricted universe multiverse

deb {ubuntu_mirror} {py_arguments.release}-security main restricted universe multiverse
#deb-src {ubuntu_mirror} {py_arguments.release}-security main restricted universe multiverse

deb {ubuntu_mirror} {py_arguments.release}-backports main restricted universe multiverse
#deb-src {ubuntu_mirror} {py_arguments.release}-backports main restricted universe multiverse"""

    with open("/etc/apt/sources.list", "w+") as f:
        f.write(sources)


def ros_apt_sources(use_local_mirror: bool = False):
    shutil.copy(
        "/files/ros-archive-keyring.gpg",
        "/usr/share/keyrings/ros-archive-keyring.gpg",
    )

    ros_mirror = default_ros_mirror
    if use_local_mirror:
        ros_mirror = local_ros_mirror

    sources = f"deb {ros_mirror} {py_arguments.release} main"
    sources = f"""Types: deb
URIs:  {ros_mirror} 
Suites: {py_arguments.release}
Components: main 
Signed-By: /usr/share/keyrings/ros-archive-keyring.gpg
    """
    with open("/etc/apt/sources.list.d/ros-latest.sources", "w+") as f:
        f.write(sources)


def ubiquity_apt_sources():
    shutil.copy(
        "/files/ubiquity-archive-keyring.gpg",
        "/usr/share/keyrings/ubiquity-archive-keyring.gpg",
    )

    sources = f"""Types: deb
URIs:  https://packages.ubiquityrobotics.com/ubuntu/ubiquity-testing 
Suites: {py_arguments.release}
Components: main pi
Signed-By: /usr/share/keyrings/ubiquity-archive-keyring.gpg
    """

    with open("/etc/apt/sources.list.d/ubiquity-latest.sources", "w+") as f:
        f.write(sources)


def chroot_cleanup():
    ubuntu_apt_sources(use_local_mirror=False)
    ros_apt_sources(use_local_mirror=False)
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

def main():
    global py_arguments

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--release",
        default="focal",
        help="Release",
    )
    parser.add_argument(
        "--rootfs",
        default="/image-builds/PiFlavourMaker/focal-build",
        help="The path of generated rootfs",
    )
    parser.add_argument(
        "--hostname",
        default="pi-focal",
        help="Network hostname of the generated rootfs",
    )

    py_arguments, unknown = parser.parse_known_args()

    print("=========================================")
    print("Output rootfs: " + str(py_arguments.rootfs))
    print("Release: " + str(py_arguments.release))
    print("Hostname: " + str(py_arguments.hostname))
    print("=========================================")

    if os.path.isdir(py_arguments.rootfs):
        shutil.rmtree(py_arguments.rootfs)
    debootstrap(py_arguments.rootfs)

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

    with Chroot(py_arguments.rootfs, mountpoints=chroot_mountpoints):
        ubuntu_apt_sources(use_local_mirror=True) #add ubuntu apt sources
        apt_update() # update ubuntu apt sources first and sync time
        ros_apt_sources() #add ros apt sources
        ubiquity_apt_sources() #add ubiquity apt sources
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
                "ubuntu-standard",
                # "ubuntu-server",
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
                "libraspberrypi-doc",
                "libraspberrypi0",
                "raspberrypi-bootloader",
                "linux-firmware",
                "raspi-config",
                "pigpiod",
                # Network Access
                "openssh-server",
                "libnss-mdns",
                "avahi-daemon",
                "pifi",
                # ROS
                "ros-noetic-ros-base",
                "python3-rosdep",
                # magni common,
                "ros-noetic-magni-robot" #needed to enable magni-base.service
            ]
        )

        # Installing python2 because firmware upgrade still has not migrated to py3 and its a blocking feature
        # TODO: When firmware upgrading migrates to py3, this can be removed
        install_python2()

        groups = ["gpio", "i2c", "input", "spi", "bluetooth", "ssl-cert"]
        for group in groups:
            subprocess.run(["groupadd", "-f", "--system", group], check=True)

        shutil.copy("/files/adduser.local", "/usr/local/sbin/adduser.local")
        linux_util.make_executable("/usr/local/sbin/adduser.local")

        # set apt-daily.service to run after boot, not during it. This saves 30s of boot time
        os.makedirs("/etc/systemd/system/apt-daily.timer.d/", exist_ok=True)
        shutil.copy("/files/override.conf", "/etc/systemd/system/apt-daily.timer.d/override.conf")

        # Setup the robot config
        os.makedirs("/etc/ubiquity", exist_ok=True)
        shutil.copy("/files/robot.yaml", "/etc/ubiquity/robot.yaml")
        with open("/etc/ubiquity/env.sh", "w+") as f:
            f.write("export ROS_HOSTNAME=$(hostname).local\n")
            f.write("export ROS_MASTER_URI=http://$(hostname):11311\n")
        with open("/etc/ubiquity/ros_setup.sh", "w+") as f:
            f.write(". /opt/ros/noetic/setup.sh\n")
            f.write(
                "catkin_setup=/home/ubuntu/catkin_ws/devel/setup.sh && test -f $catkin_setup && . $catkin_setup\n"
            )
            f.write(". /etc/ubiquity/env.sh\n")
        with open("/etc/ubiquity/ros_setup.bash", "w+") as f:
            f.write("source /opt/ros/noetic/setup.bash\n")
            f.write(
                "catkin_setup=/home/ubuntu/catkin_ws/devel/setup.bash && test -f $catkin_setup && . $catkin_setup\n"
            )
            f.write("source /etc/ubiquity/env.sh\n")

        # Make modifying the configs available to UI apps, and less of a hassle in general
        subprocess.run(["chown", "-R", "ubuntu:ubuntu", "/etc/ubiquity"])

        # Source ROS environment in the default bashrc for new users before creating the ubuntu user
        with open("/etc/skel/.bashrc", "a") as f:
            ros_source = "\n"
            ros_source += "source /etc/ubiquity/ros_setup.bash\n"
            f.write(ros_source)

        linux_util.create_user("ubuntu", "ubuntu")
        linux_util.add_user_sudo("ubuntu")

        # Init rosdep
        subprocess.run(["rosdep", "init"], check=True)
        subprocess.run(["rosdep", "update"], check=True)
        linux_util.run_as_user("ubuntu", ["rosdep", "update"])

        # Create catkin_ws
        os.makedirs("/home/ubuntu/catkin_ws/src")
        subprocess.run(["chown", "-R", "ubuntu:ubuntu", "/home/ubuntu/catkin_ws"])
        linux_util.run_as_user(
            "ubuntu",
            ["bash", "-c", "source /opt/ros/noetic/setup.bash && catkin_init_workspace"],
            cwd="/home/ubuntu/catkin_ws/src",
            check=True,
        )
        # clone the noetic branch of magni robot TODO - when apt update of this is figured out, cloning this can be removed
        linux_util.run_as_user(
            "ubuntu",
            ["bash", "-c", "git clone https://github.com/UbiquityRobotics/magni_robot.git --branch noetic-devel"],
            cwd="/home/ubuntu/catkin_ws/src",
            check=True,
        )
        # clone the oled display node TODO - when apt update of this is figured out, cloning this can be removed
        linux_util.run_as_user(
            "ubuntu",
            ["bash", "-c", "git clone https://github.com/UbiquityRobotics/oled_display_node.git"],
            cwd="/home/ubuntu/catkin_ws/src",
            check=True,
        )
        # compile and source
        linux_util.run_as_user(
            "ubuntu",
            ["bash", "-c", "source /opt/ros/noetic/setup.bash && catkin_make"],
            cwd="/home/ubuntu/catkin_ws",
            check=True,
        )

        setup_networking(py_arguments.hostname)

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

        shutil.copy("/files/pifi.conf", "/etc/pifi/pifi.conf")
        shutil.copy("/files/default_ap.em", "/etc/pifi/default_ap.em")

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
        shutil.copy("/files/roscore.service", "/etc/systemd/system/roscore.service")
        subprocess.run(["systemctl", "enable", "roscore.service"], check=True)
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
echo ""
echo "Wifi can be managed with pifi (pifi --help for more info)"
echo ""

# it is known that timeout for rtc causes large boot delays. This usually happens if MCB is not connected
# if the error message is detected prompt the user to disable the hwclock-sync.service
# see bigger discussion about this in https://github.com/UbiquityRobotics/pi_image2/issues/33
if dmesg | grep -q "Timed out waiting for device /dev/rtc" >> /dev/null; then
    echo "WARNING:"
    echo "Detected message:"
    dmesg | grep "Timed out waiting for device /dev/rtc"
    echo "Waiting for non-existent /dev/rtc can cause large boot delays."
    echo "Disable waiting for rtc with sudo systemctl disable hwclock-sync.service"
    echo ""
fi

# if rtc device is found but rtc sync is not enabled, prompt the user to enable it.
if hwclock --show > /dev/null 2>&1; then
    if systemctl is-active hwclock-sync.service |  grep -q "inactive"; then
        echo "WARNING:"
        echo "Hardware RTC detected but hwclock-sync.service is not enabled."
        echo "Enable it with sudo systemctl enable hwclock-sync.service"
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

    print("Built rootfs at: " + py_arguments.rootfs)

    # writing into rootfs the date of its gerenation

    with open(py_arguments.rootfs+"/home/ubuntu/build_info.yaml", 'w+') as f:
        d = {"rootfs_build_date": datetime.today().date()}
        d = yaml.dump(d, f)

if __name__ == "__main__":
    main()
