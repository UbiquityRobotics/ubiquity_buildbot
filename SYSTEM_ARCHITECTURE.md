# system architecture (the puppet master model)

this document explains exactly how the ubiquity robotics build system works under the hood. if you are wondering how digitalocean, aws, buildbot, and rpi-image-gen all fit together to build a 4gb ubuntu image for a robot, read this.

## 1. the orchestrator (the puppet master)

everything starts on the digitalocean server. there is a docker container running the buildbot master program here. 

this server is the puppet master. it does absolutely zero compiling or building itself. it just sits there exposing a web ui, and when you click "start build", it orchestrates the process.

**how is the master configured?**
- **the deployment:** the buildbot master is run via a docker container. when deployed, it uses a docker volume (e.g. `-v /opt/buildbot/creds:/creds`) to map files from the digitalocean host hard drive directly into the container.
- **creds.py:** because of this volume mapping, the `creds.py` file (which contains the highly sensitive aws api keys and secrets) is injected at runtime. it is never committed to github and never baked into the docker image. this keeps the system secure.
- **master.cfg:** this is the main python brain. it defines the builders, the web ui ports, and the exact step-by-step sequence of shell commands to execute.
- **workers.py:** this script specifically manages the aws compute. it imports the keys from `creds.py` to authenticate with aws, and defines the exact amazon machine image (ami) ids, instance sizes (like t4g.xlarge for arm64), and the `cloud_init_script` needed to spin up the ephemeral workers on demand.

## 2. spawning the compute (the puppet)

when a build is triggered, the master uses the python `boto3` library to send an api call to amazon web services (aws). it essentially tells aws: "hey amazon, boot up a new t4g.xlarge ec2 instance, and when it boots, run this startup script."

## 3. the handshake (the persistent tunnel)

when the aws instance finishes booting, it runs its startup script. the script installs dependencies and starts the `buildbot-worker` program.
the worker then reaches out across the public internet *back* to the digitalocean master's ip address.

they perform a handshake and establish a secure tcp connection (using the twisted perspective broker protocol). **this connection stays open for the entire duration of the build.** 

while that connection is open, the back-and-forth looks like this:
- master: "do this."
- worker: "okay, doing it. here is the terminal output... done."

## 4. where rpi-image-gen comes into play

the digitalocean master (`ubiquity_buildbot` repo) only manages the infrastructure (turning servers on and off, reporting success/failure to the web ui). it doesn't know how to build a robot image.

so, the very first command the master sends to the aws worker is: 
"run `git clone https://github.com/ubiquityrobotics/rpi-image-gen`"

the `rpi-image-gen` repository is the actual instruction manual. once the worker downloads it, almost everything that happens next is driven by the code inside that repo.
- the master tells the worker: "run `rpi-image-gen/setup_ros2_env.sh`"
- the master tells the worker: "use podman to run `rpi-image-gen/build.sh`"

## 5. the execution and the sandbox boundary

the worker executes the build using a tool called `mmdebstrap` and `podman unshare`. 

what is podman unshare and why do we need it?
when building an operating system image, the build script needs `root` (admin) privileges to create files owned by root inside the image. but running automated ci scripts as actual root on the aws machine is super dangerous.

so, we use `podman unshare`. it creates a "user namespace sandbox". it's basically a magic trick:
- inside the sandbox, `mmdebstrap` thinks it has root powers. it can create root-owned files and format the ubuntu filesystem.
- outside the sandbox, the aws host machine knows it is just a regular, unprivileged user. we get to build root filesystems without ever needing dangerous sudo access.

this creates a critical boundary between the **host** and the **target**:
*   **the host (the engine):** the aws ec2 instance running debian 12. it only runs generic tools like podman. it knows nothing about robots.
*   **the target (the car):** `mmdebstrap` creates a completely isolated, fake linux file system (a "chroot" sandbox) on the hard drive. inside that fake file system, it connects to ubuntu's servers, downloads ubuntu 24.04 (noble), installs ros 2, and compiles the robot code.

## 6. the teardown

once the ubuntu image is fully constructed inside the sandbox, compressed, and uploaded to digitalocean spaces, the worker tells the master it is finished.

the master sends one final api call to aws: "terminate the instance." aws deletes the ec2 server and permanently destroys its hard drive.

## summary

- `ubiquity_buildbot` is the puppet master.
- aws ec2 is the puppet.
- `rpi-image-gen` is the script the puppet acts out.
- the host (aws) and the target (the ubuntu image) are strictly isolated.
