#!/usr/bin/env python3

import os, sys
import subprocess
import time
import linux_util
import image_util
import argparse
from datetime import datetime
from importlib.machinery import SourceFileLoader
from build_rootfs import build_rootfs_fromscript
import yaml

# append this path to sys path so the python files from all subdirectories
# can be found by and python script - needed for sharing common 
# customizations scripts 
sys.path.append(os.getcwd())

# global conf file
conf = dict()

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

    # setup rootfs
    try:
        build_rootfs_fromscript(py_arguments.customization_script_path,
                                py_arguments.git_token)
    except Exception as e:
        print(e)
        sys.exit("Something went wrong with building rootfs")

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
            d = {"image_build_date": datetime.today().date(),
                 "image_name": image}
            d = yaml.dump(d, f)
    except Exception as e:
        print("Something wrong with reading "+conf["rootfs"]+"/home/ubuntu/build_info.yaml")
        print(e)
        exit(0)    

    # Calculate size of rootfs
    rootfs_size = linux_util.du_mb(conf["rootfs"])
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
                    subprocess.run(["rsync", "-aHAXx", conf["rootfs"] + "/", "mount/"], check=False)

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
