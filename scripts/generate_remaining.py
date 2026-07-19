#!/usr/bin/env python3
"""
E04/E05 高效生成 — 健壮脚本
- 超时/重试/日志
- 出 9 张图 (E04 S04-S06, E05 S01-S06) + 12 个配音
- 从 ComfyUI output 目录取回图片
- 用 local_providers piper 生成配音
"""

import json
import os
import random
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

# ── 环境变量：让 piper 能找到 local_providers 里的 onnxruntime ──
PIPER_ENV = {**os.environ, "PYTHONPATH": str(PIPER_PKG_DIR)}


def log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:12]
    print(f"[{ts}] {msg}", flush=True)


# ════════════════════════════════════════════════════════════
# 1. 提示词 & 台词（沿用已有脚本的内容）
# ════════════════════════════════════════════════════════════

E04_PROMPTS = {
    "S01": {
        "prompt_g": "anime scene, school gate confrontation, heroic male protagonist fighting purifiers, dramatic combat, dust and debris flying, glowing energy effects, wide angle, detailed background, intense action pose, sunset lighting, dynamic composition, high quality, best quality, masterpiece",
        "prompt_l": "school gate, fight, action, male protagonist injured but standing, heroic, dramatic, intense battle, sparks, dust, cinematic composition",
    },
    "S02": {
        "prompt_g": "anime scene, school parking lot, purifiers assembling in tactical formation, armored figures, military vehicles, tense atmosphere, overcast sky, wide shot, detailed character designs, dark color palette, dramatic lighting, high quality, best quality, masterpiece",
        "prompt_l": "parking lot, armed group gathering, armored suits, weapons, vehicles, dark atmosphere, preparation for battle, intense mood",
    },
    "S03": {
        "prompt_g": "anime scene, school boiler room interior, narrow corridor, male protagonist shielding group members, steam pipes, dim lighting, warm orange glow from pipes, desperate defense, action pose, dramatic shadows, intense expression, high quality, best quality, masterpiece",
        "prompt_l": "boiler room, steam pipes, narrow space, protagonist protecting others, defensive stance, warm lighting, dark shadows, tense moment",
    },
    "S04": {
        "prompt_g": "anime scene, empty street at dusk, male protagonist fleeing alone, surrounded by enemies on all sides, cornered, desperate expression, urban environment, dark alleyways, dramatic lighting, lonely atmosphere, rain or wet ground reflections, high quality, best quality, masterpiece",
        "prompt_l": "fleeing alone, surrounded, cornered in alley, dusk, rain, desperate running, lonely, hopeless situation, action scene",
    },
    "S05": {
        "prompt_g": "anime scene, church interior dramatic reveal, xiaolin revealed as traitor, shocking expression on protagonist's face, dramatic lighting through stained glass, dark figures, betrayal moment, intense emotional atmosphere, cinematic composition, best quality, masterpiece",
        "prompt_l": "church interior, betrayal reveal, xiaolin identity exposed, shocked protagonist, stained glass light, dramatic moment, emotional scene",
    },
    "S06": {
        "prompt_g": "anime scene, purifier commander giving orders, massive army behind, silhouette against bright light, commanding presence, dramatic sky, epic scale, wide shot, army of armored figures, dark dramatic atmosphere, high quality, best quality, masterpiece",
        "prompt_l": "commander giving orders, army of purifiers, silhouettes, epic scale, dramatic sky, war preparation, powerful leader, army formation",
    },
}

