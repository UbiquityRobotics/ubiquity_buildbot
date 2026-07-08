# Modernization Plan for the Buildbot System

This document outlines our strategy to resolve the core performance bottlenecks and stability issues in the current Buildbot infrastructure.

---

## 1. Problem

The current build system is fragile and suffers from major speed bottlenecks (often taking 40–60 minutes per run). This fragility stems from two primary issues:
1.  **Dynamic Dependency Installs on Boot:** Ephemeral AWS EC2 workers run `apt-get update && apt-get upgrade` directly during their initial boot sequence. This leaves builds vulnerable to network latency, package repository mirror failures, or `dpkg` locking issues, which frequently lead to 60-minute timeouts.
2.  **The FrankenDebian Mismatch:** The AWS host system is running Debian 12, but we are building Ubuntu 24.04 (Noble) target images. Adding Ubuntu repositories directly to the Debian host to install packaging tools creates host conflicts, dependency drift, and makes it incredibly difficult to reproduce builds reliably.

---

## 2. Modernization Plan

To reduce build times to under 10 minutes and guarantee stability, we will execute the following four improvements:

### Step 1: Bake a Golden AMI
*   **What is the issue:** Spawning a clean EC2 instance and compiling host packages from scratch on every single build is slow, bandwidth-heavy, and prone to random network failure.
*   **How to solve it (steps):**
    1. Define a HashiCorp Packer configuration (`packer.json`).
    2. Build a base Debian 12 AMI containing pre-installed packages for `podman`, `qemu-user-static`, and `buildbot-worker`.
    3. Update `workers.py` to launch workers using this pre-built Golden AMI.
*   **How will the solution be helpful:** This cuts worker initialization and handshake time down from several minutes to under 10 seconds, eliminating all host boot-time dependencies.

### Step 2: Pre-warm the APT Cache
*   **What is the issue:** The `mmdebstrap` step inside Podman downloads gigabytes of Ubuntu `.deb` packages on every build, wasting roughly 20 minutes downloading the same static assets over and over.
*   **How to solve it (steps):**
    1. During the Packer image creation process, pre-download common Ubuntu/ROS package dependencies into `/var/cache/apt/archives` on the golden image.
    2. Configure `mmdebstrap` inside the build container to utilize the local host cache directory.
*   **How will the solution be helpful:** `mmdebstrap` will resolve packages locally, reducing target OS compilation times down to under 5 minutes.

### Step 3: Switch Compression Algorithms (ZSTD instead of XZ)
*   **What is the issue:** The digital-ocean scripts currently compress the final 4GB image using `xz -T0`, which takes up to 15 minutes of compute time.
*   **How to solve it (steps):**
    1. Change the compression utility in the build pipeline from `xz` to `zstd`.
    2. Use multi-threaded configuration flags (e.g., `zstd -T0 -10`).
*   **How will the solution be helpful:** Compression time will drop from 15 minutes to under 2 minutes with virtually zero difference in final file size.

### Step 4: Fix the GPG Key Sandbox Crash
*   **What is the issue:** When trying to add the ROS 2 repository, the container runs `curl ... | gpg --dearmor` inside a user namespace sandbox. This crashes with a 502 error because the isolated sandbox environment lacks a mapped user home directory where `gpg` can write its temporary keyring.
*   **How to solve it (steps):**
    1. Download the static ROS 2 repository GPG key (`.asc`) directly on the workstation.
    2. Commit the `.asc` file directly to the `rpi-image-gen` repository under a static configuration directory.
    3. Update the Ansible playbook to simply copy the local file into `/usr/share/keyrings/` instead of fetching it via curl and gpg.
*   **How will the solution be helpful:** This cleanly avoids sandbox home directory constraints, preventing execution crashes and timeouts.

---

## 3. Testing Plan

To ensure these infrastructure changes do not impact production, we will deploy and test them in isolation:

1.  **Isolated Droplet Clone:** We will clone the current configuration to a separate, isolated folder on the DigitalOcean server (e.g., `/root/ubiquity_buildbot_v2`).
2.  **Unique Network Port Mapping:** We will configure the test master to listen on port `8011` (Web UI) and port `9990` (Worker connections) to prevent conflicts with the production master.
3.  **End-to-End Build Test:** Trigger a test run on the isolated master. Verify that the ephemeral AWS worker boots from the Golden AMI, pulls cached packages, builds the target Ubuntu image, compresses it using ZSTD, and successfully uploads the final artifact to our storage.
4.  **Production Swap:** Once validated, we will stop the production master, update its configurations, and swap the test environment into production.
