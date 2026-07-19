#!/usr/bin/env python3
"""
E01/E02 占位符修复 — 生成 7 张真图 + 6 段真配音
（E02_S01_tts.wav 已是真实文件，无需重做）
"""

import json
import os
import random
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ── 路径配置 ──
BASE = Path("/Users/eric/Desktop/herness/AIComics/10_System")
COMFY_API = "http://127.0.0.1:8188"
COMFY_OUTPUT = Path("/Users/eric/Documents/comfy/ComfyUI/output")
WORKFLOW_PATH = Path(
    "/Users/eric/Desktop/herness/saas-project/assets/workflows/animagine_xl4_txt2img.json"
)
VENV_PYTHON = BASE / ".venv" / "bin" / "python3"
PIPER_PKG_DIR = BASE / "local_providers" / "piper" / "python"
PIPER_MODEL = (
    BASE / "local_providers" / "piper" / "models" / "zh_CN-huayan-medium.onnx"
)

def log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:12]
    print(f"[{ts}] {msg}", flush=True)


# ════════════════════════════════════════════════════════════
# 1. 提示词 & 台词
# ════════════════════════════════════════════════════════════

E01_PROMPTS = {
    "S01": {
        "prompt_g": "anime scene, morning campus, male student walking on tree-lined path, sunlight filtering through leaves, warm morning atmosphere, youthful school life, japanese anime style, soft lighting, green foliage, detailed background, high quality, best quality, masterpiece",
        "prompt_l": "campus path, morning sunlight, trees, male student walking, school building background, peaceful atmosphere,青春校园,日系动漫",
    },
    "S02": {
        "prompt_g": "anime scene, dark alley after school, shadow figure suddenly attacking male student, biting, horror tension, dynamic action composition, dusk lighting, dramatic shadows, intense moment, fast movement blur, thrilling atmosphere, high quality, best quality, masterpiece",
        "prompt_l": "dark alley, attack scene, shadow figure biting, surprised male student, evening light, horror tension, dynamic pose, thrilling",
    },
    "S03": {
        "prompt_g": "anime scene, classroom interior, male student's hand turning grayish-green, classmates terrified pointing, female teacher shouting monster, oppressive atmosphere, cold color palette, fluorescent lighting, frightened expressions, school setting, dramatic moment, high quality, best quality, masterpiece",
        "prompt_l": "classroom, scared students, teacher shouting monster, mutated hand, cold tones, fear, horror, shocked expressions, school desk",
    },
    "S04": {
        "prompt_g": "anime scene, classroom, female class leader Lin Xue standing protectively in front of male protagonist, shouting at classmates, warm lighting, medium shot, determined expression, protective pose, emotional scene, defensive stance, detailed character expressions, high quality, best quality, masterpiece",
        "prompt_l": "girl protecting boy, classroom, determined expression, warm light, shouting not a monster, emotional, protective stance, medium shot",
    },
}

E02_PROMPTS = {
    "S01": {
        "prompt_g": "anime scene, school infirmary interior, Lin Xue and Chen Mo in medical room, school nurse staring in shock at healing wound, sterile white lighting, tense atmosphere, medical bed, cabinets, clinical setting, surprised expressions, dramatic reveal, high quality, best quality, masterpiece",
        "prompt_l": "infirmary, medical room, nurse shocked, healing wound, tense moment, white lighting, clinical atmosphere, surprised faces",
    },
    "S02": {
        "prompt_g": "anime scene, close up of hand, palm wound rapidly healing, glowing effect, Lin Xue watching in shock, special effect light, detailed skin texture, healing process visible, amazed expression, dramatic lighting, scientific fantasy atmosphere, high quality, best quality, masterpiece",
        "prompt_l": "hand close up, wound healing, glowing, regeneration power, shocked girl watching, special effects, detailed close up view",
    },
    "S03": {
        "prompt_g": "anime scene, school sports field, physical education class, male student accidentally demonstrating super strength, classmates gathering around in surprise, sunny outdoor lighting, wide angle perspective, sports field background, amazed crowd, dramatic moment, dynamic pose, high quality, best quality, masterpiece",
        "prompt_l": "sports field, PE class, strength display, surprised classmates, sunny day, wide view, accidental power show, crowd gathering",
    },
}

