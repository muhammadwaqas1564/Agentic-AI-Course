let sessionId = generateId();
let isLoading = false;

const chatContainer = document.getElementById("chatContainer");
const userInput = document.getElementById("userInput");
const sendBtn = document.getElementById("sendBtn");
const emptyState = document.getElementById("emptyState");
const modelSelect = document.getElementById("modelSelect");
const topbarModel = document.getElementById("topbarModel");
const sessionList = document.getElementById("sessionList");

// ── Helpers ──────────────────────────────────────────────

function generateId() {
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
}

function scrollToBottom() {
  chatContainer.scrollTop = chatContainer.scrollHeight;
}

function setLoading(val) {
  isLoading = val;
  sendBtn.disabled = val;
  userInput.disabled = val;
}

// ── Render messages ───────────────────────────────────────

function renderMessage(role, content) {
  emptyState?.remove();

  const row = document.createElement("div");
  row.className = `message-row ${role}`;

  const bubble = document.createElement("div");
  bubble.className = "bubble";

  if (role === "assistant") {
    bubble.innerHTML = marked.parse(content);
  } else {
    bubble.textContent = content;
  }

  row.appendChild(bubble);
  chatContainer.appendChild(row);
  scrollToBottom();
  return row;
}

function renderTyping() {
  const row = document.createElement("div");
  row.className = "message-row assistant";
  row.id = "typingRow";
  row.innerHTML = `<div class="bubble"><div class="typing-indicator">
    <span></span><span></span><span></span>
  </div></div>`;
  chatContainer.appendChild(row);
  scrollToBottom();
}

function removeTyping() {
  document.getElementById("typingRow")?.remove();
}

// ── Send message ──────────────────────────────────────────

async function sendMessage() {
  const msg = userInput.value.trim();
  if (!msg || isLoading) return;

  userInput.value = "";
  userInput.style.height = "auto";
  renderMessage("user", msg);
  setLoading(true);
  renderTyping();

  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: msg,
        session_id: sessionId,
        model: modelSelect.value
      })
    });

    const data = await res.json();
    removeTyping();

    if (data.error) {
      renderMessage("assistant", `⚠️ Error: ${data.error}`);
    } else {
      renderMessage("assistant", data.reply);
      loadSessions();
    }
  } catch (e) {
    removeTyping();
    renderMessage("assistant", "⚠️ Network error. Check your connection.");
  } finally {
    setLoading(false);
    userInput.focus();
  }
}

// ── Sessions ──────────────────────────────────────────────

async function loadSessions() {
  const res = await fetch("/sessions");
  const sessions = await res.json();

  sessionList.innerHTML = "";
  sessions.forEach(s => {
    const el = document.createElement("div");
    el.className = `session-item${s.id === sessionId ? " active" : ""}`;
    el.textContent = s.preview || "New chat";
    el.onclick = () => loadSession(s.id);
    sessionList.appendChild(el);
  });
}

async function loadSession(id) {
  sessionId = id;
  chatContainer.innerHTML = "";

  const res = await fetch(`/history/${id}`);
  const messages = await res.json();
  messages.forEach(m => renderMessage(m.role, m.content));

  loadSessions(); // refresh active state
}

async function newChat() {
  const res = await fetch("/new_session", { method: "POST" });
  const data = await res.json();
  sessionId = data.session_id;

  chatContainer.innerHTML = `<div class="empty-state" id="emptyState">
    <i class="bi bi-stars empty-icon"></i>
    <p>Start a conversation</p>
  </div>`;

  loadSessions();
  userInput.focus();
}

// ── Sidebar ───────────────────────────────────────────────

document.getElementById("toggleSidebar").onclick = () => {
  document.getElementById("sidebar").classList.toggle("hidden");
};
document.getElementById("closeSidebar").onclick = () => {
  document.getElementById("sidebar").classList.add("hidden");
};

// ── Events ────────────────────────────────────────────────

document.getElementById("newChatBtn").onclick = newChat;

sendBtn.onclick = sendMessage;

userInput.addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

// Auto-resize textarea
userInput.addEventListener("input", function () {
  this.style.height = "auto";
  this.style.height = Math.min(this.scrollHeight, 140) + "px";
});

modelSelect.addEventListener("change", () => {
  topbarModel.textContent = modelSelect.value;
});

// ── Init ──────────────────────────────────────────────────
loadSessions();
userInput.focus();
