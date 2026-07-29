#!/usr/bin/env python3
"""
星痕纪元 · Seedance 2.0 批量视频生成器
==========================================
读取分镜 JSON → 调 seedance_client → 下载视频 → 输出进度

用法:
  python batch_generate.py                                    # 默认: 生成 ep01, 并发1
  python batch_generate.py --episode 1 --concurrency 3        # 3路并发
  python batch_generate.py --dry-run                           # 仅打印prompt, 不调用API
  python batch_generate.py --resume                            # 从中断处恢复
  python batch_generate.py --episode 1 --shots 5,8,12          # 仅生成指定镜头

依赖:
  pip install httpx tqdm

要求:
  - seedance_client.py 或同等功能的种子视频生成模块
  - Seedance API key 已配置在环境变量 SEEDANCE_API_KEY 或通过 --api-key 传入
"""

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent
MANIFESTS_DIR = PROJECT_ROOT / "manifests"
OUTPUT_DIR = PROJECT_ROOT / "output" / "seedance_videos"
STATE_DIR = PROJECT_ROOT / "output" / ".seedance_state"

# 默认分镜 JSON 路径模式
STORYBOARD_TEMPLATE = "ep{episode:02d}_seedance.json"

# Seedance API 默认配置
DEFAULT_SEEDANCE_ENDPOINT = os.environ.get(
    "SEEDANCE_ENDPOINT", "https://api.seedance.ai/v2"
)
DEFAULT_API_KEY = os.environ.get("SEEDANCE_API_KEY", "")
DEFAULT_POLL_INTERVAL = 10       # 轮询间隔（秒）
DEFAULT_MAX_WAIT = 600           # 单镜头最大等待时间（秒）
DEFAULT_CONCURRENCY = 1          # 默认并发数


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def load_storyboard(episode: int) -> dict:
    """加载分镜 JSON"""
    path = MANIFESTS_DIR / STORYBOARD_TEMPLATE.format(episode=episode)
    if not path.exists():
        raise FileNotFoundError(f"分镜文件不存在: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def shot_cache_key(shot: dict) -> str:
    """为每个镜头生成幂等缓存键（基于 prompt 的哈希）"""
    raw = shot.get("prompt_seedance", "") + str(shot.get("shot_id", ""))
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def load_state(episode: int) -> dict:
    """加载生成进度状态"""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state_path = STATE_DIR / f"ep{episode:02d}_state.json"
    if state_path.exists():
        with open(state_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(episode: int, state: dict):
    """保存生成进度状态"""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state_path = STATE_DIR / f"ep{episode:02d}_state.json"
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Seedance 客户端抽象层
# ---------------------------------------------------------------------------

class SeedanceClient:
    """
    Seedance 2.0 视频生成客户端。

    使用方法:
      - 直接通过 HTTP API 调用（默认）
      - 通过 seedance_client.py 子进程调用（--client-mode=cli）
      - 自定义 client 类覆盖 generate() 和 poll() 方法
    """

    def __init__(
        self,
        endpoint: str = DEFAULT_SEEDANCE_ENDPOINT,
        api_key: str = DEFAULT_API_KEY,
        poll_interval: int = DEFAULT_POLL_INTERVAL,
        max_wait: int = DEFAULT_MAX_WAIT,
    ):
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.poll_interval = poll_interval
        self.max_wait = max_wait

    async def generate(self, prompt: str, shot_id: int, **kwargs) -> str:
        """
        提交生成任务，返回 task_id。
        子类或外部模块可覆盖此方法。
        """
        import httpx

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "prompt": prompt,
            "aspect_ratio": "9:16",
            "duration": kwargs.get("duration_sec", 5),
            "motion_bucket_id": kwargs.get("motion_bucket_id", 127),
            "cond_frames": kwargs.get("cond_frames", 16),
            "seed": kwargs.get("seed", -1),
            "reference_id": f"shot_{shot_id:03d}",
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.endpoint}/generate",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            task_id = data.get("task_id") or data.get("id")
            if not task_id:
                raise RuntimeError(f"Seedance API 未返回 task_id: {data}")
            return task_id

    async def poll(self, task_id: str) -> Optional[str]:
        """
        轮询任务状态，返回视频下载 URL 或 None（仍在处理中）。
        """
        import httpx

        headers = {"Authorization": f"Bearer {self.api_key}"}

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.endpoint}/status/{task_id}",
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

            status = data.get("status", "")
            if status in ("completed", "done", "succeeded"):
                return data.get("video_url") or data.get("output_url")
            elif status in ("failed", "error", "cancelled"):
                raise RuntimeError(f"任务 {task_id} 失败: {data.get('error', '未知错误')}")
            return None  # 仍在处理

    async def download(self, url: str, dest: Path) -> Path:
        """下载视频文件"""
        import httpx

        dest.parent.mkdir(parents=True, exist_ok=True)
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            dest.write_bytes(resp.content)
        return dest


