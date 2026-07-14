const state = { adminKey: localStorage.getItem('mcp_admin_key') || '', tools: [] };
const $ = (id) => document.getElementById(id);

function toast(message) {
  const el = $('toast');
  el.textContent = message;
  el.classList.remove('hidden');
  setTimeout(() => el.classList.add('hidden'), 4200);
}

async function api(path, options = {}, authenticated = true) {
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
  if (authenticated && state.adminKey) headers['X-Admin-Key'] = state.adminKey;
  const response = await fetch(path, { ...options, headers });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || body.message || `Request failed: ${response.status}`);
  return body;
}

function setConnected(connected) {
  $('connection-dot').classList.toggle('online', connected);
  $('connection-label').textContent = connected ? 'Connected' : 'Not connected';
  $('app-content').classList.toggle('hidden', !connected);
}

function formatTime(value) {
  if (!value) return 'Never';
  return new Date(value).toLocaleString();
}

function renderMetrics(summary) {
  const metrics = [
    ['Total calls', summary.total_calls],
    ['Success rate', `${(summary.success_rate * 100).toFixed(1)}%`],
    ['Denied', summary.denied_calls],
    ['P95 latency', `${summary.p95_latency_ms.toFixed(0)} ms`],
    ['Active agents', summary.active_agents],
  ];
  $('metrics').innerHTML = metrics.map(([label, value]) => `<div class="metric"><span>${label}</span><strong>${value}</strong></div>`).join('');
}

function renderTimeline(payload) {
  const buckets = payload.buckets || [];
  const max = Math.max(1, ...buckets.map(x => x.calls));
  $('activity-timeline').style.gridTemplateColumns = `repeat(${Math.max(1, buckets.length)}, minmax(8px, 1fr))`;
  $('activity-timeline').innerHTML = buckets.map(bucket => {
    const totalHeight = bucket.calls / max * 150;
    const successHeight = bucket.calls ? totalHeight * bucket.success / bucket.calls : 0;
    const deniedHeight = bucket.calls ? totalHeight * bucket.denied / bucket.calls : 0;
    const errorHeight = bucket.calls ? totalHeight * bucket.error / bucket.calls : 0;
    const label = `${new Date(bucket.start).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}: ${bucket.calls} calls, ${bucket.denied} denied`;
    return `<div class="time-column" data-label="${label}"><div class="time-error" style="height:${errorHeight}px"></div><div class="time-denied" style="height:${deniedHeight}px"></div><div class="time-success" style="height:${successHeight}px"></div></div>`;
  }).join('');
}

function renderUsage(items) {
  if (!items.length) {
    $('tool-usage').innerHTML = '<p>No calls yet. Invoke an MCP tool to populate analytics.</p>';
    return;
  }
  const max = Math.max(...items.map(x => x.count));
  $('tool-usage').innerHTML = items.map(item => `
    <div class="bar-row">
      <span>${item.tool}</span>
      <div class="bar-track"><div class="bar-fill" style="width:${Math.max(3, item.count / max * 100)}%"></div></div>
      <strong>${item.count}</strong>
    </div>`).join('');
}

function renderAgents(items) {
  $('agents-table').innerHTML = items.map(agent => `
    <tr><td>${agent.name}</td><td>${agent.environment}</td><td><span class="badge ${agent.status}">${agent.status}</span></td><td>${agent.allowed_tools.length}</td><td>${formatTime(agent.last_seen_at)}</td></tr>
  `).join('') || '<tr><td colspan="5">No agents</td></tr>';
}

function renderCredentials(items) {
  $('credentials-table').innerHTML = items.map(item => `<tr><td>${item.provider}</td><td>${item.name}</td><td>${formatTime(item.updated_at)}</td></tr>`).join('') || '<tr><td colspan="3">No credentials</td></tr>';
}

function renderAudit(items) {
  $('audit-table').innerHTML = items.map(event => `
    <tr><td>${formatTime(event.created_at)}</td><td>${event.agent_name}</td><td>${event.tool_name}</td><td>${event.purpose}</td><td><span class="badge ${event.policy_decision}">${event.policy_decision}</span></td><td><span class="badge ${event.status}">${event.status}</span></td><td>${event.latency_ms.toFixed(1)} ms</td></tr>
  `).join('') || '<tr><td colspan="7">No audit events</td></tr>';
}

function renderToolCheckboxes() {
  $('tool-checkboxes').innerHTML = state.tools.map(tool => `
    <label><input type="checkbox" value="${tool.name}" checked><span><strong>${tool.title}</strong><br><small>Risk ${tool.risk_level} · ${tool.purposes.join(', ')}</small></span></label>
  `).join('');
}

async function loadDashboard() {
  try {
    const [tenant, tools, summary, timeseries, agents, credentials, audit] = await Promise.all([
      api('/api/v1/tenant'), api('/api/v1/tools'), api('/api/v1/analytics/summary'), api('/api/v1/analytics/timeseries'), api('/api/v1/agents'), api('/api/v1/credentials'), api('/api/v1/audit?limit=80')
    ]);
    state.tools = tools;
    $('tenant-name').textContent = tenant.name;
    $('tenant-meta').textContent = `${tenant.slug} · ${tenant.id}`;
    renderMetrics(summary); renderTimeline(timeseries); renderUsage(summary.tool_usage); renderAgents(agents); renderCredentials(credentials); renderAudit(audit); renderToolCheckboxes();
    setConnected(true);
  } catch (error) {
    setConnected(false);
    toast(error.message);
  }
}

$('auth-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  state.adminKey = $('admin-key').value.trim();
  localStorage.setItem('mcp_admin_key', state.adminKey);
  await loadDashboard();
});

$('onboard-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  try {
    const result = await api('/api/v1/onboard', { method: 'POST', body: JSON.stringify({ organization_name: $('org-name').value, admin_email: $('admin-email').value }) }, false);
    $('onboard-result').textContent = JSON.stringify(result, null, 2);
    $('onboard-result').classList.remove('hidden');
    state.adminKey = result.admin_key;
    $('admin-key').value = result.admin_key;
    localStorage.setItem('mcp_admin_key', state.adminKey);
    await loadDashboard();
  } catch (error) { toast(error.message); }
});

$('agent-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  try {
    const allowedTools = [...document.querySelectorAll('#tool-checkboxes input:checked')].map(x => x.value);
    const purposes = [...new Set(state.tools.filter(t => allowedTools.includes(t.name)).flatMap(t => t.purposes))];
    const result = await api('/api/v1/agents', { method: 'POST', body: JSON.stringify({ name: $('agent-name').value, environment: $('agent-env').value, allowed_tools: allowedTools, allowed_purposes: purposes }) });
    $('agent-result').textContent = JSON.stringify(result, null, 2);
    $('agent-result').classList.remove('hidden');
    toast('Agent created. Copy the token now.');
    await loadDashboard();
  } catch (error) { toast(error.message); }
});

$('credential-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  try {
    await api('/api/v1/credentials', { method: 'POST', body: JSON.stringify({ provider: $('credential-provider').value, name: $('credential-name').value, secret: $('credential-secret').value }) });
    $('credential-secret').value = '';
    toast('Credential encrypted and stored');
    await loadDashboard();
  } catch (error) { toast(error.message); }
});

$('refresh-button').addEventListener('click', loadDashboard);
if (state.adminKey) { $('admin-key').value = state.adminKey; loadDashboard(); }
setInterval(() => { if (state.adminKey) loadDashboard(); }, 15000);