E05_PROMPTS = {
    "S01": {
        "prompt_g": "anime scene, emotional reconciliation, female protagonist forgiving xiaolin, tearful embrace, warm sunlight streaming through window, healing atmosphere, soft lighting, heartfelt emotional moment, warm color palette, close up, best quality, masterpiece",
        "prompt_l": "forgiveness, emotional embrace, tears, warm sunlight, healing, reconciliation, heartfelt, soft warm colors, close up",
    },
    "S02": {
        "prompt_g": "anime scene, assault on purifier headquarters, group of protagonists storming building, action poses, glowing weapons, explosions, dynamic combat, wide angle action shot, intense battle, cinematic lighting, destroyed entrance, high quality, best quality, masterpiece",
        "prompt_l": "assault, storming headquarters, group attack, action combat, explosions, dynamic movement, breaking through entrance",
    },
    "S03": {
        "prompt_g": "anime scene, laboratory interior, rescuing director's daughter, glass tubes and scientific equipment, high tech environment, blue and white lighting, protagonist reaching out, rescue moment, dramatic highlight, detailed lab equipment, best quality, masterpiece",
        "prompt_l": "laboratory rescue, glass tubes, high tech, blue lighting, saving girl, reaching hand, scientific equipment, hopeful moment",
    },
    "S04": {
        "prompt_g": "anime scene, shocking identity reveal, purifier leader's face revealed as deceased principal's daughter, gasping crowd, dramatic spotlight, dual portrait visual, emotional confrontation, half shadow half light, cinematic composition, best quality, masterpiece",
        "prompt_l": "identity reveal, leader removes mask, daughter of deceased principal, shocked crowd, dramatic lighting, emotional confrontation",
    },
    "S05": {
        "prompt_g": "anime scene, school rooftop,全校师生 standing together to protect female protagonist, students forming human shield, diverse characters united, sunrise lighting, heroic composition, wide shot, inspirational atmosphere, warm hopeful colors, best quality, masterpiece",
        "prompt_l": "school rooftop, all students united, protecting the heroine, human shield, sunrise, inspirational, solidarity, hope, wide shot",
    },
    "S06": {
        "prompt_g": "anime scene, dawn at school campus, zombie fully cured, protagonist restored to human, couple embracing in cherry blossom rain, happy ending, vibrant colors, blooming sakura trees, golden morning light, peaceful hopeful atmosphere, cinematic composition, best quality, masterpiece",
        "prompt_l": "dawn, cherry blossoms, complete cure, happy ending, embrace, golden light, peaceful, hope restored, sakura petals falling, romantic",
    },
}

E04_DIALOGUE = {
    "S01": '校门口，男主独自面对净化者先锋队。他握紧拳头，眼神坚定："我绝不会让你们伤害这里的任何人！"',
    "S02": '停车场内，净化者主力正在集结。装甲车辆缓缓驶入，全副武装的战士们列队整齐，空气中弥漫着肃杀的气息。',
    "S03": '锅炉房里，男主掩护着受伤的同伴撤退。蒸汽管道不断爆裂，白色的雾气中，他的身影显得格外英勇。',
    "S04": '男主孤身逃亡在空无一人的街道上。身后追兵越来越近，前方却是死胡同。他咬着牙："只能拼了……"',
    "S05": '教堂内，小林摘下伪装的面具。女主难以置信地后退两步："小林……怎么会是你？"小林低下头："对不起，我别无选择。"',
    "S06": '净化者首领高举手臂："全员听令——天亮之前，把整个学校给我夷为平地！"身后的军队整齐前进，大地为之震动。',
}

E05_DIALOGUE = {
    "S01": '女主轻轻握住小林的手："我原谅你了。每个人都会有身不由己的时候，欢迎回来。"小林泪流满面，紧紧抱住了她。',
    "S02": '突击队冲破净化者总部的大门！男主一马当先："跟我冲——救人要紧！"身后，战友们紧随其后，气势如虹。',
    "S03": '实验室内，主任的女儿被关在玻璃容器中。男主砸碎控制台："找到你了！别怕，我带你回家！"蓝光闪烁中，她睁开了眼睛。',
    "S04": '净化者首领缓缓摘下面罩。女主震惊地后退："你是……已故校长的女儿？！"首领眼中含泪："我只是想……为父亲报仇。"',
    "S05": '天台上，全校师生站了出来，将女主护在身后。班长高喊："谁敢动她，先过我们这关！"几百人齐声响应，气势磅礴。',
    "S06": '黎明破晓，樱花纷飞。男主体内的僵尸毒素完全清除，恢复了正常人的体温。两人在樱花树下紧紧相拥，新的一天终于来临。',
}


# ════════════════════════════════════════════════════════════
# 2. ComfyUI API 调用
# ════════════════════════════════════════════════════════════


def comfyui_submit(workflow: dict, timeout_submit: int = 60, timeout_poll: int = 300) -> str | None:
    """提交 workflow，轮询直到完成，返回 prompt_id；超时或失败返回 None。"""
    # 随机化种子
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

    if result.get("node_errors"):
        for nid, errs in result["node_errors"].items():
            log(f"  ⚠ Node {nid} 错误: {errs}")
        # 继续等 — 有些错误不影响执行

    log(f"  已提交 prompt_id={prompt_id[:12]}… seed={seed}")

    # ── 轮询完成 ──
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
    # ComfyUI 输出格式: {prefix}_00001_.png
    candidates = list(COMFY_OUTPUT.glob(f"{prefix}*.png"))
    if not candidates:
        candidates = list(COMFY_OUTPUT.glob(f"{prefix}*.PNG"))
    if not candidates:
        log(f"  ⚠ 未在 output 中找到 {prefix}")
        return False

    # 按修改时间排序，取最新的
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    src = candidates[0]
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    import shutil
    shutil.copy2(str(src), str(dest_path))
    size = dest_path.stat().st_size
    log(f"  ✅ 图片已就位: {dest_path.name} ({size:,} bytes)")
    return True


