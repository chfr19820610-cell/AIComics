#!/usr/bin/env python3
"""AIComics 执行层 Agent — 极简执行器. 读 tasks/tasklist.json → 调用管线 → outputs/ + execution-log.json"""
import json, os, shutil, subprocess, sys, time, urllib.request, urllib.error
from argparse import ArgumentParser
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TASKS_DIR = ROOT / "tasks"
OUTPUTS_DIR = ROOT / "outputs"
LOG_PATH = TASKS_DIR / "execution-log.json"
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
EDGE_TTS = shutil.which("edge-tts") or "edge-tts"
BLENDER = os.environ.get("BLENDER_BIN", "/Applications/Blender.app/Contents/MacOS/Blender")
COMFY_URL = os.environ.get("COMFY_URL", "http://localhost:8188")
SEEDANCE = {
    "base_url": os.environ.get("SEEDANCE_API", "http://token.yundashi.com/v1"),
    "api_key": os.environ.get("SEEDANCE_API_KEY", ""),
    "model": os.environ.get("SEEDANCE_MODEL", "seedance20"),
    "poll_interval": int(os.environ.get("SEEDANCE_POLL_INTERVAL", "5")),
    "poll_timeout": int(os.environ.get("SEEDANCE_POLL_TIMEOUT", "300")),
}

def log(msg: str, task_id=""):
    tid = str(task_id) if task_id else ""
    print(f"  [{tid}] {msg}" if tid else f"  {msg}", flush=True)

def ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True); return p

def load_tasklist(path: Path) -> list[dict]:
    raw = json.loads(path.read_text())
    return raw if isinstance(raw, list) else raw.get("tasks", raw.get("tasklist", []))

def save_execution_log(results: list[dict]):
    ensure_dir(TASKS_DIR)
    LOG_PATH.write_text(json.dumps({"executed_at": datetime.now(timezone.utc).isoformat(),
        "total": len(results), "completed": sum(1 for r in results if r["status"]=="completed"),
        "failed": sum(1 for r in results if r["status"]=="failed"),
        "skipped": sum(1 for r in results if r["status"]=="skipped"),
        "results": results}, indent=2, ensure_ascii=False))

def make_result(task: dict, status: str, output_path: str="", error: str="", elapsed: float=0):
    return {"task_id": task.get("id", task.get("task_id", "")), "type": task.get("type", ""),
        "status": status, "output": output_path, "error": error,
        "elapsed_sec": round(elapsed, 2), "executed_at": datetime.now(timezone.utc).isoformat()}

def comfyui_submit(workflow: dict, timeout: int=60):
    req = urllib.request.Request(f"{COMFY_URL}/prompt",
        data=json.dumps({"prompt": workflow}).encode(), headers={"Content-Type": "application/json"})
    pid = json.loads(urllib.request.urlopen(req, timeout=timeout).read())["prompt_id"]
    deadline = time.time() + 300
    while time.time() < deadline:
        time.sleep(3)
        try:
            req = urllib.request.Request(f"{COMFY_URL}/history/{pid}")
            hist = json.loads(urllib.request.urlopen(req, timeout=10).read()).get(pid, {})
            s = hist.get("status", {}).get("status_str", "")
            if s == "success": return pid, hist
            if s == "error": raise RuntimeError(f"ComfyUI: {hist.get('error',{}).get('exception_message','?')}")
        except urllib.error.HTTPError: continue
    raise TimeoutError(f"ComfyUI timeout {pid}")

def find_comfyui_output(prefix: str):
    comfy_dirs = os.environ.get("COMFY_OUTPUT_DIRS", "")
    if comfy_dirs:
        bases = [p.strip() for p in comfy_dirs.split(":")]
    else:
        bases = [
            "~/Documents/comfy/ComfyUI/output",
            "~/Desktop/comfy/ComfyUI/output",
            "/workspace/comfy-output"
        ]
    for base in bases:
        candidates = sorted(Path(os.path.expanduser(base)).glob(f"{prefix}*"), key=os.path.getmtime, reverse=True)
        if candidates: return str(candidates[0])

def seedance_call(prompt: str, output_path: Path, duration: int=5, size: str="1080x1920"):
    if not SEEDANCE["api_key"]: return False
    headers = {"Authorization": f"Bearer {SEEDANCE['api_key']}", "Content-Type": "application/json"}
    body = json.dumps({"model": SEEDANCE["model"], "prompt": prompt, "duration": duration, "size": size}).encode()
    try:
        resp = json.loads(urllib.request.urlopen(urllib.request.Request(
            f"{SEEDANCE['base_url']}/video/generations", data=body, headers=headers, method="POST"), timeout=30).read())
    except: return False
    gen_id = resp.get("task_id") or resp.get("id") or resp.get("generation_id", "")
    if not gen_id: return False
    deadline = time.time() + SEEDANCE["poll_timeout"]
    while time.time() < deadline:
        time.sleep(SEEDANCE["poll_interval"])
        try:
            req = urllib.request.Request(f"{SEEDANCE['base_url']}/video/generations/{gen_id}", headers=headers)
            data = json.loads(urllib.request.urlopen(req, timeout=10).read())
            s = data.get("status", "").upper()
            if s in ("COMPLETED", "SUCCESS"):
                url = data.get("video_url") or data.get("url", "")
                if url: ensure_dir(output_path.parent); output_path.write_bytes(urllib.request.urlopen(url, timeout=120).read()); return True
            elif s in ("FAILED", "ERROR"): return False
        except: return False
    return False

