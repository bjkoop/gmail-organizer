let total = 0;
let currentIndex = 0;
let currentMessageId = null;
let currentLabels = [];
let availableLabels = [];
let analysisText = null;
let currentMailbox = 'inbox';

async function fetchJSON(url, opts) {
  const res = await fetch(url, opts);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

function renderLabels(labels) {
  const el = document.getElementById('labels');
  el.innerHTML = '';
  labels.forEach(l => {
    const pill = document.createElement('span');
    pill.className = 'label-pill';
    pill.textContent = l;
    el.appendChild(pill);
  });
}

function renderIndex() {
  document.getElementById('index').textContent = `${Math.min(currentIndex+1, total)}/${total}`;
}

async function loadAvailableLabels() {
  const data = await fetchJSON('/api/labels');
  availableLabels = data.labels || [];
}

async function loadCount() {
  const data = await fetchJSON(`/api/messages/count?mailbox=${currentMailbox}`);
  total = data.count || 0;
  renderIndex();
}

async function loadMessage(index) {
  const data = await fetchJSON(`/api/messages/item?index=${index}&mailbox=${currentMailbox}`);
  currentIndex = data.index;
  total = data.total;
  currentMessageId = data.id;
  currentLabels = data.labels || [];
  analysisText = null; // reset when switching messages
  // Clear AI panel content to avoid showing previous mail's analysis
  const aiEl = document.getElementById('ai-content');
  if (aiEl) aiEl.textContent = '';

  document.getElementById('subject').textContent = data.subject || '(geen onderwerp)';
  document.getElementById('sender').textContent = data.sender || '(afzender onbekend)';
  document.getElementById('date').textContent = data.date || '(datum onbekend)';
  const contentEl = document.getElementById('content');
  const html = data.bodyHtml || '';
  if (window.DOMPurify) {
    contentEl.innerHTML = DOMPurify.sanitize(html);
  } else {
    // Fallback: insert as-is (local app), or plain text
    try {
      contentEl.innerHTML = html;
    } catch (e) {
      contentEl.textContent = data.body || '';
    }
  }
  renderLabels(currentLabels);
  renderIndex();
}
async function ensureAnalysis() {
  // Try to get cached analysis first
  try {
    const data = await fetchJSON(`/api/messages/${currentMessageId}/analysis`);
    analysisText = data.text || '';
  } catch (e) {
    // Not cached yet, generate
    const data = await fetchJSON(`/api/messages/${currentMessageId}/analyze`, { method: 'POST' });
    analysisText = data.text || '';
  }
}

function showAiPanel() {
  const panel = document.getElementById('ai-panel');
  panel.classList.add('open');
}

function hideAiPanel() {
  const panel = document.getElementById('ai-panel');
  panel.classList.remove('open');
}

async function openAiAndLoad() {
  showAiPanel();
  if (!analysisText) {
    await ensureAnalysis();
  }
  const el = document.getElementById('ai-content');
  el.textContent = analysisText || '';
}

function showLabelModal() {
  const modal = document.getElementById('label-modal');
  const list = document.getElementById('label-list');
  list.innerHTML = '';
  availableLabels.forEach(l => {
    const item = document.createElement('label');
    item.className = 'label-item';
    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.value = l;
    cb.checked = currentLabels.includes(l);
    const span = document.createElement('span');
    span.textContent = l;
    item.appendChild(cb);
    item.appendChild(span);
    list.appendChild(item);
  });
  modal.classList.remove('hidden');
}

function hideLabelModal() {
  document.getElementById('label-modal').classList.add('hidden');
}

async function applyLabelsFromModal() {
  const cbs = document.querySelectorAll('#label-list input[type="checkbox"]');
  const selected = Array.from(cbs).filter(cb => cb.checked).map(cb => cb.value);
  await fetchJSON(`/api/messages/${currentMessageId}/labels`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ labels: selected })
  });
  currentLabels = selected;
  renderLabels(currentLabels);
  hideLabelModal();
}

async function archiveMessage() {
  if (!currentMessageId) return;
  await fetchJSON(`/api/messages/${currentMessageId}/archive`, { method: 'POST' });
}

async function deleteMessage() {
  if (!currentMessageId) return;
  await fetchJSON(`/api/messages/${currentMessageId}/delete`, { method: 'POST' });
}

async function init() {
  await loadAvailableLabels();
  await loadCount();
  if (total > 0) {
    await loadMessage(0);
  }
  // Bindings
  document.getElementById('mailbox-selector').addEventListener('change', async (e) => {
    currentMailbox = e.target.value;
    currentIndex = 0;
    await loadCount();
    if (total > 0) {
      await loadMessage(0);
    } else {
      // Clear display if no messages
      document.getElementById('subject').textContent = '(geen berichten)';
      document.getElementById('sender').textContent = '';
      document.getElementById('date').textContent = '';
      document.getElementById('content').innerHTML = '';
      document.getElementById('labels').innerHTML = '';
    }
  });
  document.getElementById('btn-prev').addEventListener('click', async () => {
    if (currentIndex > 0) await loadMessage(currentIndex - 1);
  });
  document.getElementById('btn-next').addEventListener('click', async () => {
    if (currentIndex < total - 1) await loadMessage(currentIndex + 1);
  });
  document.getElementById('btn-ai').addEventListener('click', openAiAndLoad);
  document.getElementById('btn-label').addEventListener('click', showLabelModal);
  document.getElementById('label-cancel').addEventListener('click', hideLabelModal);
  document.getElementById('label-ok').addEventListener('click', applyLabelsFromModal);
  document.getElementById('ai-close').addEventListener('click', hideAiPanel);
  document.getElementById('btn-archive').addEventListener('click', async () => {
    await archiveMessage();
    // Move to next to keep flow pleasant
    if (currentIndex < total - 1) await loadMessage(currentIndex + 1);
  });
  document.getElementById('btn-delete').addEventListener('click', async () => {
    await deleteMessage();
    if (currentIndex < total - 1) await loadMessage(currentIndex + 1);
  });
}

window.addEventListener('DOMContentLoaded', init);
