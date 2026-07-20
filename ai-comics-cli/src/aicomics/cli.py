"""AIComics CLI — 命令行漫画短视频生成工具.

Commands:
  render <prompt>    用 ComfyUI 根据提示词生成单张漫画图
  batch <file>       从文本文件中批量读取提示词并逐条生成
  video              将生成图片合成短视频
  serve              ComfyUI 服务管理 (start/stop/status)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import click

# ---------------------------------------------------------------------------
# Default paths
# ---------------------------------------------------------------------------

DEFAULT_COMFYUI_URL = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")
DEFAULT_OUTPUT_DIR = Path(os.environ.get("AICOMICS_OUTPUT_DIR", str(Path.cwd() / "aicomics_output")))

WORKFLOW_REGISTRY: dict[str, dict] = {}
"""Holds loaded workflow JSONs keyed by name."""


# ---------------------------------------------------------------------------
# ComfyUI API helpers
# ---------------------------------------------------------------------------

def _api_get(endpoint: str, base_url: str) -> dict[str, Any]:
    """GET from ComfyUI."""
    import httpx
    url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"
    with httpx.Client() as client:
        resp = client.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json()


def _api_post(endpoint: str, payload: dict, base_url: str) -> dict[str, Any]:
    """POST to ComfyUI."""
    import httpx
    url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"
    with httpx.Client() as client:
        resp = client.post(url, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _upload_image(image_path: Path, base_url: str) -> dict[str, str]:
    """Upload an image file to ComfyUI's input folder via /upload/image."""
    import httpx
    url = f"{base_url.rstrip('/')}/upload/image"
    with open(image_path, "rb") as f:
        files = {"image": (image_path.name, f, "image/png")}
        resp = httpx.post(url, files=files, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _get_history(prompt_id: str, base_url: str) -> dict[str, Any] | None:
    """Poll /history until the prompt_id appears."""
    import httpx
    url = f"{base_url.rstrip('/')}/history/{prompt_id}"
    for attempt in range(120):
        try:
            resp = httpx.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if prompt_id in data:
                    return data[prompt_id]
        except Exception:
            pass
        time.sleep(2)
    return None


def _queue_prompt(workflow: dict, base_url: str) -> str:
    """Queue a workflow in ComfyUI. Returns prompt_id."""
    payload = {"prompt": workflow}
    result = _api_post("prompt", payload, base_url)
    return result["prompt_id"]


def _extract_output_images(
    history: dict,
    workflow: dict,
    output_dir: Path,
) -> list[Path]:
    """Extract generated images from a completed ComfyUI history entry."""
    from pathlib import Path as _Path

    node_outputs = history.get("outputs", {})
    saved: list[Path] = []
    for node_id, node_data in node_outputs.items():
        images = node_data.get("images", [])
        for img in images:
            filename = img.get("filename", "")
            subfolder = img.get("subfolder", "")
            image_path = _Path(subfolder) / filename if subfolder else _Path(filename)
            saved.append(Path(os.environ.get("COMFYUI_OUTPUT_DIR", str(Path.cwd()))))  # fallback
    return saved


def _resolve_image_outputs(
    history: dict,
    base_url: str,
    output_dir: Path,
) -> list[Path]:
    """Copy generated images from ComfyUI output to our output_dir."""
    import httpx
    node_outputs = history.get("outputs", {})
    saved: list[Path] = []
    output_dir.mkdir(parents=True, exist_ok=True)
    for node_id, node_data in node_outputs.items():
        images = node_data.get("images", [])
        for img in images:
            filename = img.get("filename", "")
            subfolder = img.get("subfolder", "")
            rel_path = f"{subfolder}/{filename}" if subfolder else filename
            download_url = f"{base_url.rstrip('/')}/view?filename={filename}"
            if subfolder:
                download_url += f"&subfolder={subfolder}"
            download_url += "&type=output"
            local_path = output_dir / rel_path
            local_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                r = httpx.get(download_url, timeout=30)
                r.raise_for_status()
                local_path.write_bytes(r.content)
                saved.append(local_path)
                click.echo(f"  ✓ 保存: {local_path}")
            except Exception as e:
                click.echo(f"  ✗ 下载失败 {filename}: {e}", err=True)
    return saved


# ---------------------------------------------------------------------------
# Workflow loading
# ---------------------------------------------------------------------------

def discover_workflows() -> dict[str, Path]:
    """Find all ComfyUI workflow JSON files in default locations."""
    candidates: list[Path] = []

    # Check known locations
    for env_var in ("COMFYUI_WORKFLOW_DIR", "AICOMICS_WORKFLOW_DIR"):
        val = os.environ.get(env_var, "")
        if val:
            p = Path(val)
            if p.is_dir():
                candidates.extend(sorted(p.glob("*.json")))

    # AIComics project templates
    project_templates = Path.home() / "Desktop" / "herness" / "AIComics" / "templates"
    if project_templates.is_dir():
        candidates.extend(sorted(project_templates.glob("*.json")))

    # CWD templates/
    cwd_templates = Path.cwd() / "templates"
    if cwd_templates.is_dir():
        candidates.extend(sorted(cwd_templates.glob("*.json")))

    # Default fallback: look anywhere
    if not candidates:
        for guess in (
            Path.cwd(),
            Path.cwd() / "workflows",
            Path.home() / "Desktop" / "herness" / "AIComics",
        ):
            if guess.is_dir():
                candidates.extend(sorted(guess.glob("**/*.json")))

    result: dict[str, Path] = {}
    for p in candidates:
        name = p.stem.replace("_", "-").replace(" ", "-")
        if name not in result:
            result[name] = p
    return result


def load_workflow(name_or_path: str) -> dict | None:
    """Load a workflow by name or path."""
    # Try as path first
    p = Path(name_or_path)
    if p.exists() and p.suffix == ".json":
        return json.loads(p.read_text(encoding="utf-8"))

    # Try by name in registry
    workflows = discover_workflows()
    if name_or_path in workflows:
        return json.loads(workflows[name_or_path].read_text(encoding="utf-8"))

    # Fuzzy match
    for key, wf_path in workflows.items():
        if name_or_path.lower() in key.lower():
            return json.loads(wf_path.read_text(encoding="utf-8"))

    return None


def inject_prompt(workflow: dict, prompt_text: str) -> dict:
    """Inject a prompt string into a ComfyUI workflow JSON.

    Looks for common CLIPTextEncode nodes by title or class_type.
    """
    modified = json.loads(json.dumps(workflow))  # deep copy
    injected = 0
    for node_id, node in list(modified.items()):
        if not isinstance(node, dict):
            continue
        # By title
        title = node.get("_meta", {}).get("title", "")
        if "positive" in title.lower() or "prompt" in title.lower():
            if "inputs" in node and "text" in node["inputs"]:
                node["inputs"]["text"] = prompt_text
                injected += 1
                continue
        # By class_type
        ct = node.get("class_type", "")
        if ct in ("CLIPTextEncode", "CLIPTextEncodeSD3", "CLIPTextEncodeFLUX"):
            if "inputs" in node and "text" in node["inputs"]:
                node["inputs"]["text"] = prompt_text
                injected += 1

    if injected == 0:
        # Fallback: find any CLIPTextEncode
        for node_id, node in list(modified.items()):
            if isinstance(node, dict):
                ct = node.get("class_type", "")
                if "CLIPTextEncode" in ct:
                    if "inputs" in node and "text" in node["inputs"]:
                        node["inputs"]["text"] = prompt_text
                        injected += 1
                        break

    if injected == 0:
        click.echo("  ⚠ 未能在工作流中找到文本输入节点 (CLIPTextEncode)", err=True)
    else:
        click.echo(f"  ✓ 已注入提示词 ({injected} 节点)")
    return modified


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------


@click.group()
@click.version_option(version="0.1.0", prog_name="aicomics")
def cli():
    """AIComics CLI — 一人公司漫画短视频工厂命令行工具."""
    pass


@cli.command()
@click.argument("prompt")
@click.option("--workflow", "-w", default="default",
              help="ComfyUI 工作流名称或JSON路径 (默认: default)")
@click.option("--comfyui-url", "-u", envvar="COMFYUI_URL",
              default=DEFAULT_COMFYUI_URL, show_default=True,
              help="ComfyUI 服务地址")
@click.option("--output-dir", "-o", type=Path, default=None,
              help="输出目录 (默认: CWD/aicomics_output)")
@click.option("--wait/--no-wait", default=True,
              help="等待生成完成")
def render(prompt: str, workflow: str, comfyui_url: str,
           output_dir: Path | None, wait: bool):
    """用 ComfyUI 根据提示词生成单张漫画图.

    PROMPT 是图片描述词，例如 "一个动漫少女站在樱花树下，日系风格"
    """
    out_dir = output_dir or (DEFAULT_OUTPUT_DIR / "images")
    out_dir.mkdir(parents=True, exist_ok=True)

    click.echo(f"🎨 AIComics Render")
    click.echo(f"  提示词: {prompt}")
    click.echo(f"  ComfyUI: {comfyui_url}")
    click.echo(f"  工作流: {workflow}")
    click.echo(f"  输出目录: {out_dir}")

    # 1. Check ComfyUI is running
    try:
        stats = _api_get("system_stats", comfyui_url)
        click.echo(f"  ✓ ComfyUI 在线 (设备: {stats.get('devices', [{}])[0].get('type', '?')})")
    except Exception as e:
        click.echo(f"  ✗ 无法连接 ComfyUI: {e}", err=True)
        sys.exit(1)

    # 2. Load workflow
    wf = load_workflow(workflow)
    if wf is None:
        click.echo(f"  ✗ 找不到工作流: {workflow}", err=True)
        click.echo(f"  可用工作流:", err=True)
        for name, wf_path in discover_workflows().items():
            click.echo(f"    - {name}  ({wf_path})", err=True)
        sys.exit(1)

    # 3. Inject prompt
    wf = inject_prompt(wf, prompt)

    # 4. Queue & wait
    click.echo("  ⏳ 提交到 ComfyUI ...")
    prompt_id = _queue_prompt(wf, comfyui_url)
    click.echo(f"  ✔ 任务已提交 (ID: {prompt_id})")

    if not wait:
        click.echo(f"  任务 ID: {prompt_id}")
        return

    click.echo("  ⏳ 等待生成完成 ...")
    history = _get_history(prompt_id, comfyui_url)
    if history is None:
        click.echo("  ✗ 生成超时或失败", err=True)
        sys.exit(1)

    click.echo("  ✓ 生成完成!")
    saved = _resolve_image_outputs(history, comfyui_url, out_dir)
    if saved:
        click.echo(f"  📁 共保存 {len(saved)} 张图片到: {out_dir}")
    else:
        click.echo("  ⚠ 未找到输出图片", err=True)

    return saved


@cli.command()
@click.argument("prompts_file", type=click.Path(exists=True, dir_okay=False))
@click.option("--workflow", "-w", default="default",
              help="ComfyUI 工作流名称或JSON路径")
@click.option("--comfyui-url", "-u", envvar="COMFYUI_URL",
              default=DEFAULT_COMFYUI_URL, show_default=True)
@click.option("--output-dir", "-o", type=Path, default=None,
              help="输出目录 (默认: CWD/aicomics_output)")
@click.option("--concurrent", "-c", type=int, default=1,
              help="并行任务数 (默认: 1)")
@click.option("--delay", type=float, default=0,
              help="每批提交间隔秒数")
def batch(prompts_file: str, workflow: str, comfyui_url: str,
          output_dir: Path | None, concurrent: int, delay: float):
    """从文本文件中批量读取提示词并逐条生成.

    PROMPTS_FILE 每行一个提示词，空行和 # 开头的行被忽略.
    """
    out_dir = output_dir or (DEFAULT_OUTPUT_DIR / "batch")
    out_dir.mkdir(parents=True, exist_ok=True)

    # Read prompts
    lines = Path(prompts_file).read_text(encoding="utf-8").splitlines()
    prompts = [l.strip() for l in lines if l.strip() and not l.strip().startswith("#")]
    if not prompts:
        click.echo("  ✗ 文件中没有有效的提示词", err=True)
        sys.exit(1)

    click.echo(f"📦 AIComics Batch — {len(prompts)} 条提示词")
    click.echo(f"  ComfyUI: {comfyui_url}")
    click.echo(f"  工作流: {workflow}")
    click.echo(f"  输出目录: {out_dir}")
    click.echo(f"  并行: {concurrent}, 间隔: {delay}s")

    # Load workflow
    wf = load_workflow(workflow)
    if wf is None:
        click.echo(f"  ✗ 找不到工作流: {workflow}", err=True)
        sys.exit(1)

    # Check ComfyUI
    try:
        _api_get("system_stats", comfyui_url)
    except Exception as e:
        click.echo(f"  ✗ 无法连接 ComfyUI: {e}", err=True)
        sys.exit(1)

    results: list[dict] = []
    total = len(prompts)
    progress = click.progressbar(prompts, label="  🎯 处理中") if len(prompts) > 20 else prompts
    for idx, prompt_text in enumerate(progress if len(prompts) > 20 else prompts):
        if len(prompts) <= 20:
            click.echo(f"\n  [{idx+1}/{total}] {prompt_text[:50]}{'...' if len(prompt_text) > 50 else ''}")

        wf_injected = inject_prompt(json.loads(json.dumps(wf)), prompt_text)

        try:
            prompt_id = _queue_prompt(wf_injected, comfyui_url)
            history = _get_history(prompt_id, comfyui_url)
            if history:
                batch_out = out_dir / f"batch_{idx+1:04d}"
                saved = _resolve_image_outputs(history, comfyui_url, batch_out)
                results.append({"index": idx + 1, "prompt": prompt_text, "status": "ok", "files": [str(s) for s in saved]})
            else:
                results.append({"index": idx + 1, "prompt": prompt_text, "status": "timeout", "files": []})
                click.echo(f"    ✗ 超时")
        except Exception as e:
            results.append({"index": idx + 1, "prompt": prompt_text, "status": "error", "files": [], "error": str(e)})
            click.echo(f"    ✗ 错误: {e}")

        if delay and idx < total - 1:
            time.sleep(delay)

    # Write batch report
    report_path = out_dir / "batch_report.json"
    report_path.write_text(
        json.dumps({"total": total, "succeeded": sum(1 for r in results if r["status"] == "ok"),
                     "results": results}, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    succeeded = sum(1 for r in results if r["status"] == "ok")
    click.echo(f"\n📊 批次完成: {succeeded}/{total} 成功")
    click.echo(f"  报告: {report_path}")


@cli.command()
@click.option("--input-dir", "-i", type=Path, default=None,
              help="图片来源目录 (默认: output/batch 或 output/images)")
@click.option("--output", "-o", type=Path, default=None,
              help="输出视频路径 (默认: output/video/output.mp4)")
@click.option("--fps", type=int, default=24,
              help="帧率 (默认: 24)")
@click.option("--duration", "-d", type=float, default=3.0,
              help="每张图片显示秒数 (默认: 3)")
@click.option("--resolution", "-r", default="1920x1080",
              help="视频分辨率 (默认: 1920x1080)")
@click.option("--with-audio", is_flag=True,
              help="是否添加音频 (需要 FFmpeg)")
def video(input_dir: Path | None, output: Path | None,
          fps: int, duration: float, resolution: str,
          with_audio: bool):
    """将生成图片合成短视频。

    自动查找输出目录中的图片，按文件名排序后合成为视频。
    """
    # Determine input directory
    candidates = [input_dir] if input_dir else []
    if not candidates:
        for p in (DEFAULT_OUTPUT_DIR / "batch", DEFAULT_OUTPUT_DIR / "images"):
            if p.is_dir() and any(p.glob("*.[pP][nN][gG]")) or any(p.glob("*.[jJ][pP][gG]")):
                candidates.append(p)
    if not candidates:
        # Search aicomics_output recursively
        cand = DEFAULT_OUTPUT_DIR
        if cand.is_dir():
            images = sorted(cand.rglob("*.[pP][nN][gG]")) + sorted(cand.rglob("*.[jJ][pP][gG]"))
            if images:
                # Use the common parent
                from collections import Counter
                parents = [str(img.parent) for img in images]
                common_parent = Path(max(set(parents), key=parents.count))
                candidates.append(common_parent)

    images: list[Path] = []
    for cand in candidates:
        if cand and cand.is_dir():
            images.extend(sorted(cand.rglob("*.[pP][nN][gG]")))
            images.extend(sorted(cand.rglob("*.[jJ][pP][gG]")))

    if not images:
        click.echo("  ✗ 未找到图片。请指定 --input-dir", err=True)
        click.echo(f"  搜索路径: {DEFAULT_OUTPUT_DIR}", err=True)
        sys.exit(1)

    output_path = output or (DEFAULT_OUTPUT_DIR / "video" / "output.mp4")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    click.echo(f"🎬 AIComics Video")
    click.echo(f"  图片: {len(images)} 张 ({images[0].parent})")
    click.echo(f"  输出: {output_path}")
    click.echo(f"  每张时长: {duration}s, 帧率: {fps}, 分辨率: {resolution}")

    # Check FFmpeg availability
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=False)
    except FileNotFoundError:
        click.echo("  ✗ 未找到 ffmpeg，请先安装: brew install ffmpeg", err=True)
        sys.exit(1)

    # Build concat file
    concat_file = DEFAULT_OUTPUT_DIR / "video" / "concat.txt"
    concat_file.parent.mkdir(parents=True, exist_ok=True)
    with open(concat_file, "w") as f:
        for img in images:
            f.write(f"file '{img.absolute()}'\n")
            f.write(f"duration {duration}\n")
    # Last frame needs extra entry
    if images:
        f.write(f"file '{images[-1].absolute()}'\n")

    # Build scale filter
    width, height = resolution.split("x") if "x" in resolution else ("1920", "1080")

    if with_audio:
        click.echo("  ⏳ 合成视频 (包含音频)...")
        audio_candidates = list(DEFAULT_OUTPUT_DIR.rglob("*.mp3")) + list(DEFAULT_OUTPUT_DIR.rglob("*.wav"))
        audio_input = ""
        if audio_candidates:
            audio_input = f"-i {audio_candidates[0]}"
            click.echo(f"  音频: {audio_candidates[0]}")
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_file),
            *([] if not audio_input else audio_input.split()),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-vf", f"scale={width}:{height}:force_original_aspect_ratio=1,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
            "-r", str(fps),
            str(output_path),
        ]
    else:
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_file),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-vf", f"scale={width}:{height}:force_original_aspect_ratio=1,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
            "-r", str(fps),
            str(output_path),
        ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        click.echo(f"  ✗ 视频合成失败: {result.stderr[-500:]}", err=True)
        sys.exit(1)

    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    click.echo(f"  ✓ 视频已生成: {output_path} ({file_size_mb:.1f} MB)")


