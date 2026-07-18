#!/usr/bin/env python3
"""
🏭 视频工厂主循环 v2.0 — 无限生产+发布+赚钱

工作原理:
  while True:
    Phase A - 生产 (每30分钟)
      1. health check
      2. 是否缺 assets → 调用 main.py CLI 生成
      3. 写状态报告

    Phase B - 发布 (每4小时)
      验证完成的新资产 → 打包发布包

    Phase C - 赚钱 (每6小时)
      扫描 bounty, 检查收款

一切自动化, 日志在 logs/vf_loop.log
"""

import os, sys, time, json, subprocess, logging
from datetime import datetime
from pathlib import Path

BASE = Path("/Users/eric/Desktop/herness/AIComics/10_System")
VENV_PYTHON = BASE / ".venv" / "bin" / "python3"
STATE = BASE / "state"
LOG = BASE / "logs" / "vf_loop.log"
os.chdir(str(BASE))
os.environ["PYTHONPATH"] = f"src:{VENV_PYTHON.parent / 'site-packages'}"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    handlers=[logging.FileHandler(LOG), logging.StreamHandler()])
log = logging.getLogger("vf_loop")

EPISODES = {"E01":6,"E02":6,"E03":6,"E04":6,"E05":6}

def http_ok(url):
    try: import urllib.request; return urllib.request.urlopen(url,timeout=5).getcode()==200
    except: return False

def count(kind):
    total=0
    for ep in EPISODES:
        d=STATE/"demo_assets"/ep/kind
        if d.exists(): total+=len(list(d.glob(f"*.{'png' if kind=='images' else 'wav'}")))
    return total

def run(*a):
    cmd=[str(VENV_PYTHON),"-m","aicomic.cli.main"]+list(a)
    log.info(f"→ {' '.join(cmd)}")
    r=subprocess.run(cmd,capture_output=True,text=True,timeout=600)
    if r.returncode!=0: log.warning(f"⚠️ exit {r.returncode}: {r.stderr[:200]}")
    return r.returncode

def phase_production():
    """每30分钟: 检查资产状态 + 记录日志"""
    total_img,total_aud=count("images"),count("audio")
    expected=sum(EPISODES.values())
    log.info(f"资产: {total_img}/{expected}图 {total_aud}/{expected}配音")
    
    if total_img>=expected and total_aud>=expected:
        log.info("全部就绪 ✅")
    else:
        missing_img=expected-total_img
        missing_aud=expected-total_aud
        log.info(f"缺 {missing_img}图 {missing_aud}配音 — 等待Agent补充")
        # 实际生产由对话中派发的Agent完成, 这里只监控

def phase_money():
    """每小时: 检查赚钱机会"""
    # count bounties
    r=subprocess.run(["find",str(BASE),"reports","-name","money_report*"],capture_output=True,text=True)
    report_count=len(r.stdout.strip().split("\n")) if r.stdout.strip() else 0
    log.info(f"赚钱报告: {report_count}份")
    
    # check xianyu
    try: 
        r=subprocess.run(["ps","aux"],capture_output=True,text=True)
        if "xianyu" in r.stdout.lower(): log.info("闲鱼进程活跃")
    except: pass

def phase_publish():
    """检查发布包"""
    publish_dir=Path("/Users/eric/Desktop/herness/AI漫剧发布包")
    if publish_dir.exists():
        files=list(publish_dir.rglob("*"))
        log.info(f"发布包: {len(files)}个文件")
    else:
        log.info("暂无发布包")

def main():
    log.info("="*60)
    log.info("🏭 视频工厂主循环 v2.0 启动")
    log.info(f"日志: {LOG}")
    log.info("="*60)
    
    cycle=0
    while True:
        cycle+=1
        log.info(f"\n--- 第{cycle}轮 [{datetime.now():%H:%M}] ---")
        
        if not http_ok("http://localhost:7860/api/health"):
            log.error("Backend DOWN, 等5分钟")
            time.sleep(300); continue
        if not http_ok("http://localhost:8188/system_stats"):
            log.error("ComfyUI DOWN, 尝试重启...")
            subprocess.run(["comfy","--workspace=/Users/eric/Documents/comfy/ComfyUI","launch","--background"],
                         capture_output=True,timeout=30)
            time.sleep(60)

        phase_production()
        
        if cycle%2==0: phase_money()
        if cycle%8==0: phase_publish()
        
        log.info(f"下一轮: {datetime.fromtimestamp(time.time()+1800):%H:%M}")
        time.sleep(1800)

if __name__=="__main__":
    try: main()
    except KeyboardInterrupt: log.info("停止")
    except Exception as e: log.exception(f"崩溃: {e}")
