#!/usr/bin/python3

import re
from buildbot.plugins import *

from get_creds import creds
import aptly_steps

def set_deb_properties(name, factory, arch, is_ros=False):
    '''
    This functions sets the dsc_path and deb_path buildbot properties for the build

    For ROS packages this includes prepending 'ros-DISTRO'
    '''
    factory.addStep(steps.SetPropertyFromCommand(command="dpkg-parsechangelog --show-field Version", 
        property="deb_version", haltOnFailure=True))

    # the Debian name has dashes instead of underscores
    debian_name = "-".join(name.split("_"))

    if is_ros:
        factory.addStep(steps.SetProperty(property="deb_path", 
            value=util.Interpolate("/var/cache/pbuilder/result/xenial/ros-kinetic-" + debian_name + "_%(prop:deb_version)s_" + arch +".deb")))
        factory.addStep(steps.SetProperty(property="dsc_path", 
            value=util.Interpolate("../ros-kinetic-" + debian_name + "_%(prop:deb_version)s.dsc")))
        factory.addStep(steps.SetProperty(property="deb_package_name", value='ros-kinetic-' + debian_name))
    else:
        factory.addStep(steps.SetProperty(property="deb_path", 
            value=util.Interpolate("/var/cache/pbuilder/result/xenial/" + debian_name + "_%(prop:deb_version)s_" + arch +".deb")))  
        factory.addStep(steps.SetProperty(property="dsc_path", 
            value=util.Interpolate("../" + debian_name + "_%(prop:deb_version)s.dsc")))
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

    return result['BASEPATH'] + '/etc/os-release'

def cowbuilder(arch, factory):
    '''
    Uses cowbuilder to build a dsc file into debs.

    The dsc_path property must be set
    '''

    cow_config = "cowbuilder/xenial-cowbuilder-%s" % arch
    cow_test = cowbuilder_test_path(cow_config)

    factory.addStep(steps.FileDownload(mastersrc=cow_config, workerdest="xenial-cowbuilder"))
    
    # Short shell invocation to create the cowbuilder if it doesn't exist already
    factory.addStep(steps.ShellCommand(
        command='[ -f {} ] || sudo cowbuilder --create --config {}'.format(cow_test, 'xenial-cowbuilder'),
        description="Create Cowbuilder"
    ))

    factory.addStep(steps.ShellCommand(command=['sudo', 'cowbuilder', '--configfile', 
        'xenial-cowbuilder', '--update'], description="Update Cowbuilder"))
    factory.addStep(steps.ShellCommand(command=['sudo', 'cowbuilder', '--configfile', 
        'xenial-cowbuilder', '--build', util.Property('dsc_path')], description="Build Deb"))

def single_ros_deb(name, release_repo, arch, factory):
    factory.addStep(steps.Git(repourl=release_repo,
                                     branch='debian/kinetic/xenial/%s' % name, method='clobber', mode='full', alwaysUseLatest=True))
    factory.addStep(steps.ShellCommand(command=['gbp', 'buildpackage', '-S', '-us', '-uc', '-d', '', '--git-ignore-new', '--git-ignore-branch'],
                                              description="Generate Source Deb", haltOnFailure=True))
    set_deb_properties(name, factory, arch, is_ros=True)
    cowbuilder(arch, factory)
    aptly(name, factory)


def single_ros_backport_deb(name, release_repo, arch, factory):
    factory.addStep(steps.Git(repourl=release_repo,
                                     branch='debian/kinetic/xenial/%s' % name, method='clobber', mode='full', alwaysUseLatest=True))
    factory.addStep(steps.ShellCommand(command=['dch','--local','~tbpo','--distribution','xenial',"Temp Backport"],
                                              description="Bump to backport version", haltOnFailure=True))
    factory.addStep(steps.ShellCommand(command=['gbp', 'buildpackage', '-S', '-us', '-uc', '-d', '', '--git-ignore-new', '--git-ignore-branch'],
                                              description="Generate Source Deb", haltOnFailure=True))
    set_deb_properties(name, factory, arch, is_ros=True)
    cowbuilder(arch, factory)
    aptly(name, factory)

def metapackage_ros_deb(name, packages, release_repo, arch, factory):
    # TODO Topological sort, right now we assume that the packages are already in sorted order
    for package in packages:
        single_ros_deb(package, release_repo, arch, factory)

def metapackage_ros_backport_deb(name, packages, release_repo, arch, factory):
    # TODO Topological sort, right now we assume that the packages are already in sorted order
    for package in packages:
        single_ros_backport_deb(package, release_repo, arch, factory)

def aptly(name, factory):
    aptly_url = 'https://aptly.ubiquityrobotics.com/'
    aptly_url_creds = 'https://' + creds.aptly[0] + ':' + creds.aptly[1] + '@aptly.ubiquityrobotics.com/'

    factory.addStep(steps.ShellSequence(
        commands = [
            util.ShellArg(command=['curl', '-X', 'POST', '-F', util.Interpolate('file=@%(prop:deb_path)s'), 
                aptly_url_creds + 'api/files/' + name
            ]),

            util.ShellArg(command=['curl', '-X', 'POST', aptly_url_creds + 'api/repos/main-building/file/' + name])
        ],
        description='Push deb to building',
        descriptionDone='Pushed deb to building'
    ))
    
    factory.addStep(aptly_steps.AptlyUpdatePublishStep(
        aptly_url, creds.aptly,
        'filesystem:www:building/xenial'
    ))

    factory.addStep(aptly_steps.AptlyCopyPackageStep(
        aptly_url, creds.aptly,
        'main-building', 'main-testing',
        util.Interpolate('Name (=%(prop:deb_package_name)s), Version (=%(prop:deb_version)s)')
    ))

    factory.addStep(aptly_steps.AptlyUpdatePublishStep(
        aptly_url, creds.aptly,
        'filesystem:www:ubiquity-testing/xenial'
    ))

