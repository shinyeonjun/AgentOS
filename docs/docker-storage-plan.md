# AgentOS Docker Storage Plan v0.1

작성일: 2026-06-16

## Current Host State

Initial state before repartition:

```text
root: /dev/mmcblk1p2, ext4, about 13G free
usb:  /dev/sda1, vfat, about 234G free, mounted at /mnt/usb
```

Applied storage layout on 2026-06-16:

```text
/dev/sda1  ext4   AGENTOS    200G   mounted at /mnt/usb
/dev/sda2  exfat  USB_SHARE   33G   mounted at /mnt/usb-share
```

Docker was installed on 2026-06-16 from the Ubuntu repository:

```text
docker.io 29.1.3
containerd 2.2.1
runc 1.3.4
```

## Key Constraint

The current USB filesystem is `vfat`.

This is good for broad compatibility, but it is not a good Docker data-root
filesystem. Docker image/container storage generally needs Linux filesystem
features such as permissions, links, extended attributes, and overlay
filesystem support.

Therefore, before repartition:

```text
Do not put Docker data-root directly on the current vfat /mnt/usb.
```

After repartition, `/mnt/usb` is ext4 and is suitable for AgentOS project files
and future Docker data-root.

## Options

### Option A: Docker Engine and Data on SD/root

Install Docker normally. Docker data lives under `/var/lib/docker` on the SD
root filesystem.

Pros:

- simplest
- no USB reformat
- fastest to start

Cons:

- uses limited SD space
- increases SD write load
- conflicts with the storage-role decision: USB is for projects, SD is Jarvis's body

Verdict:

Acceptable only as a short temporary test path.

### Option B: Reformat USB as ext4 and Put Docker Data on USB

Back up current AgentOS project, unmount USB, format USB as ext4, remount it,
restore project, and configure Docker data-root on USB.

Pros:

- fits storage-role decision
- Docker images/containers live on USB
- protects SD from heavy Docker writes
- enough space for future images

Cons:

- destructive format
- SanDisk default files are removed
- USB becomes less Windows-plug-and-play friendly
- requires careful backup/restore first

Verdict:

Best long-term local development path, but requires explicit user approval
before formatting.

### Option C: Split USB into ext4 Project/Docker Partition and Optional Shared Partition

Repartition USB:

- ext4 partition for AgentOS and Docker data
- optional exFAT/vfat partition for general file exchange

Pros:

- keeps Linux project/Docker storage correct
- can preserve a small cross-platform sharing area

Cons:

- more setup complexity
- destructive repartition
- not needed unless user wants Windows compatibility

Verdict:

Best if cross-platform USB use matters.

## Recommendation

For AgentOS:

1. Docker engine is installed on the system.
2. Docker data-root is configured on the ext4 AgentOS partition.
3. `/mnt/usb-share` remains the cross-platform file exchange partition.

Recommended durable path:

```text
backup AgentOS repo
-> repartition USB into ext4 + exFAT
-> restore AgentOS repo to /mnt/usb/projects/agentdesk
-> install Docker engine on system
-> configure Docker data-root to /mnt/usb/docker
```

The destructive USB repartition step was completed after explicit user approval.
The actual Docker data-root path is:

```text
/mnt/usb/docker-data
```

## Verification

Verified after repartition:

```bash
findmnt /mnt/usb
findmnt /mnt/usb-share
df -h /mnt/usb /mnt/usb-share
PYTHONPATH=/mnt/usb/projects/agentdesk/prototype python3 -m unittest discover /mnt/usb/projects/agentdesk/prototype/tests -v
```

Result:

- `/mnt/usb` mounted as ext4 `AGENTOS`
- `/mnt/usb-share` mounted as exFAT `USB_SHARE`
- AgentOS prototype tests passed

Docker verification:

```bash
sudo docker version
sudo docker info --format 'DockerRootDir={{.DockerRootDir}} Driver={{.Driver}}'
sudo docker run --rm hello-world
sudo docker system df
```

Observed:

```text
DockerRootDir=/mnt/usb/docker-data
Driver=overlay2
hello-world ran successfully on linux/arm64
docker service active/enabled
containerd service active
ubuntu user added to docker group
```
