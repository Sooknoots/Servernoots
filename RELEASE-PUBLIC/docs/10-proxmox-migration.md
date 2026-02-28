# Proxmox Migration Guide (Host-Based, Tailored)

## Current Host Layout (detected)

- OS disk (Ubuntu root): `sdb` (931.5G)
- Data disk (workspace): `sdd2` mounted at `/media/sook/Content`
- Workspace path: `/media/sook/Content/Servernoots`

## Goal

Install Proxmox VE on `sdb` (this **wipes current Ubuntu host OS**), keep data on `sdd2`, then restore stack into a VM.

## 1) Pre-install backup (run now on current host)

Create a full project archive on the data disk:

`mkdir -p /media/sook/Content/backups`

`tar -czf /media/sook/Content/backups/servernoots-pre-proxmox-$(date +%F-%H%M).tar.gz -C /media/sook/Content Servernoots`

Optional checksum:

`sha256sum /media/sook/Content/backups/servernoots-pre-proxmox-*.tar.gz > /media/sook/Content/backups/servernoots-pre-proxmox.sha256`

## 2) Create Proxmox installer USB

- Download latest Proxmox VE ISO from the official site.
- Write to USB with Rufus/Balena/`dd`.

Linux `dd` example (replace `sdX`):

`sudo dd if=proxmox-ve.iso of=/dev/sdX bs=4M status=progress oflag=sync`

## 3) Install Proxmox VE

- Boot from USB.
- Install target disk: `sdb`.
- Set management network on your LAN (same subnet as current host).
- Finish install and reboot.

## 4) First Proxmox login

- Open: `https://<proxmox-host-ip>:8006`
- Login: `root@pam`

## 5) Create Ubuntu VM for this stack

Recommended starter:

- vCPU: 6
- RAM: 16 GB
- Disk: 200+ GB (on Proxmox local-lvm or ZFS)
- Network: bridged (`vmbr0`)

## 6) Restore your project into VM

Inside new Ubuntu VM:

- Mount or copy backup archive from `/media/sook/Content/backups`
- Restore:

`mkdir -p /media/sook/Content`

`tar -xzf /path/to/servernoots-pre-proxmox-<timestamp>.tar.gz -C /media/sook/Content`

## 7) Bring services back up

- `cd /media/sook/Content/Servernoots/master-suite/phase1/gluetun && docker compose up -d`
- `cd /media/sook/Content/Servernoots/master-suite/phase1/adguard && docker compose up -d`
- `cd /media/sook/Content/Servernoots/master-suite/phase1/authentik && docker compose up -d`
- `cd /media/sook/Content/Servernoots/master-suite/phase1/crowdsec && docker compose up -d`

## 8) Snapshot strategy (after migration)

Use Proxmox snapshots on the VM:

- `day1-clean-base`
- `day2-fort-stable`

## Critical warning

Installing Proxmox on `sdb` erases current host OS. Do not proceed until backup archive is verified.
