const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const express = require('express');
const AdmZip = require('adm-zip');
const helmet = require('helmet');
const rateLimit = require('express-rate-limit');

const DEFAULT_PORT = Number(process.env.PORT || 8787);
const DEFAULT_ZIP = process.env.STOAT_ZIP || '/home/sook/Downloads/Council of Degenerates.zip';
const DEFAULT_OVERRIDES =
  process.env.STOAT_CHANNEL_OVERRIDES || path.join(__dirname, 'channel-kind-overrides.json');
const AUTH_USER = String(process.env.STOAT_AUTH_USER || '').trim();
const AUTH_PASS = String(process.env.STOAT_AUTH_PASS || '').trim();
const AUTH_REALM = String(process.env.STOAT_AUTH_REALM || 'Stoat Archive').trim();
const ALLOW_WEAK_PASSWORD = ['1', 'true', 'yes', 'on'].includes(
  String(process.env.STOAT_ALLOW_WEAK_PASSWORD || '').trim().toLowerCase()
);

function parseArgs(argv) {
  const out = {
    zip: DEFAULT_ZIP,
    port: DEFAULT_PORT,
  };

  for (let i = 2; i < argv.length; i += 1) {
    const arg = argv[i];
    if ((arg === '--zip' || arg === '-z') && argv[i + 1]) {
      out.zip = argv[i + 1];
      i += 1;
      continue;
    }
    if ((arg === '--port' || arg === '-p') && argv[i + 1]) {
      out.port = Number(argv[i + 1]);
      i += 1;
    }
  }

  return out;
}

function normalizeChannelName(raw) {
  return raw.replace(/_/g, ' ').trim();
}

function inferChannelKind(rawKey) {
  const key = String(rawKey || '');
  if (!key) {
    return 'text';
  }

  if (/[^a-z0-9_-]/.test(key)) {
    return 'voice';
  }

  return 'text';
}

function normalizeKind(value) {
  const lowered = String(value || '').trim().toLowerCase();
  if (lowered === 'voice' || lowered === 'text') {
    return lowered;
  }
  return null;
}

function readChannelKindOverrides(overridesPath) {
  if (!overridesPath || !fs.existsSync(overridesPath)) {
    return { bySlug: new Map(), byKey: new Map(), byName: new Map() };
  }

  const raw = fs.readFileSync(overridesPath, 'utf8');
  const parsed = safeJsonParse(raw, {});

  const bySlug = new Map();
  const byKey = new Map();
  const byName = new Map();

  const mapSection = (section, targetMap) => {
    if (!section || typeof section !== 'object') {
      return;
    }
    for (const [k, v] of Object.entries(section)) {
      const key = String(k || '').trim();
      const kind = normalizeKind(v);
      if (key && kind) {
        targetMap.set(key, kind);
      }
    }
  };

  mapSection(parsed.bySlug, bySlug);
  mapSection(parsed.byKey, byKey);
  mapSection(parsed.byName, byName);

  return { bySlug, byKey, byName };
}

function resolveChannelKind({ folderName, channelKey, channelName, overrides }) {
  if (overrides.bySlug.has(folderName)) {
    return overrides.bySlug.get(folderName);
  }
  if (overrides.byKey.has(channelKey)) {
    return overrides.byKey.get(channelKey);
  }
  if (overrides.byName.has(channelName)) {
    return overrides.byName.get(channelName);
  }
  return inferChannelKind(channelKey);
}

function extractChannelKeyFromJsonPath(entryName) {
  const base = path.posix.basename(entryName);
  const match = base.match(/^(.*)_page_(\d+)\.json$/);
  if (!match) {
    return null;
  }
  return {
    key: match[1],
    page: Number(match[2]),
  };
}

function safeJsonParse(value, fallback) {
  try {
    return JSON.parse(value);
  } catch {
    return fallback;
  }
}

function contentTypeForFile(fileName) {
  const ext = path.extname(fileName).toLowerCase();
  const map = {
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.webp': 'image/webp',
    '.bmp': 'image/bmp',
    '.svg': 'image/svg+xml',
    '.mp4': 'video/mp4',
    '.mov': 'video/quicktime',
    '.mp3': 'audio/mpeg',
    '.wav': 'audio/wav',
    '.ogg': 'audio/ogg',
    '.json': 'application/json; charset=utf-8',
    '.txt': 'text/plain; charset=utf-8',
  };
  return map[ext] || 'application/octet-stream';
}

function safeCompare(a, b) {
  const left = Buffer.from(String(a || ''), 'utf8');
  const right = Buffer.from(String(b || ''), 'utf8');
  if (left.length !== right.length) {
    return false;
  }
  return crypto.timingSafeEqual(left, right);
}

