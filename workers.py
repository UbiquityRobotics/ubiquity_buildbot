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
cloud_init_script = '''#!/bin/bash

# Prevent ALL interactive prompts during package installation
export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_MODE=a

# Configure debconf to use non-interactive mode
echo 'debconf debconf/frontend select Noninteractive' | debconf-set-selections

# Pre-configure openssh-server to avoid the configuration prompt
echo 'openssh-server openssh-server/permit-root-login boolean false' | debconf-set-selections

# Configure dpkg to handle config file conflicts automatically
cat > /etc/apt/apt.conf.d/50unattended-upgrades-local << EOF
Dpkg::Options {{
   "--force-confdef";
   "--force-confold";
}}
EOF

# Enable error handling and logging
set -e
exec > >(tee -a /var/log/buildbot-setup.log) 2>&1

echo "Starting buildbot worker setup at $(date)"

sudo apt update
sudo apt -y upgrade

# Install required packages including python3-pip for system-wide install
sudo apt -y install software-properties-common debhelper python3-setuptools python3-pip curl apt-utils vim htop iotop screen git-buildpackage cowbuilder build-essential libssl-dev libffi-dev python3-dev ca-certificates qemu-user-static whois netcat-openbsd

# Configure sudoers for admin user
echo 'admin ALL=(ALL) NOPASSWD:ALL' | sudo tee /etc/sudoers.d/admin

# Create buildbot directory and set ownership
sudo mkdir -p /var/lib/buildbot
sudo chown -R admin:admin /var/lib/buildbot
cd /var/lib/buildbot

# Install buildbot-worker system-wide with --break-system-packages
sudo pip3 install --break-system-packages --upgrade pip
sudo pip3 install --break-system-packages buildbot-worker[tls] pyOpenSSL service_identity

echo "Testing connectivity to master..."
if ! nc -zv build.ubiquityrobotics.com 9989; then
    echo "WARNING: Cannot connect to buildbot master"
fi

echo "Configuring buildbot worker..."
sudo -u admin bash -c 'buildbot-worker create-worker --use-tls --maxretries 10 worker build.ubiquityrobotics.com {} "{}"'

# Create systemd service
sudo tee /etc/systemd/system/buildbot-worker.service > /dev/null <<EOF
[Unit]
Description=Buildbot Worker
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=admin
Group=admin
WorkingDirectory=/var/lib/buildbot/
Environment=HOME=/var/lib/buildbot
Environment=PATH=/usr/local/bin:/usr/bin:/bin
ExecStart=/usr/local/bin/buildbot-worker start --nodaemon worker
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

# Set up info files
mkdir -p /var/lib/buildbot/worker/info
echo "Luka Kidric <lk@ubiquityrobotics.com>" > /var/lib/buildbot/worker/info/admin
echo "AWS $(hostname)" > /var/lib/buildbot/worker/info/host
sudo chown -R admin:admin /var/lib/buildbot/worker/info/

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable buildbot-worker.service
sudo systemctl start buildbot-worker.service

echo "Setup completed at $(date)"
echo "Check status with: sudo systemctl status buildbot-worker.service"
'''

boron_cloud_init_script = cloud_init_script.format("boron", creds.boron, "t4g.xlarge")
workers.append(worker.EC2LatentWorker("boron", creds.boron, 't4g.xlarge', 
                    region="us-east-2",
                    ami="ami-009dbf7acf984fc41", 
                    identifier=creds.awsPub, 
                    secret_identifier=creds.awsPriv, 
                    keypair_name='pi5key', 
                    security_name="pi5key",
                    #spot_instance=True,
                    #max_spot_price=0.02,
                    #price_multiplier=None,
                    max_builds=1,
                    user_data=boron_cloud_init_script,
                    block_device_map= [
                        {
                            "DeviceName": "/dev/xvda",
                            "Ebs" : {
                                "VolumeType": "gp3",
                                "VolumeSize": 70,
                                "DeleteOnTermination": True
                            }
                        }
                    ]
))

beryllium_cloud_init_script = cloud_init_script.format("beryllium", creds.beryllium, "t4g.xlarge")
workers.append(worker.EC2LatentWorker("beryllium", creds.beryllium, 't4g.xlarge', 
                    region="us-east-2",
                    ami="ami-009dbf7acf984fc41", 
                    identifier=creds.awsPub, 
                    secret_identifier=creds.awsPriv, 
                    keypair_name='pi5key',
                    security_name="pi5key",
                    #spot_instance=True,
                    #max_spot_price=0.02,
                    #price_multiplier=None,
                    user_data=beryllium_cloud_init_script,
                    block_device_map= [
                        {
                            "DeviceName": "/dev/xvda",
                            "Ebs" : {
                                "VolumeType": "gp3",
                                "VolumeSize": 60,
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

