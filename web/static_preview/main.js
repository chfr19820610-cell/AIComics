const API_BASE = 'http://127.0.0.1:7860';
const ACCESS_TOKEN_KEY = 'aicomic_access_token';
const REFRESH_TOKEN_KEY = 'aicomic_refresh_token';
const USER_KEY = 'aicomic_current_user';

function getStorage(key) {
  return localStorage.getItem(key) || '';
}

function saveAuthState(payload) {
  if (payload.access_token) {
    localStorage.setItem(ACCESS_TOKEN_KEY, payload.access_token);
  }
  if (payload.refresh_token) {
    localStorage.setItem(REFRESH_TOKEN_KEY, payload.refresh_token);
  }
  if (payload.user) {
    localStorage.setItem(USER_KEY, JSON.stringify(payload.user));
  }
}

function clearAuthState() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

async function requestJson(path, options = {}, allowUnauthorized = false) {
  const headers = new Headers(options.headers || {});
  const token = getStorage(ACCESS_TOKEN_KEY);
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  if (options.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
    credentials: 'include',
  });

  if (!response.ok) {
    if (response.status === 401 && !allowUnauthorized) {
      clearAuthState();
      window.location.href = './login.html';
      return null;
    }
    throw new Error(`API ${path} failed: ${response.status}`);
  }
  return response.json();
}

async function refreshSession() {
  const refreshToken = getStorage(REFRESH_TOKEN_KEY);
  if (!refreshToken) {
    return null;
  }
  try {
    const payload = await requestJson('/api/auth/refresh', {
      method: 'POST',
      body: JSON.stringify({ refresh_token: refreshToken }),
    }, true);
    if (payload && payload.authenticated) {
      saveAuthState(payload);
      return payload;
    }
  } catch {
    return null;
  }
  return null;
}

async function ensureAuthenticated() {
  const mePayload = await requestJson('/api/auth/me', undefined, true);
  if (mePayload && mePayload.authenticated) {
    if (mePayload.user) {
      localStorage.setItem(USER_KEY, JSON.stringify(mePayload.user));
    }
    return mePayload;
  }
  const refreshed = await refreshSession();
  if (refreshed && refreshed.authenticated) {
    return refreshed;
  }
  clearAuthState();
  window.location.href = './login.html';
  return null;
}

function formatValue(value) {
  if (value === null || value === undefined || value === '') {
    return '-';
  }
  if (Array.isArray(value)) {
    return value.length ? value.join(', ') : '-';
  }
  if (typeof value === 'object') {
    return JSON.stringify(value, null, 2);
  }
  return String(value);
}

function renderMetricGrid(overview = {}) {
  const container = document.getElementById('metricGrid');
  const entries = [
    ['项目数', overview.projects || 0],
    ['剧集数', overview.episodes || 0],
    ['任务数', overview.jobs || 0],
    ['成功任务', overview.succeeded_jobs || 0],
  ];
  container.innerHTML = entries.map(([label, value]) => `
    <div class="metric-card">
      <div class="label">${label}</div>
      <div class="value">${value}</div>
    </div>
  `).join('');
}

function renderList(elementId, items = []) {
  const container = document.getElementById(elementId);
  container.innerHTML = items.length
    ? items.map((item) => `<li>${item}</li>`).join('')
    : '<li class="tip">暂无内容</li>';
}

function renderKeyValueTable(elementId, rows = [], emptyText = '暂无数据') {
  const container = document.getElementById(elementId);
  if (!rows.length) {
    container.innerHTML = `<div class="card tip">${emptyText}</div>`;
    return;
  }
  const headers = Object.keys(rows[0]);
  container.innerHTML = `
    <table>
      <thead>
        <tr>${headers.map((header) => `<th>${header}</th>`).join('')}</tr>
      </thead>
      <tbody>
        ${rows.map((row) => `
          <tr>${headers.map((header) => `<td>${formatValue(row[header])}</td>`).join('')}</tr>
        `).join('')}
      </tbody>
    </table>
  `;
}

function updateUserBadge(user) {
  const userBadge = document.getElementById('userBadge');
  userBadge.textContent = user
    ? `${user.display_name || user.username} · ${user.default_role || 'creator'}`
    : '未登录';
}

function updateHealthBadge(health, edition) {
  const badge = document.getElementById('healthBadge');
  badge.textContent = `${edition?.display_name || health.edition_display_name} · ${health.status}`;
}

