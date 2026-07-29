import axios from 'axios'

const api = axios.create({
  baseURL: '',
  headers: { 'Content-Type': 'application/json' },
})

// JWT 拦截器
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  },
)

/* ── Auth ── */
export const auth = {
  login: (data) => api.post('/api/auth/login', data),
  register: (data) => api.post('/api/auth/register', data),
}

/* ── Projects ── */
export const projects = {
  list: () => api.get('/api/projects'),
  get: (id) => api.get(`/api/projects/${id}`),
  create: (data) => api.post('/api/projects', data),
  delete: (id) => api.delete(`/api/projects/${id}`),
}

/* ── Episodes ── */
export const episodes = {
  list: (projectId) => api.get(`/api/projects/${projectId}/episodes`),
  get: (id) => api.get(`/api/episodes/${id}`),
  generate: (projectId) => api.post(`/api/projects/${projectId}/generate`),
}

/* ── Graph ── */
export const graph = {
  list: () => api.get('/api/graph'),
  get: (gid) => api.get(`/api/graph/${gid}`),
  create: (data) => api.post('/api/graph', data),
  run: (gid) => api.post(`/api/graph/${gid}/run`),
  nodes: (gid) => api.get(`/api/graph/${gid}/nodes/status`),
}

export default api
