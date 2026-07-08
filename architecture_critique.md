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
*   **The problem:** We rebuild a monolithic 2GB (compressed) SD card disk image using `mmdebstrap` for every single software change (e.g., small modds in any ROS2 node). This is incredibly slow and highly inefficient. It also makes updating robots in the field difficult, as they must re-flash the entire image.
*   **How to solve:** Split the build system into a two-layer model. Build a thin, static base Ubuntu system image once. Package all ROS 2 nodes, robot control packages, and dependencies as lightweight Docker containers (or Snaps). When developers push code changes, the CI/CD pipeline only builds and tests a small 50MB container in a few seconds. The robots out in the field can pull container updates over-the-air using a management tool like AWS IoT Greengrass or Balena.

---

## 2. Final Word

The current pipeline was a great for bootstrapping our builds, but its way too monolithic and hybrid-cloud system now acts as a bottleneck for build speed and debug access. By gradually decoupling the state, moving compute to a single cloud(AWS), and migrating to containerized deployment strategies, we can transition to a modern infrastructure that is highly orthogonal, secure, and resilient and also future proof.
