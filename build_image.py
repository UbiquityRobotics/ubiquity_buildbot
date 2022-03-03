#!/usr/bin/env python3

import os, sys
from re import sub
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
from importlib.machinery import SourceFileLoader


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
    print(command)
    subprocess.run(command, check=True)


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
                "hostname",
                "apt_get_packages"}
    for key in valid_keys:
        if key not in conf.keys():
            print("Imported conf is missing key: " + key)
            return False

    # currently only possible value for release is "focal"
    if conf["release"] != "focal":
        print("'release' is set to "+conf["release"]+". Currently only possible value for release is 'focal'. Please correct this")
        return False
    
    return True

def subprocess_run(command):
    print("RUNNING COMMAND: " + command)
    subprocess.run(command, shell= True, check=True)


def main():
    global conf

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--customization_script_path",
        default="",
        help="Customization script path",
    )
    parser.add_argument(
        "--skip_compressing_image",
        action="store_true",
        help="Weather to skip compressing final image. For debug purposes",
    )
    parser.add_argument(
        "--skip_making_image",
        action="store_true",
        help="Weather to skip making final image (file that ends with .img). For debug purposes. If this is true, also image compression will be skipped",
    )
    parser.add_argument(
        "--git_token",
        default="",
        help="git token that is going to be temporary set as GIT_TOKEN in chroot session. Users can invoke that to authenticate git actions",
    )
    py_arguments, unknown = parser.parse_known_args()


    # import of customize image script from specified path
    if py_arguments.customization_script_path != "":
        try:
            ci = SourceFileLoader("customize_image", py_arguments.customization_script_path).load_module()
            customize_image = ci.customizeImage()
        except Exception as e:
            print("Importing of customization script failed.")
            print(e)
            return
    else:
        sys.exit("Customization script path was not defined. This can be done with --customization_script_path argument. Exiting")

    # try importing settings from the config yaml file
    try:
        conf = customize_image.conf
        # check if imported config is valid and exit if its not
        if not is_conf_valid(conf):
            return False
    except Exception as e:
        print("Error reading imported config from customization script")
        print(e)

    # create image name from the parameters imported from config
    image = str(datetime.today().date())+"-"+conf["flavour"]+"-"+conf["release"]+"-raspberry-pi.img"


    print("=========================================")
    print("Settings from scripts arguments:")
    print("Skip making image: " + str(py_arguments.skip_making_image))
    print("Skip compressing image: " + str(py_arguments.skip_compressing_image))
    print("---")
    print("Settings from customization script:")
    print("Rootfs: " + conf["rootfs"])
    print("Release: " + conf["release"])
    print("Imagedir: " + conf["imagedir"])
    print("Rootfs extra space (mb): " + str(conf["rootfs_extra_space_mb"]))
    print("Getting customization script from: " + str(py_arguments.customization_script_path))
    print("Apt packages to install:")
    print(*conf["apt_get_packages"])
    print("---")
    print("Will generate image with name: " + image)
    print("=========================================")

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

    if not os.path.isdir(conf["rootfs"]):
        print("WARNING: Could not find " + conf["rootfs"] + ". Automatically starting the building of rootfs:")
        # we run the rootfs build script with absolute path so it works both on test machines and buildbot.
        subprocess_run("sudo python3 "+os.getcwd()+"/build_rootfs.py --rootfs " + conf["rootfs"])

    # warning of the build rootfs date if that is too large
    try:
        # opening the build_info.yaml with r+ so we read, write and prepend new stuff 
        with open(conf["rootfs"]+"/home/ubuntu/build_info.yaml", "r+") as f:
            build_info = yaml.safe_load(f)
            print("root fs build date: "+str(build_info["rootfs_build_date"]))
            d_days = datetime.today().date()-build_info["rootfs_build_date"]
            if d_days.days > 7:
                print("WARNING: the rootfs was built "+str(d_days.days)+" days ago")

            # add the image build date
            d = {"image_build_date": datetime.today().date()}
            d = yaml.dump(d, f)
    except Exception as e:
        print("Something wrong with reading "+conf["rootfs"]+"/home/ubuntu/build_info.yaml")
        print(e)
        exit(0)

    rootfs_ext = conf["rootfs"] + "-extended"

    # using rsync is faster then cp, since if doing it multiple times on same machine it takes less time
    # options used with rsync
    # -a  : all files, with permissions, etc..
    # -x  : stay on one file system
    # -H  : preserve hard links (not included with -a)
    # -A  : preserve ACLs/permissions (not included with -a)
    # -X  : preserve extended attributes (not included with -a)
    # --delete: deletes files in the destination that are not present in the source.
    subprocess_run("sudo rsync -axHAX --delete "+ conf["rootfs"]+"/" + " " + rootfs_ext+"/")

    with Chroot(rootfs_ext, mountpoints=chroot_mountpoints):
        # since we are taking an already made rootfs, the rights to some folders need to be restored
        subprocess_run("chmod 1777 /tmp")
        subprocess_run("chmod -R 775 /var/cache/man/")
        
        ssl_update()
        apt_update()
        apt_upgrade()

        # set git token as temporary global variable so external apt packages can easily authenticate 
        # git actions using command "git clone https://$GIT_TOKEN@github.com/repolik.git"
        if py_arguments.git_token != "":
            os.environ["GIT_TOKEN"] = py_arguments.git_token

        print("========== now installing external apt packages ==============")

        apt_install_packages(conf["apt_get_packages"])

        if py_arguments.customization_script_path != "":
            print("========== now running external customizations ===============")
            customize_image.execute_customizations()
            print("========== end of external customizations ====================")

        chroot_cleanup()
    
    # Calculate size of rootfs
    rootfs_size = linux_util.du_mb(rootfs_ext)
    print(f"Root FS is {rootfs_size} MiB")

    # Leave free space in the root partition
    root_part_size = rootfs_size + conf["rootfs_extra_space_mb"]
    print(f"Root Part will be {root_part_size} MiB")

    # Make image file
    # create imagedir if it does not already exist
    if not os.path.isdir(conf["imagedir"]):
        subprocess.run(["mkdir", "-p", conf["imagedir"]], check=True)

    # don't make image if the flag skip_making_image is true
    if not py_arguments.skip_making_image:
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
                    print("The next couple of rsync executions will fail with 'Operation not permitted'. This can be ignored.")
                    subprocess.run(["rsync", "-aHAXx", rootfs_ext + "/", "mount/"], check=False)

            # don't compress image if skip_compressing_image is true
            if not py_arguments.skip_compressing_image:
                print("Compressing image to "+conf["imagedir"]+"/"+image+".xz")
                # if file already exists, delete it
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
    else:
        print("Skipping making of .img file")

    print("Script ending successfully")

if __name__ == "__main__":
    main()