function parseBasicAuth(req) {
  const header = String(req.headers.authorization || '');
  if (!header.startsWith('Basic ')) {
    return null;
  }

  let decoded = '';
  try {
    decoded = Buffer.from(header.slice(6), 'base64').toString('utf8');
  } catch {
    return null;
  }

  const idx = decoded.indexOf(':');
  if (idx < 0) {
    return null;
  }

  return {
    user: decoded.slice(0, idx),
    pass: decoded.slice(idx + 1),
  };
}

function buildArchiveModel(zipPath, overridesPath) {
  if (!fs.existsSync(zipPath)) {
    throw new Error(`Zip not found: ${zipPath}`);
  }

  const zip = new AdmZip(zipPath);
  const overrides = readChannelKindOverrides(overridesPath);
  const entries = zip.getEntries().filter((entry) => !entry.isDirectory);
  const byName = new Map(entries.map((entry) => [entry.entryName, entry]));

  const channels = new Map();
  const avatarsByUser = new Map();

  for (const entry of entries) {
    const entryName = entry.entryName;

    if (entryName.startsWith('avatars/')) {
      const parts = entryName.split('/');
      if (parts.length >= 3) {
        const userId = parts[1];
        const file = parts[2];
        const baseHash = file.split('.')[0];
        if (!avatarsByUser.has(userId)) {
          avatarsByUser.set(userId, new Map());
        }
        avatarsByUser.get(userId).set(baseHash, entryName);
      }
      continue;
    }

    const channelMeta = extractChannelKeyFromJsonPath(entryName);
    if (!channelMeta) {
      continue;
    }

    const folderName = path.posix.dirname(entryName);
    if (!channels.has(folderName)) {
      const normalizedName = normalizeChannelName(channelMeta.key);
      const kind = resolveChannelKind({
        folderName,
        channelKey: channelMeta.key,
        channelName: normalizedName,
        overrides,
      });
      channels.set(folderName, {
        id: folderName,
        slug: folderName,
        key: channelMeta.key,
        name: normalizedName,
        kind,
        pageFiles: [],
        messages: [],
        mediaByAttachmentName: new Map(),
      });
    }

    channels.get(folderName).pageFiles.push({
      page: channelMeta.page,
      entryName,
    });
  }

  for (const entry of entries) {
    if (!entry.entryName.includes('_media/')) {
      continue;
    }
    const folderName = entry.entryName.split('/')[0];
    if (!channels.has(folderName)) {
      continue;
    }

    const filename = path.posix.basename(entry.entryName);
    const parts = filename.split('_');
    if (parts.length < 4) {
      continue;
    }
    const originalAndSuffix = parts.slice(3).join('_');
    const marker = originalAndSuffix.indexOf('.');
    if (marker < 0) {
      continue;
    }
    const originalName = originalAndSuffix.slice(0, marker).toLowerCase();
    if (!originalName) {
      continue;
    }

    const channel = channels.get(folderName);
    if (!channel.mediaByAttachmentName.has(originalName)) {
      channel.mediaByAttachmentName.set(originalName, []);
    }
    channel.mediaByAttachmentName.get(originalName).push(entry.entryName);
  }

  for (const channel of channels.values()) {
    channel.pageFiles.sort((a, b) => a.page - b.page);

    for (const pageFile of channel.pageFiles) {
      const entry = byName.get(pageFile.entryName);
      if (!entry) {
        continue;
      }
      const raw = entry.getData().toString('utf8');
      const parsed = safeJsonParse(raw, []);
      if (!Array.isArray(parsed)) {
        continue;
      }

      for (const message of parsed) {
        if (!message || typeof message !== 'object') {
          continue;
        }

        const author = message.author || {};
        const attachments = Array.isArray(message.attachments) ? message.attachments : [];
        const resolvedAttachments = attachments.map((attachment) => {
          const fileName = String(attachment.filename || '').trim();
          const options = channel.mediaByAttachmentName.get(fileName.toLowerCase()) || [];
          const localPath = options.length > 0 ? options[0] : null;
          return {
            ...attachment,
            localPath,
          };
        });

        const userId = String(author.id || '');
        const avatarHash = String(author.avatar || '');
        let avatarPath = null;
        if (userId && avatarHash && avatarsByUser.has(userId)) {
          avatarPath = avatarsByUser.get(userId).get(avatarHash) || null;
        }

        channel.messages.push({
          id: String(message.id || ''),
          channelId: String(message.channel_id || ''),
          timestamp: message.timestamp || null,
          editedTimestamp: message.edited_timestamp || null,
          content: message.content || '',
          userName: message.userName || author.global_name || author.username || 'Unknown',
          author: {
            id: userId,
            username: author.username || null,
            globalName: author.global_name || null,
            avatarHash: avatarHash || null,
            avatarPath,
          },
          attachments: resolvedAttachments,
          embeds: Array.isArray(message.embeds) ? message.embeds : [],
        });
      }
    }

    channel.messages.sort((a, b) => {
      const ta = a.timestamp ? new Date(a.timestamp).getTime() : 0;
      const tb = b.timestamp ? new Date(b.timestamp).getTime() : 0;
      return ta - tb;
    });
  }

  return {
    zip,
    channels,
    channelList: Array.from(channels.values())
      .map((channel) => ({
        id: channel.id,
        slug: channel.slug,
        key: channel.key,
        name: channel.name,
        kind: channel.kind,
        pages: channel.pageFiles.length,
        messageCount: channel.messages.length,
      }))
      .sort((a, b) => b.messageCount - a.messageCount),
  };
}

