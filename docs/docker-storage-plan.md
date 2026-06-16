# AgentOS Docker Storage Plan v0.1

작성일: 2026-06-16

## Current Host State

Observed:

```text
root: /dev/mmcblk1p2, ext4, about 13G free
usb:  /dev/sda1, vfat, about 234G free, mounted at /mnt/usb
```

Docker is not installed yet.

## Key Constraint

The current USB filesystem is `vfat`.

This is good for broad compatibility, but it is not a good Docker data-root
filesystem. Docker image/container storage generally needs Linux filesystem
features such as permissions, links, extended attributes, and overlay
filesystem support.

Therefore:

```text
Do not put Docker data-root directly on the current vfat /mnt/usb.
```

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

1. Do not install Docker data-root on the current vfat USB.
2. If speed matters right now, install Docker on SD/root temporarily.
3. If doing it properly for the project, reformat or repartition the USB to
   ext4 first, then place Docker data-root on USB.

Recommended durable path:

```text
backup AgentOS repo
-> reformat USB as ext4
-> restore AgentOS repo to /mnt/usb/projects/agentdesk
-> install Docker engine on system
-> configure Docker data-root to /mnt/usb/docker
```

Do not execute the destructive USB format step without explicit user approval.