E01_DIALOGUE = {
    "S01": "清晨的阳光透过树叶洒在校园的林荫道上，陈默背着书包走在前往教室的路上。微风拂过，带来一天新的开始，他却不知道今天将彻底改变他的命运。",
    "S02": "放学后的小巷里，陈默正低头走着。突然，一道黑影从角落窜出，狠狠地咬中了他的手臂。剧痛袭来，他惊恐地发现——那竟然是一个人形的怪物！",
    "S03": "教室内，陈默的手开始变得青灰，指甲迅速变长。周围的同学惊恐地后退，女老师尖声喊道：怪物！快叫保安！整个教室陷入一片恐慌之中。",
    "S04": "就在所有人都在喊打喊杀的时候，班长林雪大步上前，张开双臂挡在陈默身前：他不是怪物！给我闭嘴！她的声音坚定而有力，让整个教室瞬间安静了下来。",
}

E02_DIALOGUE = {
    "S01": "医务室里，校医难以置信地看着陈默手臂上的伤口。那道被咬的伤痕，正在以肉眼可见的速度愈合。校医的手在颤抖：这、这怎么可能……",
    "S02": "陈默摊开手掌，一道新鲜的伤口正在快速愈合。林雪瞪大了眼睛，不可思议地看着这一幕。伤口边缘泛着微弱的蓝光，几秒钟之内就完全消失了。",
    "S03": "体育课上，陈默不小心用力过猛，手中的铅球飞出超出了正常距离好几倍。周围的同学纷纷侧目，惊叹声此起彼伏。陈默赶紧低下头，假装什么都没发生。",
}


# ════════════════════════════════════════════════════════════
# 2. ComfyUI API 调用
# ════════════════════════════════════════════════════════════

def comfyui_submit(workflow: dict, timeout_submit: int = 60, timeout_poll: int = 360) -> str | None:
    seed = random.randint(1, 999999999999)
    for nid, node in workflow.items():
        if isinstance(node, dict) and "seed" in node.get("inputs", {}):
            node["inputs"]["seed"] = seed

    payload = json.dumps({"prompt": workflow}).encode("utf-8")
    req = urllib.request.Request(
        f"{COMFY_API}/prompt",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        resp = urllib.request.urlopen(req, timeout=timeout_submit)
        result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        log(f"  ⚠ HTTP {e.code} 提交失败: {body[:200]}")
        return None
    except Exception as e:
        log(f"  ⚠ 提交异常: {e}")
        return None

    prompt_id = result.get("prompt_id")
    if not prompt_id:
        log(f"  ⚠ 无 prompt_id: {result}")
        return None

    log(f"  已提交 prompt_id={prompt_id[:12]}… seed={seed}")

    # 轮询
    start = time.time()
    interval = 2.0
    while time.time() - start < timeout_poll:
        time.sleep(interval)
        interval = min(8.0, interval * 1.3)

        try:
            req2 = urllib.request.Request(f"{COMFY_API}/history/{prompt_id}")
            resp2 = urllib.request.urlopen(req2, timeout=30)
            hist = json.loads(resp2.read())
        except Exception:
            continue

        entry = hist.get(prompt_id) if isinstance(hist, dict) else None
        if not isinstance(entry, dict):
            continue

        st = entry.get("status", {})
        if st.get("completed", False):
            elapsed = time.time() - start
            log(f"  完成！耗时 {elapsed:.1f}s")
            return prompt_id

        if st.get("status_str") == "error":
            err_msg = st.get("error_messages", ["未知错误"])
            log(f"  ✗ ComfyUI 执行错误: {err_msg}")
            return None

    log(f"  ✗ 超时 {timeout_poll}s（prompt_id={prompt_id}）")
    return None


def copy_from_comfyui_output(prefix: str, dest_path: Path) -> bool:
    """从 ComfyUI output 目录搜索最新同名文件并拷贝到目标路径。"""
    candidates = list(COMFY_OUTPUT.glob(f"{prefix}*.png"))
    if not candidates:
        candidates = list(COMFY_OUTPUT.glob(f"{prefix}*.PNG"))
    if not candidates:
        log(f"  ⚠ 未在 output 中找到 {prefix}")
        return False

    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    src = candidates[0]
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(src), str(dest_path))
    size = dest_path.stat().st_size
    log(f"  ✅ 图片已就位: {dest_path.name} ({size:,} bytes)")
    return True


