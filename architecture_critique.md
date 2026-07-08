# Architecture Critique and Future Enhancements

This document evaluates the design problems of our current Buildbot setup and proposes modern solutions to transition to a more reliable, orthogonal, and scalable system.

---

## 1. Architectural Critiques

### Master/Worker Cloud Distribution (Hybrid Cloud Architecture)
*   **Description of the problem:** The Buildbot Master runs on DigitalOcean, while the ephemeral Workers are spawned on AWS EC2. This hybrid-cloud setup introduces unwanted latency,(requires opening ports across different clouds), and incurs substantial external bandwidth costs as images are pulled and pushed across two distinct cloud providers.
*   **A quick solution:** Move the Buildbot Master from DigitalOcean to AWS, hosting it inside the exact same Virtual Private Cloud (VPC) and subnet as the EC2 workers. This simplifies stuff, drops communication latency to negligible timeouts, and keeps all build traffic on AWS's high-speed local network.

### Monolithic CI Configuration (Imperative `master.cfg`)
*   **Description of the problem:** The entire build pipeline is defined imperatively in a monolithic Python file (`master.cfg`). A single syntax error or typo (such as unescaped curly braces) immediately crashes the entire Buildbot daemon, breaking the CI system for all users. Developers cannot modify the build process of their own repositories without modifying the infrastructure code itself.
*   **A quick solution proposal:** While standard GitHub-hosted runners lack the kernel privileges (such as `/dev/loop` loopback devices and user namespaces) required to build and format raw OS disk images, we can move to a declarative model by using **self-hosted GitHub Actions runners on ephemeral AWS EC2 instances** (e.g., using an orchestrator like Philips Labs' Terraform module). This keeps the pipeline configuration declarative in `.github/workflows/` within the repo, while providing the necessary host-level privileges to construct the `.img` files. Lightweight code checks and node compilation can run on standard, free GitHub-hosted runners.

### State Management (Local SQLite Database)
*   **Description of the problem:** Buildbot keeps all build records, state history, and queue management inside a single local SQLite file on the Master container's hard drive. If the DigitalOcean droplet suffers disk corruption or database locks, the entire history is lost and the orchestrator cannot function. This prevents us from running multiple Masters for high availability.
*   **A quick solution proposal:** Migrate the state database from SQLite to a managed PostgreSQL instance on AWS Relational Database Service (RDS). This decouples state from compute, allows automated database backups, and lets us run multiple Master containers behind a load balancer.

### Monolithic SD Card Disk Image Builds
*   **Description of the problem:** We rebuild a monolithic 4GB SD card disk image using `mmdebstrap` for every single software change (e.g., small modifications in `zenoh` or a ROS node). This is incredibly slow and highly inefficient. It also makes updating robots in the field difficult, as they must re-flash the entire image.
*   **A quick solution proposal:** Split the build system into a two-layer model. Build a thin, static base Ubuntu system image once. Package all ROS 2 nodes, robot control packages, and dependencies as lightweight Docker containers (or Snaps). When developers push code changes, the CI/CD pipeline only builds and tests a small 50MB container in a few seconds. The robots out in the field can pull container updates over-the-air using a management tool like AWS IoT Greengrass or Balena.

---

## 2. Final Remarks

The current pipeline was a great starting point for bootstrapping our automated builds, but its monolithic and hybrid-cloud nature now acts as a bottleneck for our engineering velocity. By gradually decoupling the state, moving compute to a single cloud network, and migrating to containerized deployment strategies, we can transition to a modern infrastructure that is highly orthogonal, secure, and resilient.
