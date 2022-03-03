# pi_image2

## Building a new image manually
The raspberry pi image build can only be triggered on an ARM machine. You can either configure a local ARM machine (eg. raspberry-pi), sync this repo onto it, install dependencies and trigger the build. Another way is to setup an instance on the AWS server and trigger the build on that. 

### Setting up a build on AWS server
**Setting up a build machine**

Here is how you configure an AWS instance for building a new image:

https://aws.amazon.com -> `Sign In to the Console` -> Login with account given to you by Admin -> `EC2` -> Launch instances button dropdown -> `Launch instance from template` -> Source template: `image-build-testing` -> `Launch Instance` -> `View Launch Templates` -> Copy `Public IPv4` of your instance (if there is more of them listed, usually the latest one is the bottom of list of Type `t4g.micro` ). The IP is going to be something like for example: `3.129.90.191`

Now open a terminal on your workstation and ssh onto the instance using the `.pem` security file

    ssh -i ~/Downloads/John.pem ubuntu@3.129.90.191

If you don't have a `.pem` security file for aws server, ask Admin to get you one.

You are now able to ssh onto the aws build machine, next is to sync the code pi_image2 code onto it:

**Syncing code onto the AWS machine**

To sync the code, open a terminal on your workstation and enter:

    rsync -avzhe "ssh -i Downloads/John.pem" /PATH_TO_CODE/pi_image2/ ubuntu@3.129.90.191:pi_image2/

where `PATH_TO_CODE` is the path to your local code files which you want to test building.

### Install Dependencies
(This may be unnecessary on AWS template that has this already pre-installed)

Python dependencies:
  
    sudo pip install pychroot
  
and additionally you need to install debootstrap tool:
  
    sudo apt install debootstrap 
  
### Triggering a new build

You need to run using root privileges:

    sudo python3 build_image.py --customization_script_path <PATH TO CUSTOMIZATION SCRIPT>
  
This will run `build_image.py` with default settings taken from given customization script. To run script with base image customizations you can run

    sudo python3 build_image.py --customization_script_path customizations/customize_base_image.py

To see other available options run:

    python3 build_image.py -h

In any case, the build will take a while, so you might as well grab a coffee :)


### Design choices

 - For desktop environment we chose gdm3 because at the time of writing other lighter weight DMs like xubuntu and lubuntu had lots of troubles with Focal: https://github.com/UbiquityRobotics/pi_image2/issues/24#issuecomment-1023287561

 - Why does the image have only a startup message how to lower boot time and not some other slicker solutions: RPI does not have internal hardware RTC so we are getting then from MCB. If MCB is not connected, there are long boot times because RPI waits for hardware RTC to be connected and we could not find how to lower that timeout through either `hwrtc-sync` or with `systemctl`. https://github.com/UbiquityRobotics/pi_image2/issues/33

 - why have we moved form yaml configuration folder to python customization scripts: We enabled users to do project-specific customizations to base image filesystem from project repos. It then made no sense to have a separate yaml file besides that script to as a configuration folder. The configurations were implemented as part of the script in the https://github.com/UbiquityRobotics/pi_image2/commit/671d99201d6be16e9ba63a37f31ec4fc3110ffde. The decision for this was discussed in https://github.com/UbiquityRobotics/pi_image2/pull/28#issuecomment-1047214238