def generate_one_image(episode: str, scene: str, prompt_data: dict) -> bool:
    """生成一张图：加载 workflow → 注入提示词 → 提交 → 取回。"""
    dest = (
        BASE / "state" / "demo_assets" / episode / "images" / f"{episode}_{scene}_key.png"
    )
    if dest.exists():
        log(f"  {episode}_{scene}: 图片已存在，跳过")
        return True

    # 加载 workflow 模板
    try:
        with open(WORKFLOW_PATH) as f:
            wf = json.load(f)
    except Exception as e:
        log(f"  ✗ 读取 workflow 模板失败: {e}")
        return False

    # 注入提示词与文件名
    prefix = f"{episode}_{scene}_key"
    for nid, node in wf.items():
        ct = node.get("class_type", "")
        if ct == "CLIPTextEncodeSDXL":
            title = node.get("_meta", {}).get("title", "")
            if "Positive" in title or "positive" in title:
                node["inputs"]["text_g"] = prompt_data.get("prompt_g", "")
                node["inputs"]["text_l"] = prompt_data.get("prompt_l", "")
        elif ct == "SaveImage":
            node["inputs"]["filename_prefix"] = prefix

    # 提交 + 重试 (最多3次)
    prompt_id = None
    for attempt in range(1, 4):
        log(f"  尝试 #{attempt}...")
        prompt_id = comfyui_submit(wf, timeout_poll=360)
        if prompt_id:
            break
        if attempt < 3:
            wait = 5 * attempt
            log(f"  等待 {wait}s 后重试...")
            time.sleep(wait)

    if not prompt_id:
        log(f"  ✗ {episode}_{scene}: 所有重试均失败")
        return False

    # 从 ComfyUI output 取回
    ok = copy_from_comfyui_output(prefix, dest)
    return ok


def generate_images(episode: str, prompts: dict) -> tuple:
    success = 0
    total = len(prompts)
    for scene in sorted(prompts.keys()):
        log(f"\n── [{episode}_{scene}] 开始出图 ──")
        ok = generate_one_image(episode, scene, prompts[scene])
        if ok:
            success += 1
        time.sleep(1)
    return success, total


# ════════════════════════════════════════════════════════════
# 3. Piper TTS 配音
# ════════════════════════════════════════════════════════════

def generate_one_audio(episode: str, scene: str, text: str) -> bool:
    audio_dir = BASE / "state" / "demo_assets" / episode / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    output_path = audio_dir / f"{episode}_{scene}_tts.wav"

    if output_path.exists():
        log(f"  {episode}_{scene}: 配音已存在，跳过")
        return True

    log(f"  配音内容: \"{text[:40]}…\" ({len(text)} 字)")

    cmd = [
        str(VENV_PYTHON),
        "-c",
        """
import sys
sys.path.insert(0, sys.argv[1])   # PIPER_PKG_DIR
from piper.__main__ import main
sys.argv = [
    'piper',
    '--model', sys.argv[2],
    '--output_file', sys.argv[3],
]
import io
sys.stdin = io.StringIO(sys.argv[4])
try:
    main()
except SystemExit as e:
    pass
""",
        str(PIPER_PKG_DIR),
        str(PIPER_MODEL),
        str(output_path),
        text,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(BASE),
        )
        if result.returncode == 0 and output_path.exists():
            size = output_path.stat().st_size
            log(f"  ✅ 配音就位: {output_path.name} ({size:,} bytes)")
            return True
        else:
            stderr_short = (result.stderr or "")[:200]
            log(f"  ✗ Piper 失败 (rc={result.returncode}): {stderr_short}")
            return False
    except subprocess.TimeoutExpired:
        log(f"  ✗ Piper 超时 120s")
        return False
    except Exception as e:
        log(f"  ✗ Piper 异常: {e}")
        return False


