#!/usr/bin/python3

import re
import time
from buildbot.plugins import *

from get_creds import creds
import aptly_steps

def set_deb_properties(name, distro, factory, arch, is_ros=False, ros_distro=""):
    '''
    This functions sets the dsc_path and deb_path buildbot properties for the build

    For ROS packages this includes prepending 'ros-{ros_distro}'
    '''
    factory.addStep(steps.SetPropertyFromCommand(command="dpkg-parsechangelog --show-field Version", 
        property="deb_version", haltOnFailure=True))

    # the Debian name has dashes instead of underscores
    debian_name = "-".join(name.split("_"))

    if is_ros:
        factory.addStep(steps.SetProperty(property="deb_path", 
            value=util.Interpolate(f"/var/cache/pbuilder/result/{distro}/ros-{ros_distro}-{debian_name}_%(prop:deb_version)s_{arch}.deb")))
        factory.addStep(steps.SetProperty(property="dsc_path", 
            value=util.Interpolate(f"../ros-{ros_distro}-{debian_name}_%(prop:deb_version)s.dsc")))
        factory.addStep(steps.SetProperty(property="deb_package_name", value=f'ros-{ros_distro}-{debian_name}'))
    else:
        factory.addStep(steps.SetProperty(property="deb_path", 
            value=util.Interpolate(f"/var/cache/pbuilder/result/{distro}/{debian_name}_%(prop:deb_version)s_{arch}.deb")))  
        factory.addStep(steps.SetProperty(property="dsc_path", 
            value=util.Interpolate(f"../{debian_name}_%(prop:deb_version)s.dsc")))
        factory.addStep(steps.SetProperty(property="deb_package_name", value=debian_name))

def cowbuilder_test_path(cow_config):
    '''
    Returns a path to a file, if that exists then the builder already exists
    '''
    envre = re.compile(r'''^([^\s=]+)=(?:[\s"']*)(.+?)(?:[\s"']*)$''')
    result = {}
    with open(cow_config) as ins:
        for line in ins:
            match = envre.match(line)
            if match is not None:
                result[match.group(1)] = match.group(2)

    # Return a path to a file that would exist if the cowbuilder was already created
    return result['BASEPATH'] + '/etc/os-release'

def cowbuilder(distro, arch, factory):
    '''
    Uses cowbuilder to build a dsc file into debs.

    The dsc_path property must be set
    '''

    cow_config = f"cowbuilder/{distro}-cowbuilder-{arch}"
    cow_test = cowbuilder_test_path(cow_config)

    factory.addStep(steps.FileDownload(mastersrc=cow_config, workerdest=f"{distro}-cowbuilder-{arch}"))
    factory.addStep(steps.FileDownload(mastersrc="cowbuilder/ros-archive-keyring.gpg", workerdest="ros-archive-keyring.gpg"))
    factory.addStep(steps.FileDownload(mastersrc="cowbuilder/ubiquity-archive-keyring.gpg", workerdest="ubiquity-archive-keyring.gpg"))
    
    # Short shell invocation to create the cowbuilder if it doesn't exist already
    factory.addStep(steps.ShellCommand(
        command=f"[ -f {cow_test} ] || sudo cowbuilder --create --config {distro}-cowbuilder-{arch}",
        description="Create Cowbuilder"
    ))

    factory.addStep(steps.ShellCommand(command=['sudo', 'cowbuilder', '--configfile', 
        f'{distro}-cowbuilder-{arch}', '--update'], description="Update Cowbuilder"))
    factory.addStep(steps.ShellCommand(command=['sudo', 'cowbuilder', '--configfile', 
        f'{distro}-cowbuilder-{arch}', '--build', util.Property('dsc_path')], description="Build Deb"))

def single_ros_deb(name, release_repo, distro, ros_distro, arch, factory):
    factory.addStep(steps.Git(repourl=release_repo,
                                     branch=f'debian/{ros_distro}/{distro}/{name}', method='clobber', mode='full', alwaysUseLatest=True))
    factory.addStep(steps.ShellCommand(command=['gbp', 'buildpackage', '-S', '-us', '-uc', '-d', '', '--git-ignore-new', '--git-ignore-branch'],
                                              description="Generate Source Deb", haltOnFailure=True))
    set_deb_properties(name, distro, factory, arch, is_ros=True, ros_distro=ros_distro)
    cowbuilder(distro, arch, factory)
    aptly(distro, name, factory)


def single_ros_backport_deb(name, release_repo, distro, ros_distro, arch, factory):
    factory.addStep(steps.Git(repourl=release_repo,
                                     branch=f'debian/{ros_distro}/{distro}/{name}', method='clobber', mode='full', alwaysUseLatest=True))
    factory.addStep(steps.ShellCommand(command=['dch','--local','~tbpo','--distribution', distro,"Temp Backport"],
                                              description="Bump to backport version", haltOnFailure=True))
    factory.addStep(steps.ShellCommand(command=['gbp', 'buildpackage', '-S', '-us', '-uc', '-d', '', '--git-ignore-new', '--git-ignore-branch'],
                                              description="Generate Source Deb", haltOnFailure=True))
    set_deb_properties(name, distro, factory, arch, is_ros=True, ros_distro=ros_distro)
    cowbuilder(distro, arch, factory)
    aptly(distro, name, factory)

def metapackage_ros_deb(name, packages, release_repo, distro, ros_distro, arch, factory):
    # TODO Topological sort, right now we assume that the packages are already in sorted order
    for package in packages:
        single_ros_deb(package, release_repo, distro, ros_distro, arch, factory)

def metapackage_ros_backport_deb(name, packages, release_repo, distro, ros_distro, arch, factory):
    # TODO Topological sort, right now we assume that the packages are already in sorted order
    for package in packages:
        single_ros_backport_deb(package, release_repo, distro, ros_distro, arch, factory)

def aptly(distro, name, factory):
    aptly_url = 'https://aptly.ubiquityrobotics.com/'
    aptly_url_creds = 'https://' + creds.aptly[0] + ':' + creds.aptly[1] + '@aptly.ubiquityrobotics.com/'

    building_repo = f"{distro}-main-building"
    testing_repo = f"{distro}-main-testing"

    # Due to a lack of foresight the xenial repos don't have the distro name
    if distro == "xenial":
        building_repo = "main-building"
        testing_repo = "main-testing"
        
    dir_name = f"{distro}__{name}"

    factory.addStep(steps.ShellSequence(
        commands = [
            util.ShellArg(command=['curl', '-X', 'POST', '-F', util.Interpolate('file=@%(prop:deb_path)s'), 
                aptly_url_creds + 'api/files/' + dir_name
            ]),

            util.ShellArg(command=['curl', '-X', 'POST', aptly_url_creds + f'api/repos/{building_repo}/file/' + dir_name])
        ],
        description='Push deb to building',
        descriptionDone='Pushed deb to building'
    ))
    
    factory.addStep(aptly_steps.AptlyUpdatePublishStep(
        aptly_url, creds.aptly,
        f'filesystem:www:building/{distro}'
    ))

    factory.addStep(aptly_steps.AptlyCopyPackageStep(
        aptly_url, creds.aptly,
        building_repo, testing_repo,
        util.Interpolate('Name (=%(prop:deb_package_name)s), Version (=%(prop:deb_version)s)')
    ))

    factory.addStep(aptly_steps.AptlyUpdatePublishStep(
        aptly_url, creds.aptly,
        f'filesystem:www:ubiquity-testing/{distro}'
    ))

