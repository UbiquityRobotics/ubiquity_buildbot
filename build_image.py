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
import image_util
import argparse
from datetime import datetime
import yaml

# global conf file
conf = dict()

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

def install_desktop_environment():
    # install the new desktop enviroment
    subprocess.run(["apt-get", "install", "-y", "gdm3"], check=False)

    # Setup the desktop to not logout on idle
    os.makedirs("/usr/share/glib-2.0/schemas/", exist_ok=True)
    # In chroot "gsettings set" commands don't work, thats why we change default desktop settings
    # https://answers.launchpad.net/cubic/+question/696919
    shutil.copy("files/org.gnome.desktop.screensaver.gschema.xml", "/usr/share/glib-2.0/schemas/org.gnome.desktop.screensaver.gschema.xml")
    shutil.copy("files/org.gnome.settings-daemon.plugins.power.gschema.xml", "/usr/share/glib-2.0/schemas/org.gnome.settings-daemon.plugins.power.gschema.xml")
    # schemas must be recompiled after every change
    subprocess.run(["glib-compile-schemas", "/usr/share/glib-2.0/schemas"], check=False)
        
    # enable automatic login for user ubuntu by setting AutomaticLoginEnable and AutomaticLogin to true
    subprocess.run(["sed", "-i", '/AutomaticLoginEnable.*/c\AutomaticLoginEnable = true', "/etc/gdm3/custom.conf"], check=False)
    subprocess.run(["sed", "-i", '/AutomaticLogin .*/c\AutomaticLogin = ubuntu', "/etc/gdm3/custom.conf"], check=False)

def install_python2():
    subprocess.run(["apt-get", "install", "python2", "-y"], check=False)
    subprocess.run(["curl", "https://bootstrap.pypa.io/pip/2.7/get-pip.py", "--output" , "get-pip.py"], check=False)
    subprocess.run(["python2", "get-pip.py"], check=False)
    subprocess.run(["pip2", "install", "requests"], check=False)
    subprocess.run(["pip2", "install", "pyserial"], check=False)

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
            conf["rootfs"],
            ubuntu_mirror,
        ],
        check=True,
    )


