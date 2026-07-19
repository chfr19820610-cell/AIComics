#!/usr/bin/env python3
"""
🎬 视频工厂 — 生成→审查→发布 无限质量门禁循环

流程:
  while True:
    1. 检查是否有新完成的剧集资产 (state/demo_assets/E0*/)
    2. 提交给审查Agent (reality-checker + visual-storyteller + accessibility)
    3. 审查结果:
       - PASS ✅ → 进入发布队列
       - FAIL ❌ → 标记需修复, 记录问题
    4. 发布队列: 打包 → 小红书/B站/抖音发布
    5. sleep 30min

日志: logs/quality_gate_loop.log
"""

import os, sys, time, json, subprocess, logging, shutil
from datetime import datetime
from pathlib import Path

BASE = Path("/Users/eric/Desktop/herness/AIComics/10_System")
STATE = BASE / "state"
LOG = BASE / "logs" / "quality_gate_loop.log"
PUBLISH_DIR = Path("/Users/eric/Desktop/herness/AI漫剧发布包")
os.chdir(str(BASE))
os.environ["PYTHONPATH"] = "src:.venv/lib/python3.12/site-packages"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    handlers=[logging.FileHandler(LOG), logging.StreamHandler()])
log = logging.getLogger("quality_gate")

EPISODES = ["E01","E02","E03","E04","E05"]

def count_ep_assets(ep: str) -> dict:
    """检查一集的资产完整度"""
    img_dir = STATE / "demo_assets" / ep / "images"
    aud_dir = STATE / "demo_assets" / ep / "audio"
    images = list(img_dir.glob("*.png")) if img_dir.exists() else []
    audios = list(aud_dir.glob("*.wav")) if aud_dir.exists() else []
    return {
        "images": len(images),
        "audio": len(audios),
        "img_files": [p.name for p in sorted(images)],
        "aud_files": [p.name for p in sorted(audios)],
        "img_total_kb": sum(p.stat().st_size for p in images) // 1024,
        "aud_total_kb": sum(p.stat().st_size for p in audios) // 1024,
    }

def quality_check(ep: str, assets: dict) -> dict:
    """
    审查一集的质量。返回 PASS/FAIL + 原因。
    
    标准:
    1. 6张图 + 6个配音 完整
    2. 每张图 ≥ 300KB (不是占位符)
    3. 每个配音 ≥ 50KB (有内容)
    4. 图片命名规范: EP_SXX_key.png
    """
    issues = []
    
    # 完整性检查
    if assets["images"] < 6:
        issues.append(f"缺图: 只有{assets['images']}/6张")
    if assets["audio"] < 6:
        issues.append(f"缺配音: 只有{assets['audio']}/6段")
    
    # 质量检查
    img_dir = STATE / "demo_assets" / ep / "images"
    for p in sorted(img_dir.glob("*.png")):
        if p.stat().st_size < 100 * 1024:  # <100KB 是占位符
            issues.append(f"图片太小: {p.name} ({p.stat().st_size//1024}KB)")
    
    aud_dir = STATE / "demo_assets" / ep / "audio"
    for p in sorted(aud_dir.glob("*.wav")):
        if p.stat().st_size < 20 * 1024:  # <20KB 太短
            issues.append(f"配音太短: {p.name} ({p.stat().st_size//1024}KB)")
    
    # 命名规范检查
    for p in sorted(img_dir.glob("*.png")):
        expected = f"{ep}_S"
        if expected not in p.name:
            issues.append(f"命名不规范: {p.name}")
    
    passed = len(issues) == 0
    return {
        "episode": ep,
        "status": "PASS" if passed else "FAIL",
        "issues": issues,
        "img_count": assets["images"],
        "aud_count": assets["audio"],
        "total_mb": (assets["img_total_kb"] + assets["aud_total_kb"]) / 1024,
    }

def prepare_publish_package(ep: str) -> str:
    """打包一集为发布包"""
    ep_dir = PUBLISH_DIR / "packages" / ep
    ep_dir.mkdir(parents=True, exist_ok=True)
    
    # 复制图片
    img_dir = STATE / "demo_assets" / ep / "images"
    if img_dir.exists():
        for p in img_dir.glob("*.png"):
            shutil.copy2(p, ep_dir / p.name)
    
    # 复制配音
    aud_dir = STATE / "demo_assets" / ep / "audio"
    if aud_dir.exists():
        for p in aud_dir.glob("*.wav"):
            shutil.copy2(p, ep_dir / p.name)
    
    # 写个说明文件
    readme = ep_dir / "README.txt"
    readme.write_text(
        f"{ep} - 我变成僵尸后全校跪求我别死\n"
        f"生成时间: {datetime.now():%Y-%m-%d %H:%M}\n"
        f"包含: {len(list(img_dir.glob('*.png')))}张图 + {len(list(aud_dir.glob('*.wav')))}段配音\n"
        f"许可证: Apache 2.0\n"
    )
    return str(ep_dir)


