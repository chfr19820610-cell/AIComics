#!/usr/bin/env python3
"""
SeedanceVideoClient — Production-grade Seedance 2.0 API client.

Seedance 2.0 豆包视频生成模型管线
  POST → Poll → Download → Batch

Models:
  doubao-seedance-2-0       Highest quality
  doubao-seedance-2-0-fast  Balanced
  doubao-seedance-2-0-mini  Fastest (default)

Usage:
  # CLI single prompt
  python seedance_client.py --prompt "森林中的仙女跳舞" --output shot.mp4

  # CLI batch from manifest JSON (reads generator='seedance' scenes)
  python seedance_client.py --manifest manifests/ep01.json --output-dir source_frames/ep01/

  # Python API
  from seedance_client import SeedanceVideoClient
  client = SeedanceVideoClient()
  task = client.submit("一只猫在月光下漫步")
  client.poll(task.task_id)
  client.download(task.task_id, "output/cat.mp4")
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import signal
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple, Union

# ── Logging ──────────────────────────────────────────────
logger = logging.getLogger("seedance")
_handler = logging.StreamHandler(sys.stderr)
_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
logger.addHandler(_handler)
logger.setLevel(logging.INFO)


# ═══════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════

DEFAULT_BASE_URL = "http://token.yundashi.com/v1"
DEFAULT_API_KEY = "sk-1VW5Wz1AZVmZoV7aMqFcQbQMREmqYVHexeUUNzto2sh4IYQJ"

MODELS = {
    "pro": "doubao-seedance-2-0",       # Highest quality
    "fast": "doubao-seedance-2-0-fast", # Balanced
    "mini": "doubao-seedance-2-0-mini", # Fastest
}

# Shorthand aliases
MODEL_ALIASES = {
    "seedance20": "doubao-seedance-2-0",
    "seedance20-fast": "doubao-seedance-2-0-fast",
    "seedance20-mini": "doubao-seedance-2-0-mini",
    "pro": "doubao-seedance-2-0",
    "fast": "doubao-seedance-2-0-fast",
    "mini": "doubao-seedance-2-0-mini",
}

DEFAULT_MODEL = MODELS["mini"]
DEFAULT_SIZE = "1024x576"
DEFAULT_POLL_INTERVAL = 5       # seconds between status checks
DEFAULT_POLL_TIMEOUT = 600      # 10 minutes
DEFAULT_DOWNLOAD_TIMEOUT = 300  # 5 minutes
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 2         # seconds base delay
DEFAULT_MAX_CONCURRENCY = 3     # parallel submissions for batch mode


# ═══════════════════════════════════════════════════════════
# Enums & Data Classes
# ═══════════════════════════════════════════════════════════

class TaskStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


@dataclass
class GenerationTask:
    """A submitted video generation task."""
    task_id: str
    model: str
    prompt: str
    size: str
    status: TaskStatus = TaskStatus.PENDING
    video_url: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
    attempts: int = 0
    _raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_terminal(self) -> bool:
        return self.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)


@dataclass
class BatchResult:
    """Aggregated result from a batch generation run."""
    total: int
    completed: int
    failed: int
    tasks: List[GenerationTask]
    start_time: str
    end_time: str

    @property
    def success_rate(self) -> float:
        return self.completed / self.total if self.total > 0 else 1.0


# ═══════════════════════════════════════════════════════════
# Exceptions
# ═══════════════════════════════════════════════════════════

class SeedanceError(Exception):
    """Base exception for Seedance client."""

class SeedanceAuthError(SeedanceError):
    """Authentication failed (401/403)."""

class SeedanceTimeoutError(SeedanceError):
    """Operation timed out."""

class SeedanceTaskFailedError(SeedanceError):
    """Task reached FAILED status."""

class SeedanceNetworkError(SeedanceError):
    """Network-level error (connection, DNS, etc.)."""

class SeedanceRateLimitError(SeedanceError):
    """Rate limited (429)."""


# ═══════════════════════════════════════════════════════════
# Client Implementation
# ═══════════════════════════════════════════════════════════

class SeedanceVideoClient:
    """
    Seedance 2.0 Video Generation Client.

    Full lifecycle: submit → poll → download, with retry and batch support.

    Examples
    --------
    >>> client = SeedanceVideoClient()  # uses defaults
    >>> task = client.submit("A cat walking under moonlight")
    >>> client.wait_for_completion(task.task_id)
    >>> path = client.download(task.task_id, "/tmp/cat.mp4")
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        size: str = DEFAULT_SIZE,
        poll_interval: int = DEFAULT_POLL_INTERVAL,
        poll_timeout: int = DEFAULT_POLL_TIMEOUT,
        download_timeout: int = DEFAULT_DOWNLOAD_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_delay: float = DEFAULT_RETRY_DELAY,
        max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
        progress_callback: Optional[Callable[[GenerationTask], None]] = None,
    ):
        """
        Args:
            api_key: Bearer token. Defaults to SEEDANCE_API_KEY env or built-in.
            base_url: API base URL.
            model: Default model to use.
            size: Default resolution (e.g. "1024x576").
            poll_interval: Seconds between status checks.
            poll_timeout: Max seconds to wait for completion.
            download_timeout: Max seconds for file download.
            max_retries: Max submission retries on transient failures.
            retry_delay: Base backoff delay in seconds (doubles each retry).
            max_concurrency: Max parallel tasks in batch mode.
            progress_callback: Optional fn(task) called on status change.
        """
        self.api_key = (
            api_key
            or os.environ.get("SEEDANCE_API_KEY")
            or DEFAULT_API_KEY
        )
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.model = self._resolve_model(model)
        self.size = size
        self.poll_interval = poll_interval
        self.poll_timeout = poll_timeout
        self.download_timeout = download_timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.max_concurrency = max_concurrency
        self.progress_callback = progress_callback

        # Track in-flight tasks
        self._tasks: Dict[str, GenerationTask] = {}
        self._cancel_flags: Dict[str, bool] = {}
        self._available: Optional[bool] = None

        # Session for connection reuse (urllib opener)
        self._opener = urllib.request.build_opener()

        logger.debug("SeedanceVideoClient initialized: model=%s base=%s", self.model, self.base_url)

    # ── Model resolution ─────────────────────────────────

    @staticmethod
    def _resolve_model(model: str) -> str:
        """Resolve alias to full model name."""
        resolved = MODEL_ALIASES.get(model, model)
        if resolved not in MODELS.values() and resolved not in MODEL_ALIASES:
            logger.warning("Unknown model '%s', using as-is", model)
        return resolved

    @classmethod
    def list_models(cls) -> Dict[str, str]:
        """Return dict of {alias: full_model_name}."""
        return {**MODEL_ALIASES}

    # ── Health check ──────────────────────────────────────

    def check_available(self, force: bool = False) -> bool:
        """Ping the API endpoint to verify connectivity.

        Returns True if reachable. Caches the result unless force=True.
        """
        if self._available is not None and not force:
            return self._available
        try:
            req = self._build_request("GET", "/models")
            self._request(req, timeout=10)
            self._available = True
            logger.info("Seedance API reachable at %s", self.base_url)
        except Exception as exc:
            logger.warning("Seedance API unreachable: %s", exc)
            self._available = False
        return self._available

    # ── Submission ────────────────────────────────────────

    def submit(
        self,
        prompt: str,
        model: Optional[str] = None,
        size: Optional[str] = None,
        task_id: Optional[str] = None,
        **extra_params,
    ) -> GenerationTask:
        """
        Submit a video generation task.

        Args:
            prompt: Chinese/English generation prompt.
            model: Override default model.
            size: Override default resolution ("1024x576").
            task_id: Optional custom task ID (for tracking).
            **extra_params: Additional API body fields.

        Returns:
            A GenerationTask with task_id populated.

        Raises:
            SeedanceAuthError: On 401/403.
            SeedanceRateLimitError: On 429.
            SeedanceNetworkError: On connection failure.
            SeedanceError: On other errors.
        """
        resolved_model = self._resolve_model(model or self.model)
        body: Dict[str, Any] = {
            "model": resolved_model,
            "prompt": prompt,
            "size": size or self.size,
        }
        body.update(extra_params)

        task = GenerationTask(
            task_id=task_id or "",
            model=resolved_model,
            prompt=prompt,
            size=size or self.size,
        )

        def _submit_once() -> Dict[str, Any]:
            req = self._build_request("POST", "/video/generations", body=body)
            return self._request(req, timeout=30)

        result = self._with_retry(
            _submit_once,
            operation=f"submit(prompt={prompt[:50]}...)",
            task=task,
        )

        # API returns "task_id" according to spec
        task.task_id = result.get("task_id") or result.get("id") or result.get("generation_id", "")
        if not task.task_id:
            raise SeedanceError(f"No task_id in response: {result}")

        task._raw = result
        task.status = TaskStatus.PENDING
        task.attempts = 1

        self._tasks[task.task_id] = task
        logger.info("Submitted task %s (model=%s)", task.task_id, resolved_model)
        self._notify_progress(task)

        return task

    # ── Polling ───────────────────────────────────────────

    def poll(self, task_id: str) -> GenerationTask:
        """
        Check the status of a generation task.

        Returns the updated GenerationTask. Does not block — call in a loop or
        use wait_for_completion().

        Raises:
            SeedanceTaskFailedError: if status is FAILED.
            SeedanceError: if task not found.
        """
        task = self._tasks.get(task_id)
        if task is None:
            task = GenerationTask(task_id=task_id, model="", prompt="", size=self.size)

        try:
            req = self._build_request("GET", f"/video/generations/{task_id}")
            data = self._request(req, timeout=10)
        except Exception as exc:
            logger.error("Poll failed for %s: %s", task_id, exc)
            raise SeedanceNetworkError(f"Poll failed: {exc}") from exc

        # Map status string
        status_str = data.get("status", "UNKNOWN").upper()
        try:
            task.status = TaskStatus(status_str)
        except ValueError:
            task.status = TaskStatus.UNKNOWN

        task.video_url = data.get("video_url") or data.get("url")
        task.error_message = data.get("error") or data.get("error_message")
        task._raw = data

        if task.status == TaskStatus.COMPLETED:
            task.completed_at = datetime.now(timezone.utc).isoformat()
            logger.info("Task %s COMPLETED", task_id)
        elif task.status == TaskStatus.FAILED:
            msg = task.error_message or "No error detail"
            logger.error("Task %s FAILED: %s", task_id, msg)
            raise SeedanceTaskFailedError(f"Task {task_id} failed: {msg}")

        self._tasks[task_id] = task
        self._notify_progress(task)
        return task

    def wait_for_completion(
        self,
        task_id: str,
        poll_interval: Optional[int] = None,
        timeout: Optional[int] = None,
        on_progress: Optional[Callable[[GenerationTask], None]] = None,
    ) -> GenerationTask:
        """
        Poll until the task reaches a terminal status.

        Args:
            task_id: Task to wait on.
            poll_interval: Override default poll interval.
            timeout: Override default timeout (seconds).
            on_progress: Called after each poll with current task.

        Returns:
            The completed GenerationTask.

        Raises:
            SeedanceTimeoutError: if timeout exceeded.
            SeedanceTaskFailedError: if task failed.
        """
        interval = poll_interval if poll_interval is not None else self.poll_interval
        deadline = time.time() + (timeout if timeout is not None else self.poll_timeout)
        self._cancel_flags[task_id] = False

        task = self._tasks.get(task_id)
        if task is None:
            task = GenerationTask(task_id=task_id, model="", prompt="", size=self.size)

        logger.info("Waiting for task %s (timeout=%ds, interval=%ds)", task_id, timeout or self.poll_timeout, interval)

        while time.time() < deadline:
            if self._cancel_flags.get(task_id, False):
                logger.info("Task %s cancelled by user", task_id)
                task.status = TaskStatus.CANCELLED
                self._notify_progress(task)
                return task

            task = self.poll(task_id)
            if on_progress:
                on_progress(task)

            if task.is_terminal:
                return task

            time.sleep(interval)

        raise SeedanceTimeoutError(f"Task {task_id} did not complete within {timeout or self.poll_timeout}s (status={task.status.value})")

    def cancel(self, task_id: str) -> None:
        """Request cancellation of an in-flight task (sets polling flag)."""
        self._cancel_flags[task_id] = True
        logger.info("Cancellation requested for task %s", task_id)

    # ── Download ──────────────────────────────────────────

    def download(
        self,
        task_id: str,
        output_path: Union[str, Path],
        video_url: Optional[str] = None,
        overwrite: bool = False,
    ) -> Path:
        """
        Download generated video to a local file.

        Args:
            task_id: Task ID (used to look up video_url if not provided).
            output_path: Local file path. Directories are auto-created.
            video_url: Direct video URL (bypasses task lookup).
            overwrite: If True, overwrite existing file.

        Returns:
            Path to downloaded file.

        Raises:
            SeedanceError: if no video_url found.
            SeedanceNetworkError: on download failure.
        """
        output = Path(output_path)
        if output.exists() and not overwrite:
            logger.info("File already exists, skipping: %s", output)
            return output

        url = video_url
        if not url:
            task = self._tasks.get(task_id)
            if task and task.video_url:
                url = task.video_url
            else:
                # Try a fresh poll to get the URL
                task = self.poll(task_id)
                url = task.video_url

        if not url:
            raise SeedanceError(f"No video_url for task {task_id}")

        output.parent.mkdir(parents=True, exist_ok=True)

        logger.info("Downloading %s → %s", task_id, output)

        def _download_once():
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "SeedanceVideoClient/1.0"},
            )
            resp = self._opener.open(req, timeout=self.download_timeout)
            data = resp.read()
            output.write_bytes(data)
            return output

        result = self._with_retry(
            _download_once,
            operation=f"download({task_id})",
            retries=2,
            delay=3,
        )

        size_kb = output.stat().st_size / 1024
        logger.info("Downloaded %s (%.0f KB)", output.name, size_kb)
        return result

    # ── One-shot convenience ──────────────────────────────

    def generate(
        self,
        prompt: str,
        output_path: Union[str, Path],
        model: Optional[str] = None,
        size: Optional[str] = None,
        poll_timeout: Optional[int] = None,
    ) -> GenerationTask:
        """
        Submit → wait → download in one call.

        Returns the completed GenerationTask. The video is at output_path,
        and the task's video_url points to the local file.

        This is the high-level convenience method.
        """
        task = self.submit(prompt, model=model, size=size)
        task = self.wait_for_completion(task.task_id, timeout=poll_timeout)
        if task.status == TaskStatus.COMPLETED:
            path = self.download(task.task_id, output_path, video_url=task.video_url)
            task.video_url = str(path.absolute())
        return task

    # ── Batch generation ──────────────────────────────────

    def batch_generate(
        self,
        shots: List[Dict[str, Any]],
        output_dir: Union[str, Path],
        model: Optional[str] = None,
        size: Optional[str] = None,
        concurrency: Optional[int] = None,
    ) -> BatchResult:
        """
        Generate videos for multiple shots in parallel.

        Args:
            shots: List of dicts with at least:
                - 'prompt_sd' or 'prompt': the generation prompt
                - 'scene_id' or 'shot_id': unique identifier (optional)
            output_dir: Directory to save generated videos.
            model: Override default model.
            size: Override default size.
            concurrency: Max parallel submissions (default: self.max_concurrency).

        Returns:
            BatchResult with aggregated stats.

        Example shot dict:
            {"scene_id": 1, "prompt_sd": "rainy campus, moody lighting, ..."}
        """
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        workers = concurrency or self.max_concurrency

        logger.info("Batch: %d shots, concurrency=%d, output=%s", len(shots), workers, out_dir)

        start_time = datetime.now(timezone.utc).isoformat()
        tasks: List[GenerationTask] = []

        # Phase 1: Submit all tasks
        logger.info("── Batch Phase 1: Submitting %d shots ──", len(shots))

        def _submit_shot(shot: Dict[str, Any], index: int) -> Tuple[int, GenerationTask]:
            prompt = shot.get("prompt_sd") or shot.get("prompt", "")
            shot_id = shot.get("scene_id") or shot.get("shot_id") or shot.get("id", f"shot_{index:04d}")

            try:
                task = self.submit(prompt, model=model, size=size, task_id=str(shot_id))
                return index, task
            except Exception as exc:
                logger.error("Submit failed for shot %s: %s", shot_id, exc)
                fail_task = GenerationTask(
                    task_id=str(shot_id),
                    model=model or self.model,
                    prompt=prompt,
                    size=size or self.size,
                    status=TaskStatus.FAILED,
                    error_message=str(exc),
                )
                return index, fail_task

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures: Dict[Future, int] = {}
            for i, shot in enumerate(shots):
                f = executor.submit(_submit_shot, shot, i)
                futures[f] = i

            results: Dict[int, GenerationTask] = {}
            for f in as_completed(futures):
                i, task = f.result()
                results[i] = task
                logger.info("  [%d/%d] Submitted: %s → %s", i + 1, len(shots), task.task_id, task.status.value)

            ordered = [results[i] for i in sorted(results)]
            tasks = ordered

        # Phase 2: Poll all tasks
        logger.info("── Batch Phase 2: Polling %d tasks ──", len(tasks))

        def _wait_for(task: GenerationTask) -> GenerationTask:
            if task.status == TaskStatus.FAILED:
                return task
            try:
                return self.wait_for_completion(task.task_id)
            except Exception as exc:
                logger.error("Poll failed for %s: %s", task.task_id, exc)
                task.status = TaskStatus.FAILED
                task.error_message = str(exc)
                return task

        with ThreadPoolExecutor(max_workers=workers) as executor:
            poll_futures = {executor.submit(_wait_for, t): t for t in tasks}
            for f in as_completed(poll_futures):
                updated = f.result()
                logger.info("  Task %s: %s", updated.task_id, updated.status.value)

        # Phase 3: Download completed tasks
        logger.info("── Batch Phase 3: Downloading completed tasks ──")
        for task in tasks:
            if task.status == TaskStatus.COMPLETED and task.video_url:
                filename = f"{task.task_id}.mp4"
                try:
                    self.download(task.task_id, out_dir / filename, video_url=task.video_url)
                except Exception as exc:
                    logger.error("Download failed for %s: %s", task.task_id, exc)
                    task.status = TaskStatus.FAILED
                    task.error_message = f"Download: {exc}"

        end_time = datetime.now(timezone.utc).isoformat()

        completed = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)
        failed = sum(1 for t in tasks if t.status == TaskStatus.FAILED)

        result = BatchResult(
            total=len(tasks),
            completed=completed,
            failed=failed,
            tasks=tasks,
            start_time=start_time,
            end_time=end_time,
        )

        logger.info(
            "Batch complete: %d/%d succeeded (%.0f%%)",
            completed, len(tasks), result.success_rate * 100,
        )
        return result

    # ── Manifest helpers ──────────────────────────────────

    @staticmethod
    def extract_shots_from_manifest(manifest_path: Union[str, Path]) -> Generator[Dict[str, Any], None, None]:
        """
        Yield shot dicts from a manifest JSON for all scenes with generator='seedance'.

        Each yielded dict has: scene_id, prompt_sd, narration, generator, shot_type, camera.
        """
        path = Path(manifest_path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for scene in data.get("scenes", []):
            generator = scene.get("generator", "comfyui")
            if generator != "seedance":
                continue
            yield {
                "scene_id": scene.get("scene_id", 0),
                "prompt_sd": scene.get("prompt_sd", ""),
                "narration": scene.get("narration", ""),
                "generator": generator,
                "shot_type": scene.get("shot_type", ""),
                "camera": scene.get("camera", ""),
                "duration_sec": scene.get("duration_sec", 5),
            }

    # ── Internal helpers ──────────────────────────────────

    def _build_request(
        self,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None,
    ) -> urllib.request.Request:
        """Build a urllib Request with auth and content-type headers."""
        url = f"{self.base_url}{path}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "SeedanceVideoClient/1.0",
        }

        data = None
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        return req

    def _request(self, req: urllib.request.Request, timeout: int = 30) -> Dict[str, Any]:
        """Execute an HTTP request, parse JSON response, handle errors."""
        try:
            resp = self._opener.open(req, timeout=timeout)
            raw = resp.read()
            return json.loads(raw)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")
            status = exc.code
            if status == 401 or status == 403:
                raise SeedanceAuthError(f"Auth failed ({status}): {body[:500]}")
            if status == 429:
                raise SeedanceRateLimitError(f"Rate limited ({status}): {body[:500]}")
            raise SeedanceError(f"HTTP {status}: {body[:500]}") from exc
        except urllib.error.URLError as exc:
            raise SeedanceNetworkError(f"Network error: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise SeedanceError(f"Invalid JSON response: {exc}") from exc

    def _with_retry(
        self,
        fn: Callable[[], Any],
        operation: str = "operation",
        retries: Optional[int] = None,
        delay: Optional[float] = None,
        task: Optional[GenerationTask] = None,
    ) -> Any:
        """
        Execute fn with exponential backoff retry on transient errors.
        Does NOT retry on auth errors or task failures.
        """
        max_attempts = retries if retries is not None else self.max_retries
        base_delay = delay if delay is not None else self.retry_delay

        last_exc = None
        for attempt in range(1, max_attempts + 2):  # +1 for first try, +1 for range exclusive
            try:
                return fn()
            except (SeedanceAuthError, SeedanceTaskFailedError):
                raise  # Never retry auth or task failures
            except SeedanceRateLimitError as exc:
                wait = base_delay * (2 ** (attempt - 1))
                logger.warning("Rate limited on %s (attempt %d/%d), waiting %.0fs", operation, attempt, max_attempts, wait)
                last_exc = exc
                if attempt <= max_attempts:
                    time.sleep(wait)
            except SeedanceNetworkError as exc:
                wait = base_delay * (2 ** (attempt - 1))
                logger.warning("Network error on %s (attempt %d/%d): %s, waiting %.0fs", operation, attempt, max_attempts, exc, wait)
                last_exc = exc
                if attempt <= max_attempts:
                    time.sleep(wait)
            except SeedanceError as exc:
                # Less severe errors — retry with backoff
                wait = base_delay * (2 ** (attempt - 1))
                logger.warning("%s failed (attempt %d/%d): %s, retrying in %.0fs", operation, attempt, max_attempts, exc, wait)
                last_exc = exc
                if attempt <= max_attempts:
                    time.sleep(wait)
            except Exception as exc:
                logger.error("Unexpected error on %s: %s", operation, exc)
                raise

        if task:
            task.status = TaskStatus.FAILED
            task.error_message = str(last_exc)
        raise SeedanceError(f"{operation} failed after {max_attempts} retries: {last_exc}")

    def _notify_progress(self, task: GenerationTask) -> None:
        """Call user-provided progress callback if set."""
        if self.progress_callback:
            try:
                self.progress_callback(task)
            except Exception:
                logger.exception("Progress callback failed")


# ═══════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════

def cli_main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="SeedanceVideoClient — Seedance 2.0 Video Generation CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --prompt "雨中的校园" --output shot.mp4
  %(prog)s --manifest manifests/ep01.json --output-dir source_frames/ep01/
  %(prog)s --prompt "test" --model doubao-seedance-2-0-mini --size 1024x576
  %(prog)s --check                           # just verify API connectivity
        """,
    )

    parser.add_argument("--prompt", "-p", type=str, help="Single generation prompt")
    parser.add_argument("--manifest", "-m", type=str, help="Path to episode manifest JSON (batch mode)")
    parser.add_argument("--output", "-o", type=str, default="output/seedance.mp4", help="Output path for single mode")
    parser.add_argument("--output-dir", "-d", type=str, default="source_frames/", help="Output directory for batch mode")
    parser.add_argument("--model", type=str, default="mini", help="Model: pro|fast|mini, or full model name")
    parser.add_argument("--size", type=str, default=DEFAULT_SIZE, help="Resolution (e.g. 1024x576)")
    parser.add_argument("--api-key", type=str, help="API key (env: SEEDANCE_API_KEY)")
    parser.add_argument("--base-url", type=str, default=DEFAULT_BASE_URL, help="API base URL")
    parser.add_argument("--timeout", type=int, default=DEFAULT_POLL_TIMEOUT, help="Poll timeout in seconds")
    parser.add_argument("--concurrency", type=int, default=DEFAULT_MAX_CONCURRENCY, help="Max parallel tasks (batch)")
    parser.add_argument("--retries", type=int, default=DEFAULT_MAX_RETRIES, help="Max submission retries")
    parser.add_argument("--check", action="store_true", help="Only check API reachability")
    parser.add_argument("--list-models", action="store_true", help="List available model aliases")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")
    parser.add_argument("--dry-run", action="store_true", help="Parse manifest but don't submit")

    args = parser.parse_args(argv)

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # List models
    if args.list_models:
        print("Available Seedance models:")
        for alias, full in MODEL_ALIASES.items():
            print(f"  {alias:25s} → {full}")
        return 0

    # Init client
    client = SeedanceVideoClient(
        api_key=args.api_key,
        base_url=args.base_url,
        model=args.model,
        size=args.size,
        poll_timeout=args.timeout,
        max_retries=args.retries,
        max_concurrency=args.concurrency,
    )

    # Health check
    if args.check:
        ok = client.check_available(force=True)
        print(f"Seedance API: {'✅ reachable' if ok else '❌ unreachable'}")
        return 0 if ok else 1

    # Single prompt mode
    if args.prompt:
        output = Path(args.output)
        print(f"Generating video for prompt: {args.prompt}")
        task = client.generate(
            prompt=args.prompt,
            output_path=output,
            model=args.model,
            size=args.size,
            poll_timeout=args.timeout,
        )
        if task.status == TaskStatus.COMPLETED:
            print(f"✅ Done: {output} ({output.stat().st_size / 1024:.0f} KB)")
            return 0
        else:
            print(f"❌ Failed: {task.error_message}")
            return 1

    # Manifest batch mode
    if args.manifest:
        manifest_path = Path(args.manifest)
        if not manifest_path.exists():
            print(f"❌ Manifest not found: {args.manifest}", file=sys.stderr)
            return 1

        shots = list(client.extract_shots_from_manifest(manifest_path))
        print(f"📋 Manifest: {manifest_path.name}")
        print(f"   Seedance shots: {len(shots)}")

        if args.dry_run:
            for i, shot in enumerate(shots):
                print(f"   [{i+1}] scene_id={shot['scene_id']} ({shot['shot_type']})")
                print(f"       prompt: {shot['prompt_sd'][:80]}...")
            return 0

        if not shots:
            print("⚠️  No scenes with generator='seedance' in manifest.")
            return 0

        result = client.batch_generate(
            shots=shots,
            output_dir=args.output_dir,
            model=args.model,
            size=args.size,
            concurrency=args.concurrency,
        )

        # Summary
        print(f"\n{'='*60}")
        print(f"Batch Summary")
        print(f"{'='*60}")
        print(f"  Total:     {result.total}")
        print(f"  Completed: {result.completed}")
        print(f"  Failed:    {result.failed}")
        print(f"  Rate:      {result.success_rate:.0%}")
        if result.failed > 0:
            print(f"\n  Failures:")
            for t in result.tasks:
                if t.status == TaskStatus.FAILED:
                    print(f"    - {t.task_id}: {t.error_message}")
        return 0 if result.failed == 0 else 1

    parser.print_help()
    return 1


# ═══════════════════════════════════════════════════════════
# main
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    sys.exit(cli_main())


# ═══════════════════════════════════════════════════════════
# Integration note for compose_video.py:
#
#   from seedance_client import SeedanceVideoClient
#
#   client = SeedanceVideoClient(model="mini")
#   task = client.generate("...", output_path)
#   if task.status == TaskStatus.COMPLETED:
#       print(f"Saved to {task.video_url}")
#
# Or batch mode from manifest:
#
#   shots = list(SeedanceVideoClient.extract_shots_from_manifest("manifests/ep01.json"))
#   result = client.batch_generate(shots, "source_frames/ep01/")
# ═══════════════════════════════════════════════════════════
