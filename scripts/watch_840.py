#!/usr/bin/env python3
"""840 镜生成监控 + 自愈

每 5 分钟检查一次：
1. h3stream 进程是否活着（死了 → 重启批量）
2. 当前镜是否卡住（同一镜超过 40 分钟无新 output → kill 并重试）
3. 连续失败（≥3 次 → 告警并跳过）

用法: python scripts/watch_840.py
"""
import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path

BASE = Path("/Users/eric/Desktop/hermes/AlComics")
D = BASE / "state" / "projects" / "xianxia-12"
H3 = Path("/Users/eric/Desktop/hermes/tools/minimax-h3-stream-mac")
PY = BASE / ".venv" / "bin" / "python"
LOG = Path("/tmp/p6_watch.log")
BATCH_SCRIPT = Path("/tmp/batch_p6_align.sh")
STALL_MINUTES = 40
CHECK_INTERVAL = 300

EPS = ["E01", "E02", "E03", "E04", "E05", "E06",
       "E07", "E08", "E09", "E10", "E11", "E12"]


def log(msg):
    line = f"[{datetime.now().strftime('%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def count_done():
    total = 0
    per_ep = {}
    for ep in EPS:
        d = D / "assets" / ep / "h3video"
        n = len(list(d.glob("*.mp4"))) if d.exists() else 0
        per_ep[ep] = n
        total += n
    return total, per_ep


def h3_running():
    r = subprocess.run(["pgrep", "-f", "h3stream generate"],
                       capture_output=True, text=True)
    return bool(r.stdout.strip())


def batch_running():
    r = subprocess.run(["pgrep", "-f", "batch_p6_align"],
                       capture_output=True, text=True)
    return bool(r.stdout.strip())


def current_shot():
    """从 h3stream 进程的 --run-dir 参数找当前镜（最可靠）

    进程命令行含: --run-dir runs/p6_E01_S05
    """
    try:
        r = subprocess.run(["pgrep", "-a", "-f", "h3stream generate"],
                           capture_output=True, text=True)
        for line in r.stdout.splitlines():
            # runs/p6_E01_S05 → E01/S05
            import re
            m = re.search(r"p6_(E\d{2})_(S\d{2,3})", line)
            if m:
                return f"{m.group(1)}/{m.group(2)}"
    except Exception:
        pass
    # 回退：从日志找
    try:
        log = Path("/tmp/p6_align.log")
        if log.exists():
            lines = log.read_text(encoding="utf-8", errors="ignore").splitlines()
            for line in reversed(lines[-300:]):
                if "🎬" in line:
                    parts = line.split("🎬")
                    if len(parts) > 1:
                        return parts[1].strip().split()[0]
    except Exception:
        pass
    return None


def last_output_mtime(shot):
    """当前镜的 run-dir 最近文件时间"""
    if not shot:
        return None
    ep, sid = shot.split("/")
    rundir = H3 / "runs" / f"p6_{ep}_{sid}"
    if not rundir.exists():
        return None
    mtimes = [f.stat().st_mtime for f in rundir.rglob("*") if f.is_file()]
    return max(mtimes) if mtimes else None


def kill_h3():
    subprocess.run(["pkill", "-9", "-f", "h3stream generate"],
                   capture_output=True)
    time.sleep(3)


def start_batch():
    log("🚀 重启批量脚本")
    subprocess.Popen(["bash", str(BATCH_SCRIPT)],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    time.sleep(5)


def main():
    log("========== 840 镜监控启动 ==========")
    consecutive_fail = 0
    same_shot_checks = 0
    last_shot = None

    while True:
        total, per_ep = count_done()
        shot = current_shot()

        # 全完成？
        if total >= 840:
            log("🎉 全部 840 镜完成！")
            break

        # 记录
        if shot != last_shot:
            last_shot = shot
            same_shot_checks = 0
        else:
            same_shot_checks += 1

        status = "✅" if h3_running() else "❌"
        log(f"进度 {total}/840 | 当前 {shot or '无'} | h3stream {status} | 连续{consecutive_fail}次异常")

        # 1) h3stream 死了但批量还在 → 重启批量（会跳过已存在的）
        if not h3_running() and batch_running():
            log("⚠️ h3stream 进程消失但批量脚本还在，重启批量")
            kill_h3()
            time.sleep(5)
            start_batch()
            consecutive_fail += 1

        # 2) 批量脚本也死了 → 重启
        if not h3_running() and not batch_running():
            log("⚠️ h3stream 和批量脚本都没了，重启批量")
            start_batch()
            consecutive_fail += 1

        # 3) 同一镜超过 40 分钟无新文件 → 判定卡住
        mtime = last_output_mtime(shot)
        if mtime:
            stall = (time.time() - mtime) / 60
            if stall > STALL_MINUTES:
                log(f"⚠️ {shot} 已 {stall:.0f} 分钟无新文件，判定卡住，kill 重试")
                kill_h3()
                time.sleep(5)
                start_batch()
                consecutive_fail += 1

        # 连续异常 3 次 → 长等待
        if consecutive_fail >= 3:
            log("🔴 连续 3 次异常，等待 5 分钟后继续")
            consecutive_fail = 0
            time.sleep(300)

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
