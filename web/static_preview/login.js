const API_BASE = 'http://127.0.0.1:7860';
const ACCESS_TOKEN_KEY = 'aicomic_access_token';
const REFRESH_TOKEN_KEY = 'aicomic_refresh_token';
const USER_KEY = 'aicomic_current_user';

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

async function requestJson(path, options = {}) {
  const headers = new Headers(options.headers || {});
  const token = localStorage.getItem(ACCESS_TOKEN_KEY) || '';
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
    throw new Error(`API ${path} failed: ${response.status}`);
  }
  return response.json();
}

async function init() {
  const authStatusBadge = document.getElementById('authStatusBadge');
  const providerList = document.getElementById('providerList');
  const authNote = document.getElementById('authNote');
  const loginMessage = document.getElementById('loginMessage');

  clearAuthState();

  try {
    const [health, config, providers, mePayload] = await Promise.all([
      requestJson('/api/health'),
      requestJson('/api/auth/config'),
      requestJson('/api/auth/providers'),
      requestJson('/api/auth/me'),
    ]);

    if (mePayload && mePayload.authenticated) {
      saveAuthState(mePayload);
      window.location.href = './index.html';
      return;
    }

    authStatusBadge.textContent =
      `后端在线：${health.status} · 鉴权 ${config.auth_enabled ? '已启用' : '当前关闭'}`;
    providerList.innerHTML = (providers.items || []).map((item) =>
      `<li>${item.label}：<strong>${item.enabled ? '可用' : '关闭'}</strong></li>`).join('');
    authNote.textContent = config.auth_reason || config.creator_only_reason || '请使用个人创作者账号登录。';

    document.getElementById('loginForm').addEventListener('submit', async (event) => {
      event.preventDefault();
      loginMessage.textContent = '正在登录...';
      try {
        const payload = await requestJson('/api/auth/login', {
          method: 'POST',
          body: JSON.stringify({
            username: document.getElementById('usernameInput').value.trim(),
            password: document.getElementById('passwordInput').value,
          }),
        });
        saveAuthState(payload);
        loginMessage.textContent = '登录成功，正在进入控制台...';
        window.location.href = './index.html';
      } catch (error) {
        loginMessage.textContent = `登录失败：${error.message}`;
      }
    });
  } catch (error) {
    authStatusBadge.textContent = `后端连接失败：${error.message}`;
    loginMessage.textContent = '请先启动后端 API，再重试登录。';
  }
}

void init();
