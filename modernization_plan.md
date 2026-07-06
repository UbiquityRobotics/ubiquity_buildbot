modernization plan for the buildbot system

so the current system is pretty fragile because it runs apt-get upgrade on every boot of the aws ec2 instance. this causes 60 minute timeouts when mirrors fail or dpkg locks up. also, the host is debian 12 but we are building ubuntu 24.04 noble target images, so adding ubuntu repos to the debian host breaks things (frankendebian problem).

to fix this and make it take 10 mins instead of 40 mins:

1. use packer to bake a golden ami
instead of running apt-get install podman qemu etc on every boot, we use hashicorp packer to make an ami that has all this stuff pre-installed. the worker will boot in 10 seconds.

2. pre-warm the apt cache
the mmdebstrap podman step takes 20 mins because it downloads huge ubuntu debs. we can just have packer download these debs into /var/cache/apt/archives on the ami so mmdebstrap finds them instantly.

3. use zstd instead of xz
the digital ocean script uses xz -T0 which takes 15 mins to compress a 4gb image. changing it to zstd -T0 -10 will take like 2 minutes.

4. fix the gpg key crash
the ros2.yaml runs curl ... | gpg --dearmor inside a sandbox. gpg crashes because there is no home dir in the sandbox, which caused the 502 errors and timeouts. fix is to just download the .asc key, commit it to the rpi-image-gen repo, and copy it locally using cp instead of curl and gpg.

how to deploy this safely:
create a new branch. clone it to a new folder on the digital ocean droplet like /root/ubiquity_buildbot_v2. run it on port 8011 and 9990 so it doesnt clash with production. test it, then swap.
