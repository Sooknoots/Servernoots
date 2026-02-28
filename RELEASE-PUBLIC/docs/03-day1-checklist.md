# Day 1 Checklist (Beginner-Safe)

## Day 1 Goal

Create a stable base you can recover from, then prove your VM is reachable and ready for Phase 1.

## Time Budget

- Total: 2 to 4 hours
- Stop point: after snapshot + SSH verification

## Prerequisites

- Proxmox host installed and accessible in browser
- Ubuntu 24.04 LTS ISO available
- One notebook/text file for passwords, IPs, and hostnames

## Step 1 — Create your first VM

Target: a clean Ubuntu VM to host the suite core.

Suggested starter sizing:

- vCPU: 4
- RAM: 8 to 16 GB
- Disk: 80 to 120 GB (thin-provisioned if available)
- Network: bridged adapter (default bridge)

Verification:

- VM boots to Ubuntu installer
- Install completes and reboots normally

## Step 2 — Basic Ubuntu setup

In VM terminal:

- Create your main admin user
- Install OpenSSH server if installer did not include it
- Run updates

Verification:

- `sudo apt update` completes without errors
- `sudo apt upgrade -y` completes without errors
- `systemctl status ssh` shows active/running

## Step 3 — Give VM a stable identity

Set and record:

- Hostname (example: `ms-core-01`)
- Static DHCP lease or static IP
- Timezone

Verification:

- `hostnamectl` shows expected hostname
- VM keeps same IP after reboot

## Step 4 — Enable safe admin basics

Do only these today:

- Keep SSH password auth on for now (beginner-friendly start)
- Add your user to sudo group (if not already)
- Confirm firewall package exists (UFW) but do not lock down aggressively yet

Verification:

- `sudo -v` works from your user
- `ufw status` returns command output (even if inactive)

## Step 5 — Checkpoint backup (critical)

If running on host system (no Proxmox):

- Create checkpoint archive named `day1-clean-base.tar.gz` of core config/docs folders
- Save it outside the working directory (external drive or separate backup path)

Verification:

- Checkpoint archive exists and can be listed with `tar -tzf`
- System reboots and services still healthy

## Step 6 — Remote access test

From your main computer:

- SSH into VM
- Run a simple command and exit

Verification:

- SSH login works from another machine
- No timeout or connection refusal

## Step 7 — Write your Day 1 inventory

Create a simple record with:

- Proxmox node IP
- VM name and VM ID
- VM IP and hostname
- Admin username
- Snapshot name (`day1-clean-base`)

Verification:

- You can find this info in under 1 minute

## Do Not Do on Day 1

- Do not expose services to internet
- Do not deploy all containers at once
- Do not enable autonomous command execution yet
- Do not skip snapshots

## Day 1 Definition of Done

You are done when all are true:

1. Ubuntu VM is installed and updated
2. SSH works reliably from another device
3. VM identity (hostname/IP) is stable
4. Checkpoint `day1-clean-base` exists and is boot-tested
5. You have a written inventory of access details

## Day 2 Preview

Next, start Phase 1 "The Fort":

- Gluetun (Windscribe)
- AdGuard Home
- Authentik (MFA)
- CrowdSec

## End of Day 1 TODO

- [x] Add Stoat server setup/migration task (replace Discord for friends group) using archive from `~/Downloads/Council of Degenerates.zip` as source data reference.

## VPN + qBittorrent Security Verification (Leak-Proof Check)

Run these after `gluetun` and `qbittorrent` are up.

1. Confirm containers are healthy:

- `cd /media/sook/Content/Servernoots/master-suite/phase1/gluetun`
- `docker compose ps`

Expected:

- `gluetun` is `healthy`
- `qbittorrent` is `Up`

1. Confirm VPN egress IP (not your ISP WAN IP):

- `docker exec gluetun wget -qO- https://ipinfo.io/ip`

Expected:

- IP equals VPN exit IP (currently `82.21.158.133`)

1. Confirm qBittorrent shares Gluetun network namespace:

- `docker inspect -f '{{.HostConfig.NetworkMode}}' qbittorrent`

Expected:

- `service:gluetun`

1. Confirm qBittorrent listen port matches forwarded port:

- `docker exec qbittorrent sh -lc "grep -E 'Session\\\\Port|Connection\\\\PortRangeMin' /config/qBittorrent/qBittorrent.conf"`

Expected:

- Both values are `40000`

1. Simulate VPN failure to validate kill switch:

- `docker stop gluetun`
- In qBittorrent WebUI, force reannounce on an active torrent.

Expected:

- Torrent traffic stalls (no peers/data transfer)
- After `docker start gluetun`, traffic resumes only after tunnel is up

Operational note:

- If `gluetun` is restarted or recreated, also restart dependent containers (`qbittorrent`, `prowlarr`, `sonarr`) so they reattach cleanly to the refreshed network namespace.

If step 5 fails, stop and fix before any normal use.