@cli.group()
def serve():
    """ComfyUI 服务管理 (start/stop/status)."""
    pass


@serve.command()
@click.option("--host", default="127.0.0.1", help="监听地址")
@click.option("--port", default=8188, type=int, help="监听端口")
@click.option("--comfyui-dir", type=Path, default=None,
              help="ComfyUI 目录路径 (默认自动查找)")
@click.option("--python", "python_path", default="python",
              help="Python 可执行文件路径")
def start(host: str, port: int, comfyui_dir: Path | None,
          python_path: str):
    """启动 ComfyUI 服务 (后台运行)."""
    # Find ComfyUI directory
    if comfyui_dir is None:
        for guess in (
            Path.cwd() / "ComfyUI",
            Path.home() / "Desktop" / "herness" / "AIComics" / "local_providers" / "comfyui" / "runtime" / "ComfyUI",
            Path.home() / "ComfyUI",
        ):
            if (guess / "main.py").exists():
                comfyui_dir = guess
                break

    if comfyui_dir is None or not (comfyui_dir / "main.py").exists():
        click.echo("  ✗ 找不到 ComfyUI 目录。请指定 --comfyui-dir", err=True)
        sys.exit(1)

    click.echo(f"  ComfyUI 目录: {comfyui_dir}")
    click.echo(f"  启动: {host}:{port}")

    pid_file = DEFAULT_OUTPUT_DIR / "comfyui.pid"
    pid_file.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        python_path,
        "main.py",
        "--listen", host,
        "--port", str(port),
        "--disable-auto-launch",
    ]

    log_file = DEFAULT_OUTPUT_DIR / "comfyui.log"
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=comfyui_dir,
            stdout=open(log_file, "a"),
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        pid_file.write_text(str(proc.pid))
        click.echo(f"  ✓ ComfyUI 已启动 (PID: {proc.pid})")
        click.echo(f"  日志: {log_file}")
    except Exception as e:
        click.echo(f"  ✗ 启动失败: {e}", err=True)
        sys.exit(1)