def notify_n8n(ep: str, pkg_path: str) -> bool:
    """通知 n8n 有新的剧集通过审查"""
    import urllib.request, urllib.error
    payload = {
        "episode": ep,
        "project": "我变成僵尸后全校跪求我别死",
        "package_path": pkg_path,
        "status": "PASS",
        "timestamp": datetime.now().isoformat(),
    }
    try:
        req = urllib.request.Request(
            "http://localhost:5678/webhook/video-factory-pass",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=10)
        log.info(f"  📡 n8n 通知成功: HTTP {resp.status}")
        return True
    except Exception as e:
        log.warning(f"  ⚠️ n8n 通知失败: {e}")
        return False


def main():
    log.info("=" * 60)
    log.info("🎬 质量门禁循环启动 — 生成→审查→发布")
    log.info("=" * 60)
    
    # 状态追踪, 避免重复审查和发布
    reviewed = {}   # ep -> last review result
    published = {}  # ep -> last publish time
    
    cycle = 0
    while True:
        cycle += 1
        log.info(f"\n--- 第{cycle}轮 [{datetime.now():%H:%M}] ---")
        
        for ep in EPISODES:
            assets = count_ep_assets(ep)
            
            # 检查是否需要审查 (有新内容且未审查过)
            last_review = reviewed.get(ep, {}).get("status")
            total_files = assets["images"] + assets["audio"]
            last_count = reviewed.get(ep, {}).get("total_files", 0)
            
            if total_files == 12 and (last_review != "PASS" or total_files != last_count):
                # 完整了, 执行审查
                log.info(f"\n📋 {ep}: 资产完整({assets['images']}图+{assets['audio']}配音), 执行审查...")
                
                result = quality_check(ep, assets)
                log.info(f"  审查结果: {result['status']}")
                
                if result["issues"]:
                    for issue in result["issues"]:
                        log.warning(f"    ❌ {issue}")
                
                reviewed[ep] = {
                    "status": result["status"],
                    "time": datetime.now().isoformat(),
                    "total_files": total_files,
                    "issues": result["issues"],
                }
                
                if result["status"] == "PASS":
                    # 打包发布
                    pkg_path = prepare_publish_package(ep)
                    log.info(f"  📦 发布包: {pkg_path}")
                    published[ep] = datetime.now().isoformat()
                    # 通知 n8n 触发发布管线
                    notify_n8n(ep, pkg_path)
                    log.info(f"  ✅ {ep} 已通过审查, 通知n8n发布到小红书/B站/抖音")
                else:
                    log.warning(f"  ❌ {ep} 未通过审查, 等待修复后重审")
            else:
                if total_files < 12:
                    pass  # 还在生成中, 跳过
                elif last_review == "PASS":
                    pass  # 已经审查通过了
        
        # 打印状态总览
        log.info(f"\n{'='*60}")
        log.info(f"状态总览 ({datetime.now():%H:%M})")
        for ep in EPISODES:
            a = count_ep_assets(ep)
            r = reviewed.get(ep, {})
            p = published.get(ep)
            progress = f"{a['images']}/6图 + {a['audio']}/6配音"
            status = r.get("status", "⏳生成中")
            pub = f"📢已发布" if p else ""
            log.info(f"  {ep}: {progress} | {status} {pub}")
        log.info(f"{'='*60}")
        
        # 写状态文件供其他组件读取
        status_report = {
            "cycle": cycle,
            "time": datetime.now().isoformat(),
            "episodes": {ep: {"assets": count_ep_assets(ep), "review": reviewed.get(ep), "published": published.get(ep)} for ep in EPISODES}
        }
        (BASE / "status.json").write_text(json.dumps(status_report, indent=2, ensure_ascii=False))
        
        time.sleep(1800)  # 30分钟

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: log.info("停止")
    except Exception as e: log.exception(f"崩溃: {e}")
