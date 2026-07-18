import type {
  AuthConfigPayload,
  AuthProvidersPayload,
  AuthSessionPayload,
  BatchExecutionPreviewHistoryPayload,
  BatchExecutionQueueHistoryPayload,
  BatchExecutionOperationsArchiveCleanupResult,
  BatchExecutionOperationsArchivesPayload,
  BatchExecutionOperationsExportResult,
  BatchExecutionQueueStatusResult,
  BatchExecutionPlanPreviewResult,
  BatchExecutionPlanQueueResult,
  BatchesPayload,
  BatchRecord,
  BatchRetryGenerateResult,
  BatchRetryHistoryPayload,
  CreatorActionRunResult,
  CreatorProjectRecord,
  CreatorRunRecord,
  CreatorSampleReviewPayload,
  CreatorWorkspacePayload,
  DashboardPayload,
  EditionCapabilityPayload,
  EpisodeRecord,
  HealthPayload,
  JobRecord,
  ListPayload,
  ProviderExecutionRecord,
  ProjectsPayload,
  ReviewMetricsPayload,
} from '@/types/api';

const apiBaseUrl =
  (typeof process !== 'undefined' ? process.env.UMI_APP_API_BASE_URL : '') || 'http://127.0.0.1:7860';
const ACCESS_TOKEN_KEY = 'aicomic_access_token';
const REFRESH_TOKEN_KEY = 'aicomic_refresh_token';
const USER_KEY = 'aicomic_current_user';

function isBrowser(): boolean {
  return typeof window !== 'undefined';
}

function getStorageItem(key: string): string {
  if (!isBrowser()) {
    return '';
  }
  return window.localStorage.getItem(key) ?? '';
}

function setStorageItem(key: string, value: string): void {
  if (!isBrowser()) {
    return;
  }
  window.localStorage.setItem(key, value);
}

function removeStorageItem(key: string): void {
  if (!isBrowser()) {
    return;
  }
  window.localStorage.removeItem(key);
}

export function getAccessToken(): string {
  return getStorageItem(ACCESS_TOKEN_KEY);
}

export function getRefreshToken(): string {
  return getStorageItem(REFRESH_TOKEN_KEY);
}

export function clearAuthState(): void {
  removeStorageItem(ACCESS_TOKEN_KEY);
  removeStorageItem(REFRESH_TOKEN_KEY);
  removeStorageItem(USER_KEY);
}

export function persistAuthState(payload: AuthSessionPayload): void {
  if (payload.access_token) {
    setStorageItem(ACCESS_TOKEN_KEY, payload.access_token);
  }
  if (payload.refresh_token) {
    setStorageItem(REFRESH_TOKEN_KEY, payload.refresh_token);
  }
  if (payload.user) {
    setStorageItem(USER_KEY, JSON.stringify(payload.user));
  }
}

async function fetchJson<T>(
  path: string,
  init?: RequestInit,
  allowUnauthorized = false,
  timeoutMs = 30000,
): Promise<T> {
  const buildHeaders = (): Headers => {
    const headers = new Headers(init?.headers ?? {});
    if (init?.body && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
    }
    const accessToken = getAccessToken();
    if (accessToken && !headers.has('Authorization')) {
      headers.set('Authorization', `Bearer ${accessToken}`);
    }
    return headers;
  };

  const abortController = new AbortController();
  const timeoutId = setTimeout(() => abortController.abort(), timeoutMs);
  const { signal } = abortController;

  try {
    const response = await fetch(`${apiBaseUrl}${path}`, {
      ...init,
      headers: buildHeaders(),
      credentials: 'include',
      signal,
    });
    if (!response.ok) {
      const responseText = await response.text();
      let detail = '';
      if (responseText) {
        try {
          const payload = JSON.parse(responseText) as { detail?: unknown; message?: unknown };
          if (typeof payload.detail === 'string' && payload.detail.trim()) {
            detail = payload.detail.trim();
          } else if (typeof payload.message === 'string' && payload.message.trim()) {
            detail = payload.message.trim();
          }
        } catch {
          detail = responseText.trim();
        }
      }
      if (response.status === 401 && !allowUnauthorized) {
        clearTimeout(timeoutId);
        try {
          const refreshResult = await refreshAuthSession();
          persistAuthState(refreshResult);
          // Retry original request with refreshed token
          const retryResponse = await fetch(`${apiBaseUrl}${path}`, {
            ...init,
            headers: buildHeaders(),
            credentials: 'include',
          });
          if (retryResponse.ok) {
            return retryResponse.json() as Promise<T>;
          }
          const retryText = await retryResponse.text();
          let retryDetail = '';
          if (retryText) {
            try {
              const payload = JSON.parse(retryText) as { detail?: unknown; message?: unknown };
              if (typeof payload.detail === 'string' && payload.detail.trim()) {
                retryDetail = payload.detail.trim();
              } else if (typeof payload.message === 'string' && payload.message.trim()) {
                retryDetail = payload.message.trim();
              }
            } catch {
              retryDetail = retryText.trim();
            }
          }
          if (retryDetail) detail = retryDetail;
        } catch {
          // Token refresh failed, fall through to clearAuthState + throw
        }
        clearAuthState();
      }
      throw new Error(detail ? `API 请求失败（${response.status}）：${detail}` : `API 请求失败：${response.status}`);
    }
    return response.json() as Promise<T>;
  } catch (error: unknown) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new Error('API 请求超时，请检查网络连接或服务状态');
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function getHealth(): Promise<HealthPayload> {
  return fetchJson<HealthPayload>('/api/health', undefined, true);
}

export async function getEdition(): Promise<EditionCapabilityPayload> {
  return fetchJson<EditionCapabilityPayload>('/api/edition', undefined, true);
}

export async function getAuthConfig(): Promise<AuthConfigPayload> {
  return fetchJson<AuthConfigPayload>('/api/auth/config', undefined, true);
}

export async function getAuthProviders(): Promise<AuthProvidersPayload> {
  return fetchJson<AuthProvidersPayload>('/api/auth/providers', undefined, true);
}

export async function getCurrentUser(): Promise<AuthSessionPayload> {
  return fetchJson<AuthSessionPayload>('/api/auth/me', undefined, true);
}

export async function passwordLogin(payload: {
  username: string;
  password: string;
}): Promise<AuthSessionPayload> {
  return fetchJson<AuthSessionPayload>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify(payload),
  }, true);
}

