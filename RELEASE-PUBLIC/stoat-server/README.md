# Public Release Notice
This is a public release. All secrets, tokens, and user-specific data have been removed. You must generate your own credentials and configuration. See INSTALLATION.md for details.
# Stoat Server (Discrub Backup Replacement)

Local web server that loads a Discrub zip export and provides a Discord-style archive browser for channels, messages, avatars, and attachments.

## Source archive

Default input zip:

`/home/sook/Downloads/Council of Degenerates.zip`

Override with `--zip`.

## Quick start

```bash
cd $INSTALL_DIR/stoat-server
npm install
npm start
```

Open:

`http://127.0.0.1:8787`

## Quick start (Docker, no npm required)

```bash
cd $INSTALL_DIR/stoat-server
docker compose up -d --build
```

Open:

`http://127.0.0.1`

Stop:

```bash
docker compose down
```

## Public exposure via reverse proxy (Caddy)

This stack now includes `stoat-proxy` (Caddy) on ports `80` and `443`, with Stoat app traffic proxied internally.

By default on this host, proxy ports are mapped as:

- host `18087` -> container `80`
- host `18447` -> container `443`

This avoids conflicts with existing services already using host port `443`.

1. Set these values in `.env`:

```dotenv
STOAT_PUBLIC_HOST=stoat.yourdomain.com
STOAT_ACME_EMAIL=you@example.com
```

2. Point DNS `A` record for `stoat.yourdomain.com` to your public IP.

3. On your router, port-forward:

- TCP `80` -> this server (`${STOAT_PROXY_HTTP_PORT}`; default `18087`)
- TCP `443` -> this server (`${STOAT_PROXY_HTTPS_PORT}`; default `18447`)

4. Start/restart:

```bash
cd $INSTALL_DIR/stoat-server
docker compose up -d --build
```

5. Verify:

```bash
docker compose logs --tail=100 stoat-proxy
curl -I https://stoat.yourdomain.com
```

Then share this invite URL:

`https://stoat.yourdomain.com`

Users will still be prompted for Stoat credentials (`stoatadmin` / your password).

## CLI options

```bash
node server.js --zip /path/to/export.zip --port 8787
```

## What it matches from Discrub exports

- Loads channel pages from `*_page_*.json` files.
- Renders message author, timestamp, text, and embeds metadata.
- Resolves local archived attachments from `<channel>/_media/...` when possible.
- Resolves archived avatars from `avatars/<userId>/<avatarHash>.*`.
- Infers and groups channel kind as Text vs Voice from exported channel naming constraints.

## Voice/Text override file

Override channel kind classification with:

`$INSTALL_DIR/stoat-server/channel-kind-overrides.json`

Supported sections:

- `bySlug`: full export folder slug (example: `Spess Muhrines_Saa-4nFDWl`)
- `byKey`: raw channel key from page filename prefix (example: `Spess Muhrines`)
- `byName`: normalized display name (example: `Spess Muhrines`)

Allowed values are `"voice"` or `"text"`.

You can also set a custom override path with environment variable `STOAT_CHANNEL_OVERRIDES`.

## Notes

- Attachment matching uses filename mapping against `_media` exports, which is best-effort when duplicate filenames exist.
- If no local attachment match is found, the message shows the original URL.

## systemd auto-start

Service file:

`$INSTALL_DIR/stoat-server/systemd/stoat-server.service`

Install and enable:

```bash
sudo cp $INSTALL_DIR/stoat-server/systemd/stoat-server.service /etc/systemd/system/stoat-server.service
sudo systemctl daemon-reload
sudo systemctl enable --now stoat-server.service
```

One-command installer:

```bash
sudo $INSTALL_DIR/stoat-server/scripts/install-stoat-systemd.sh
```

Check status:

```bash
systemctl status stoat-server.service
docker ps --filter name=stoat-server
docker ps --filter name=stoat-proxy
```

Rollback / uninstall:

```bash
sudo $INSTALL_DIR/stoat-server/scripts/uninstall-stoat-systemd.sh
```

This command removes the systemd unit and also runs `docker compose down` in the Stoat folder.