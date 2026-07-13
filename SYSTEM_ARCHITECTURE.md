# System Architecture (The Puppet Master Model)

This document explains exactly how the Ubiquity Robotics build system works under the hood. If you are wondering how DigitalOcean, AWS, Buildbot, and `rpi-image-gen` all fit together to build a 4GB Ubuntu image for a robot, read this.

---

## 1. The Orchestrator (The Puppet Master)

Everything starts on the DigitalOcean server. There is a Docker container running the Buildbot Master program here. 

This server acts as the "Puppet Master." It does absolutely zero compiling or building itself. It just sits there exposing a Web UI, and when you click "Start Build", it orchestrates the process.

### How is the Master configured?
*   **The Deployment:** The Buildbot Master is run via a Docker container. When deployed, it uses a Docker volume (e.g., `-v /opt/buildbot/creds:/creds`) to map files from the DigitalOcean host hard drive directly into the container.
*   **creds.py:** Because of this volume mapping, the `creds.py` file (which contains the highly sensitive AWS API keys and secrets) is injected at runtime. It is never committed to GitHub and never baked into the Docker image. This keeps the system secure.
*   **master.cfg:** This is the main Python brain. It defines the builders, the Web UI ports, and the exact step-by-step sequence of shell commands to execute.
*   **workers.py:** This script specifically manages the AWS compute. It imports the keys from `creds.py` to authenticate with AWS, and defines the exact Amazon Machine Image (AMI) IDs, instance sizes (like `t4g.xlarge` for ARM64), and the `cloud_init_script` needed to spin up the ephemeral workers on demand.

---

## 2. Spawning the Compute (The Puppet)

When a build is triggered, the Master uses the Python `boto3` library to send an API call to Amazon Web Services (AWS). It essentially tells AWS: "Hey Amazon, boot up a new `t4g.xlarge` EC2 instance, and when it boots, run this startup script."

---

## 3. The Handshake (The Persistent Tunnel)

When the AWS instance finishes booting, it runs its startup script. The script installs dependencies and starts the `buildbot-worker` program. 

The worker then reaches out across the public internet *back* to the DigitalOcean Master's IP address.

They perform a handshake and establish a secure TCP connection (using the Twisted Perspective Broker protocol). **This connection stays open for the entire duration of the build.** 

While that connection is open, the back-and-forth looks like this:
*   **Master:** "Do this."
*   **Worker:** "Okay, doing it. Here is the terminal output... Done."

---

## 4. Where `rpi-image-gen` Comes into Play

The DigitalOcean Master (`ubiquity_buildbot` repo) only manages the infrastructure (turning servers on and off, reporting success/failure to the Web UI). It doesn't know how to build a robot image.

So, the very first command the Master sends to the AWS worker is: 
`run git clone https://github.com/ubiquityrobotics/rpi-image-gen`

The `rpi-image-gen` repository is the actual instruction manual. Once the worker downloads it, almost everything that happens next is driven by the code inside that repo:
*   The Master tells the worker: "Run `rpi-image-gen/setup_ros2_env.sh`"
*   The Master tells the worker: "Use Podman to run `rpi-image-gen/build.sh`"

---

## 5. The Execution and the Sandbox Boundary

The worker executes the build using a tool called `mmdebstrap` and `podman unshare`. 

### What is `podman unshare` and why do we need it?
When building an operating system image, the build script needs `root` (admin) privileges to create files owned by root inside the image. But running automated CI scripts as actual root on the AWS machine is super dangerous.

So, we use `podman unshare`. It creates a "user namespace sandbox." It's basically a magic trick:
*   **Inside the sandbox:** `mmdebstrap` thinks it has root powers. It can create root-owned files and format the Ubuntu filesystem.
*   **Outside the sandbox:** The AWS host machine knows it is just a regular, unprivileged user. We get to build root filesystems without ever needing dangerous `sudo` access.

This creates a critical boundary between the **Host** and the **Target**:
*   **The Host (The Engine):** The AWS EC2 instance running Debian 12. It only runs generic tools like Podman. It knows nothing about robots.
*   **The Target (The Car):** `mmdebstrap` creates a completely isolated, fake Linux file system (a "chroot" sandbox) on the hard drive. Inside that fake file system, it connects to Ubuntu's servers, downloads Ubuntu 24.04 (Noble), installs ROS 2, and compiles the robot code.

---

## 6. Image Storage and Retention (DigitalOcean Spaces)

Once the Ubuntu image is fully constructed and compressed inside the sandbox, it needs to be stored for users to download.

The Buildbot Master generates a pre-signed S3 upload URL using `boto3`. The AWS worker then uses `curl` to `PUT` the 2GB compressed `.xz` file directly into our **DigitalOcean Spaces** bucket (specifically, the `ubiquity-pi-image` bucket in the `sfo2` region). It applies a `public-read` ACL so anyone can download it.

**What happens to older images?** 
Buildbot *does not* delete old images. Every subsequent successful build simply uploads a new file with a new timestamp into the bucket. To prevent infinite storage costs, retention is handled entirely outside of this codebase via a manual **Lifecycle Rule** configured in the DigitalOcean Spaces web dashboard (e.g., automatically deleting artifacts older than 30 or 60 days).

---

## 7. The Teardown

After the artifact is safely uploaded to DigitalOcean Spaces, the worker tells the Master it is finished.

The Master sends one final API call to AWS: "Terminate the instance." AWS deletes the EC2 server and permanently destroys its hard drive.

---

## Summary

*   `ubiquity_buildbot` is the puppet master.
*   AWS EC2 is the puppet.
*   `rpi-image-gen` is the script the puppet acts out.
*   The host (AWS) and the target (the Ubuntu image) are strictly isolated.
