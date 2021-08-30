# pi_image2

## Install Dependencies

Python dependencies:
  
  sudo pip install pychroot
  
and additionaly you need to install debootstrap tool:
1.) Get latest debian package from: 

  https://deb.debian.org/debian/pool/main/d/debootstrap/
  
2.) Then install the package by typing:

  dpkg -i debootstrap_X.X.X_all.deb
  
## How to run

You need to run using root privileges:

  sudo python3 build_image.py
  
It will take a while, so you might as well grab a coffee :)