def generate_one_image(
    episode: str, scene: str, prompt_data: dict
) -> bool:
    """生成一张图：加载 workflow → 注入提示词 → 提交 → 取回。"""
    dest = (
        BASE
        / "state"
        / "demo_assets"
        / episode
        / "images"
        / f"{episode}_{scene}_key.png"
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

    # 提交 + 重试
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


def generate_images(episode: str, prompts: dict) -> int:
    """生成某集的所有缺失图片。返回成功张数。"""
    success = 0
    total = len(prompts)
    for scene in sorted(prompts.keys()):
        log(f"\n── [{episode}_{scene}] 开始出图 ──")
        ok = generate_one_image(episode, scene, prompts[scene])
        if ok:
            success += 1
        # 每张图之间喘口气
        time.sleep(1)
    return success, total


# ════════════════════════════════════════════════════════════
# 3. Piper TTS 配音
# ════════════════════════════════════════════════════════════


def generate_one_audio(episode: str, scene: str, text: str) -> bool:
    """用 Piper 生成一句配音。"""
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


def generate_audio(episode: str, dialogues: dict) -> int:
    """生成某集的所有缺失配音。返回成功数。"""
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


def verify(episodes: list[str]) -> bool:
    """验证所有期待的文件是否到位。"""
    all_ok = True
    for ep in episodes:
        img_dir = BASE / "state" / "demo_assets" / ep / "images"
        aud_dir = BASE / "state" / "demo_assets" / ep / "audio"
        for sn in range(1, 7):
            scene = f"S{sn:02d}"
            img = img_dir / f"{ep}_{scene}_key.png"
            aud = aud_dir / f"{ep}_{scene}_tts.wav"
            if not img.exists():
                log(f"  ❌ 缺失: {ep}_{scene} 图片")
                all_ok = False
            if not aud.exists():
                log(f"  ❌ 缺失: {ep}_{scene} 配音")
                all_ok = False

        img_count = len(list(img_dir.glob("*.png")))
        aud_count = len(list(aud_dir.glob("*.wav")))
        log(f"  {ep}: {img_count}/6 图片, {aud_count}/6 配音")

    if all_ok:
        log("  ✅ 全部 12 图片 + 12 配音已到位！")
    return all_ok


# ════════════════════════════════════════════════════════════
# 5. 主流程
# ════════════════════════════════════════════════════════════


def main():
    print("=" * 60, flush=True)
    print(" E04/E05 高效生产引擎", flush=True)
    print("=" * 60, flush=True)

    # Step 1: E04 缺失图片 (S04-S06)
    log("\n═══ Step 1/4: E04 图片 ═══")
    e04_img_ok, e04_img_total = generate_images("E04", E04_PROMPTS)
    log(f"  E04 图片: {e04_img_ok}/{e04_img_total}")

    # Step 2: E04 配音 (S01-S06)
    log("\n═══ Step 2/4: E04 配音 ═══")
    e04_aud_ok, e04_aud_total = generate_audio("E04", E04_DIALOGUE)
    log(f"  E04 配音: {e04_aud_ok}/{e04_aud_total}")

    # Step 3: E05 缺失图片 (S01-S06)
    log("\n═══ Step 3/4: E05 图片 ═══")
    e05_img_ok, e05_img_total = generate_images("E05", E05_PROMPTS)
    log(f"  E05 图片: {e05_img_ok}/{e05_img_total}")

    # Step 4: E05 配音 (S01-S06)
    log("\n═══ Step 4/4: E05 配音 ═══")
    e05_aud_ok, e05_aud_total = generate_audio("E05", E05_DIALOGUE)
    log(f"  E05 配音: {e05_aud_ok}/{e05_aud_total}")

    # 验证
    log("\n═══ 验证 ═══")
    verify(["E04", "E05"])

    print("\n" + "=" * 60, flush=True)
    print(" 生产完成", flush=True)
    print("=" * 60, flush=True)


if __name__ == "__main__":
    main()
