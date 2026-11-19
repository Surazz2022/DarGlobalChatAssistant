const form = document.querySelector('#chat-form');
const input = document.querySelector('#chat-input');
const messages = document.querySelector('#messages');
const modelSelect = document.querySelector('#model-select');
const history = [];

function escapeHtml(value) {
  const div = document.createElement('div');
  div.textContent = value;
  return div.innerHTML;
}

function addMessage(role, content, sources = [], metadata = null) {
  const article = document.createElement('article');
  article.className = `message ${role}`;
  const sourceHtml = sources.length ? `<div class="sources"><strong>Sources</strong>${sources.map(s => `<a href="${escapeHtml(s.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(s.source)} — ${escapeHtml(s.title)}</a>`).join('')}</div>` : '';
  const metaHtml = metadata ? `<div class="message-meta"><span>${escapeHtml(metadata.intent)}</span><span>${escapeHtml(metadata.confidence)} retrieval confidence</span></div>` : '';
  article.innerHTML = `<div class="avatar">${role === 'user' ? 'YOU' : 'AI'}</div><div class="bubble"><p>${escapeHtml(content).replaceAll('\n','<br>')}</p>${metaHtml}${sourceHtml}</div>`;
  messages.appendChild(article);
  messages.scrollTop = messages.scrollHeight;
}

async function send(message) {
  if (!message.trim()) return;
  addMessage('user', message);
  history.push({role:'user', content:message});
  input.value = '';
  form.querySelector('button').disabled = true;
  let thinkingMessage;
  try {
    thinkingMessage = addThinkingMessage();
    const response = await fetch('/api/chat', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message,history:history.slice(-10),model:modelSelect.value})});
    if (!response.ok) throw new Error('Request failed');
    const data = await response.json();
    if (thinkingMessage) thinkingMessage.remove();
    addMessage('assistant', data.answer, data.sources, {intent:data.intent, confidence:data.confidence});
    history.push({role:'assistant', content:data.answer});
  } catch (error) {
    if (thinkingMessage) thinkingMessage.remove();
    addMessage('assistant', 'Sorry, I could not reach the assistant service. Please try again.');
  } finally {
    form.querySelector('button').disabled = false;
    input.focus();
  }
}

async function loadModels() {
  try {
    const response = await fetch('/api/models');
    if (!response.ok) return;
    const data = await response.json();
    for (const model of data.models || []) {
      const option = document.createElement('option');
      option.value = model.id;
      option.textContent = model.name;
      modelSelect.appendChild(option);
    }
  } catch (_) {}
}

function addThinkingMessage() {
  const article = document.createElement('article');
  article.className = 'message assistant thinking-message';
  article.innerHTML = `
    <div class="avatar">AI</div>
    <div class="thinking-card">
      <div class="thinking-toggle">
        <span class="thinking-spinner"></span>
        <span class="thinking-title">Searching sources…</span>
      </div>
    </div>`;
  messages.appendChild(article);
  messages.scrollTop = messages.scrollHeight;
  return article;
}

form.addEventListener('submit', event => { event.preventDefault(); send(input.value); });
document.querySelectorAll('.suggestions button').forEach(button => button.addEventListener('click', () => send(button.textContent)));
loadModels();