@serve.command()
def stop():
    """停止 ComfyUI 服务."""
    pid_file = DEFAULT_OUTPUT_DIR / "comfyui.pid"
    if not pid_file.exists():
        click.echo("  ⚠ PID 文件不存在", err=True)
        # Try pkill
        try:
            subprocess.run(["pkill", "-f", "main.py --listen"], check=False)
            click.echo("  → 已尝试 pkill main.py")
        except Exception:
            pass
        return

    pid = int(pid_file.read_text().strip())
    try:
        os.kill(pid, 15)  # SIGTERM
        click.echo(f"  ✓ ComfyUI (PID: {pid}) 已停止")
        pid_file.unlink()
    except ProcessLookupError:
        click.echo(f"  ⚠ 进程 (PID: {pid}) 不存在")
        pid_file.unlink()
    except Exception as e:
        click.echo(f"  ✗ 停止失败: {e}", err=True)


@serve.command()
def status():
    """查看 ComfyUI 服务状态."""
    pid_file = DEFAULT_OUTPUT_DIR / "comfyui.pid"
    if pid_file.exists():
        pid = int(pid_file.read_text().strip())
        try:
            os.kill(pid, 0)
            click.echo(f"  ✓ ComfyUI 运行中 (PID: {pid})")
        except OSError:
            click.echo(f"  ⚠ PID 文件存在但进程已死 (PID: {pid})")
    else:
        click.echo("  ⚠ PID 文件不存在")

    # Probe via API
    try:
        stats = _api_get("system_stats", DEFAULT_COMFYUI_URL)
        click.echo(f"  ✓ API 可达 ({DEFAULT_COMFYUI_URL})")
        devices = stats.get("devices", [])
        if devices:
            click.echo(f"  设备: {devices[0].get('type', '?')} ({devices[0].get('name', '?')})")
    except Exception:
        click.echo(f"  ✗ API 不可达 ({DEFAULT_COMFYUI_URL})")


