#!/bin/bash

cd "$(dirname "$0")"

docker build .. -t registry.digitalocean.com/ubiquityrobotics/ubiquity_buildbot:latest
docker push registry.digitalocean.com/ubiquityrobotics/ubiquity_buildbot:latest

ansible-playbook -i hosts ansible.yaml

