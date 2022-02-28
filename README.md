Buildbot

### Deploying Buildbot

Clone and edit buildbot code on your workstation

`cd <PATH_TO_BUILDBOT>`
`git clone https://github.com/UbiquityRobotics/ubiquity_buildbot.git`

When its time to deploy the edited code, on your workstation do:

`sudo apt install ansible`

Also install Docker and then add credentials for it for the ubiquity digital ocean:

`docker login -u TOKEN -p TOKEN registry.digitalocean.com`

to get the `TOKEN` you need to have been invited to ubiquity digital ocean through Davids account - Ask Rohan how to get that.

After that is configured, deploy the code from the workstation onto digitalocean

```
cd <PATH_TO_BUILDBOT>/ubiquity_buildbot/deploying
./deploy.sh
```

After that syncs the buildbot code on your local machine has been synced to ubiquity digitalocean and is ready to build. To start a build go to:

https://build.ubiquityrobotics.com/ -> `Builds` -> `Builders` -> Find your builder on the list and click on its name (eg. `pi-lxde-focal-testing-image`) -> `force`

### Debugging Buildbot
If there are any troubles deploying buildbot there are a couple of ways of debugging. They are listed in our internal documentation https://wiki.ubiquityrobotics.com/e/en/internal/buildbot