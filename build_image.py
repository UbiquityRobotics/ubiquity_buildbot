#!/usr/bin/env python3

import os, sys
import subprocess
import shutil
import crypt
from contextlib import contextmanager

from pychroot import Chroot

import typing
from typing import Iterator

import linux_util
import image_util

hostname = "pi-focal"

rootfs = "/focal-build"
release = "focal"

default_ubuntu_mirror = "http://ports.ubuntu.com/"
# local_ubuntu_mirror = "http://ports.ubuntu.com/"
local_ubuntu_mirror = "http://us-east-2.ec2.ports.ubuntu.com/ubuntu-ports/"
# local_ubuntu_mirror = "http://mirrors.mit.edu/ubuntu-ports/"
default_ros_mirror = "http://packages.ros.org/ros/ubuntu"
local_ros_mirror = "http://packages.ros.org/ros/ubuntu"


def apt_update():
    subprocess.run(["apt-get", "update"], check=True)


def apt_upgrade():
    subprocess.run(["apt-get", "-yy", "upgrade"], check=True)

def ssl_update():
    subprocess.run(["apt-get", "install", "pt-transport-https", "ca-certificates", "-y"], check=True)
    subprocess.run(["update-ca-certificates"], check=True)

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


def debootstrap(use_local_mirror: bool = True):
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


def ros_apt_sources(use_local_mirror: bool = False):
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


def ubiquity_apt_sources():
    shutil.copy(
        "/files/ubiquity-archive-keyring.gpg",
        "/usr/share/keyrings/ubiquity-archive-keyring.gpg",
    )

    sources = f"""Types: deb
URIs:  https://packages.ubiquityrobotics.com/ubuntu/ubiquity-testing 
Suites: {release}
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


if os.path.isdir(rootfs):
    shutil.rmtree(rootfs)

debootstrap()

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
    ubuntu_apt_sources(use_local_mirror=True)
    ros_apt_sources()
    ubiquity_apt_sources()
    ssl_update()
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
            "ros-noetic-raspicam-node",
            "ros-noetic-pi-sonar",
            "ros-noetic-ubiquity-motor",
            "ros-noetic-oled-display-node",
            "ros-noetic-move-basic",
            "ros-noetic-fiducials",
            "ros-noetic-magni-robot",
            "ros-noetic-teleop-twist-keyboard",
            "ros-noetic-carrot-planner", # Required but not properly installed by magni-robot
            "cairosvg",  # Required but not properly installed by fiducals
            "poppler-utils",  # Required but not properly installed by fiducals
        ]
    )

    groups = ["gpio", "i2c", "input", "spi", "bluetooth", "ssl-cert"]
    for group in groups:
        subprocess.run(["groupadd", "-f", "--system", group], check=True)

    shutil.copy("/files/adduser.local", "/usr/local/sbin/adduser.local")
    linux_util.make_executable("/usr/local/sbin/adduser.local")

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
    linux_util.run_as_user(
        "ubuntu",
        ["bash", "-c", "source /opt/ros/noetic/setup.bash && catkin_make"],
        cwd="/home/ubuntu/catkin_ws",
        check=True,
    )

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
"""
        f.write(motd)
    subprocess.run(["chmod", "+x", "/etc/update-motd.d/50-ubiquity"], check=True)

    # Locales, ugly shell to generate all English UTF-8 locales
    subprocess.run(
        "grep 'en_.*\.UTF-8' /usr/share/i18n/SUPPORTED | awk '{print $1}' | xargs -L 1 locale-gen",
        shell=True,
        check=True,
    )

    # The file is missing on Focal by default, compared to Xenial, so chroot throws weird errors
    # On the Xenial image the file's content is one entry: /usr/lib/arm-linux-gnueabihf/libarmmem.so
    # It's unclear what it does, if it should be added here as well or not, but leaving the file empty seems to be enough to clear up chroot errors
    subprocess.run(["touch", "/etc/ld.so.preload"], check=True)

    chroot_cleanup()


# Something is creating a file that is in focal-build/focal-build, we want to get rid of it
shutil.rmtree("/focal-build/focal-build")

# Calculate size of rootfs
rootfs_size = linux_util.du_mb(rootfs)
print(f"Root FS is {rootfs_size} MiB")

# Leave 500 MiB free space in the root partition
root_part_size = rootfs_size + 500
print(f"Root Part will be {root_part_size} MiB")

# Make image file
image_util.create_image_file("focal.img", 128, root_part_size)

with image_util.loopdev_context_manager("focal.img") as loop:
    boot_loop = loop + "p1"
    root_loop = loop + "p2"
    subprocess.run(
        ["mkfs.vfat", "-n", "BOOT", "-S", "512", "-s", "16", "-v", boot_loop],
        check=True,
    )

    subprocess.run(
        ["mkfs.ext4", "-L", "ROOT", "-m", "0", "-O", "^huge_file", root_loop],
        check=True,
    )

    with image_util.mount_context_manager(root_loop, "mount", "ext4"):
        os.makedirs("mount/boot", exist_ok=True)
        with image_util.mount_context_manager(boot_loop, "mount/boot", "vfat"):
            # rsync errors on copying some attrs to /boot because it is fat
            # so we disable the check for the subprocess call. We should find
            # a better solution, like figuring out how to ignore only the expected error.
            subprocess.run(["rsync", "-aHAXx", rootfs + "/", "mount/"], check=False)
