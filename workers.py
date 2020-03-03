#!/usr/bin/python3

from get_creds import creds

from buildbot.plugins import *

workers = []

# Legacy ARM Builders
workers.append(worker.Worker("hydrogen", creds.hydrogen, max_builds=1))
workers.append(worker.Worker("helium", creds.helium, max_builds=1))
workers.append(worker.Worker("lithium", creds.lithium, max_builds=1))

# Legacy Intel Builders
workers.append(worker.Worker("dasher", creds.dasher))
workers.append(worker.Worker("dancer", creds.dancer))

## AWS based ARM builders
workers.append(worker.EC2LatentWorker("boron", creds.boron, 'a1.medium', 
                    region="us-east-2",
                    ami="ami-0f8436cc7d6daabdd", 
                    identifier=creds.awsPub, 
                    secret_identifier=creds.awsPriv, 
                    keypair_name='awsBuildbots', 
                    security_name="awsBuildbots", 
                    spot_instance=True,
                    max_spot_price=0.015,
                    price_multiplier=None,
                    max_builds=1
))


# AWS Intel Builders
workers.append(worker.EC2LatentWorker("prancer", creds.prancer, 'm5.large',
                    region="us-east-2",
                    ami="ami-00535e270cac192be",
                    identifier=creds.awsPub,
                    secret_identifier=creds.awsPriv,
                    keypair_name='awsBuildbots',
                    security_name="awsBuildbots",
                    spot_instance=True,
                    max_spot_price=0.028,
                    price_multiplier=None,
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

