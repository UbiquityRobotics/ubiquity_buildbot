# Creating an external custom image using pi_image2

In the tutorial we are going to have a specific example named "coolproject" - in your case this should be changed to an appropriate variable

We have a new project called "coolproject" which is a ROS metapackage (package of ROS packages) and has its own repo somewhere on github. It looks something like this:

```
ubuntu@ubiquityrobot:~/catkin_ws/src/coolproject$ ls
coolproject_launch  coolproject_nav
```

We want to create a RPI image specific for this project using pi_image2 and buildbot. Lets start.

## Creating a `coolproject_image`

In project folder we create a folder called `coolproject_image`

    mdkir -p ~/catkin_ws/src/coolproject/coolproject_image

Notice here that this is NOT a ROS package, but simply a folder created with mkdir. Nonetheless this is going to look like any other ROS package and is going to live among them in the meta package. If your project is not a metapackage, simply place the `coolproject_image` in the root directory of your repo and continue with the tutorial.

## Creating the image minimal customization script

Now lets create a python script that will hold instructions for making this project specific image:

    nano ~/catkin_ws/src/coolproject/coolproject_image/customize_coolproject_image.py

Notice here that the `.py` script can be arbitrarily named but it is recommended to keep the naming convention `customize_NAME_image.py` where `NAME` is the name of your project (for consistency).

Now copy/paste the minimal necessary customization script inside that can be found [here](customizations/customize_base_image.py) (this is used for making minimal base images). 

Note that there are some standards in that script:
 - it contains a class named `customizeImage` - this MUST be named exactly like in the example since its invoked from other scripts by that name
 - the class `customizeImage` MUST define a `self.conf` dict inside its `def __init__(self):` function. 
 - the `self.conf` MUST contain all of the entries as shown in the example, refer to what each of those entries mean in the comment above it
 - the presence of `apt_get_packages` is necessary, even if its empty. The content of the `apt_get_packages` are names of apt packages (be carefully that you spell them correctly) and are arbitrary. Note that image that the customizations are going to be executed on already comes with some apt packages pre-installed. Which apt packages exactly come pre-installed can be checked inside [build_rootfs.py -> main() -> apt_install_packages](https://github.com/UbiquityRobotics/pi_image2/blob/35e20cb6ba0ae049ed316580fdcd23a4f268fb35/build_rootfs.py#L242)

## Adding some project-specific customizations 

Now lets say in addition to minimal example (which basically generates the base image) we want the coolproject image to print a welcome message every time someone SSH-s onto it. 