async function loadPage() {
  const session = await ensureAuthenticated();
  if (!session) {
    return;
  }

  updateUserBadge(session.user || JSON.parse(getStorage(USER_KEY) || 'null'));

  const [
    health,
    edition,
    dashboard,
    workspace,
    episodes,
    jobs,
    batches,
    providers,
    review,
  ] = await Promise.all([
    requestJson('/api/health', undefined, true),
    requestJson('/api/edition', undefined, true),
    requestJson('/api/dashboard'),
    requestJson('/api/creator/workspace'),
    requestJson('/api/episodes'),
    requestJson('/api/jobs'),
    requestJson('/api/batches/summary'),
    requestJson('/api/providers/executions'),
    requestJson('/api/review-metrics'),
  ]);

  updateHealthBadge(health, edition);
  renderMetricGrid(dashboard.overview || {});
  renderList('nextActions', dashboard.next_actions || []);
  document.getElementById('dashboardSummary').textContent = JSON.stringify({
    status: dashboard.status,
    edition: edition.display_name,
    batch: dashboard.batch || {},
    provider: dashboard.provider || {},
    retry: dashboard.retry || {},
  }, null, 2);

  document.getElementById('creatorProjectSummary').textContent = JSON.stringify({
    project: workspace.project.project_name,
    project_id: workspace.project.project_id,
    genre: workspace.project.genre,
    style_profile: workspace.project.style_profile,
    planned_episode_count: workspace.production_summary.planned_episode_count,
    shot_count: workspace.production_summary.shot_count,
    completion_rate: workspace.production_summary.completion_rate,
  }, null, 2);
  renderList('creatorActions', (workspace.action_catalog || []).map((item) => `${item.label} - ${item.description}`));

  renderKeyValueTable(
    'episodesTable',
    (episodes.items || []).map((item) => ({
      剧集: item.episode_code,
      标题: item.title,
      状态: item.status,
      镜头数: item.shot_count,
      时长秒: item.total_duration_seconds,
      已完成任务: item.completed_jobs,
      总任务: item.total_jobs,
    })),
  );

  renderKeyValueTable(
    'jobsTable',
    (jobs.items || []).map((item) => ({
      JobID: item.job_id,
      剧集: item.episode_code,
      类型: item.job_type,
      Provider: item.provider,
      状态: item.status,
    })),
  );

  document.getElementById('batchRuntimeSummary').textContent = JSON.stringify({
    runtime_status: batches.runtime_monitor?.status || 'unknown',
    job_total_count: batches.runtime_monitor?.job_total_count || 0,
    job_active_count: batches.runtime_monitor?.job_active_count || 0,
    job_failed_count: batches.runtime_monitor?.job_failed_count || 0,
    blocked_batch_count: batches.multi_batch_summary?.blocked_batch_count || 0,
    latest_batch_id: batches.multi_batch_summary?.latest_batch_id || '',
    latest_status: batches.multi_batch_summary?.latest_status || '',
  }, null, 2);
  renderList('batchActions', batches.runtime_monitor?.next_actions || []);
  renderKeyValueTable(
    'batchesTable',
    (batches.items || []).map((item) => ({
      BatchID: item.batch_id,
      范围类型: item.scope_type,
      范围值: item.scope_value,
      状态: item.status,
      步骤数: item.step_count,
      已完成: item.completed_step_count,
      进度: `${item.step_completion_rate || 0}%`,
    })),
  );

  renderKeyValueTable(
    'providerTable',
    (providers.items || []).map((item) => ({
      报告: item.name,
      请求数: item.request_count,
      成功: item.success_count,
      失败: item.failed_count,
      DryRun: item.dry_run_count,
      Blocked: item.blocked_count,
      ConfirmLive: item.confirm_live,
    })),
  );

  document.getElementById('reviewMetrics').textContent = JSON.stringify(review.metrics || {}, null, 2);
  document.getElementById('reviewRisks').textContent = JSON.stringify(review.risk_flags || [], null, 2);
  document.getElementById('reviewRecommendations').textContent = JSON.stringify(review.recommendations || [], null, 2);
}

document.getElementById('refreshAllButton').addEventListener('click', () => {
  void loadPage();
});

document.getElementById('logoutButton').addEventListener('click', async () => {
  try {
    await requestJson('/api/auth/logout', {
      method: 'POST',
      body: JSON.stringify({ refresh_token: getStorage(REFRESH_TOKEN_KEY) }),
    }, true);
  } finally {
    clearAuthState();
    window.location.href = './login.html';
  }
});

void loadPage();
