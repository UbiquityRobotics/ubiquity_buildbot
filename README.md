# pi_image2

## Install Dependencies

Python dependencies:
  
    sudo pip install pychroot
  
and additionaly you need to install debootstrap tool: <br>

- Download latest debian package from: 
  
      sudo apt install debootstrap 
  
## How to run

You need to run using root privileges:

    sudo python3 build_image.py
  
This will run `build_image.py` with default settings taken from `default-build-settings.yaml`. To redirect it to another config file, do 

    sudo python3 build_image.py --config_path PATH_TO_CONFIG/CONFIG.yaml

To see other available options run:

    python3 build_image.py -h

In any case, the build will take a while, so you might as well grab a coffee :)