def execute_image(task: dict, dry_run: bool):
    prompt = task.get("prompt", ""); output_name = task.get("output", f"img_{int(time.time())}.png")
    output_path = OUTPUTS_DIR / output_name; seed = task.get("seed", int(time.time()) % 1000000)
    if output_path.exists(): return make_result(task, "skipped", str(output_path))
    if dry_run: log(f"[dry-run] img: {prompt[:60]}... → {output_name}", task.get("id")); return make_result(task, "dry_run", str(output_path))
    t0 = time.time()
    try:
        model = task.get("model", "animagine-xl-4.0-opt.safetensors")
        neg = task.get("negative_prompt", "nsfw, lowres, bad anatomy, bad hands, text, worst quality")
        w, h = task.get("width", 1024), task.get("height", 1536)
        prefix = task.get("prefix", "aicomics_gen")
        workflow = {
            "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": model}},
            "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
            "3": {"class_type": "CLIPTextEncode", "inputs": {"text": neg, "clip": ["1", 1]}},
            "4": {"class_type": "EmptyLatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}},
            "5": {"class_type": "KSampler", "inputs": {"seed": seed, "steps": task.get("steps", 25), "cfg": task.get("cfg", 7),
                "sampler_name": "euler", "scheduler": "normal", "denoise": 1, "model": ["1", 0],
                "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0]}},
            "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
            "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": prefix}},
        }
        if "workflow" in task:
            for k, v in task["workflow"].items(): workflow[k] = v
        comfyui_submit(workflow)
        src = find_comfyui_output(prefix)
        if src: ensure_dir(output_path.parent); shutil.copy2(src, output_path); return make_result(task, "completed", str(output_path), elapsed=time.time()-t0)
        raise RuntimeError(f"Output not found: {prefix}")
    except Exception as e: return make_result(task, "failed", error=str(e), elapsed=time.time()-t0)

def execute_video(task: dict, dry_run: bool):
    prompt = task.get("prompt", ""); output_name = task.get("output", f"vid_{int(time.time())}.mp4")
    output_path = OUTPUTS_DIR / output_name
    if output_path.exists(): return make_result(task, "skipped", str(output_path))
    if dry_run: log(f"[dry-run] vid: {prompt[:60]}... → {output_name}", task.get("id")); return make_result(task, "dry_run", str(output_path))
    t0 = time.time()
    ok = seedance_call(prompt, output_path, task.get("duration_sec", 5), task.get("size", "1080x1920"))
    return make_result(task, "completed" if ok else "failed", str(output_path) if ok else "", elapsed=time.time()-t0)

def execute_tts(task: dict, dry_run: bool):
    text = task.get("text", task.get("narration", "")); output_name = task.get("output", f"tts_{int(time.time())}.mp3")
    output_path = OUTPUTS_DIR / output_name
    if output_path.exists(): return make_result(task, "skipped", str(output_path))
    if dry_run: log(f"[dry-run] tts: {text[:60]}... → {output_name}", task.get("id")); return make_result(task, "dry_run", str(output_path))
    t0 = time.time()
    try:
        ensure_dir(output_path.parent)
        env = os.environ.copy()
        for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
            env.pop(k, None)
        subprocess.run([EDGE_TTS, "--voice", task.get("voice", "zh-CN-XiaoxiaoNeural"), "--text", text, "--write-media", str(output_path)],
            capture_output=True, text=True, timeout=120, env=env)
        if output_path.exists() and output_path.stat().st_size > 0: return make_result(task, "completed", str(output_path), elapsed=time.time()-t0)
        raise RuntimeError("edge-tts empty")
    except Exception as e: return make_result(task, "failed", error=str(e), elapsed=time.time()-t0)

def execute_render_3d(task: dict, dry_run: bool):
    fbx = task.get("fbx", ""); output_name = task.get("output", f"render_{int(time.time())}")
    output_dir = OUTPUTS_DIR / output_name
    if not dry_run and (not fbx or not Path(fbx).exists()): return make_result(task, "failed", error=f"FBX missing: {fbx}")
    if dry_run: log(f"[dry-run] 3d: {fbx} → {output_name}", task.get("id")); return make_result(task, "dry_run", str(output_dir))
    t0 = time.time()
    try:
        ensure_dir(output_dir)
        script = ROOT / "render_shot.py"
        cmd = [BLENDER, "--background", "--python", str(script), "--",
            "--fbx", fbx, "--output", str(output_dir),
            "--shot-type", task.get("shot_type", "MS"),
            "--camera", task.get("camera", "static"),
            "--duration", str(task.get("duration_sec", 5)),
            "--fps", str(task.get("fps", 24)),
            "--lighting", task.get("lighting", "cinematic_noir"),
            "--resolution", task.get("resolution", "1080x1920")]
        if task.get("env_fbx"): cmd += ["--env-fbx", task["env_fbx"]]
        subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        frames = list(output_dir.glob("*.png"))
        if frames: return make_result(task, "completed", str(output_dir), elapsed=time.time()-t0)
        raise RuntimeError("No frames rendered")
    except Exception as e: return make_result(task, "failed", error=str(e), elapsed=time.time()-t0)

