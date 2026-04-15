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
set -e

# Enable error handling and logging immediately
exec > >(tee -a /var/log/buildbot-setup.log) 2>&1

echo "Starting buildbot worker setup at $(date)"

# Prevent ALL interactive prompts during package installation
export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_MODE=a

# Configure debconf to use non-interactive mode
echo 'debconf debconf/frontend select Noninteractive' | debconf-set-selections
echo 'openssh-server openssh-server/permit-root-login boolean false' | debconf-set-selections

# Configure dpkg to handle config file conflicts automatically
cat > /etc/apt/apt.conf.d/50unattended-upgrades-local << EOF
Dpkg::Options {{
   "--force-confdef";
   "--force-confold";
}}
EOF

# 1. Ensure 'admin' user exists and is configured for sudo (Primary Worker User)
if ! id -u admin > /dev/null 2>&1; then
    useradd -m -s /bin/bash admin
fi
echo 'admin ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/admin
chmod 440 /etc/sudoers.d/admin

# 2. Inject SSH keys
mkdir -p /root/.ssh /home/admin/.ssh /home/ubuntu/.ssh 2>/dev/null || true

SSH_KEY="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQCTLV/yxi26viVUrnOmvbhMMZYYgxg2GQS6ztPHoCAdIDzXIPljQIXCRUT2gB8zmEm2vOcoig4QNWkCkoWgWqDUwDejIpUAn2tIFR52XhrKRgWpzC0p174GoEcRyDcXpXOBs57aGmOUeMcovOQ8d5O+1ju4bUliS61ZDxnn3OE3c/ksgXZiZ9wEk22DxDjBV2b1s4qTOCgd/MqgBtSZF7NSFONYZ5qh3Q1QsjQq5PCAO1WXpR+88SSavKZHGNyXlBulUaRFo34FfEQg02oC5HPHWjLJUXRSChEHeW+xnJw8ZqGb5aisVR8vPlWB9tSkV5q1wdoTb0Q/DHmogA2LLPzfwvET5wNZRxW7wdHyjsQCNO/8Y2teEf9iXOebtPPBI0K46/cVfMj+2yGsRvds3+n4ZEoWvcC4syM8KMS/dNQ/Q3C8D026zKWPAzgA/FrItk+yu7s6RBYTyUZyLhDbbdq4ZY+B4Cl69+lMPNVl0uzG7spWlZmme7CGj4Z/2mw102qbJFphGSu9AIWVeipV3PWNOPENWgPUdnb5h8DNF7zsNVQwjVpqfEtfv43SnMGO5CQjZoSTey1s+gSc6dvh113rK0+ShvNaj5RXV+scvT3WJTnOGeUaOgcFIwNq/hKNurIC+uHOzXPA4yG/t2yWln9o3u8XnZdBycj+aYkiAHAl5w== michael@michael-HYM-WXX"

echo "$SSH_KEY" >> /root/.ssh/authorized_keys
chmod 700 /root/.ssh; chmod 600 /root/.ssh/authorized_keys

echo "$SSH_KEY" >> /home/admin/.ssh/authorized_keys
chown -R admin:admin /home/admin/.ssh
chmod 700 /home/admin/.ssh; chmod 600 /home/admin/.ssh/authorized_keys

# Fallback for Ubuntu AMIs backward compatibility
if id -u ubuntu > /dev/null 2>&1; then
    echo "$SSH_KEY" >> /home/ubuntu/.ssh/authorized_keys
    chown -R ubuntu:ubuntu /home/ubuntu/.ssh
    chmod 700 /home/ubuntu/.ssh; chmod 600 /home/ubuntu/.ssh/authorized_keys
fi

# Update packages safely
apt-get update
apt-get -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" upgrade

# Install required packages (using python3-venv to avoid PEP 668)
apt-get -y install software-properties-common debhelper python3-setuptools python3-venv python3-pip curl apt-utils vim htop iotop screen git-buildpackage cowbuilder build-essential libssl-dev libffi-dev python3-dev ca-certificates qemu-user-static whois netcat-openbsd

# Create buildbot directory and set ownership
mkdir -p /var/lib/buildbot
chown -R admin:admin /var/lib/buildbot

# Set up Python virtual environment for buildbot-worker to avoid system pip conflicts
sudo -u admin python3 -m venv /var/lib/buildbot/venv
sudo -u admin /var/lib/buildbot/venv/bin/pip install --upgrade pip
# Pin worker to 2.10.5 to exactly match the master server's protocol
sudo -u admin /var/lib/buildbot/venv/bin/pip install buildbot-worker[tls]==2.10.5 pyOpenSSL service_identity

echo "Testing connectivity to master..."
if ! nc -zv build.ubiquityrobotics.com 9989; then
    echo "WARNING: Cannot connect to buildbot master"
fi

echo "Configuring buildbot worker..."
sudo -u admin bash -c '/var/lib/buildbot/venv/bin/buildbot-worker create-worker --use-tls --maxretries 10 /var/lib/buildbot/worker build.ubiquityrobotics.com {} "{}"'

# Create systemd service using the venv executable
cat > /etc/systemd/system/buildbot-worker.service <<EOF
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
ExecStart=/var/lib/buildbot/venv/bin/buildbot-worker start --nodaemon /var/lib/buildbot/worker
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

# Set up info files
mkdir -p /var/lib/buildbot/worker/info
echo "Luka Kidric <lk@ubiquityrobotics.com>" > /var/lib/buildbot/worker/info/admin
echo "AWS \$(hostname)" > /var/lib/buildbot/worker/info/host
chown -R admin:admin /var/lib/buildbot/worker/info/

# Enable and start service
systemctl daemon-reload
systemctl enable buildbot-worker.service
systemctl start buildbot-worker.service

echo "Setup completed at \$(date)"
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
                                "VolumeSize": 80,
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
                                "VolumeSize": 80,
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