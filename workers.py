#!/usr/bin/python3

from get_creds import creds

from buildbot.plugins import *
import base64

workers = []

# Legacy ARM Builders
#workers.append(worker.Worker("hydrogen", creds.hydrogen, max_builds=1))
#workers.append(worker.Worker("helium", creds.helium, max_builds=1))
#workers.append(worker.Worker("lithium", creds.lithium, max_builds=1))

# Legacy Intel Builders
#workers.append(worker.Worker("dasher", creds.dasher))
#workers.append(worker.Worker("dancer", creds.dancer))

## AWS based ARM builders
cloud_init_script ='''#!/bin/bash

sudo apt update
sudo apt -y upgrade
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt -y install debhelper python-setuptools python3-setuptools python3.10-venv curl python3.10-dev python3-venv apt-utils vim htop iotop screen git-buildpackage cowbuilder python3-venv build-essential libssl-dev libffi-dev python-dev ca-certificates qemu-user-static whois
echo 'ubuntu ALL=(ALL) NOPASSWD:ALL' | sudo tee /etc/sudoers.d/ubuntu
sudo mkdir -p /var/lib/buildbot
sudo chown -R ubuntu:ubuntu /var/lib/buildbot
cd /var/lib/buildbot

sudo apt install -y python3.10-venv

python3.10 -m venv sandbox
source sandbox/bin/activate
sudo chown -R ubuntu:ubuntu /var/lib/buildbot/sandbox/
pip install --upgrade pip
pip install buildbot-worker[tls]
pip install pyOpenSSL
pip install service_identity

>&2 echo "Configuring buildbot"
cd /var/lib/buildbot
sudo -u ubuntu bash -c '. sandbox/bin/activate; buildbot-worker create-worker --use-tls --maxretries 10 worker build.ubiquityrobotics.com {} "{}"'

sudo sh -c "cat <<EOM >/etc/systemd/system/buildbot-worker.service
# This template file assumes the buildbot worker lives in a subdirectory od
# /var/lib/buildbot
# Usage:
#   cd /var/lib/buildbot
#   buildbot-worker create-worker [directory] [master hostname] [name] [password]
#   systemctl enable --now buildbot-worker@[directory].service
[Unit]
Description=Buildbot Worker
After=network.target

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/var/lib/buildbot/
ExecStart=/var/lib/buildbot/sandbox/bin/buildbot-worker start --nodaemon worker
# if using EC2 Latent worker, you want to uncomment following line, and comment out the Restart line
#ExecStopPost=sudo shutdown now

[Install]
WantedBy=multi-user.target
EOM"

echo "Luka Kidric <lk@ubiquityrobotics.com>" >/var/lib/buildbot/worker/info/admin
echo "AWS {}" >/var/lib/buildbot/worker/info/host

sudo systemctl enable buildbot-worker.service
sudo systemctl start buildbot-worker.service

# Manually inject the SSH key for the ubuntu user
mkdir -p /home/ubuntu/.ssh
echo "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQCTLV/yxi26viVUrnOmvbhMMZYYgxg2GQS6ztPHoCAdIDzXIPljQIXCRUT2gB8zmEm2vOcoig4QNWkCkoWgWqDUwDejIpUAn2tIFR52XhrKRgWpzC0p174GoEcRyDcXpXOBs57aGmOUeMcovOQ8d5O+1ju4bUliS61ZDxnn3OE3c/ksgXZiZ9wEk22DxDjBV2b1s4qTOCgd/MqgBtSZF7NSFONYZ5qh3Q1QsjQq5PCAO1WXpR+88SSavKZHGNyXlBulUaRFo34FfEQg02oC5HPHWjLJUXRSChEHeW+xnJw8ZqGb5aisVR8vPlWB9tSkV5q1wdoTb0Q/DHmogA2LLPzfwvET5wNZRxW7wdHyjsQCNO/8Y2teEf9iXOebtPPBI0K46/cVfMj+2yGsRvds3+n4ZEoWvcC4syM8KMS/dNQ/Q3C8D026zKWPAzgA/FrItk+yu7s6RBYTyUZyLhDbbdq4ZY+B4Cl69+lMPNVl0uzG7spWlZmme7CGj4Z/2mw102qbJFphGSu9AIWVeipV3PWNOPENWgPUdnb5h8DNF7zsNVQwjVpqfEtfv43SnMGO5CQjZoSTey1s+gSc6dvh113rK0+ShvNaj5RXV+scvT3WJTnOGeUaOgcFIwNq/hKNurIC+uHOzXPA4yG/t2yWln9o3u8XnZdBycj+aYkiAHAl5w== michael@michael-HYM-WXX" >> /home/ubuntu/.ssh/authorized_keys

# Set correct permissions
chown -R ubuntu:ubuntu /home/ubuntu/.ssh
chmod 700 /home/ubuntu/.ssh
chmod 600 /home/ubuntu/.ssh/authorized_keys

cd /var/lib/buildbot
source sandbox/bin/activate
'''