def generate_audio(episode: str, dialogues: dict) -> tuple:
    success = 0
    total = len(dialogues)
    for scene in sorted(dialogues.keys()):
        log(f"\n── [{episode}_{scene}] 开始配音 ──")
        ok = generate_one_audio(episode, scene, dialogues[scene])
        if ok:
            success += 1
        time.sleep(0.5)
    return success, total


# ════════════════════════════════════════════════════════════
# 4. 验证
# ════════════════════════════════════════════════════════════

def verify():
    all_ok = True
    required = {
        "E01": {
            "images": ["S01", "S02", "S03", "S04", "S05", "S06"],
            "audio": ["S01", "S02", "S03", "S04", "S05", "S06"],
        },
        "E02": {
            "images": ["S01", "S02", "S03", "S04", "S05", "S06"],
            "audio": ["S01", "S02", "S03", "S04", "S05", "S06"],
        },
    }
    for ep, scenes in required.items():
        for sn in scenes["images"]:
            p = BASE / "state" / "demo_assets" / ep / "images" / f"{ep}_{sn}_key.png"
            if not p.exists():
                log(f"  ❌ 缺失图片: {ep}_{sn}_key.png")
                all_ok = False
            elif p.stat().st_size < 100000:
                log(f"  ⚠ 图片太小: {ep}_{sn}_key.png ({p.stat().st_size:,} bytes)")
                all_ok = False
            else:
                log(f"  ✅ {ep}_{sn}_key.png ({p.stat().st_size:,} bytes)")
        for sn in scenes["audio"]:
            p = BASE / "state" / "demo_assets" / ep / "audio" / f"{ep}_{sn}_tts.wav"
            if not p.exists():
                log(f"  ❌ 缺失配音: {ep}_{sn}_tts.wav")
                all_ok = False
            elif p.stat().st_size < 20000:
                log(f"  ⚠ 配音太小: {ep}_{sn}_tts.wav ({p.stat().st_size:,} bytes)")
                all_ok = False
            else:
                log(f"  ✅ {ep}_{sn}_tts.wav ({p.stat().st_size:,} bytes)")

    if all_ok:
        log("  ✅ 全部文件验证通过！")
    else:
        log("  ❌ 验证未通过，存在缺失或文件过小")
    return all_ok


# ════════════════════════════════════════════════════════════
# 5. 主流程
# ════════════════════════════════════════════════════════════

def main():
    print("=" * 60, flush=True)
    print(" E01/E02 占位符修复", flush=True)
    print("=" * 60, flush=True)

    # Step 1: E01 图片 (S01-S04)
    log("\n═══ Step 1/4: E01 图片 ═══")
    e01_img_ok, e01_img_total = generate_images("E01", E01_PROMPTS)
    log(f"  E01 图片: {e01_img_ok}/{e01_img_total}")

    # Step 2: E01 配音 (S01-S04)
    log("\n═══ Step 2/4: E01 配音 ═══")
    e01_aud_ok, e01_aud_total = generate_audio("E01", E01_DIALOGUE)
    log(f"  E01 配音: {e01_aud_ok}/{e01_aud_total}")

    # Step 3: E02 图片 (S01-S03)
    log("\n═══ Step 3/4: E02 图片 ═══")
    e02_img_ok, e02_img_total = generate_images("E02", E02_PROMPTS)
    log(f"  E02 图片: {e02_img_ok}/{e02_img_total}")

    # Step 4: E02 配音 (S01-S03; 但 S01 已存在)
    log("\n═══ Step 4/4: E02 配音 ═══")
    e02_aud_ok, e02_aud_total = generate_audio("E02", E02_DIALOGUE)
    log(f"  E02 配音: {e02_aud_ok}/{e02_aud_total}")

    # 验证
    log("\n═══ 验证 ═══")
    verify()

    print("\n" + "=" * 60, flush=True)
    print(" 生产完成", flush=True)
    print("=" * 60, flush=True)


if __name__ == "__main__":
    main()