export async function refreshAuthSession(): Promise<AuthSessionPayload> {
  return fetchJson<AuthSessionPayload>('/api/auth/refresh', {
    method: 'POST',
    body: JSON.stringify({ refresh_token: getRefreshToken() }),
  }, true);
}

export async function logoutAuth(): Promise<AuthSessionPayload> {
  return fetchJson<AuthSessionPayload>('/api/auth/logout', {
    method: 'POST',
    body: JSON.stringify({ refresh_token: getRefreshToken() }),
  }, true);
}

export async function getDashboard(): Promise<DashboardPayload> {
  return fetchJson<DashboardPayload>('/api/dashboard');
}

export async function getProjects(): Promise<ProjectsPayload> {
  return fetchJson<ProjectsPayload>('/api/projects');
}

export async function getCreatorWorkspace(projectId?: string): Promise<CreatorWorkspacePayload> {
  const search = projectId ? `?project_id=${encodeURIComponent(projectId)}` : '';
  return fetchJson<CreatorWorkspacePayload>(`/api/creator/workspace${search}`);
}

export async function getCreatorRuns(projectId?: string, limit = 10): Promise<ListPayload<CreatorRunRecord>> {
  const params = new URLSearchParams();
  if (projectId) {
    params.set('project_id', projectId);
  }
  params.set('limit', String(limit));
  return fetchJson<ListPayload<CreatorRunRecord>>(`/api/creator/runs?${params.toString()}`);
}

