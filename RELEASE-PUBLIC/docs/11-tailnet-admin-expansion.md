# Tailnet Admin Expansion (Computers + Phones)

## Goal

Extend Master Suite access to approved admins (for example, <your_admin_username>) across Tailscale devices without exposing admin ports publicly.

## Security model

- Keep Docker services bound to `127.0.0.1`.
- Publish only selected services through Tailscale Serve HTTPS ports.
- Limit who can reach those ports using Tailnet ACL groups/tags.
- Keep MFA enabled inside app surfaces (especially Authentik and n8n admin).

## 1) Prepare admin identities

On the Tailscale admin console:

- Ensure each admin signs in with their own identity.
- Confirm device ownership for phones + computers.
- Add admins to a dedicated group.

Suggested ACL fragment:

```json
{
  "groups": {
    "group:servernoots-admins": [
      "you@example.com",
      "<your_admin_email>"
    ]
  },
  "tagOwners": {
    "tag:servernoots": ["group:servernoots-admins"]
  },
  "acls": [
    {
      "action": "accept",
      "src": ["group:servernoots-admins"],
      "dst": ["tag:servernoots:*"]
    }
  ]
}
```

Apply tag to server node:

- `sudo tailscale set --advertise-tags=tag:servernoots`

## 2) Enable Serve mappings on server

Run from workspace root:

- `cd /media/sook/Content/Servernoots/master-suite/phase1/tailscale`
- `chmod +x enable-admin-access.sh disable-admin-access.sh`
- `./enable-admin-access.sh`

This creates private HTTPS endpoints on your tailnet DNS name:

- `:8443` Homepage
- `:8444` Authentik
- `:8445` n8n
- `:8446` Netdata
- `:8447` Beszel
- `:8448` Scrutiny
- `:8449` Overseerr
- `:8450` Sonarr
- `:8451` Radarr
- `:8452` Prowlarr
- `:8453` qBittorrent
- `:8454` Tautulli
- `:8455` Plex Web
- `:8456` ntfy

To roll back dedicated mappings:

- `./disable-admin-access.sh`

## 3) Admin device onboarding

For each admin phone/computer:

1. Install Tailscale app.
2. Sign in with allowed identity.
3. Confirm the device appears in Tailnet admin console.
4. Open Homepage URL: `https://<server-tailnet-dns>:8443/`
5. Validate Authentik login at `https://<server-tailnet-dns>:8444/`

## 4) Operations checklist

- Run `tailscale serve status` after any change.
- Keep `No unintended public admin exposure` gate as required.
- Re-run `./enable-admin-access.sh` after adding new services.
- If ACL changes are made, retest from one allowed and one non-allowed device.

## 5) Notes

- Your existing `https://<server-tailnet-dns>/` root mapping may already point to ntfy; this is fine and can coexist with dedicated `:8456`.
- If you later want a single-domain path layout (`/auth`, `/n8n`, etc.), migrate in a separate change after ACL validation.
