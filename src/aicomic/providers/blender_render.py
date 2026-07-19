"""
BlenderRenderProvider — 3D 场景渲染 Provider
============================================

通过 subprocess 调用 Blender 的 Python API (bpy) 实现本地 3D 三渲二渲染。
支持 EEVEE Next (实时) 和 CYCLES (路径追踪) 两种渲染引擎。

工作流:
  1. build_request()  → 构建 Blender 命令预览
  2. execute_request() → subprocess 执行 blender -b -P script.py 并通过环境变量传参
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, ClassVar

from aicomic.providers.base import IProvider, ProviderCapability, ProviderInfo


class BlenderRenderProvider(IProvider):
    """Provider adapter for local Blender 3D rendering (三渲二).

    Renders 3D scenes using Blender's Python API via subprocess.
    Supports:
      - EEVEE Next real-time renderer (fast, cel shading suitable)
      - CYCLES path-tracing renderer (slow, photorealistic)
      - Freestyle line art outlines
      - Camera animation for video output
    """

    provider_name: ClassVar[str] = "blender"
    display_name: ClassVar[str] = "Blender 三渲二"
    capabilities: ClassVar[ProviderCapability] = ProviderCapability(
        job_types=("video", "image"),
        dispatch_channel="local",
        auth_required=False,
        required_env=(),
    )

    BLENDER_PATH: ClassVar[str] = "/Applications/Blender.app/Contents/MacOS/Blender"

    # ── Helpers ──────────────────────────────────────────────────────────

    def _find_blender(self) -> str:
        """Locate the Blender executable."""
        blender = shutil.which("blender")
        if blender:
            return blender
        if Path(self.BLENDER_PATH).exists():
            return self.BLENDER_PATH
        for p in [
            "/Applications/Blender.app/Contents/MacOS/Blender",
            "/usr/local/bin/blender",
            "/opt/homebrew/bin/blender",
        ]:
            if Path(p).exists():
                return p
        return "blender"

    def _resolve_script(self, name: str) -> str:
        """Resolve path to a Blender Python script."""
        search_paths = [
            Path.cwd() / "local_providers" / "blender" / "scripts" / name,
            Path(__file__).resolve().parents[4]
            / "local_providers" / "blender" / "scripts" / name,
        ]
        for p in search_paths:
            if p.exists():
                return str(p)
        return name

    def _build_env(
        self,
        cfg: dict[str, Any],
        frame_start: int,
        frame_end: int,
        output_prefix: str,
        outdir: str,
    ) -> dict[str, str]:
        """Build environment variables dict for Blender subprocess."""
        return {
            "BLENDER_SCENE_OUTDIR": outdir,
            "BLENDER_ENGINE": str(cfg.get("engine", "BLENDER_EEVEE_NEXT")),
            "BLENDER_RESOLUTION_X": str(cfg.get("resolution_x", 1280)),
            "BLENDER_RESOLUTION_Y": str(cfg.get("resolution_y", 720)),
            "BLENDER_FPS": str(cfg.get("fps", 24)),
            "BLENDER_FRAME_START": str(frame_start),
            "BLENDER_FRAME_END": str(frame_end),
            "BLENDER_OUTPUT_PREFIX": output_prefix,
            "BLENDER_RENDER_SAMPLES": str(cfg.get("render_samples", 64)),
            "BLENDER_USE_FREESTYLE": str(1 if cfg.get("use_freestyle", True) else 0),
        }

    # ── Config ──────────────────────────────────────────────────────────

    def validate_config(self) -> dict[str, Any]:
        """Validate Blender installation and bpy accessibility."""
        errors: list[str] = []
        warnings: list[str] = []

        blender_path = self._find_blender()
        blender_exists = Path(blender_path).exists()

        if not blender_exists:
            errors.append(
                f"Blender not found at '{blender_path}'. Install from https://www.blender.org/download/"
            )

        scripts_dir = Path(__file__).resolve().parents[4] / "local_providers" / "blender" / "scripts"
        if not scripts_dir.exists():
            warnings.append(f"Blender scripts directory not found: {scripts_dir}")

        bpy_ok = False
        if blender_exists:
            try:
                result = subprocess.run(
                    [blender_path, "-b", "--python-expr",
                     "import bpy; print(bpy.app.version_string)"],
                    capture_output=True, text=True, timeout=15,
                )
                bpy_ok = result.returncode == 0
                if not bpy_ok:
                    errors.append(f"Blender bpy check failed: {result.stderr.strip()[:300]}")
            except FileNotFoundError:
                errors.append(f"Blender binary not executable: {blender_path}")
            except subprocess.TimeoutExpired:
                errors.append("Blender bpy check timed out (15s)")

        return {
            "ready": len(errors) == 0 and bpy_ok,
            "errors": errors,
            "warnings": warnings,
            "blender_path": blender_path,
            "blender_exists": blender_exists,
            "bpy_ok": bpy_ok,
        }

    # ── Request Building ────────────────────────────────────────────────

    def build_request(
        self,
        request_item: dict[str, Any],
        providers_config_path: Path,
    ) -> dict[str, Any]:
        """Build a preview of the Blender render command."""
        payload = request_item.get("payload", {})
        job_type = payload.get("job_type", "video")
        script_path = self._resolve_script("render_frame.py")
        settings = self._load_settings(providers_config_path)
        blender_cfg = settings.get("blender_local", {})

        outdir = str(Path(
            str(blender_cfg.get("scene_outdir", "/tmp/blender_frames"))
        ).resolve())

        frame_start = payload.get("frame_start", 1)
        frame_end = payload.get("frame_end", 72 if job_type == "video" else 1)
        output_prefix = str(blender_cfg.get("output_prefix", "blender_scene"))

        env = self._build_env(blender_cfg, frame_start, frame_end, output_prefix, outdir)
        blender_path = self._find_blender()

        return {
            "method": "SUBPROCESS",
            "url": "",
            "headers": {},
            "body": {
                "command": [blender_path, "-b", "-P", script_path],
                "env": env,
            },
            "preflight": {
                "ready": self.is_ready(),
                "blender_path": blender_path,
                "script_path": script_path,
                "output_dir": outdir,
                "frame_start": frame_start,
                "frame_end": frame_end,
                "engine": blender_cfg.get("engine", "BLENDER_EEVEE_NEXT"),
            },
        }

    # ── Execution ───────────────────────────────────────────────────────

    def execute_request(
        self,
        request_item: dict[str, Any],
        providers_config_path: Path,
    ) -> dict[str, Any]:
        """Execute the Blender render via subprocess with env vars."""
        payload = request_item.get("payload", {})
        job_type = payload.get("job_type", "video")
        output_path = str(payload.get("output_path", ""))

        settings = self._load_settings(providers_config_path)
        blender_cfg = settings.get("blender_local", {})

        blender_path = self._find_blender()
        if not Path(blender_path).exists():
            raise RuntimeError(
                f"Blender not found at '{blender_path}'. "
                "Install from https://www.blender.org/download/"
            )

        script_path = self._resolve_script("render_frame.py")
        if not Path(script_path).exists():
            raise RuntimeError(f"Render script not found: {script_path}")

        outdir = str(Path(
            str(blender_cfg.get("scene_outdir", "/tmp/blender_frames"))
        ).resolve())

        if output_path:
            out_path = Path(output_path)
            outdir = str(out_path.parent.resolve())
            output_prefix = out_path.stem
        else:
            output_prefix = str(blender_cfg.get("output_prefix", "blender_scene"))

        frame_start = payload.get("frame_start", 1)
        frame_end = payload.get("frame_end", 72 if job_type == "video" else 1)

        env = self._build_env(blender_cfg, frame_start, frame_end, output_prefix, outdir)
        # Merge with current env
        full_env = {**os.environ, **env}

        cmd = [blender_path, "-b", "-P", script_path]

        try:
            result = subprocess.run(
                cmd,
                env=full_env,
                capture_output=True,
                text=True,
                timeout=int(blender_cfg.get("timeout_seconds", 600)),
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"Blender render timed out after {blender_cfg.get('timeout_seconds', 600)}s"
            )

        if result.returncode != 0:
            raise RuntimeError(
                f"Blender render failed (exit={result.returncode}):\n"
                f"STDERR: {result.stderr[:2000]}"
            )

        # Parse RENDER_RESULT from stdout
        render_metadata: dict[str, Any] = {}
        for line in result.stdout.splitlines():
            if line.startswith("RENDER_RESULT:"):
                try:
                    render_metadata = json.loads(line[len("RENDER_RESULT:"):])
                except json.JSONDecodeError:
                    render_metadata = {"raw": line}

        is_animation = frame_end > frame_start
        if is_animation:
            final_output = str(Path(outdir) / f"{output_prefix}_####.png")
        else:
            final_output = str(Path(outdir) / f"{output_prefix}_0001.png")

        return {
            "provider": "blender",
            "output_path": final_output,
            "content_type": "video" if is_animation else "image",
            "metadata": {
                "engine": render_metadata.get("engine", blender_cfg.get("engine", "BLENDER_EEVEE_NEXT")),
                "resolution": render_metadata.get(
                    "resolution",
                    f"{blender_cfg.get('resolution_x', 1280)}x{blender_cfg.get('resolution_y', 720)}",
                ),
                "fps": render_metadata.get("fps", blender_cfg.get("fps", 24)),
                "frame_start": render_metadata.get("frame_start", frame_start),
                "frame_end": render_metadata.get("frame_end", frame_end),
                "total_frames": render_metadata.get("total_frames", frame_end - frame_start + 1),
                "output_dir": render_metadata.get("output_dir", outdir),
                "output_prefix": render_metadata.get("output_prefix", output_prefix),
                "exit_code": result.returncode,
            },
        }

    # ── Metadata ────────────────────────────────────────────────────────

    def get_provider_info(self) -> ProviderInfo:
        return ProviderInfo(
            provider_name=self.provider_name,
            display_name=self.display_name,
            capabilities=self.capabilities,
            run_mode="本地 Blender 三渲二渲染",
            notes="基于 Blender Python API 的本地 3D 渲染 Provider。"
                  "支持 EEVEE Next / CYCLES 引擎、Freestyle 线稿、精确摄像机控制。"
                  "适合三渲二动画风格视频和静帧渲染。",
        )

    def is_ready(self, request_item: dict[str, Any] | None = None) -> bool:
        config = self.validate_config()
        return bool(config.get("ready", False))