boron_cloud_init_script = cloud_init_script.format("boron", creds.boron, "m6g.medium")
workers.append(worker.EC2LatentWorker("boron", creds.boron, 'm6g.medium', 
                    region="us-east-2",
                    ami="ami-039e419d24a37cb82", 
                    identifier=creds.awsPub, 
                    secret_identifier=creds.awsPriv, 
                    keypair_name='test', 
                    security_name="test",
                    #spot_instance=True,
                    #max_spot_price=0.02,
                    #price_multiplier=None,
                    max_builds=1,
                    user_data=boron_cloud_init_script,
                    block_device_map= [
                        {
                            "DeviceName": "/dev/sda1",
                            "Ebs" : {
                                "VolumeType": "gp2",
                                "VolumeSize": 50,
                                "DeleteOnTermination": True
                            }
                        }
                    ]
))

beryllium_cloud_init_script = cloud_init_script.format("beryllium", creds.beryllium, "m6g.medium")
workers.append(worker.EC2LatentWorker("beryllium", creds.beryllium, 'm6g.medium', 
                    region="us-east-2",
                    ami="ami-039e419d24a37cb82", 
                    identifier=creds.awsPub, 
                    secret_identifier=creds.awsPriv, 
                    keypair_name='awsBuildbots', 
                    security_name="awsBuildbots", 
                    #spot_instance=True,
                    #max_spot_price=0.02,
                    #price_multiplier=None,
                    max_builds=1,
                    user_data=beryllium_cloud_init_script,
                    block_device_map= [
                        {
                            "DeviceName": "/dev/sda1",
                            "Ebs" : {
                                "VolumeType": "gp2",
                                "VolumeSize": 50,
                                "DeleteOnTermination": True
                            }
                        }
                    ]
))

# AWS Intel Builders
workers.append(worker.EC2LatentWorker("prancer", creds.prancer, 'm5.large',
                    region="us-east-2",
                    ami="ami-036841078a4b68e14",
                    identifier=creds.awsPub,
                    secret_identifier=creds.awsPriv,
                    keypair_name='awsBuildbots',
                    security_name="awsBuildbots",
#                    spot_instance=True,
#                    max_spot_price=0.028,
#                    price_multiplier=None,
                    max_builds=1
))


# AWS Windows Builder for firmware builds
#workers.append(worker.EC2LatentWorker("tofu", creds.tofu, 't3a.medium',
#                    region="us-east-2",
#                    ami="ami-02e57400f716e673e",
#                    identifier=creds.awsPub,
#                    secret_identifier=creds.awsPriv,
#                    spot_instance=True,
#                    keypair_name='awsBuildbots',
#                    security_name="awsBuildbots",
#                    max_spot_price=0.032,
#                    price_multiplier=None,
#                    max_builds=1
#))


armhf_workers = ["boron", "beryllium"]
arm64_workers = ["boron", "beryllium"]
amd64_workers = ["prancer"]

workers_for_arch = {
    'armhf' : armhf_workers,
    'amd64' : amd64_workers,
    'arm64' : arm64_workers
}

