"""
AIComics v2.0 — Backend API
FastAPI + SQLite + JWT + WebSocket
"""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiosqlite
import bcrypt
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from jose import JWTError, jwt
from pydantic import BaseModel

# ── Config ────────────────────────────────────────
DB_PATH = Path(os.getenv("AICOMICS_DB", "/app/data/aicomics.db"))
DATA_DIR = Path(os.getenv("AICOMICS_DATA", "/app/data"))
_raw_secret = os.getenv("AICOMICS_JWT_SECRET")
if not _raw_secret:
    raise RuntimeError("AICOMICS_JWT_SECRET environment variable is required")
SECRET_KEY: str = _raw_secret
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

# Ensure data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="AIComics API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("AICOMICS_CORS_ORIGINS", "http://localhost:8080").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Database Init ─────────────────────────────────
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                script TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS episodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                ep_number INTEGER NOT NULL,
                status TEXT DEFAULT 'pending',
                output_path TEXT DEFAULT '',
                duration REAL DEFAULT 0,
                thumbnail TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (project_id) REFERENCES projects(id)
            );
        """)
        await db.commit()

# ── Auth ──────────────────────────────────────────
class UserCreate(BaseModel):
    username: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    token: str
    user: dict

def create_token(user_id: int, username: str) -> str:
    payload = {
        "sub": str(user_id),
        "username": username,
        "exp": datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    """Decode and validate a JWT token. Returns user dict or raises HTTPException."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {"id": int(payload["sub"]), "username": payload["username"]}
    except JWTError:
        raise HTTPException(401, "Invalid or expired token")

async def get_current_user_from_header(authorization: str = "") -> dict:
    """Dependency: extract user from Authorization header value."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid token")
    return decode_token(authorization[7:])

async def get_current_user(request: Request) -> dict:
    """Dependency: extract user from Request object. Use this in routes."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid token")
    return decode_token(auth[7:])

@app.post("/api/auth/register", response_model=TokenResponse)
async def register(body: UserCreate):
    if not body.username or not body.password:
        raise HTTPException(400, "username and password required")
    if len(body.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    pw_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            cur = await db.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (body.username, pw_hash))
            await db.commit()
            user_id = cur.lastrowid
        except sqlite3.IntegrityError:
            raise HTTPException(409, "Username already exists")
    token = create_token(user_id, body.username)
    return {"token": token, "user": {"id": user_id, "username": body.username}}

@app.post("/api/auth/login", response_model=TokenResponse)
async def login(body: UserLogin):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE username = ?", (body.username,))
        user = await cur.fetchone()
    if not user or not bcrypt.checkpw(body.password.encode(), user["password_hash"].encode()):
        raise HTTPException(401, "Invalid credentials")
    token = create_token(user["id"], user["username"])
    return {"token": token, "user": {"id": user["id"], "username": user["username"]}}

# ── Projects ──────────────────────────────────────
class ProjectCreate(BaseModel):
    title: str
    script: str = ""