def ubuntu_apt_sources(use_local_mirror: bool = False):
    ubuntu_mirror = default_ubuntu_mirror
    if use_local_mirror:
        ubuntu_mirror = local_ubuntu_mirror

    sources = f"""deb {ubuntu_mirror} {conf['release']} main restricted universe multiverse
#deb-src {ubuntu_mirror} {conf['release']} main restricted universe multiverse

deb {ubuntu_mirror} {conf['release']}-updates main restricted universe multiverse
#deb-src {ubuntu_mirror} {conf['release']}-updates main restricted universe multiverse

deb {ubuntu_mirror} {conf['release']}-security main restricted universe multiverse
#deb-src {ubuntu_mirror} {conf['release']}-security main restricted universe multiverse

deb {ubuntu_mirror} {conf['release']}-backports main restricted universe multiverse
#deb-src {ubuntu_mirror} {conf['release']}-backports main restricted universe multiverse"""

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

    sources = f"deb {ros_mirror} {conf['release']} main"
    sources = f"""Types: deb
URIs:  {ros_mirror} 
Suites: {conf['release']}
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
Suites: {conf['release']}
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

def is_conf_valid(conf):
    # first check if conf is dict
    if type(conf) != dict:
        print("Imported config file is not dictionary")
        return False

    # check if the valid keys are in conf
    valid_keys={"flavour",
                "release", 
                "imagedir", 
                "rootfs_extra_space_mb", 
                "rootfs",
                "hostname"}
    for key in valid_keys:
        if key not in conf.keys():
            print("Imported conf is missing key: " + key)
            return False
    
    return True

def main():
    global conf

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skip_compressing_image",
        action="store_true",
        help="Weather to skip compressing final image. For debug purposes",
    )
    parser.add_argument(
        "--config_path",
        default="default-build-settings.yaml",
        help="Path to settings yaml",
    )
    py_arguments, unknown = parser.parse_known_args()

    # try importing settings from the config yaml file
    try:
        with open(py_arguments.config_path) as yp:
            conf = yaml.safe_load(yp)
            # check if imported config is valid and exit if its not
            if not is_conf_valid(conf):
                return False
    except Exception as e:
        print("Error reading " + py_arguments.config_path)
        print(e)

    # create image name from the parameters imported from config
    image = str(datetime.today().date())+"-"+conf["flavour"]+"-"+conf["release"]+"-raspberry-pi.img"

    print("=========================================")
    print("Settings from scripts arguments:")
    print("Skip compressing image: " + str(py_arguments.skip_compressing_image))
    print("Config path: " + str(py_arguments.config_path))
    print("---")
    print("Settings from yaml:")
    print("Rootfs: " + conf["rootfs"])
    print("Release: " + conf["release"])
    print("Imagedir: " + conf["imagedir"])
    print("Rootfs extra space (mb): " + str(conf["rootfs_extra_space_mb"]))
    print("---")
    print("Generated image name: " + image)
    print("=========================================")

    if os.path.isdir(conf["rootfs"]):
        shutil.rmtree(conf["rootfs"])
    debootstrap()

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

    with Chroot(conf["rootfs"], mountpoints=chroot_mountpoints):
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

        # Installing python2 because firmware upgrade still has not migrated to py3 and its a blocking feature
        # TODO: When firmware upgrading migrates to py3, this can be removed
        install_python2()

        # Installing and configuring desktop environment
        install_desktop_environment()

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

        setup_networking(conf["hostname"])

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
echo ""
echo "If RPI is not connected to Ubiquity Robotics MCB, make sure to comment out line dtoverlay=i2c-rtc,mcp7940x in /boot/config.txt to shorthen boot times"
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
    # shutil.rmtree("/focal-build/focal-build")

    # Calculate size of rootfs
    rootfs_size = linux_util.du_mb(conf["rootfs"])
    print(f"Root FS is {rootfs_size} MiB")

    # Leave 500 MiB free space in the root partition
    root_part_size = rootfs_size + conf["rootfs_extra_space_mb"]
    print(f"Root Part will be {root_part_size} MiB")

    # Make image file
    # create imagedir if it does not already exist
    if not os.path.isdir(conf["imagedir"]):
        subprocess.run(["mkdir", "-p", conf["imagedir"]], check=True)

    # remove image file if it already exsists
    if os.path.exists(conf["imagedir"]+"/"+image):
        os.remove(conf["imagedir"]+"/"+image)

    # create image file
    image_util.create_image_file(conf["imagedir"]+"/"+image, 128, root_part_size)

    print("Created image: "+conf["imagedir"]+"/"+image)

    with image_util.loopdev_context_manager(conf["imagedir"]+"/"+image) as loop:
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
                subprocess.run(["rsync", "-aHAXx", conf["rootfs"] + "/", "mount/"], check=False)

    if not py_arguments.skip_compressing_image:
        print("Compressing image to "+conf["imagedir"]+"/"+image+".xz")
        # if file already exsists, delete it
        if os.path.exists(conf["imagedir"]+"/"+image+".xz"):
            os.remove(conf["imagedir"]+"/"+image+".xz")
        # execute compression
        subprocess.run(["xz", "-4", conf["imagedir"]+"/"+image], check=False)
    else:
        print("Skipping compression of image")

    print("Overwriting latest_image with: "+conf["imagedir"]+"/"+image)
    # overwrite latest_image the name of the latest image for buildbot to be able to upload
    f = open("latest_image", "w")
    f.write(conf["imagedir"]+"/"+image)
    subprocess.run(["chmod", "a+r", "latest_image"], check=False)
    f.close()

    print("Image build successfully")

if __name__ == "__main__":
    main()