export async function createCreatorProject(payload: {
  project_name: string;
  genre?: string;
  style_profile?: string;
  project_id?: string;
  logline?: string;
  protagonist_name?: string;
  target_audience?: string;
  tone?: string;
  season_hook?: string;
  episode_target_count?: number;
}): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>('/api/creator/projects', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function saveCreatorProjectProfile(payload: {
  project_id?: string;
  project_name: string;
  genre: string;
  style_profile: string;
  logline?: string;
  protagonist_name?: string;
  target_audience?: string;
  tone?: string;
  season_hook?: string;
  episode_target_count?: number;
  target_platforms?: string[];
  expected_project_manifest_revision_id?: string;
  expected_season_manifest_revision_id?: string;
}): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>('/api/creator/project-profile', {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function saveCreatorEpisode(payload: {
  project_id?: string;
  episode_code: string;
  title: string;
  status?: string;
  publish_title?: string;
  cover_text?: string;
  creator_goal?: string;
  ending_hook?: string;
  expected_episode_manifest_revision_id?: string;
}): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>('/api/creator/episodes', {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export async function saveCreatorShot(payload: {
  project_id?: string;
  episode_code: string;
  shot_id: string;
  duration?: number;
  scene?: string;
  characters?: string[];
  visual?: string;
  action?: string;
  dialogue?: string;
  emotion?: string;
  camera?: string;
  ai_video?: boolean;
  priority?: string;
  expected_episode_manifest_revision_id?: string;
}): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>('/api/creator/shots', {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export async function deleteCreatorShot(payload: {
  project_id?: string;
  episode_code: string;
  shot_id: string;
  expected_episode_manifest_revision_id?: string;
}): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>('/api/creator/shots/delete', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function runCreatorAction(payload: {
  project_id?: string;
  action: string;
  episode_code?: string;
}): Promise<CreatorActionRunResult> {
  return fetchJson<CreatorActionRunResult>('/api/creator/actions/run', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function buildCreatorAssetUrl(projectId: string, relativePath: string): string {
  return `${apiBaseUrl}/api/creator/assets?project_id=${encodeURIComponent(projectId)}&path=${encodeURIComponent(relativePath)}`;
}

export async function getCreatorSampleReview(projectId?: string, episodeCode = 'E01'): Promise<CreatorSampleReviewPayload> {
  const params = new URLSearchParams();
  if (projectId) {
    params.set('project_id', projectId);
  }
  params.set('episode_code', episodeCode);
  return fetchJson<CreatorSampleReviewPayload>(`/api/creator/sample-review?${params.toString()}`);
}

export async function saveCreatorSampleReview(payload: {
  project_id?: string;
  episode_code: string;
  review_status: string;
  decision_summary?: string;
  review_notes?: string;
  issues?: Array<Record<string, unknown>>;
}): Promise<CreatorSampleReviewPayload> {
  return fetchJson<CreatorSampleReviewPayload>('/api/creator/sample-review', {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export async function getEpisodes(): Promise<ListPayload<EpisodeRecord>> {
  return fetchJson<ListPayload<EpisodeRecord>>('/api/episodes');
}

export async function getJobs(params?: Record<string, string>): Promise<ListPayload<JobRecord>> {
  const search = new URLSearchParams(params ?? {}).toString();
  const path = search ? `/api/jobs?${search}` : '/api/jobs';
  return fetchJson<ListPayload<JobRecord>>(path);
}

export async function getBatches(): Promise<BatchesPayload> {
  return fetchJson<BatchesPayload>('/api/batches');
}

export async function getBatchSummary(): Promise<BatchesPayload> {
  return fetchJson<BatchesPayload>('/api/batches/summary');
}

export async function getBatchRetryHistoryPage(page = 1, pageSize = 10): Promise<BatchRetryHistoryPayload> {
  return fetchJson<BatchRetryHistoryPayload>(`/api/batches/retry-history?page=${page}&page_size=${pageSize}`);
}

export async function getBatchExecutionPreviewHistoryPage(
  page = 1,
  pageSize = 10,
): Promise<BatchExecutionPreviewHistoryPayload> {
  return fetchJson<BatchExecutionPreviewHistoryPayload>(`/api/batches/execution-previews?page=${page}&page_size=${pageSize}`);
}

export async function getBatchExecutionQueueHistoryPage(
  page = 1,
  pageSize = 10,
): Promise<BatchExecutionQueueHistoryPayload> {
  return fetchJson<BatchExecutionQueueHistoryPayload>(`/api/batches/execution-queue?page=${page}&page_size=${pageSize}`);
}

export async function generateBatchRetryPackage(payload: {
  statuses?: string[];
  episode_code?: string;
  provider?: string;
  dry_run?: boolean;
}): Promise<BatchRetryGenerateResult> {
  return fetchJson<BatchRetryGenerateResult>('/api/batches/retry', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function previewBatchExecutionPlan(payload: {
  plan_key: string;
  target?: string;
  mode?: string;
}): Promise<BatchExecutionPlanPreviewResult> {
  return fetchJson<BatchExecutionPlanPreviewResult>('/api/batches/execution-plans/preview', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function queueBatchExecutionPlan(payload: {
  plan_key: string;
  target?: string;
  mode?: string;
}): Promise<BatchExecutionPlanQueueResult> {
  return fetchJson<BatchExecutionPlanQueueResult>('/api/batches/execution-plans/queue', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateBatchExecutionQueueStatus(payload: {
  queue_run_id: string;
  queue_status: string;
  execution_status: string;
  result_note?: string;
}): Promise<BatchExecutionQueueStatusResult> {
  return fetchJson<BatchExecutionQueueStatusResult>('/api/batches/execution-plans/queue/status', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function exportBatchExecutionOperationsReport(payload: {
  export_format?: string;
  export_scope?: string;
}): Promise<BatchExecutionOperationsExportResult> {
  return fetchJson<BatchExecutionOperationsExportResult>('/api/batches/execution-operations/export', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getBatchExecutionArchives(limit = 20): Promise<BatchExecutionOperationsArchivesPayload> {
  return fetchJson<BatchExecutionOperationsArchivesPayload>(`/api/batches/execution-archives?limit=${limit}`);
}

export async function cleanupBatchExecutionArchives(payload: {
  retention_days?: number;
  dry_run?: boolean;
}): Promise<BatchExecutionOperationsArchiveCleanupResult> {
  return fetchJson<BatchExecutionOperationsArchiveCleanupResult>('/api/batches/execution-archives/cleanup', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getProviderExecutions(): Promise<ListPayload<ProviderExecutionRecord>> {
  return fetchJson<ListPayload<ProviderExecutionRecord>>('/api/providers/executions');
}

export async function getReviewMetrics(): Promise<ReviewMetricsPayload> {
  return fetchJson<ReviewMetricsPayload>('/api/review-metrics');
}
