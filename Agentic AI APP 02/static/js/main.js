/* ══════════════════════════════════════════════════
   AI Career Mentor — Main JavaScript
   Theme | Upload | Agent Steps | API calls | UI
══════════════════════════════════════════════════ */

// ── Theme ──────────────────────────────────────────────────────────────────────
const html = document.documentElement;
const themeKey = 'cm-theme';

function initTheme() {
  const saved = localStorage.getItem(themeKey) || 'dark';
  applyTheme(saved);
}

function applyTheme(theme) {
  html.setAttribute('data-theme', theme);
  localStorage.setItem(themeKey, theme);
  const icon = theme === 'dark' ? '☀' : '☾';
  document.querySelectorAll('#themeIcon, #themeIconMobile').forEach(el => { if (el) el.textContent = icon; });
}

function toggleTheme() {
  const current = html.getAttribute('data-theme');
  applyTheme(current === 'dark' ? 'light' : 'dark');
}

document.getElementById('themeToggle')?.addEventListener('click', toggleTheme);
document.getElementById('themeToggleMobile')?.addEventListener('click', toggleTheme);
initTheme();


// ── Mobile Sidebar ─────────────────────────────────────────────────────────────
const sidebar = document.getElementById('sidebar');
const menuToggle = document.getElementById('menuToggle');

menuToggle?.addEventListener('click', () => {
  sidebar.classList.toggle('open');
});

document.addEventListener('click', (e) => {
  if (sidebar?.classList.contains('open') && !sidebar.contains(e.target) && e.target !== menuToggle) {
    sidebar.classList.remove('open');
  }
});


// ── Loading Overlay ────────────────────────────────────────────────────────────
const overlay = document.getElementById('loadingOverlay');
const agentSteps = ['step-observe','step-parse','step-analyse','step-search','step-match','step-decide'];
let stepTimer = null;

function showLoading(title = 'Agent Running', sub = 'Analysing your profile…') {
  document.getElementById('loadingTitle').textContent = title;
  document.getElementById('loadingSub').textContent = sub;
  overlay.classList.add('active');
  // Reset steps
  agentSteps.forEach(id => {
    const el = document.getElementById(id);
    if (el) { el.classList.remove('active', 'done'); }
  });
  // Animate steps
  let i = 0;
  stepTimer = setInterval(() => {
    if (i > 0 && document.getElementById(agentSteps[i - 1])) {
      document.getElementById(agentSteps[i - 1]).classList.remove('active');
      document.getElementById(agentSteps[i - 1]).classList.add('done');
    }
    if (i < agentSteps.length) {
      const el = document.getElementById(agentSteps[i]);
      if (el) el.classList.add('active');
      i++;
    } else {
      clearInterval(stepTimer);
    }
  }, 1400);
}

function hideLoading() {
  clearInterval(stepTimer);
  overlay.classList.remove('active');
}


// ── Session clear ──────────────────────────────────────────────────────────────
async function clearSession() {
  if (!confirm('Start a new session? Your current analysis will be cleared.')) return;
  await fetch('/api/clear-session', { method: 'POST' });
  window.location.href = '/';
}


// ── Tab switching ──────────────────────────────────────────────────────────────
function initTabs() {
  document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      const group = tab.closest('.tabs');
      const targetId = tab.dataset.tab;
      group.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const container = group.nextElementSibling;
      container?.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
      document.getElementById(targetId)?.classList.add('active');
    });
  });
}
initTabs();


// ── Cover Letter Modal ─────────────────────────────────────────────────────────
function openCoverLetterModal(jobTitle, company, jobDescription, jobUrl) {
  const modal = document.getElementById('coverLetterModal');
  if (!modal) return;
  document.getElementById('clJobTitle').value = jobTitle || '';
  document.getElementById('clCompany').value = company || '';
  document.getElementById('clJobDesc').value = jobDescription || '';
  document.getElementById('clJobUrl').value = jobUrl || '#';
  document.getElementById('clResult').style.display = 'none';
  document.getElementById('clContent').textContent = '';
  modal.classList.add('open');
}

function closeCoverLetterModal() {
  document.getElementById('coverLetterModal')?.classList.remove('open');
}

