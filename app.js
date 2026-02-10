const $ = (id) => document.getElementById(id);

const state = {
  token: localStorage.getItem('token') || null,
  me: null,
  chats: [],
  chatId: null,
  abort: null,
  settings: {
    uiBaseUrl: localStorage.getItem('uiBaseUrl') || '',
    ragTopK: Number(localStorage.getItem('ragTopK') || '5')
  }
};

function setStatus(text) { $('status').textContent = text; }
function show(el, on) { el.classList.toggle('hidden', !on); }

async function api(path, { method='GET', headers={}, body=null } = {}) {
  const h = { 'Content-Type': 'application/json', ...headers };
  if (state.token) h['Authorization'] = `Bearer ${state.token}`;
  const r = await fetch(path, { method, headers: h, body: body ? JSON.stringify(body) : null });
  const t = await r.text();
  const data = t ? JSON.parse(t) : null;
  if (!r.ok) {
    const msg = data?.detail || data?.error || `HTTP ${r.status}`;
    throw new Error(msg);
  }
  return data;
}

async function apiUpload(file, chatId) {
  const fd = new FormData();
  fd.append('file', file);
  fd.append('chat_id', chatId);
  fd.append('top_k', String(state.settings.ragTopK));

  const headers = {};
  if (state.token) headers['Authorization'] = `Bearer ${state.token}`;

  const r = await fetch('/api/upload', { method: 'POST', headers, body: fd });
  const t = await r.text();
  const data = t ? JSON.parse(t) : null;
  if (!r.ok) throw new Error(data?.detail || `HTTP ${r.status}`);
  return data;
}

function renderChats() {
  const wrap = $('chats');
  wrap.innerHTML = '';
  for (const c of state.chats) {
    const div = document.createElement('div');
    div.className = 'chat-item' + (c.id === state.chatId ? ' active' : '');
    div.onclick = () => selectChat(c.id);
    div.innerHTML = `<div class="chat-title">${escapeHtml(c.title || '(untitled)')}</div>
      <div class="chat-meta">${new Date(c.updated_at).toLocaleString()}</div>`;
    wrap.appendChild(div);
  }
}

function renderMessages(msgs) {
  const wrap = $('messages');
  wrap.innerHTML = '';
  for (const m of msgs) {
    const div = document.createElement('div');
    div.className = 'msg role-' + m.role;
    div.innerHTML = `<div class="role">${m.role}</div><pre>${escapeHtml(m.content || '')}</pre>`;
    wrap.appendChild(div);
  }
  wrap.scrollTop = wrap.scrollHeight;
}

function appendAssistantMessagePlaceholder() {
  const wrap = $('messages');
  const div = document.createElement('div');
  div.className = 'msg role-assistant';
  div.innerHTML = `<div class="role">assistant</div><pre id="streamBox"></pre>`;
  wrap.appendChild(div);
  wrap.scrollTop = wrap.scrollHeight;
}

function setStreamText(text) {
  const pre = $('streamBox');
  if (!pre) return;
  pre.textContent = text;
  $('messages').scrollTop = $('messages').scrollHeight;
}

async function refreshMe() {
  if (!state.token) return;
  try {
    state.me = await api('/api/me');
  } catch (e) {
    state.token = null;
    localStorage.removeItem('token');
  }
}

async function refreshModels() {
  const sel = $('model');
  sel.innerHTML = '';
  const data = await api('/api/models');
  const models = data.models || [];
  for (const m of models) {
    const opt = document.createElement('option');
    opt.value = m.id;
    opt.textContent = m.id;
    sel.appendChild(opt);
  }
  if (data.default_chat_model) sel.value = data.default_chat_model;
}

async function refreshChats() {
  state.chats = (await api('/api/chats')).chats;
  renderChats();
}

async function selectChat(chatId) {
  state.chatId = chatId;
  renderChats();
  const msgs = (await api(`/api/chats/${chatId}/messages`)).messages;
  renderMessages(msgs);
}

async function newChat() {
  const { chat } = await api('/api/chats', { method: 'POST', body: { title: '' } });
  await refreshChats();
  await selectChat(chat.id);
}

