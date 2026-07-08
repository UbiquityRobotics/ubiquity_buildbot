# Architecture Critique and Future Enhancements

This document evaluates the design problems of our current Buildbot setup and proposes modern solutions to transition to a more reliable, orthogonal, debuggable, and scalable system.

---

## 1. Architectural Critiques

### Master/Worker Cloud Distribution (Hybrid Cloud Architecture)
*   **The problem:** The Buildbot Master runs on DigitalOcean, while the ephemeral Workers are spawned on AWS EC2. This hybrid-cloud setup introduces unwanted latency,(requires opening ports across different clouds), and incurs substantial external bandwidth costs as images are pulled and pushed across two distinct cloud providers.
*   **How to solve:** Move the Buildbot Master from DigitalOcean to AWS, hosting it inside the exact same Virtual Private Cloud (VPC) and subnet as the EC2 workers. This simplifies stuff, drops communication latency to negligible timeouts, and keeps all build traffic on AWS's high-speed local network.

### Monolithic CI Configuration (Imperative `master.cfg`)
*   **The problem:** The entire build pipeline is defined imperatively in a monolithic Python file (`master.cfg`). A single syntax error or typo (such as unescaped curly braces) immediately crashes the entire Buildbot daemon, breaking the CI system for all users. Developers cannot modify the build process of their own repositories without modifying the infrastructure code itself.
*   **How to solve:** While standard GitHub-hosted runners lack the kernel privileges (such as `/dev/loop` loopback devices and user namespaces) required to build and format raw OS disk images, we can move to a declarative model by using **self-hosted GitHub Actions runners on AWS EC2 instances** (e.g., using an orchestrator like Philips Labs' Terraform module). This keeps the pipeline configuration declarative in `.github/workflows/` within the repo, while providing the necessary host-level privileges to construct the `.img` files. Lightweight code checks, buidds and tests and node compilation shlould all run on standard, free GitHub CI runners.

### State Management (Local SQLite Database)
*   **The problem:** Buildbot keeps all build records, state history, and queue management inside a single local SQLite file on the Master container's hard drive. If the DigitalOcean droplet suffers disk corruption or database locks, the entire history is lost and the orchestrator cannot function. This prevents us from running multiple Masters for high availability.
*   **How to solve:** Migrate the state database from SQLite to a managed PostgreSQL instance on AWS Relational Database Service (RDS). This decouples state from compute, allows automated database backups, and lets us run multiple Master containers behind a load balancer.

### Monolithic SD Card Disk Image Builds
*   **Description of the problem:** We rebuild a monolithic 4GB SD card disk image using `mmdebstrap` for every single software change (e.g., small modifications in `zenoh` or a ROS node). This is incredibly slow and highly inefficient because we are compiling custom code from source inside an emulated QEMU environment during image construction. It also makes updating robots in the field difficult, as they must re-flash the entire image.
*   **A quick solution proposal:** We should implement a **"Package-First, Image-Second"** pipeline. 
    1.  **Build Packages Individually:** Instead of compiling code during the image build, each repository (e.g., `move_smooth`, `ezmap`) will compile its code and generate standard Debian packages (`.deb` format) using GitHub Actions.
    2.  **Publish to our Aptly Repository:** These `.deb` files will be uploaded automatically to our managed Aptly repository (leveraging the existing `aptly_steps.py` infrastructure).
    3.  **Image Creation as Assembly Only:** The `rpi-image-gen` script will simply register our private Aptly repo as an APT source and run `apt-get install ros-jazzy-move-smooth` inside `mmdebstrap`. 
    
    This splits the build process cleanly. Image creation drops from 45 minutes to under 5 minutes because it behaves purely as a packager rather than a compiler. Furthermore, robots in the field can now pull critical software updates via simple `sudo apt update && sudo apt upgrade` rather than requiring a full re-flash or complex container orchestration.

---

## 2. Final Word

The current pipeline was a great for bootstrapping our builds, but its way too monolithic and hybrid-cloud system now acts as a bottleneck for build speed and debug access. By gradually decoupling the state, moving compute to a single cloud(AWS), and migrating to containerized deployment strategies, we can transition to a modern infrastructure that is highly orthogonal, secure, and resilient and also future proof.