async function generateCoverLetter() {
  const btn = document.getElementById('generateClBtn');
  const jobTitle = document.getElementById('clJobTitle').value;
  const company = document.getElementById('clCompany').value;
  const jobDescription = document.getElementById('clJobDesc').value;

  if (!jobTitle || !company) { alert('Job title and company are required.'); return; }

  btn.textContent = 'Generating…';
  btn.disabled = true;

  try {
    const resp = await fetch('/api/generate-cover-letter', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_title: jobTitle, company, job_description: jobDescription }),
    });
    const data = await resp.json();

    if (data.success) {
      document.getElementById('clContent').textContent = data.cover_letter;
      document.getElementById('clResult').style.display = 'block';
      document.getElementById('clResult').dataset.letterId = data.id;
    } else {
      alert(data.error || 'Failed to generate cover letter.');
    }
  } catch (e) {
    alert('Network error. Please try again.');
  } finally {
    btn.textContent = 'Generate Cover Letter';
    btn.disabled = false;
  }
}

function copyCoverLetter() {
  const text = document.getElementById('clContent')?.textContent;
  if (text) {
    navigator.clipboard.writeText(text).then(() => {
      const btn = event.target;
      btn.textContent = 'Copied!';
      setTimeout(() => { btn.textContent = 'Copy'; }, 2000);
    });
  }
}


// ── Auto Apply ────────────────────────────────────────────────────────────────
async function autoApply(jobTitle, company, jobUrl) {
  if (!confirm(`Simulate application to ${jobTitle} at ${company}?`)) return;

  const btn = event.target;
  btn.textContent = 'Applying…';
  btn.disabled = true;

  try {
    const resp = await fetch('/api/auto-apply', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_title: jobTitle, company, job_url: jobUrl }),
    });
    const data = await resp.json();

    if (data.success) {
      btn.textContent = '✓ Applied';
      btn.classList.remove('btn-cyan');
      btn.classList.add('btn-secondary');
      showToast(`Application logged for ${jobTitle} at ${company}!`, 'success');
    } else {
      alert(data.error || 'Apply failed.');
      btn.textContent = 'Auto Apply';
      btn.disabled = false;
    }
  } catch (e) {
    alert('Network error.');
    btn.textContent = 'Auto Apply';
    btn.disabled = false;
  }
}


// ── Roadmap Generation ─────────────────────────────────────────────────────────
async function generateRoadmap(targetCareer) {
  showLoading('Building Roadmap', 'Crafting your personalised learning plan…');

  try {
    const resp = await fetch('/api/generate-roadmap', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target_career: targetCareer }),
    });
    const data = await resp.json();
    hideLoading();

    if (data.success) {
      window.location.href = '/roadmap';
    } else {
      alert(data.error || 'Roadmap generation failed.');
    }
  } catch (e) {
    hideLoading();
    alert('Network error. Please try again.');
  }
}


// ── Toast Notification ─────────────────────────────────────────────────────────
function showToast(message, type = 'success') {
  const toast = document.createElement('div');
  toast.style.cssText = `
    position: fixed; bottom: 24px; right: 24px;
    background: var(--bg-2); border: 1px solid var(--border);
    border-left: 3px solid var(--${type === 'success' ? 'success' : 'danger'});
    color: var(--text); padding: 12px 20px; border-radius: 10px;
    font-size: 14px; z-index: 2000; box-shadow: var(--shadow);
    animation: fadeSlideIn 0.3s both;
  `;
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3500);
}


// ── Progress bar animation on load ───────────────────────────────────────────
function animateProgressBars() {
  document.querySelectorAll('.progress-fill').forEach(bar => {
    const target = bar.dataset.width || '0';
    bar.style.width = '0%';
    setTimeout(() => { bar.style.width = target + '%'; }, 100);
  });
}

window.addEventListener('load', animateProgressBars);


// ── Match ring animation ──────────────────────────────────────────────────────
function animateRings() {
  document.querySelectorAll('.fill-ring').forEach(ring => {
    const r = ring.getAttribute('r');
    const circ = 2 * Math.PI * r;
    const pct = parseFloat(ring.dataset.pct || 0) / 100;
    ring.style.strokeDasharray = circ;
    ring.style.strokeDashoffset = circ;
    setTimeout(() => {
      ring.style.strokeDashoffset = circ * (1 - pct);
    }, 150);
  });
}

window.addEventListener('load', animateRings);