async function sendMessage() {
  const prompt = $('prompt').value.trim();
  if (!prompt) return;
  if (!state.chatId) await newChat();

  $('prompt').value = '';

  // render optimistic
  const msgs = (await api(`/api/chats/${state.chatId}/messages`)).messages;
  renderMessages(msgs.concat([{ role: 'user', content: prompt }]));
  appendAssistantMessagePlaceholder();

  const model = $('model').value;
  const controller = new AbortController();
  state.abort = controller;

  const headers = {};
  if (state.token) headers['Authorization'] = `Bearer ${state.token}`;

  const r = await fetch(`/api/chats/${state.chatId}/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...headers },
    body: JSON.stringify({ model, prompt, rag_top_k: state.settings.ragTopK }),
    signal: controller.signal
  });

  if (!r.ok) {
    const t = await r.text();
    throw new Error(JSON.parse(t)?.detail || `HTTP ${r.status}`);
  }

  const reader = r.body.getReader();
  const dec = new TextDecoder('utf-8');
  let acc = '';
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    const chunk = dec.decode(value, { stream: true });
    // SSE: lines starting with "data: "
    for (const line of chunk.split(/\r?\n/)) {
      if (!line.startsWith('data:')) continue;
      const payload = line.slice(5).trim();
      if (!payload) continue;
      if (payload === '[DONE]') continue;
      try {
        const ev = JSON.parse(payload);
        const delta = ev.delta || '';
        acc += delta;
        setStreamText(acc);
      } catch {
        // ignore
      }
    }
  }

  // final refresh
  await refreshChats();
  await selectChat(state.chatId);
}

function stopStream() {
  if (state.abort) {
    state.abort.abort();
    state.abort = null;
  }
}

function escapeHtml(s) {
  return s.replace(/[&<>\"']/g, (c) => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'
  }[c]));
}

function applyAuthUI() {
  const loggedIn = !!state.token && !!state.me;
  show($('authPanel'), !loggedIn);
  show($('chatPanel'), loggedIn);
  show($('chats'), loggedIn);
  show($('composer'), loggedIn);
  show($('btnLogout'), loggedIn);
  setStatus(loggedIn ? `已登入：${state.me.email}` : '未登入');
}

async function boot() {
  $('uiBaseUrl').value = state.settings.uiBaseUrl;
  $('ragTopK').value = String(state.settings.ragTopK);
  $('ver').textContent = 'dev';

  await refreshMe();
  applyAuthUI();

  if (state.me) {
    await refreshModels();
    await refreshChats();
    if (state.chats.length) await selectChat(state.chats[0].id);
  }

  $('btnLogin').onclick = async () => {
    $('authMsg').textContent = '';
    try {
      const email = $('email').value.trim();
      const password = $('password').value;
      const data = await api('/api/login', { method: 'POST', body: { email, password } });
      state.token = data.token;
      localStorage.setItem('token', state.token);
      await refreshMe();
      applyAuthUI();
      await refreshModels();
      await refreshChats();
    } catch (e) {
      $('authMsg').textContent = e.message;
    }
  };

  $('btnRegister').onclick = async () => {
    $('authMsg').textContent = '';
    try {
      const email = $('email').value.trim();
      const password = $('password').value;
      await api('/api/register', { method: 'POST', body: { email, password } });
      $('authMsg').textContent = '註冊成功，請登入';
    } catch (e) {
      $('authMsg').textContent = e.message;
    }
  };

  $('btnLogout').onclick = async () => {
    state.token = null;
    state.me = null;
    localStorage.removeItem('token');
    applyAuthUI();
    $('messages').innerHTML = '';
  };

  $('btnNewChat').onclick = () => newChat();
  $('btnRefresh').onclick = () => refreshChats();

  $('btnSend').onclick = async () => {
    $('hint').textContent = '';
    try { await sendMessage(); }
    catch (e) { $('hint').textContent = e.message; }
  };

  $('btnStop').onclick = () => stopStream();

  $('prompt').addEventListener('keydown', (ev) => {
    if (ev.key === 'Enter' && !ev.shiftKey) {
      ev.preventDefault();
      $('btnSend').click();
    }
  });

  $('btnSettings').onclick = () => $('dlgSettings').showModal();

  $('btnSaveSettings').onclick = () => {
    state.settings.uiBaseUrl = $('uiBaseUrl').value.trim();
    state.settings.ragTopK = Number($('ragTopK').value || '5');
    localStorage.setItem('uiBaseUrl', state.settings.uiBaseUrl);
    localStorage.setItem('ragTopK', String(state.settings.ragTopK));
  };

  $('btnUpload').onclick = () => {
    $('fileInput').value = '';
    $('fileInput').click();
  };

  $('fileInput').onchange = async () => {
    const f = $('fileInput').files?.[0];
    if (!f) return;
    try {
      if (!state.chatId) await newChat();
      $('hint').textContent = `上傳中：${f.name}`;
      const res = await apiUpload(f, state.chatId);
      $('hint').textContent = `已建立索引：chunks=${res.chunks}`;
    } catch (e) {
      $('hint').textContent = e.message;
    }
  };
}

boot();
