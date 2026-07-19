#!/usr/bin/env python3
"""视频工厂无限自循环 — 最轻量的后台生产引擎

工作原理:
  while True:
    1. 检查系统健康 (backend + ComfyUI)
    2. 检查僵尸项目产出状态
    3. 补充缺失的图片和配音
    4. 构建并执行批次
    5. sleep 30分钟

用法:
  python3 scripts/video_factory_loop.py &
  # 或作为后台进程运行
"""

import os
import sys
import time
import json
import subprocess
import logging
from datetime import datetime
from pathlib import Path

# ── 配置 ──
BASE = Path("/Users/eric/Desktop/herness/AIComics/10_System")
VENV_PYTHON = BASE / ".venv" / "bin" / "python3"
STATE = BASE / "state"
LOG = BASE / "logs" / "video_factory_loop.log"
SLEEP_MINUTES = 30

EPISODES = ["E01", "E02", "E03", "E04", "E05"]
SHOTS_PER_EPISODE = {"E01": 6, "E02": 6, "E03": 6, "E04": 6, "E05": 6}

os.chdir(str(BASE))
os.environ["PYTHONPATH"] = f"src:{VENV_PYTHON.parent / 'site-packages'}"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG), logging.StreamHandler()],
)
log = logging.getLogger("vf_loop")


def http_ok(url: str) -> bool:
    try:
        import urllib.request
        return urllib.request.urlopen(url, timeout=5).getcode() == 200
    except Exception:
        return False


def count_assets(ep: str, kind: str) -> int:
    d = STATE / "demo_assets" / ep / kind
    if not d.exists():
        return 0
    return len(list(d.glob(f"*.{ 'png' if kind == 'images' else 'wav' }")))


def run_cli(*args: str) -> tuple[int, str]:
    cmd = [str(VENV_PYTHON), "-m", "aicomic.cli.main"] + list(args)
    log.info(f"RUN: {' '.join(cmd)}")
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        log.warning(f"EXIT {r.returncode}: {r.stderr[:200]}")
    return r.returncode, r.stdout + r.stderr


def health_check() -> bool:
    ok = True
    if not http_ok("http://localhost:7861/api/health"):
        log.error("Backend DOWN")
        ok = False
    if not http_ok("http://localhost:8188/system_stats"):
        log.error("ComfyUI DOWN")
        ok = False
    return ok


def production_run() -> dict:
    """一次生产运行: 检查缺失→生成→构建→执行"""
    report = {"generated_images": 0, "generated_audio": 0, "errors": []}

    for ep in EPISODES:
        expected = SHOTS_PER_EPISODE[ep]
        have_img = count_assets(ep, "images")
        have_aud = count_assets(ep, "audio")
        need_img = expected - have_img
        need_aud = expected - have_aud

        if need_img > 0 or need_aud > 0:
            log.info(f"{ep}: 缺 {need_img}图 {need_aud}配音 (已有 {have_img}图 {have_aud}配音)")

            # 用API方式补充: 调用 ComfyUI 和 Piper
            for s in range(1, expected + 1):
                sn = f"{ep}_S{s:02d}"
                img_path = STATE / "demo_assets" / ep / "images" / f"{sn}_key.png"
                aud_path = STATE / "demo_assets" / ep / "audio" / f"{sn}_tts.wav"

                # 如果缺图, 标记但继续
                if not img_path.exists():
                    report["generated_images"] += 1

                # 如果缺配音, 标记
                if not aud_path.exists():
                    report["generated_audio"] += 1

    # 构建并执行批次 (如果发现新资产)
    if report["generated_images"] > 0 or report["generated_audio"] > 0:
        log.info("有新的生产需求, 执行 build-season-jobs...")
        run_cli("build-season-jobs",
                "--project-id", "我变成僵尸后全校跪求我别死")

        log.info("执行 build-provider-requests...")
        run_cli("build-provider-requests")

        log.info("执行 execute-provider-requests...")
        run_cli("execute-provider-requests", "--confirm-live")

    return report


def summary(assets: dict) -> str:
    lines = [f"  视频工厂状态 ({datetime.now():%m-%d %H:%M})"]
    for ep in EPISODES:
        i = assets.get(ep, {}).get("images", 0)
        a = assets.get(ep, {}).get("audio", 0)
        exp = SHOTS_PER_EPISODE[ep]
        lines.append(f"  {ep}: {i}/{exp}图 {a}/{exp}配音 {'✅' if i>=exp and a>=exp else '⏳'}")
    return "\n".join(lines)


def main():
    log.info("=" * 50)
    log.info("视频工厂自循环引擎启动")
    log.info(f"间隔: {SLEEP_MINUTES}分钟")
    log.info(f"日志: {LOG}")
    log.info("=" * 50)

    cycle = 0
    while True:
        cycle += 1
        log.info(f"\n--- 第 {cycle} 轮 [{datetime.now():%H:%M}] ---")

        # 1. 健康检查
        if not health_check():
            log.warning("系统异常, 等待重试...")
            time.sleep(60 * 5)
            continue

        # 2. 检查资产状态
        assets = {}
        for ep in EPISODES:
            assets[ep] = {
                "images": count_assets(ep, "images"),
                "audio": count_assets(ep, "audio"),
            }
        log.info(f"\n{summary(assets)}")

        # 3. 如有缺失, 生产
        total_missing = sum(
            SHOTS_PER_EPISODE[ep] - assets[ep]["images"] + SHOTS_PER_EPISODE[ep] - assets[ep]["audio"]
            for ep in EPISODES
        )
        if total_missing > 0:
            log.info(f"总缺 {total_missing//2} 个资产, 执行生产...")
            rpt = production_run()
            log.info(f"生产结果: {rpt}")
        else:
            log.info("全部资产已就绪 ✅")

        # 4. 下一轮
        next_time = datetime.now().timestamp() + SLEEP_MINUTES * 60
        log.info(f"下一轮: {datetime.fromtimestamp(next_time):%H:%M}")
        time.sleep(SLEEP_MINUTES * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("收到停止信号, 退出")
    except Exception as e:
        log.exception(f"崩溃: {e}")
