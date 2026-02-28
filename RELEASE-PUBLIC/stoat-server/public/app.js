const state = {
  channels: [],
  filteredChannels: [],
  selectedSlug: null,
  offset: 0,
  limit: 200,
  hasMore: false,
};

const channelListEl = document.getElementById('channelList');
const channelFilterEl = document.getElementById('channelFilter');
const headerEl = document.getElementById('header');
const messagesEl = document.getElementById('messages');
const loadMoreBtn = document.getElementById('loadMore');

function formatTimestamp(timestamp) {
  if (!timestamp) {
    return 'unknown time';
  }
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return timestamp;
  }
  return date.toLocaleString();
}

function isImage(fileName) {
  return /\.(png|jpe?g|gif|webp|bmp|svg)$/i.test(fileName || '');
}

function isVideo(fileName) {
  return /\.(mp4|mov|webm)$/i.test(fileName || '');
}

function renderChannels() {
  channelListEl.innerHTML = '';

  const textChannels = state.filteredChannels.filter((channel) => channel.kind !== 'voice');
  const voiceChannels = state.filteredChannels.filter((channel) => channel.kind === 'voice');

  const groups = [
    { title: 'Text Channels', items: textChannels },
    { title: 'Voice Channels', items: voiceChannels },
  ];

  for (const group of groups) {
    if (group.items.length === 0) {
      continue;
    }

    const heading = document.createElement('div');
    heading.className = 'channel-group-title';
    heading.textContent = group.title;
    channelListEl.appendChild(heading);

    for (const channel of group.items) {
      const btn = document.createElement('button');
      btn.className = 'channel-item';
      if (channel.slug === state.selectedSlug) {
        btn.classList.add('active');
      }
      const prefix = channel.kind === 'voice' ? '🔊' : '#';
      btn.textContent = `${prefix} ${channel.name} (${channel.messageCount})`;
      btn.addEventListener('click', () => selectChannel(channel.slug));
      channelListEl.appendChild(btn);
    }
  }
}

function renderMessage(message, prepend = false) {
  const item = document.createElement('article');
  item.className = 'message';

  const avatar = document.createElement('img');
  avatar.className = 'avatar';
  if (message.author?.avatarPath) {
    avatar.src = `/asset?path=${encodeURIComponent(message.author.avatarPath)}`;
  }

  const body = document.createElement('div');

  const meta = document.createElement('div');
  meta.className = 'meta';

  const author = document.createElement('span');
  author.className = 'author';
  author.textContent = message.userName || message.author?.username || 'Unknown';

  const time = document.createElement('span');
  time.className = 'time';
  time.textContent = formatTimestamp(message.timestamp);

  meta.appendChild(author);
  meta.appendChild(time);
  body.appendChild(meta);

  const content = document.createElement('div');
  content.className = 'content';
  content.textContent = message.content || '';
  body.appendChild(content);

  for (const attachment of message.attachments || []) {
    const wrapper = document.createElement('div');
    wrapper.className = 'attachment';

    const source = attachment.localPath
      ? `/asset?path=${encodeURIComponent(attachment.localPath)}`
      : attachment.url;

    if (attachment.localPath && isImage(attachment.filename)) {
      const img = document.createElement('img');
      img.src = source;
      img.alt = attachment.filename || 'attachment';
      wrapper.appendChild(img);
    } else if (attachment.localPath && isVideo(attachment.filename)) {
      const video = document.createElement('video');
      video.controls = true;
      video.src = source;
      wrapper.appendChild(video);
    } else {
      const link = document.createElement('a');
      link.href = source;
      link.target = '_blank';
      link.rel = 'noreferrer';
      link.textContent = attachment.filename || 'attachment';
      wrapper.appendChild(link);
    }

    body.appendChild(wrapper);
  }

  item.appendChild(avatar);
  item.appendChild(body);

  if (prepend && messagesEl.firstChild) {
    messagesEl.insertBefore(item, messagesEl.firstChild);
  } else {
    messagesEl.appendChild(item);
  }
}

async function loadMessages({ reset }) {
  if (!state.selectedSlug) {
    return;
  }

  const url = `/api/channel/${encodeURIComponent(state.selectedSlug)}/messages?offset=${state.offset}&limit=${state.limit}`;
  const response = await fetch(url);
  if (!response.ok) {
    return;
  }
  const data = await response.json();

  if (reset) {
    messagesEl.innerHTML = '';
    const prefix = data.channel.kind === 'voice' ? '🔊' : '#';
    headerEl.textContent = `${prefix} ${data.channel.name} (${data.channel.messageCount} messages)`;
  }

  for (const item of data.items) {
    renderMessage(item);
  }

  state.offset += data.paging.returned;
  state.hasMore = data.paging.hasMore;
  loadMoreBtn.disabled = !state.hasMore;

  if (reset) {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }
}

async function selectChannel(slug) {
  state.selectedSlug = slug;
  state.offset = 0;
  state.hasMore = false;
  renderChannels();
  await loadMessages({ reset: true });
}

function applyFilter() {
  const query = channelFilterEl.value.trim().toLowerCase();
  if (!query) {
    state.filteredChannels = state.channels.slice();
  } else {
    state.filteredChannels = state.channels.filter((channel) =>
      channel.name.toLowerCase().includes(query)
    );
  }
  renderChannels();
}

async function bootstrap() {
  const response = await fetch('/api/channels');
  state.channels = response.ok ? await response.json() : [];
  state.filteredChannels = state.channels.slice();
  renderChannels();

  if (state.channels.length > 0) {
    await selectChannel(state.channels[0].slug);
  }
}

channelFilterEl.addEventListener('input', applyFilter);
loadMoreBtn.addEventListener('click', () => loadMessages({ reset: false }));

bootstrap();