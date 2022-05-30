# Creating an external custom image using pi_image2

In the tutorial we are going to have a specific example named "coolproject" - in your case this should be changed to an appropriate variable

---

**Before you continue**, here it is assumed that you already know how to make a AWS instance for building the images manually. If not, please first follow the [README](README.md)

---


We have a new project called "coolproject" which is a ROS metapackage (package of ROS packages) and has its own repo somewhere on github. It looks something like this:

```
ubuntu@ubiquityrobot:~/catkin_ws/src/coolproject$ ls
coolproject_launch  coolproject_nav
```

We want to create a RPI image specific for this project using pi_image2 and buildbot. Lets start.

## Creating a `coolproject_image`

In project folder we create a folder called `coolproject_image`

    mkdir -p ~/catkin_ws/src/coolproject/coolproject_image

Notice here that this is NOT a ROS package, but simply a folder created with `mkdir`. Nonetheless this is going to look like any other ROS package and is going to live among them in the meta package. If your project is not a meta-package, simply place the `coolproject_image` in the root directory of your repo and continue with the tutorial.

## Creating the image minimal customization script

Now lets copy/paste a minimal necessary customization script that can be found [here](customizations/customize_base_image.py). In the example, the pi_image2 repo has been cloned to ~/ for clearer example

    cd ~
    git clone https://github.com/UbiquityRobotics/pi_image2.git
    cp ~/pi_image2/customizations/customize_base_image.py ~/catkin_ws/src/coolproject/coolproject_image/customize_coolproject_image.py

Notice here that the `.py` script can be arbitrarily named but it is recommended to keep the naming convention `customize_NAME_image.py` (for some consistency) where `NAME` is the name of your project. 

If you take a look whats inside of the script you should note that there are some standards:
 - it contains a class named `customizeImage` - this MUST be named exactly like in the example since its invoked from other scripts by that name
 - the class `customizeImage` MUST define a `self.conf` dict inside its `def __init__(self):` function. 
 - the `self.conf` MUST contain all of the entries as shown in the example, refer to what each of those entries mean in the comment above it
 - the presence of `apt_get_packages` is necessary, even if its empty. The content of the `apt_get_packages` are names of apt packages (be careful that you spell them correctly) and are arbitrary. Note that image that the customizations are going to be executed on already comes with some apt packages pre-installed. Which apt packages exactly come pre-installed can be checked inside [build_rootfs.py -> main() -> apt_install_packages](https://github.com/UbiquityRobotics/pi_image2/blob/35e20cb6ba0ae049ed316580fdcd23a4f268fb35/build_rootfs.py#L242)

## Adding some project-specific customizations 

Now lets say in addition to minimal example (which basically generates the base image) we want the coolproject image to print a welcome message every time someone SSH-s onto it. Additionally we want the package `python3-serial` to be installed and a private repo [ota_update](https://github.com/UbiquityRobotics/ota_update) to be installed and compiled in `~/catkin_ws/src` of the generated image.


To get gdm3 installed we use **the pre-prepared gdm mod** by first including the mod into the script

    from common_img_mods import gdm3_mod

We also need to include subprocess library since we will use it 

    import subprocess

To install `python3-serial` we simply add it to `apt_get_packages` so it looks something like

    "apt_get_packages": [
                    ...,
                    "python3-serial"
                ]

Here the "..." indicates other apt packages that will also get installed. 

And then invoking it to actually be applied to the image within `execute_customizations(self)`:

    def execute_customizations(self):
        gdm3_mod.install()

        echo_welcome_text = 'echo "Welcome to the CoolProject Image!"'
        subprocess.run("echo '" + echo_welcome_text + "' >> /etc/update-motd.d/50-ubiquity", check=True, shell=True)

        subprocess.run("git clone https://$GIT_TOKEN@github.com/UbiquityRobotics/ota_update", shell= True, check=True, cwd="/home/ubuntu/catkin_ws/src/")
        return

We also added the welcome text to be echoed into the `/etc/update-motd.d/50-ubiquity` which holds the messages that get printed on every ssh login.

Some other stuff to note:

 - you can clone UbiquityRobotics owned private repos simply by invoking a global environment variable `$GIT_TOKEN` to authenticate git actions. 
 - You don't need to add a `catkin_make` command, since it is going to be run in the background after these customizations have all been executed in any case. 
 - `shell=True` needs to be there if the given command is one string. 
 - `check=True` is very recommended, since this is what enables you too see the output of the command once it will be executed.

## Making an image using our customization script MANUALLY

Manually here means that we will setup the machine and trigger the commands that make the images ourselves (as opposed to buildbot doing that exact same thing for us). This is good to do because:

a) We trigger the process on a SEPARATE aws instance and can debug the image creation without worrying about breaking any production setup on actual buildbot.

b) We get to know the process that buildbot will be doing later instead of us (and thus have an overview of whats going on in the background)


1. The image will be built on a new ARM instance of our AWS servers. Open a new AWS instance. (If you don't know how to do that, fist follow [README](https://github.com/UbiquityRobotics/pi_image2 )).
2. Once we are able to ssh onto the AWS instance, we can sync our local project files onto the aws server

        PEM_PATH=~/path_to_pem_file/Name.pem
        AWS_IP=3.17.133.191
        rsync -avzhe "ssh -i $PEM_PATH" ~/catkin_ws/src/coolproject/coolproject_image ubuntu@$AWS_IP:~/


    where `~/path_to_pem_file/Name.pem` is the path local `.pem` file and `AWS_IP` should contain the randomly generated IP of AWS instance.
3. Now we ssh onto aws machine and clone the pi_image2 code

        ssh -i $PEM_PATH ubuntu@$AWS_IP
        git clone https://github.com/UbiquityRobotics/pi_image2.git

4. We are now ready to trigger building the image on aws instance with 

        cd pi_image2/
        GIT_TOKEN=ghp_8Jfsdf670978sdaASZFD67asdf9 # insert your presonal git token that has access to invoked repos
        sudo python3 build_image.py --customization_script_path ../coolproject_image/customize_coolproject_image.py --git_token $GIT_TOKEN

    note here how we pointed the build_image.py to the local customization script with `--customization_script_path` flag. Also note that since we are cloning private repos inside our customization script the flag `--git_token` also needs to be added (otherwise it does not have to be).

Now the image building process should begin and if everything goes alright, you should have generated image. You can rsync it over to your system and test it out.

**Tip:** Making images takes a lot of time and most likely you'll have to run it multiple times in your debugging process. To make the debugging cycle shorter, take a look at [Tips for devs](README.md#tips-for-devs)

___

**Next step** would be adding the image generation with the customizations to the buildbot: TODO