def execute_compose_scene(task: dict, dry_run: bool):
    inputs = task.get("inputs", task.get("sources", [])); output_name = task.get("output", f"scene_{int(time.time())}.mp4")
    output_path = OUTPUTS_DIR / output_name
    if output_path.exists(): return make_result(task, "skipped", str(output_path))
    if dry_run: log(f"[dry-run] compose: {len(inputs)} inputs → {output_name}", task.get("id")); return make_result(task, "dry_run", str(output_path))
    t0 = time.time()
    try:
        ensure_dir(output_path.parent); tmp_dir = OUTPUTS_DIR / f".tmp_{int(time.time())}"; ensure_dir(tmp_dir); clips = []
        for i, src in enumerate(inputs):
            img = src.get("image", ""); audio = src.get("audio", ""); dur = src.get("duration_sec", 5)
            if not img or not Path(img).exists(): continue
            clip = tmp_dir / f"c{i:03d}.mp4"
            cmd = [FFMPEG, "-y", "-loop", "1", "-i", img, "-c:v", "libx264", "-t", str(dur), "-pix_fmt", "yuv420p",
                "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2"]
            if audio and Path(audio).exists(): cmd += ["-i", audio, "-c:a", "aac", "-shortest"]
            else: cmd += ["-an"]
            cmd += [str(clip)]
            subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if clip.exists(): clips.append(str(clip))
        if not clips: raise RuntimeError("No clips produced")
        (tmp_dir/"concat.txt").write_text("\n".join(f"file '{p}'" for p in clips))
        subprocess.run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(tmp_dir/"concat.txt"),
            "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k", str(output_path)], capture_output=True, text=True, timeout=300)
        shutil.rmtree(tmp_dir, ignore_errors=True)
        if output_path.exists(): return make_result(task, "completed", str(output_path), elapsed=time.time()-t0)
        raise RuntimeError("Composition failed")
    except Exception as e: return make_result(task, "failed", error=str(e), elapsed=time.time()-t0)

EXECUTORS = {"generate_image": execute_image, "generate_video": execute_video,
    "generate_tts": execute_tts, "render_3d": execute_render_3d, "compose_scene": execute_compose_scene}

def main():
    ap = ArgumentParser(description="AIComics 执行层 Agent")
    ap.add_argument("--tasks", default=str(TASKS_DIR / "tasklist.json"), help="Tasklist JSON path")
    ap.add_argument("--output-dir", default=str(OUTPUTS_DIR), help="Output artifacts directory")
    ap.add_argument("--log", default=str(LOG_PATH), help="Execution log JSON path")
    ap.add_argument("--dry-run", action="store_true", help="Print without executing")
    args = ap.parse_args()
    tasks_path = Path(args.tasks)
    if not tasks_path.exists(): print(f"❌ Not found: {tasks_path}", flush=True); sys.exit(1)
    tasklist = load_tasklist(tasks_path)
    # Apply CLI overrides to module paths
    if args.output_dir != str(OUTPUTS_DIR):
        globals()["OUTPUTS_DIR"] = Path(args.output_dir)
    if args.log != str(LOG_PATH):
        globals()["LOG_PATH"] = Path(args.log)
    ensure_dir(OUTPUTS_DIR); results = []
    print(f"\n{'='*60}\n  AIComics 执行层 Agent\n  Tasks: {len(tasklist)} | Dry-run: {args.dry_run}\n{'='*60}\n", flush=True)
    for idx, task in enumerate(tasklist, 1):
        task_type = task.get("type", ""); task_id = task.get("id", task.get("task_id", f"task_{idx}"))
        runner = EXECUTORS.get(task_type)
        if not runner:
            results.append(make_result(task, "skipped", error=f"Unknown type: {task_type}"))
            log(f"⏭️ [{task_type}] skipped — unknown type", task_id); continue
        result = runner(task, args.dry_run); results.append(result)
        icon = {"completed":"✅","failed":"❌","skipped":"⏭️","dry_run":"🔍"}.get(result["status"],"❓")
        log(f"{icon} [{task_type}] {result['status']} ({result['elapsed_sec']:.1f}s)" + (f" — {result.get('error','')}" if result.get("error") else ""), task_id)
    c = sum(1 for r in results if r["status"]=="completed")
    f = sum(1 for r in results if r["status"]=="failed")
    save_execution_log(results)
    print(f"\n{'='*60}\n  ✅ {c} completed | ❌ {f} failed | 📝 {len(results)} total\n  Log: {LOG_PATH}\n{'='*60}\n", flush=True)
    return 1 if f > 0 else 0

if __name__ == "__main__":
    sys.exit(main())
