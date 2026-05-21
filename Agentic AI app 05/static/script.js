// ─── State ───────────────────────────────────────────────────
let selectedFile = null;
let documentLoaded = false;
let chatHistory = [];
let isThinking = false;

// ─── DOM Refs ─────────────────────────────────────────────────
const uploadZone    = document.getElementById('uploadZone');
const fileInput     = document.getElementById('fileInput');
const uploadBtn     = document.getElementById('uploadBtn');
const uploadBtnText = document.getElementById('uploadBtnText');
const uploadStatus  = document.getElementById('uploadStatus');
const statusDot     = document.getElementById('statusDot');
const statusText    = document.getElementById('statusText');
const statusFilename= document.getElementById('statusFilename');
const statusMeta    = document.getElementById('statusMeta');
const messages      = document.getElementById('messages');
const welcomeState  = document.getElementById('welcomeState');
const messageInput  = document.getElementById('messageInput');
const sendBtn       = document.getElementById('sendBtn');
const docIndicator  = document.getElementById('docIndicator');
const docName       = document.getElementById('docName');

// ─── Upload Zone: click & drag ────────────────────────────────
uploadZone.addEventListener('click', () => fileInput.click());

uploadZone.addEventListener('dragover', (e) => {
  e.preventDefault();
  uploadZone.classList.add('drag-over');
});

uploadZone.addEventListener('dragleave', () => {
  uploadZone.classList.remove('drag-over');
});

uploadZone.addEventListener('drop', (e) => {
  e.preventDefault();
  uploadZone.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) handleFileSelect(file);
});

fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) handleFileSelect(fileInput.files[0]);
});

function handleFileSelect(file) {
  const ext = file.name.split('.').pop().toLowerCase();
  if (!['pdf', 'docx'].includes(ext)) {
    setStatus('error', 'Invalid type', 'Only PDF and DOCX allowed', file.name);
    uploadBtn.disabled = true;
    return;
  }
  if (file.size > 16 * 1024 * 1024) {
    setStatus('error', 'File too large', 'Max 16 MB', file.name);
    uploadBtn.disabled = true;
    return;
  }
  selectedFile = file;
  setStatus('idle', 'Ready to process', formatSize(file.size), file.name);
  uploadBtn.disabled = false;
  uploadBtnText.textContent = 'Process Document';
}

// ─── Upload Button ────────────────────────────────────────────
uploadBtn.addEventListener('click', async () => {
  if (!selectedFile) return;

  setStatus('loading', 'Processing…', 'Extracting and indexing', selectedFile.name);
  uploadBtn.disabled = true;
  uploadBtnText.textContent = 'Processing…';

  const formData = new FormData();
  formData.append('file', selectedFile);

  try {
    const res = await fetch('/upload', { method: 'POST', body: formData });
    const data = await res.json();

    if (!res.ok || data.error) {
      setStatus('error', 'Failed', data.error || 'Upload error', selectedFile.name);
      uploadBtnText.textContent = 'Try Again';
      uploadBtn.disabled = false;
      return;
    }

    setStatus('success', 'Document ready', `${data.chunks} chunks indexed`, data.filename);
    uploadBtnText.textContent = 'Reprocess';
    uploadBtn.disabled = false;
    activateChat(data.filename);

  } catch (err) {
    setStatus('error', 'Network error', err.message, selectedFile.name);
    uploadBtnText.textContent = 'Try Again';
    uploadBtn.disabled = false;
  }
});

function setStatus(type, text, meta, filename) {
  uploadStatus.style.display = 'flex';
  statusDot.className = 'status-dot ' + (type === 'idle' ? '' : type);
  statusText.textContent = text;
  statusMeta.textContent = meta || '';
  statusFilename.textContent = filename || '';
}

function formatSize(bytes) {
  return bytes < 1024 * 1024
    ? `${(bytes / 1024).toFixed(1)} KB`
    : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// ─── Activate Chat ────────────────────────────────────────────
function activateChat(filename) {
  documentLoaded = true;
  chatHistory = [];

  // Update header indicator
  docName.textContent = filename;
  docIndicator.querySelector('.doc-dot').classList.add('active');

  // Clear welcome state
  welcomeState.style.display = 'none';
  messages.innerHTML = '';

  // Enable input
  messageInput.disabled = false;
  sendBtn.disabled = false;
  messageInput.focus();

  // Show system message
  appendMessage('assistant', `Document loaded: <strong>${filename}</strong><br/>Ask me anything about it.`);
}

// ─── Send Message ─────────────────────────────────────────────
sendBtn.addEventListener('click', sendMessage);

messageInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

messageInput.addEventListener('input', () => {
  messageInput.style.height = 'auto';
  messageInput.style.height = Math.min(messageInput.scrollHeight, 120) + 'px';
});

async function sendMessage() {
  const text = messageInput.value.trim();
  if (!text || isThinking || !documentLoaded) return;

  isThinking = true;
  messageInput.value = '';
  messageInput.style.height = 'auto';
  sendBtn.disabled = true;

  appendMessage('user', escapeHtml(text));
  const typingId = appendTyping();

  try {
    const res = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text })
    });

    const data = await res.json();
    removeTyping(typingId);

    if (!res.ok || data.error) {
      appendMessage('assistant', `<span style="color:var(--red)">Error: ${data.error}</span>`);
    } else {
      appendMessage('assistant', escapeHtml(data.response));
    }

  } catch (err) {
    removeTyping(typingId);
    appendMessage('assistant', `<span style="color:var(--red)">Network error. Please try again.</span>`);
  }

  isThinking = false;
  sendBtn.disabled = false;
  messageInput.focus();
}

// ─── Message Helpers ──────────────────────────────────────────
function appendMessage(role, html) {
  const div = document.createElement('div');
  div.className = `message ${role}`;

  const avatar = document.createElement('div');
  avatar.className = 'msg-avatar';
  avatar.textContent = role === 'user' ? 'U' : '⬡';

  const content = document.createElement('div');
  content.className = 'msg-content';
  content.innerHTML = html;

  div.appendChild(avatar);
  div.appendChild(content);
  messages.appendChild(div);
  messages.scrollTop = messages.scrollHeight;
  return div;
}

function appendTyping() {
  const id = 'typing-' + Date.now();
  const div = document.createElement('div');
  div.className = 'message assistant';
  div.id = id;

  const avatar = document.createElement('div');
  avatar.className = 'msg-avatar';
  avatar.textContent = '⬡';

  const content = document.createElement('div');
  content.className = 'msg-content';
  content.innerHTML = `<div class="typing-dots"><span></span><span></span><span></span></div>`;

  div.appendChild(avatar);
  div.appendChild(content);
  messages.appendChild(div);
  messages.scrollTop = messages.scrollHeight;
  return id;
}

function removeTyping(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

function escapeHtml(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\n/g, '<br/>');
}
