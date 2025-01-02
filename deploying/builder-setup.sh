sudo apt update
sudo apt -y upgrade
sudo apt -y install debhelper python-setuptools python3-setuptools curl python3-dev python3-venv apt-utils vim htop iotop screen git-buildpackage cowbuilder python3-venv build-essential libssl-dev libffi-dev python-dev ca-certificates qemu-user-static whois

sudo mkdir -p /var/lib/buildbot
sudo chown -R ubuntu:ubuntu /var/lib/buildbot
cd /var/lib/buildbot

python3 -m venv sandbox
source sandbox/bin/activate
pip install --upgrade pip
pip install buildbot-worker[tls]
pip install pyOpenSSL
pip install service_identity

#source sandbox/bin/activate
#buildbot-worker create-worker --use-tls --maxretries 10 worker build.ubiquityrobotics.com boron "3vx2JsssoCqDgyDJ7YVUBWzYwowskT+Gc8IMffRwhds="

#sudo sh -c "cat <<EOM >/etc/systemd/system/buildbot-worker.service
# This template file assumes the buildbot worker lives in a subdirectory od
# /var/lib/buildbot
# Usage:
#   cd /var/lib/buildbot
#   buildbot-worker create-worker [directory] [master hostname] [name] [password]
#   systemctl enable --now buildbot-worker@[directory].service
#[Unit]
#Description=Buildbot Worker
#After=network.target

#[Service]
#User=ubuntu
#Group=ubuntu
#WorkingDirectory=/var/lib/buildbot/
#ExecStart=/var/lib/buildbot/sandbox/bin/buildbot-worker start --nodaemon worker
# if using EC2 Latent worker, you want to uncomment following line, and comment out the Restart line
#ExecStopPost=sudo shutdown now

#[Install]
#WantedBy=multi-user.target
#EOM"

#echo "Rohan Agrawal <ra@ubiquityrobotics.com>" >/var/lib/buildbot/worker/info/admin
#echo "AWS m6g.medium" >/var/lib/buildbot/worker/info/host

#sudo systemctl enable buildbot-worker.service
#sudo systemctl start buildbot-worker.service
