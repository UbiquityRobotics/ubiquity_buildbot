#!/bin/bash

if [ -z "$1" ]
then
	echo "Git token required as first argument."	
	exit 1
fi

echo "Building EZ-Map images..."

python3 build_image.py --customization_script_path /home/ubuntu/ezmapimage/customizations/customize_ezmap.py --git_token "$1"