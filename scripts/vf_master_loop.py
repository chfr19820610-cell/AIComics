#!/usr/bin/env python3
"""
🏭 视频工厂主循环 v2.1 — 无限生产+发布+赚钱+自生产

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

    Phase D - 自生产 (每轮, 30/30就绪时激活)
      1. 检查 generated_projects/ 中是否有待生产项目
      2. 有→按时间顺序派发 build-season-jobs
      3. 全部清空→用随机参数 init-project 创建新演示内容

一切自动化, 日志在 logs/vf_loop.log
"""

import os, sys, time, json, subprocess, logging, random
from datetime import datetime
from pathlib import Path

BASE = Path("/Users/eric/Desktop/herness/AIComics/10_System")
VENV_PYTHON = BASE / ".venv" / "bin" / "python3"
STATE = BASE / "state"
LOG = BASE / "logs" / "vf_loop.log"
os.chdir(str(BASE))
os.environ["PYTHONPATH"] = "src"

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

def phase_self_produce():
    """Phase D: 当 30/30 全部就绪时, 自动创建新内容"""
    total_img, total_aud = count("images"), count("audio")
    expected = sum(EPISODES.values())

    # 只有当前资产全部就绪时才激活
    if total_img < expected or total_aud < expected:
        return False

    log.info("🎯 Phase D: 30/30全部就绪，检查自生产机会")

    # 1) 优先检查 generated_projects/ 中的待生产项目
    generated_root = STATE / "generated_projects"
    if generated_root and generated_root.exists():
        for proj_dir in sorted(generated_root.iterdir(), key=lambda p: p.stat().st_mtime):
            if not proj_dir.is_dir():
                continue
            manifest_file = proj_dir / "manifests" / "episode_manifest.json"
            if not manifest_file.exists():
                continue
            try:
                with open(manifest_file) as f:
                    manifest = json.load(f)
                project_id = manifest.get("project_id", proj_dir.name)
                episodes = manifest.get("episodes", [])
                incomplete = [ep for ep in episodes
                              if ep.get("status") in ("idea", "script_ready", "shotlist_ready")]
                if incomplete:
                    log.info(f"📦 发现待生产项目 [{project_id}]: {len(incomplete)}集待生产")
                    code = run("build-season-jobs", "--episode-manifest", str(manifest_file))
                    if code == 0:
                        log.info(f"✅ Phase D: [{project_id}] 任务已派发")
                    else:
                        log.warning(f"⚠️ Phase D: [{project_id}] build-season-jobs 失败 ({code})")
                    return True
            except Exception as e:
                log.warning(f"⚠️ Phase D: 读取 {manifest_file} 出错: {e}")

    # 2) 全部清空 — 用随机参数创建新演示项目
    log.info("🎲 Phase D: 全部清空，创建新演示内容")
    genres = [
        "现代职场逆袭", "校园僵尸喜剧", "古风仙侠", "都市悬疑", "奇幻冒险",
        "赛博朋克", "重生逆袭", "甜宠搞笑", "科幻末世", "民国谍战",
    ]
    styles = [
        "日系青春动画", "古风水墨", "赛博朋克", "复古手绘", "厚涂油画",
        "3D卡通渲染", "美式漫画", "水彩风格", "像素艺术", "浮世绘",
    ]

    genre = random.choice(genres)
    style = random.choice(styles)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    project_name = f"auto_{timestamp}"

    log.info(f"🎨 参数: genre={genre}, style={style}, name={project_name}")
    code = run(
        "init-project",
        "--project-name", project_name,
        "--genre", genre,
        "--style", style,
        "--episode-target-count", "3",
    )
    if code == 0:
        log.info(f"✅ Phase D: 新项目 [{project_name}] ({genre}/{style}) 创建成功")
    else:
        log.warning(f"⚠️ Phase D: 新建项目失败 (exit={code})")
    return True

def main():
    log.info("="*60)
    log.info("🏭 视频工厂主循环 v2.1 启动")
    log.info(f"日志: {LOG}")
    log.info("="*60)

    cycle = 0
    last_summary = ""    # 追踪资产状态变化

    while True:
        cycle += 1
        timestamp = datetime.now()
        log.info(f"\n--- 第{cycle}轮 [{timestamp:%H:%M}] ---")

        if not http_ok("http://localhost:7861/api/health"):
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

        # Phase D: 每轮检查自生产（只在 30/30 就绪时激活）
        phase_self_produce()

        # 状态变化检测
        total_img, total_aud = count("images"), count("audio")
        expected = sum(EPISODES.values())
        summary = f"图:{total_img}/{expected} 音:{total_aud}/{expected}"
        if summary != last_summary:
            log.info(f"📊 状态变化: {last_summary} → {summary}")
            last_summary = summary

        log.info(f"下一轮: {datetime.fromtimestamp(time.time()+1800):%H:%M}")
        time.sleep(1800)

if __name__=="__main__":
    try: main()
    except KeyboardInterrupt: log.info("停止")
    except Exception as e: log.exception(f"崩溃: {e}")
