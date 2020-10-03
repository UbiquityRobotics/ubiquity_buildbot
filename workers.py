#!/usr/bin/python3

from get_creds import creds

from buildbot.plugins import *
import base64

workers = []

# Legacy ARM Builders
workers.append(worker.Worker("hydrogen", creds.hydrogen, max_builds=1))
workers.append(worker.Worker("helium", creds.helium, max_builds=1))
workers.append(worker.Worker("lithium", creds.lithium, max_builds=1))

# Legacy Intel Builders
workers.append(worker.Worker("dasher", creds.dasher))
workers.append(worker.Worker("dancer", creds.dancer))

## AWS based ARM builders
cloud_init_script ='''#!/bin/bash
source sandbox/bin/activate
buildbot-worker create-worker --use-tls --maxretries 10 worker build.ubiquityrobotics.com {} "{}"

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
ExecStopPost=sudo shutdown now

[Install]
WantedBy=multi-user.target
EOM"

echo "Rohan Agrawal <ra@ubiquityrobotics.com>" >/var/lib/buildbot/worker/info/admin
echo "AWS {}" >/var/lib/buildbot/worker/info/host

sudo systemctl enable buildbot-worker.service
sudo systemctl start buildbot-worker.service
'''

workers.append(worker.EC2LatentWorker("boron", creds.boron, 'm6g.medium', 
                    region="us-east-2",
                    ami="ami-031cd6d993a2b9990", 
                    identifier=creds.awsPub, 
                    secret_identifier=creds.awsPriv, 
                    keypair_name='awsBuildbots', 
                    security_name="awsBuildbots", 
                    spot_instance=True,
                    max_spot_price=0.02,
                    price_multiplier=None,
                    max_builds=1,
                    user_data=str(base64.b64encode(cloud_init_script.format("boron", creds.boron, "m6g.medium")), "ascii"),
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

workers.append(worker.EC2LatentWorker("beryllium", creds.beryllium, 'm6g.medium', 
                    region="us-east-2",
                    ami="ami-031cd6d993a2b9990", 
                    identifier=creds.awsPub, 
                    secret_identifier=creds.awsPriv, 
                    keypair_name='awsBuildbots', 
                    security_name="awsBuildbots", 
                    spot_instance=True,
                    max_spot_price=0.02,
                    price_multiplier=None,
                    max_builds=1,
                    user_data=str(base64.b64encode(cloud_init_script.format("beryllium", creds.beryllium, "m6g.medium")), "ascii"),
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
                    ami="ami-0c0e09bda138fbc12",
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
workers.append(worker.EC2LatentWorker("tofu", creds.tofu, 't3a.medium',
                    region="us-east-2",
                    ami="ami-0bd35b8c6065abdcb",
                    identifier=creds.awsPub,
                    secret_identifier=creds.awsPriv,
                    spot_instance=True,
                    keypair_name='awsBuildbots',
                    security_name="awsBuildbots",
                    max_spot_price=0.032,
                    price_multiplier=None,
                    max_builds=1
))


armhf_workers = ["hydrogen", "helium", "lithium", "boron"]
arm64_workers = ["boron"]
amd64_workers = ["dasher", "dancer", "prancer"]


workers_for_arch = {
    'armhf' : armhf_workers,
    'amd64' : amd64_workers,
    'arm64' : arm64_workers
}

