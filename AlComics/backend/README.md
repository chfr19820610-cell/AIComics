# AIComics Backend API

## Stack
FastAPI + SQLite(aiosqlite) + python-jose(JWT) + WebSocket

## Auth
- POST /api/auth/register {username, password} → {token, user}
- POST /api/auth/login {username, password} → {token, user}
- GET /api/auth/me → {user}
- JWT Bearer token, 24h expiry, bcrypt password

## Projects
- GET  /api/projects → [{id, title, status, episodes_count, created_at}]
- POST /api/projects {title, script} → {project}
- GET  /api/projects/{id} → {project, episodes: [...]}
- DELETE /api/projects/{id}

## Generate
- POST /api/projects/{id}/generate → {task_id} (异步启动3层Agent管线)
- WS  /api/projects/{id}/ws → 实时进度推送 {stage, progress, message}
- GET /api/projects/{id}/episodes → [{ep_number, status, duration, output_url}]
- GET /api/episodes/{id}/view → 视频文件流

## Data Models
User: id, username, password_hash, created_at
Project: id, user_id, title, script(text), status(pending/generating/done/failed), created_at, updated_at
Episode: id, project_id, ep_number, status(pending/generating/done/failed), output_path, duration, thumbnail

## Code Style
- 单文件 main.py (< 500行)
- FastAPI + APIRouter
- SQLite + aiosqlite 直接SQL(不用ORM)
- bcrypt 密码
- python-jose JWT
- 所有API返回 JSON