function createApp(model) {
  const app = express();
  const publicDir = path.join(__dirname, 'public');

  app.disable('x-powered-by');

  app.use(
    helmet({
      crossOriginEmbedderPolicy: false,
      contentSecurityPolicy: {
        useDefaults: true,
        directives: {
          "default-src": ["'self'"],
          "script-src": ["'self'"],
          "style-src": ["'self'"],
          "img-src": ["'self'", 'data:'],
          "media-src": ["'self'"],
          "connect-src": ["'self'"],
          "object-src": ["'none'"],
          "frame-ancestors": ["'none'"],
          "base-uri": ["'self'"],
        },
      },
      hsts: false,
    })
  );

  app.use((req, res, next) => {
    if (!['GET', 'HEAD'].includes(req.method)) {
      res.status(405).json({ error: 'method not allowed' });
      return;
    }
    next();
  });

  app.use(
    rateLimit({
      windowMs: 60 * 1000,
      limit: 180,
      standardHeaders: true,
      legacyHeaders: false,
      message: { error: 'rate limit exceeded' },
    })
  );

  app.use((req, res, next) => {
    const creds = parseBasicAuth(req);
    const ok = creds && safeCompare(creds.user, AUTH_USER) && safeCompare(creds.pass, AUTH_PASS);

    if (!ok) {
      res.setHeader('WWW-Authenticate', `Basic realm="${AUTH_REALM}"`);
      res.status(401).send('authentication required');
      return;
    }

    next();
  });

  app.use(express.static(publicDir));

  app.get('/healthz', (_req, res) => {
    res.json({ ok: true, channels: model.channelList.length });
  });

  app.get('/api/channels', (_req, res) => {
    res.json(model.channelList);
  });

  app.get('/api/channel/:slug/messages', (req, res) => {
    const slug = req.params.slug;
    const channel = model.channels.get(slug);
    if (!channel) {
      res.status(404).json({ error: 'Channel not found' });
      return;
    }

    const offset = Math.max(0, Number(req.query.offset || 0));
    const limit = Math.min(500, Math.max(1, Number(req.query.limit || 200)));
    const end = Math.min(channel.messages.length, offset + limit);
    const items = channel.messages.slice(offset, end);

    res.json({
      channel: {
        id: channel.id,
        slug: channel.slug,
        name: channel.name,
        kind: channel.kind,
        messageCount: channel.messages.length,
      },
      paging: {
        offset,
        limit,
        returned: items.length,
        hasMore: end < channel.messages.length,
      },
      items,
    });
  });

  app.get('/asset', (req, res) => {
    const entryName = String(req.query.path || '');
    if (!entryName || entryName.includes('..')) {
      res.status(400).send('invalid asset path');
      return;
    }
    const entry = model.zip.getEntry(entryName);
    if (!entry || entry.isDirectory) {
      res.status(404).send('asset not found');
      return;
    }

    const data = entry.getData();
    res.setHeader('Content-Type', contentTypeForFile(entryName));
    res.setHeader('Cache-Control', 'public, max-age=86400');
    res.send(data);
  });

  return app;
}

function main() {
  if (!AUTH_USER || !AUTH_PASS) {
    console.error('Missing required auth environment variables: STOAT_AUTH_USER and STOAT_AUTH_PASS');
    process.exit(1);
  }

  if (AUTH_PASS.length < 16 && !ALLOW_WEAK_PASSWORD) {
    console.error('STOAT_AUTH_PASS must be at least 16 characters for safe public exposure');
    process.exit(1);
  }

  if (AUTH_PASS.length < 16 && ALLOW_WEAK_PASSWORD) {
    console.warn('Warning: weak Stoat password is allowed by STOAT_ALLOW_WEAK_PASSWORD');
  }

  const args = parseArgs(process.argv);
  const model = buildArchiveModel(args.zip, DEFAULT_OVERRIDES);
  const app = createApp(model);

  app.listen(args.port, () => {
    console.log(`Stoat server listening on http://127.0.0.1:${args.port}`);
    console.log(`Loaded archive: ${args.zip}`);
    console.log(`Channel kind overrides: ${DEFAULT_OVERRIDES}`);
    console.log(`Channels: ${model.channelList.length}`);
  });
}

main();