@app.get("/api/projects")
async def list_projects(user: dict = Depends(get_current_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT p.*, (SELECT COUNT(*) FROM episodes e WHERE e.project_id = p.id) as episodes_count "
            "FROM projects p WHERE p.user_id = ? ORDER BY p.created_at DESC",
            (user["id"],)
        )
        rows = await cur.fetchall()
    return [dict(r) for r in rows]

@app.post("/api/projects")
async def create_project(body: ProjectCreate, user: dict = Depends(get_current_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "INSERT INTO projects (user_id, title, script) VALUES (?, ?, ?)",
            (user["id"], body.title, body.script)
        )
        await db.commit()
        project_id = cur.lastrowid
        cur2 = await db.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        row = await cur2.fetchone()
    return dict(row)

@app.get("/api/projects/{project_id}")
async def get_project(project_id: int, user: dict = Depends(get_current_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM projects WHERE id = ? AND user_id = ?",
            (project_id, user["id"])
        )
        proj = await cur.fetchone()
        if not proj:
            raise HTTPException(404, "Project not found")
        cur2 = await db.execute(
            "SELECT * FROM episodes WHERE project_id = ? ORDER BY ep_number",
            (project_id,)
        )
        episodes = await cur2.fetchall()
    return {**dict(proj), "episodes": [dict(e) for e in episodes]}

@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: int, user: dict = Depends(get_current_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id FROM projects WHERE id = ? AND user_id = ?", (project_id, user["id"]))
        if not await cur.fetchone():
            raise HTTPException(404, "Project not found")
        await db.execute("DELETE FROM episodes WHERE project_id = ?", (project_id,))
        await db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        await db.commit()
    return {"ok": True}

# ── Generate ──────────────────────────────────────
@app.post("/api/projects/{project_id}/generate")
async def generate_project(project_id: int, user: dict = Depends(get_current_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT * FROM projects WHERE id = ? AND user_id = ?", (project_id, user["id"]))
        proj = await cur.fetchone()
        if not proj:
            raise HTTPException(404, "Project not found")
        await db.execute("UPDATE projects SET status = 'generating', updated_at = datetime('now') WHERE id = ?", (project_id,))
        await db.commit()
    task_id = str(uuid.uuid4())
    # Launch async generation (placeholder — real pipeline connects to 3-layer agents)
    asyncio.create_task(_run_generation(project_id, task_id))
    return {"task_id": task_id}

async def _run_generation(project_id: int, task_id: str):
    """Async placeholder: creates episodes with progress simulation + WebSocket push."""
    await asyncio.sleep(2)
    async with aiosqlite.connect(DB_PATH) as db:
        for ep in range(1, 13):
            await db.execute(
                "INSERT INTO episodes (project_id, ep_number, status) VALUES (?, ?, 'generating')",
                (project_id, ep)
            )
            await db.commit()
            # Push progress via WebSocket
            progress_msg = json.dumps({
                "type": "progress",
                "payload": {"percent": int(ep / 12 * 100), "message": f"生成第{ep}集..."}
            })
            if project_id in active_connections:
                dead = []
                for ws in active_connections[project_id]:
                    try:
                        await ws.send_text(progress_msg)
                    except Exception:
                        dead.append(ws)
                for ws in dead:
                    active_connections[project_id].remove(ws)
            await asyncio.sleep(3)
            await db.execute(
                "UPDATE episodes SET status = 'done' WHERE project_id = ? AND ep_number = ?",
                (project_id, ep)
            )
            await db.commit()
        await db.execute("UPDATE projects SET status = 'done', updated_at = datetime('now') WHERE id = ?", (project_id,))
        await db.commit()
        # Push completion
        complete_msg = json.dumps({"type": "complete", "payload": {}})
        if project_id in active_connections:
            for ws in active_connections[project_id]:
                try:
                    await ws.send_text(complete_msg)
                except Exception:
                    pass

# ── Episodes ──────────────────────────────────────
@app.get("/api/projects/{project_id}/episodes")
async def list_episodes(project_id: int, user: dict = Depends(get_current_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT e.* FROM episodes e JOIN projects p ON p.id = e.project_id "
            "WHERE e.project_id = ? AND p.user_id = ? ORDER BY e.ep_number",
            (project_id, user["id"])
        )
        rows = await cur.fetchall()
    return [dict(r) for r in rows]

@app.get("/api/episodes/{episode_id}/view")
async def view_episode(episode_id: int, user: dict = Depends(get_current_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT e.* FROM episodes e JOIN projects p ON p.id = e.project_id "
            "WHERE e.id = ? AND p.user_id = ?",
            (episode_id, user["id"])
        )
        ep = await cur.fetchone()
    if not ep or not ep["output_path"]:
        raise HTTPException(404, "Episode not found or no output")
    path = Path(ep["output_path"])
    if not path.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(str(path), media_type="video/mp4")

# ── WebSocket ─────────────────────────────────────
active_connections: dict[int, list[WebSocket]] = {}

@app.websocket("/api/projects/{project_id}/ws")
async def project_ws(websocket: WebSocket, project_id: int):
    await websocket.accept()
    if project_id not in active_connections:
        active_connections[project_id] = []
    active_connections[project_id].append(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep alive
    except WebSocketDisconnect:
        if project_id in active_connections:
            try:
                active_connections[project_id].remove(websocket)
            except ValueError:
                pass

# ── Startup ───────────────────────────────────────
@app.on_event("startup")
async def startup():
    await init_db()

@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "2.0"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("BACKEND_PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False, log_level="info")