@cli.command()
@click.option("--comfyui-url", "-u", envvar="COMFYUI_URL",
              default=DEFAULT_COMFYUI_URL, show_default=True)
def check(comfyui_url: str):
    """检查 ComfyUI 连接和可用工作流."""
    click.echo("🔍 AIComics 诊断")
    click.echo(f"  ComfyUI URL: {comfyui_url}")

    try:
        stats = _api_get("system_stats", comfyui_url)
        devices = stats.get("devices", [])
        click.echo(f"  ✓ ComfyUI 在线")
        click.echo(f"  系统: {stats.get('system', {}).get('os', '?')}")
        click.echo(f"  Python: {stats.get('system', {}).get('python_version', '?')}")
        for dev in devices:
            click.echo(f"  设备: {dev.get('type', '?')} — {dev.get('name', '?')}")
    except Exception as e:
        click.echo(f"  ✗ 无法连接: {e}")

    click.echo("")
    click.echo("📂 可用工作流:")
    workflows = discover_workflows()
    if workflows:
        for name, wf_path in workflows.items():
            click.echo(f"    - {name}  ({wf_path})")
    else:
        click.echo("    (未找到工作流文件，可放置 .json 到 ~/Desktop/herness/AIComics/templates/)")

    click.echo("")
    click.echo(f"📁 输出目录: {DEFAULT_OUTPUT_DIR}")
    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    cli()