# ---------------------------------------------------------------------------
# 子进程模式: 调用 seedance_client.py
# ---------------------------------------------------------------------------

class SeedanceCLIClient(SeedanceClient):
    """
    通过 seedance_client.py 子进程调用。
    假设 seedance_client.py 接口:
      python seedance_client.py generate --prompt "..." --duration 5 --output-id
      python seedance_client.py status <task_id>
      python seedance_client.py download <task_id> --output <path>
    """

    def __init__(self, client_script: str = "seedance_client.py", **kwargs):
        super().__init__(**kwargs)
        self.script = Path(client_script)

    async def _run(self, *args) -> str:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, str(self.script), *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(PROJECT_ROOT),
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(
                f"seedance_client 返回 {proc.returncode}: {stderr.decode()}"
            )
        return stdout.decode().strip()

    async def generate(self, prompt: str, shot_id: int, **kwargs) -> str:
        duration = kwargs.get("duration_sec", 5)
        output = await self._run(
            "generate",
            "--prompt", prompt,
            "--duration", str(duration),
            "--output-id",
        )
        return output.strip()

    async def poll(self, task_id: str) -> Optional[str]:
        output = await self._run("status", task_id)
        lines = output.splitlines()
        for line in lines:
            if line.startswith("video_url="):
                return line.split("=", 1)[1].strip()
            if line.startswith("status="):
                status = line.split("=", 1)[1].strip()
                if status in ("failed", "error"):
                    raise RuntimeError(f"任务 {task_id} 失败")
        return None

    async def download(self, url: str, dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        await self._run("download", url, "--output", str(dest))
        return dest


# ---------------------------------------------------------------------------
# 批量生成协调器
# ---------------------------------------------------------------------------

class BatchGenerator:
    """批量视频生成主控"""

    def __init__(
        self,
        episode: int,
        client: SeedanceClient,
        concurrency: int = DEFAULT_CONCURRENCY,
        dry_run: bool = False,
        resume: bool = False,
        only_shots: Optional[list[int]] = None,
    ):
        self.episode = episode
        self.client = client
        self.concurrency = concurrency
        self.dry_run = dry_run
        self.resume = resume
        self.only_shots = only_shots

        self.storyboard = load_storyboard(episode)
        self.shots = self.storyboard.get("scenes", [])
        self.output_ep_dir = OUTPUT_DIR / f"ep{episode:02d}"
        self.state: dict = {}

    def filter_shots(self) -> list[dict]:
        """筛选需要处理的镜头"""
        if self.only_shots:
            shot_ids = set(self.only_shots)
            return [s for s in self.shots if s["shot_id"] in shot_ids]

        if self.resume:
            # 加载状态，跳过已完成的
            state = load_state(self.episode)
            completed = set(state.get("completed_shots", []))
            pending = [s for s in self.shots if s["shot_id"] not in completed]
            print(f"📋 恢复模式: {len(self.shots)} 总镜头, "
                  f"{len(completed)} 已完成, {len(pending)} 待处理")
            return pending

        return list(self.shots)

    async def process_shot(self, shot: dict, semaphore: asyncio.Semaphore) -> dict:
        """处理单个镜头"""
        async with semaphore:
            shot_id = shot["shot_id"]
            shot_type = shot.get("shot_type", "medium")
            duration = shot.get("duration_sec", 5)
            prompt = shot.get("prompt_seedance", "")
            dialogue = shot.get("dialogue", "")
            speaker = shot.get("speaker", "")

            cache_key = shot_cache_key(shot)
            output_file = self.output_ep_dir / f"shot_{shot_id:03d}_{cache_key}.mp4"

            result = {
                "shot_id": shot_id,
                "output_file": str(output_file),
                "status": "pending",
                "task_id": None,
                "error": None,
                "elapsed_sec": 0,
            }

            # 跳过已有的完整文件
            if output_file.exists() and output_file.stat().st_size > 0:
                result["status"] = "cached"
                print(f"  ✅ 镜头 {shot_id:02d} 已缓存: {output_file.name}")
                return result

            # Dry-run
            if self.dry_run:
                print(f"  🔍 [DRY-RUN] 镜头 {shot_id:02d} ({shot_type}, {duration}s)")
                print(f"     Prompt: {prompt[:80]}...")
                if dialogue:
                    print(f"     对白 [{speaker}]: {dialogue[:60]}")
                result["status"] = "dry_run"
                return result

            # === 实际生成 ===
            t_start = time.time()
            print(f"  🎬 镜头 {shot_id:02d} | 提交生成 | {shot_type} | {duration}s")

            try:
                # 1) 提交
                task_id = await self.client.generate(
                    prompt=prompt,
                    shot_id=shot_id,
                    duration_sec=duration,
                )
                result["task_id"] = task_id
                print(f"     ⏳ 任务ID: {task_id}")

                # 2) 轮询
                waited = 0
                video_url: Optional[str] = None
                while waited < self.client.max_wait:
                    await asyncio.sleep(self.client.poll_interval)
                    waited += self.client.poll_interval

                    video_url = await self.client.poll(task_id)
                    if video_url:
                        print(f"     ✅ 生成完成 ({waited}s)")
                        break
                    print(f"     ⏳ 等待中... ({waited}s / {self.client.max_wait}s)")

                if not video_url:
                    raise TimeoutError(f"镜头 {shot_id:02d} 超时 ({self.client.max_wait}s)")

                # 3) 下载
                await self.client.download(video_url, output_file)
                result["status"] = "completed"
                result["elapsed_sec"] = time.time() - t_start
                file_size_mb = output_file.stat().st_size / (1024 * 1024)
                print(f"     💾 已保存: {output_file.name} ({file_size_mb:.1f}MB)")

            except Exception as e:
                result["status"] = "failed"
                result["error"] = str(e)
                result["elapsed_sec"] = time.time() - t_start
                print(f"     ❌ 失败: {e}")

            return result

    async def run(self):
        """主执行入口"""
        title = self.storyboard.get("title", f"第{self.episode}集")
        total_dur = self.storyboard.get("target_duration_sec", 0)
        all_shots = self.shots
        pending = self.filter_shots()

        print("=" * 60)
        print(f"🚀 星痕纪元 · Seedance 批量生成器")
        print(f"📺 {title}")
        print(f"🎯 总镜头: {len(all_shots)} | 待处理: {len(pending)} | "
              f"目标时长: {total_dur}s")
        print(f"🔧 并发: {self.concurrency} | Dry-run: {self.dry_run}")
        print(f"📁 输出: {self.output_ep_dir}")
        print("=" * 60)

        if not pending:
            print("✨ 所有镜头已生成完毕!")
            return

        semaphore = asyncio.Semaphore(self.concurrency)

        # 收集结果
        results = []
        total = len(pending)
        completed_count = 0
        failed_count = 0

        # 分批处理
        for i in range(0, total, self.concurrency):
            batch = pending[i : i + self.concurrency]
            tasks = [self.process_shot(s, semaphore) for s in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # 展平异常
            flat_results = []
            for r in batch_results:
                if isinstance(r, Exception):
                    flat_results.append({"status": "failed", "error": str(r)})
                else:
                    flat_results.append(r)
            results.extend(flat_results)

            # 计数
            for r in flat_results:
                if r.get("status") == "completed":
                    completed_count += 1
                elif r.get("status") == "failed":
                    failed_count += 1

            # 保存进度
            completed_ids = [
                r["shot_id"] for r in results
                if r.get("status") in ("completed", "cached")
            ]
            self.state["completed_shots"] = completed_ids
            self.state["last_updated"] = datetime.now().isoformat()
            self.state["results"] = [
                {k: v for k, v in r.items() if k != "error"} for r in results
            ]
            save_state(self.episode, self.state)

            # 进度条
            pct = (i + len(batch)) / total * 100
            print(f"\n📊 进度: {min(pct, 100):.0f}% "
                  f"({i + len(batch)}/{total}) "
                  f"| ✅ {completed_count} | ❌ {failed_count}\n")

        # === 生成报告 ===
        print("\n" + "=" * 60)
        print("📋 生成报告")
        print("=" * 60)

        for r in results:
            sid = r.get("shot_id", "?")
            status = r.get("status", "?")
            icon = {"completed": "✅", "cached": "💾", "failed": "❌", "dry_run": "🔍"}.get(status, "❓")
            elapsed = r.get("elapsed_sec", 0)
            err = r.get("error", "")
            print(f"  {icon} 镜头 {sid:02d} | {status} | {elapsed:.0f}s", end="")
            if err:
                print(f" | {err[:60]}")
            else:
                print()

        # 保存最终报告
        report_path = self.output_ep_dir / "generation_report.json"
        report = {
            "episode": self.episode,
            "title": title,
            "generated_at": datetime.now().isoformat(),
            "total_shots": len(all_shots),
            "completed": completed_count,
            "failed": failed_count,
            "cached": sum(1 for r in results if r.get("status") == "cached"),
            "results": results,
        }
        self.output_ep_dir.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        completed_total = completed_count + sum(
            1 for r in results if r.get("status") == "cached"
        )
        print(f"\n✨ 完成! {completed_total}/{len(all_shots)} 镜头 | "
              f"报告: {report_path}")
        if failed_count:
            print(f"⚠️  {failed_count} 个镜头失败，可使用 --resume 重新处理")


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="星痕纪元 · Seedance 2.0 批量视频生成器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s                                      # 生成 EP01, 单并发
  %(prog)s --episode 2 --concurrency 3          # 生成 EP02, 3路并发
  %(prog)s --dry-run                             # 预览所有镜头, 不调用API
  %(prog)s --shots 1,5,8                         # 仅生成指定镜头
  %(prog)s --resume                               # 从中断处恢复
        """,
    )
    parser.add_argument(
        "--episode", "-e", type=int, default=1,
        help="集数 (默认: 1)"
    )
    parser.add_argument(
        "--concurrency", "-c", type=int, default=DEFAULT_CONCURRENCY,
        help=f"并发数 (默认: {DEFAULT_CONCURRENCY})"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="仅打印prompt不调用API"
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="从中断处恢复 (跳过已完成镜头)"
    )
    parser.add_argument(
        "--shots", type=str,
        help="仅处理指定镜头 (逗号分隔, 如: 1,5,8)"
    )
    parser.add_argument(
        "--api-key", type=str, default=DEFAULT_API_KEY,
        help="Seedance API Key (默认从 SEEDANCE_API_KEY 环境变量读取)"
    )
    parser.add_argument(
        "--endpoint", type=str, default=DEFAULT_SEEDANCE_ENDPOINT,
        help=f"Seedance API 端点 (默认: {DEFAULT_SEEDANCE_ENDPOINT})"
    )
    parser.add_argument(
        "--client-mode", type=str, choices=["api", "cli"], default="api",
        help="客户端模式: api (HTTP直连) 或 cli (seedance_client.py 子进程)"
    )
    parser.add_argument(
        "--client-script", type=str, default="seedance_client.py",
        help="CLI模式下 seedance_client.py 路径"
    )
    parser.add_argument(
        "--poll-interval", type=int, default=DEFAULT_POLL_INTERVAL,
        help=f"轮询间隔秒数 (默认: {DEFAULT_POLL_INTERVAL})"
    )
    parser.add_argument(
        "--max-wait", type=int, default=DEFAULT_MAX_WAIT,
        help=f"单镜头最大等待秒数 (默认: {DEFAULT_MAX_WAIT})"
    )

    args = parser.parse_args()

    # 解析仅处理镜头列表
    only_shots = None
    if args.shots:
        only_shots = [int(s.strip()) for s in args.shots.split(",") if s.strip()]

    # 选择客户端
    if args.client_mode == "cli":
        client = SeedanceCLIClient(
            client_script=args.client_script,
            endpoint=args.endpoint,
            api_key=args.api_key,
            poll_interval=args.poll_interval,
            max_wait=args.max_wait,
        )
    else:
        client = SeedanceClient(
            endpoint=args.endpoint,
            api_key=args.api_key,
            poll_interval=args.poll_interval,
            max_wait=args.max_wait,
        )

    # 运行
    generator = BatchGenerator(
        episode=args.episode,
        client=client,
        concurrency=args.concurrency,
        dry_run=args.dry_run,
        resume=args.resume,
        only_shots=only_shots,
    )

    try:
        asyncio.run(generator.run())
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断。使用 --resume 恢复。")
        sys.exit(130)
    except FileNotFoundError as e:
        print(f"❌ {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 运行异常: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
