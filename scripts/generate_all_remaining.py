#!/usr/bin/env python3
"""集中生成 E01/E02/E03/E05 全部剩余16张图+15段配音"""

from __future__ import annotations

import hashlib
import json
import os
import random
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = PROJECT_ROOT / "state" / "local_provider_output"
COMFYUI_BASE = os.environ.get("AICOMIC_COMFYUI_BASE_URL", "http://127.0.0.1:8188").rstrip("/")
PIPER_MODEL = str(PROJECT_ROOT / "local_providers" / "piper" / "models" / "zh_CN-huayan-medium.onnx")
PIPER_CONFIG = str(PROJECT_ROOT / "local_providers" / "piper" / "models" / "zh_CN-huayan-medium.onnx.json")
PIPER_BIN = os.environ.get("PIPER_BIN", "") or subprocess.run(["which", "piper"], capture_output=True, text=True).stdout.strip()

NO_PROXY_OPENER = build_opener(ProxyHandler({}))

IMAGE_TIMEOUT = 360
IMAGE_RETRIES = 3
IMAGE_POLL_INTERVAL = 3
AUDIO_TIMEOUT = 120
IMAGE_MIN_BYTES = 100 * 1024  # 100KB
AUDIO_MIN_BYTES = 20 * 1024   # 20KB

# Known placeholder md5 hash (E01 S01-S04, E02 S01-S03 all share this)
KNOWN_PLACEHOLDER_HASHES = {"40b83820b4484987e26e5d751b07d0c4"}

# ── Scene definitions ──────────────────────────────────────────────
# Each scene: (episode, shot, image_prompt_g, image_prompt_l, dialog_text)

NEGATIVE_G = (
    "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, "
    "fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, "
    "signature, watermark, username, blurry, deformed, ugly, messy drawing, "
    "multiple views, 3d, photo"
)
NEGATIVE_L = NEGATIVE_G

SCENES = [
    # ── E01 ──
    ("E01", "S01",
     "anime scene, early morning on school campus, male student Chen Mo walking on tree-lined path, "
     "sunlight filtering through green leaves, soft golden hour glow, peaceful atmosphere, "
     "dappled light on ground, school buildings in background, cherry blossoms, "
     "best quality, masterpiece",
     "morning campus, sunlight through trees, student walking, peaceful, golden hour, school path"),

    ("E01", "S02",
     "anime scene, dark alley after school, shadow figure suddenly attacking male student, "
     "biting his neck, horror tension, dramatic shadows, dusk lighting, "
     "intense moment, thrilling atmosphere, high quality",
     "dark alley, attack scene, shadow figure biting, surprised male student, evening light, horror"),

    ("E01", "S03",
     "anime scene, classroom horror, male student Chen Mo's hand turning pale gray, "
     "zombie-like transformation, classmates watching in fear, cold classroom lighting, "
     "pale blue color tone, shocked expressions, tense atmosphere, detailed hand, "
     "best quality, masterpiece",
     "classroom horror, hand transforming pale gray, scared classmates, cold tones, mutation"),

    ("E01", "S04",
     "anime scene, brave female class leader Lin Xue standing in front of Chen Mo, "
     "protective pose, warm light behind her, determined expression, "
     "classroom background, facing frightened classmates, noble sacrifice atmosphere, "
     "soft warm backlighting, best quality, masterpiece",
     "female class leader protects male student, standing in front, determined, warm light"),

    # ── E02 ──
    ("E02", "S01",
     "anime scene, tense confrontation in school medical room, Lin Xue and Chen Mo, "
     "cold fluorescent light, medical bed and cabinets, concerned nurse in background, "
     "Chen Mo looking at his hand, Lin Xue examining him, sterile atmosphere, "
     "best quality, masterpiece",
     "medical room confrontation, school nurse, cold white light, concerned atmosphere"),

    ("E02", "S02",
     "anime extreme close-up, palm of hand with wound healing rapidly, "
     "flesh reknitting, glowing light effect, cells regenerating, "
     "supernatural healing, detailed macro shot, skin texture, dramatic lighting, "
     "best quality, masterpiece",
     "close up hand wound healing, regeneration, glowing, supernatural, skin knitting together"),

    ("E02", "S03",
     "anime wide angle, school sports field, PE class, Chen Mo accidentally showing "
     "superhuman strength, students gathered around in awe, dramatic action pose, "
     "bright daylight, athletic field background, impressed classmates, "
     "dynamic composition, best quality, masterpiece",
     "sports field, students watching, superhuman strength, daylight, amazed classmates"),

    # ── E03 S04-S06 ──
    ("E03", "S04",
     "anime scene, rooftop standoff, Purifier organization members revealed, "
     "dramatic sunset backlighting, silhouettes against orange sky, "
     "tense confrontation, Chen Mo facing them, wind blowing, serious expressions, "
     "epic composition, best quality, masterpiece",
     "rooftop standoff, purifier revealed, sunset silhouette, tense confrontation"),

    ("E03", "S05",
     "anime dynamic action scene, Chen Mo and female lead fighting side by side, "
     "combat poses, warm color palette, energy effects, "
     "moving fast, teamwork, determined expressions, cinematic action shot, "
     "best quality, masterpiece",
     "fighting together, duo combat, dynamic action, warm colors, side by side"),

    ("E03", "S06",
     "anime scene, Purifier forces retreating, male protagonist Chen Mo collapsing weakly, "
     "hazy dreamy atmosphere, fading light, exhausted expression, "
     "figures walking away in background, soft focus, emotional ending, "
     "misty lighting, best quality, masterpiece",
     "purifier retreat, protagonist collapsing, exhausted, hazy atmosphere, fading light"),

    # ── E05 all ──
    ("E05", "S01",
     "anime scene, emotional reconciliation, female protagonist forgiving her friend, "
     "tearful embrace on rooftop, warm sunrise lighting, golden rays, "
     "healing atmosphere, soft lighting, heartfelt moment, warm color palette, "
     "close up emotional faces, best quality, masterpiece",
     "forgiveness, emotional embrace on rooftop, tears, warm sunrise, healing, heartfelt"),

    ("E05", "S02",
     "anime scene, assault on Purifier headquarters, group of protagonists storming "
     "the building, action combat, glowing powers, explosions behind them, "
     "dynamic wide angle, intense battle, cinematic lighting, "
     "smoke and debris, heroic poses, best quality, masterpiece",
     "assault on headquarters, storming building, combat action, explosions, heroic"),

    ("E05", "S03",
     "anime scene, laboratory rescue, cold white fluorescent light, "
     "scientific equipment and tubes, captured people being freed, "
     "sterile environment, rescue atmosphere, medical pods, urgency, "
     "dramatic lighting, best quality, masterpiece",
     "laboratory rescue, cold white light, scientific equipment, freeing captives"),

    ("E05", "S04",
     "anime dramatic close up, Purifier leader identity revealed, "
     "shocking expression, face illuminated half in shadow, "
     "intense eye contact, plot twist, high impact composition, "
     "dramatic single light source, best quality, masterpiece",
     "identity reveal, purifier leader close up, shocking, dramatic lighting"),

    ("E05", "S05",
     "anime epic wide angle, entire school students and teachers standing united, "
     "facing the threat together, massive crowd, determined faces, "
     "school courtyard, banners, solidarity, inspiring composition, "
     "spectacular scale, best quality, masterpiece",
     "full school united, massive crowd of students and teachers, solidarity, epic wide"),

    ("E05", "S06",
     "anime ending scene, dawn after the battle, cured zombies returning to normal, "
     "cherry blossom petals falling, warm golden sunrise, peaceful atmosphere, "
     "hope and renewal, characters silhouettes against sunrise, "
     "beautiful sky, emotional finale, best quality, masterpiece",
     "dawn ending, cured zombies, cherry blossoms, warm sunrise, hope, peaceful finale"),
]

# Dialog text for each scene (配音文本)
DIALOG = {
    # E01
    ("E01", "S01"): "清晨的阳光透过树叶洒在林荫道上，陈默背着书包，独自走在熟悉的校园小路上。他不知道，今天将是改变他命运的一天。",
    ("E01", "S01_alt"): "【旁白】清晨的校园，安静而美好。陈默像往常一样，穿过这条林荫道去教室。但今天，有什么不同在等待着他。",
    ("E01", "S02"): "放学后的小巷里，陈默被一道黑影袭击。黑暗之中，什么东西咬中了他，一股刺痛传遍全身。",
    ("E01", "S02_alt"): "【陈默】啊——！是谁？！",
    ("E01", "S03"): "教室里传来惊恐的尖叫。陈默的手正在变成青灰色——那是...僵尸的颜色。同学们纷纷后退，恐惧在蔓延。",
    ("E01", "S03_alt"): "【同学甲】他的手！他的手变了！",
    ("E01", "S04"): "【林雪】都别怕！我来保护他！班长林雪挺身而出，挡在陈默身前。她的眼神坚定而温暖，仿佛一道光照进了这片黑暗。",
    # E02
    ("E02", "S01"): "校医室里，气氛紧张。林雪站在陈默身边，警惕地盯着校医。冷白的灯光下，每个人都在消化刚才发生的一切。",
    ("E02", "S01_alt"): "【林雪】校医，他不是怪物。",
    ("E02", "S02"): "陈默摊开手掌，刚才的伤口正在以肉眼可见的速度愈合。血肉重新生长，皮肤光洁如初。林雪屏住了呼吸。",
    ("E02", "S02_alt"): "【陈默】你看...我好像，不只是会变成僵尸。",
    ("E02", "S03"): "体育课上，陈默无意中展现出了惊人的力量。同学们围拢过来，惊叹声此起彼伏。",
    ("E02", "S03_alt"): "【同学乙】天哪，他刚才扔了多远？！",
    # E03
    ("E03", "S04"): "天台上，夕阳如血。自称'净化者'的神秘组织成员突然现身，揭开了这场危机的真相。空气仿佛凝固了。",
    ("E03", "S04_alt"): "【净化者】被选中的人，你的存在就是最大的威胁。",
    ("E03", "S05"): "陈默与女主并肩而战，两人的配合天衣无缝。拳脚交错之间，一道又一道攻击被化解。",
    ("E03", "S05_alt"): "【女主】别怕，有我在！我们一起上！",
    ("E03", "S06"): "净化者撤退了，但陈默也耗尽了最后一丝力气。他缓缓倒下，视线越来越模糊。朦胧中，似乎有人向他跑来。",
    ("E03", "S06_alt"): "【旁白】战斗结束了，但代价是什么？",
    # E05
    ("E05", "S01"): "天台上，金色的晨光洒落。小林眼中含着泪水，女主的原谅让她再也绷不住。两人紧紧拥抱在一起，一切误会都在这一刻烟消云散。",
    ("E05", "S02"): "突击队攻入净化者总部，战斗在走廊间爆发。蓝银色的能量光芒交织，爆炸声震耳欲聋。",
    ("E05", "S03"): "实验室里，冰冷的器械和试管构成了恐怖的景象。被困的人们看到救援，眼中重新燃起了希望的光芒。",
    ("E05", "S04"): "面罩揭开的瞬间，所有人都愣住了。净化者的首领，竟然是......那张熟悉的面孔让全场陷入死寂。",
    ("E05", "S05"): "全校师生站了出来，他们不再害怕，不再逃避。操场上，密密麻麻的人群汇聚成一股不可阻挡的力量。",
    ("E05", "S06"): "黎明终于到来。被感染的僵尸恢复了人类的模样，樱花在晨风中飘落。陈默望着初升的太阳，嘴角露出一丝微笑——一切都结束了，一切都才刚刚开始。",
}


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def post_json(url: str, body: dict[str, Any], timeout: int) -> dict[str, Any]:
    req = Request(url, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                  headers={"Content-Type": "application/json"}, method="POST")
    try:
        with NO_PROXY_OPENER.open(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        raise RuntimeError(f"HTTPError {e.code}: {e.read().decode('utf-8', errors='replace')}") from e
    except URLError as e:
        raise RuntimeError(f"URLError: {e.reason}") from e


def get_json(url: str, timeout: int) -> dict[str, Any]:
    try:
        with NO_PROXY_OPENER.open(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        raise RuntimeError(f"HTTPError {e.code}: {e.read().decode('utf-8', errors='replace')}") from e
    except URLError as e:
        raise RuntimeError(f"URLError: {e.reason}") from e


def get_bytes(url: str, timeout: int) -> bytes:
    try:
        with NO_PROXY_OPENER.open(url, timeout=timeout) as resp:
            return resp.read()
    except HTTPError as e:
        raise RuntimeError(f"HTTPError {e.code}: {e.read().decode('utf-8', errors='replace')}") from e
    except URLError as e:
        raise RuntimeError(f"URLError: {e.reason}") from e


def wait_for_comfyui_idle() -> None:
    """Wait until ComfyUI queue is empty."""
    while True:
        try:
            data = get_json(f"{COMFYUI_BASE}/queue", 5)
        except Exception:
            time.sleep(2)
            continue
        running = data.get("queue_running", [])
        pending = data.get("queue_pending", [])
        if not running and not pending:
            log("ComfyUI queue idle, proceeding")
            return
        log(f"Waiting: {len(running)} running + {len(pending)} pending")
        time.sleep(5)


def get_file_hash(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def is_placeholder(path: Path) -> bool:
    """Check if file is a known placeholder (duplicate md5 of first placeholder)."""
    if not path.exists() or path.stat().st_size < IMAGE_MIN_BYTES:
        return True
    # Check if all S01-S04 share same hash (placeholder pattern)
    return False


def generate_image(episode: str, shot: str, prompt_g: str, prompt_l: str) -> Path:
    """Generate one image via ComfyUI API and return the output path."""
    output_path = OUTPUT_ROOT / episode / "images" / f"{episode}_{shot}_key.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Build the SDXL animagine workflow
    seed = random.randint(100000000000, 999999999999)
    workflow = {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "animagine-xl-4.0-opt.safetensors"},
            "_meta": {"title": "Load Checkpoint (Animagine XL 4.0)"}
        },
        "2": {
            "class_type": "CLIPTextEncodeSDXL",
            "inputs": {
                "clip": ["1", 1],
                "width": 1024, "height": 1024,
                "crop_w": 0, "crop_h": 0,
                "target_width": 1024, "target_height": 1024,
                "text_g": prompt_g,
                "text_l": prompt_l,
            },
            "_meta": {"title": "CLIP Text Encode (Positive)"}
        },
        "3": {
            "class_type": "CLIPTextEncodeSDXL",
            "inputs": {
                "clip": ["1", 1],
                "width": 1024, "height": 1024,
                "crop_w": 0, "crop_h": 0,
                "target_width": 1024, "target_height": 1024,
                "text_g": NEGATIVE_G,
                "text_l": NEGATIVE_L,
            },
            "_meta": {"title": "CLIP Text Encode (Negative)"}
        },
        "4": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": 1024, "height": 1024, "batch_size": 1},
            "_meta": {"title": "Empty Latent Image"}
        },
        "5": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["4", 0],
                "seed": seed,
                "steps": 28,
                "cfg": 6.0,
                "sampler_name": "euler_ancestral",
                "scheduler": "normal",
                "denoise": 1.0,
            },
            "_meta": {"title": "KSampler"}
        },
        "6": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["5", 0], "vae": ["1", 2]},
            "_meta": {"title": "VAE Decode"}
        },
        "7": {
            "class_type": "SaveImage",
            "inputs": {
                "images": ["6", 0],
                "filename_prefix": f"{episode}_{shot}_key",
            },
            "_meta": {"title": "Save Image"}
        },
    }

    client_id = f"aicomic-gen-{uuid.uuid4()}"
    log(f"Submitting {episode} {shot} (seed={seed})...")
    submit_resp = post_json(f"{COMFYUI_BASE}/prompt",
                            {"prompt": workflow, "client_id": client_id},
                            IMAGE_TIMEOUT)
    prompt_id = str(submit_resp.get("prompt_id", ""))
    if not prompt_id:
        raise RuntimeError(f"No prompt_id in response: {submit_resp}")

    deadline = time.time() + IMAGE_TIMEOUT
    artifact = None
    while time.time() < deadline:
        history = get_json(f"{COMFYUI_BASE}/history/{prompt_id}", IMAGE_TIMEOUT)
        prompt_history = history.get(prompt_id, {})
        outputs = prompt_history.get("outputs", {})
        # Scan outputs for images
        for out in outputs.values():
            if not isinstance(out, dict):
                continue
            images = out.get("images", [])
            if images and isinstance(images, list) and len(images) > 0:
                img = images[0]
                if isinstance(img, dict) and img.get("filename"):
                    artifact = img
                    break
        if artifact:
            break
        # Check for errors
        status = prompt_history.get("status", {})
        messages = status.get("messages", []) if isinstance(status, dict) else []
        for msg in reversed(messages):
            if isinstance(msg, list) and len(msg) == 2 and msg[0] == "execution_error":
                details = msg[1] if isinstance(msg[1], dict) else {}
                err_msg = details.get("exception_message", "unknown error")
                raise RuntimeError(f"ComfyUI execution error: {err_msg}")
        time.sleep(IMAGE_POLL_INTERVAL)
    else:
        raise RuntimeError(f"Timeout after {IMAGE_TIMEOUT}s waiting for {episode} {shot}")

    # Download the image
    query = f"filename={artifact['filename']}&subfolder={artifact.get('subfolder', '')}&type={artifact.get('type', 'output')}"
    img_bytes = get_bytes(f"{COMFYUI_BASE}/view?{query}", IMAGE_TIMEOUT)
    output_path.write_bytes(img_bytes)
    actual_size = output_path.stat().st_size
    log(f"  -> Downloaded {len(img_bytes)} bytes to {output_path.name} ({actual_size/1024:.0f}KB)")
    return output_path


def generate_audio(episode: str, shot: str, text: str) -> Path:
    """Generate TTS audio via Piper CLI."""
    output_path = OUTPUT_ROOT / episode / "audio" / f"{episode}_{shot}_tts.wav"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not PIPER_BIN:
        raise RuntimeError("piper binary not found in PATH")

    log(f"Generating audio for {episode} {shot}...")
    cmd = [PIPER_BIN, "-m", PIPER_MODEL, "-c", PIPER_CONFIG, "-f", str(output_path)]
    try:
        result = subprocess.run(
            cmd, input=text, capture_output=True, text=True,
            timeout=AUDIO_TIMEOUT, check=False,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Piper timed out after {AUDIO_TIMEOUT}s for {episode} {shot}")
    except FileNotFoundError:
        raise RuntimeError(f"Piper binary not found: {PIPER_BIN}")

    if result.returncode != 0:
        stderr = (result.stderr or result.stdout or "").strip()[-500:]
        raise RuntimeError(f"Piper failed (code {result.returncode}): {stderr}")

    if not output_path.exists():
        raise RuntimeError(f"Piper did not create output: {output_path}")

    size = output_path.stat().st_size
    log(f"  -> Generated {output_path.name} ({size/1024:.0f}KB)")
    return output_path


def verify_output(path: Path, min_bytes: int, label: str) -> bool:
    if not path.exists():
        log(f"  FAIL: {label} missing: {path.name}")
        return False
    size = path.stat().st_size
    if size < min_bytes:
        log(f"  FAIL: {label} too small ({size/1024:.0f}KB < {min_bytes/1024:.0f}KB): {path.name}")
        return False
    log(f"  PASS: {label} ({size/1024:.0f}KB): {path.name}")
    return True


def main() -> int:
    log("=" * 60)
    log("AIComics 批量生成启动")
    log(f"ComfyUI: {COMFYUI_BASE}")
    log(f"Piper: {PIPER_BIN}")
    log(f"Model: {PIPER_MODEL}")
    log("=" * 60)

    # Track what to generate
    images_to_gen: list[tuple[str, str, str, str]] = []
    audio_to_gen: list[tuple[str, str, str]] = []

    # Check existing files and build worklist
    for episode, shot, prompt_g, prompt_l in SCENES:
        img_path = OUTPUT_ROOT / episode / "images" / f"{episode}_{shot}_key.png"
        audio_path = OUTPUT_ROOT / episode / "audio" / f"{episode}_{shot}_tts.wav"

        needs_image = False
        if img_path.exists() and img_path.stat().st_size >= IMAGE_MIN_BYTES:
            fhash = hashlib.md5(img_path.read_bytes()).hexdigest()
            if fhash in KNOWN_PLACEHOLDER_HASHES:
                log(f"  PLACEHOLDER image: {episode} {shot} (duplicate, needs regeneration)")
                needs_image = True
            else:
                log(f"  EXISTS image: {episode} {shot} ({img_path.stat().st_size/1024:.0f}KB)")
        else:
            needs_image = True

        if needs_image:
            images_to_gen.append((episode, shot, prompt_g, prompt_l))

        dialog_key = (episode, shot)
        if dialog_key in DIALOG:
            text = DIALOG[dialog_key]
            if audio_path.exists() and audio_path.stat().st_size >= AUDIO_MIN_BYTES:
                log(f"  EXISTS audio: {episode} {shot} ({audio_path.stat().st_size/1024:.0f}KB)")
            else:
                audio_to_gen.append((episode, shot, text))

    log(f"\n计划: {len(images_to_gen)} 张图 + {len(audio_to_gen)} 段配音")
    if not images_to_gen and not audio_to_gen:
        log("全部已完成!")
        return 0

    # ── Generate Images ──
    if images_to_gen:
        log(f"\n{'='*60}")
        log(f"开始生成 {len(images_to_gen)} 张图片...")
        log(f"{'='*60}")

        wait_for_comfyui_idle()

        success_count = 0
        fail_count = 0
        for episode, shot, prompt_g, prompt_l in images_to_gen:
            for attempt in range(IMAGE_RETRIES):
                try:
                    img_path = generate_image(episode, shot, prompt_g, prompt_l)
                    if verify_output(img_path, IMAGE_MIN_BYTES, f"image {episode} {shot}"):
                        success_count += 1
                        break
                    else:
                        raise RuntimeError("Output too small")
                except Exception as e:
                    log(f"  Attempt {attempt+1}/{IMAGE_RETRIES} failed: {e}")
                    if attempt < IMAGE_RETRIES - 1:
                        time.sleep(5)
                        wait_for_comfyui_idle()
            else:
                log(f"  FAILED: {episode} {shot} after {IMAGE_RETRIES} retries")
                fail_count += 1

        log(f"\n图片完成: {success_count} success, {fail_count} failed")

    # ── Generate Audio ──
    if audio_to_gen:
        log(f"\n{'='*60}")
        log(f"开始生成 {len(audio_to_gen)} 段配音...")
        log(f"{'='*60}")

        success_count = 0
        fail_count = 0
        for episode, shot, text in audio_to_gen:
            try:
                audio_path = generate_audio(episode, shot, text)
                if verify_output(audio_path, AUDIO_MIN_BYTES, f"audio {episode} {shot}"):
                    success_count += 1
                else:
                    fail_count += 1
            except Exception as e:
                log(f"  FAILED: {episode} {shot}: {e}")
                fail_count += 1

        log(f"\n配音完成: {success_count} success, {fail_count} failed")

    # ── Final Verification ──
    log(f"\n{'='*60}")
    log("最终验证")
    log(f"{'='*60}")
    total_images = 0
    pass_images = 0
    total_audio = 0
    pass_audio = 0
    for episode, shot, prompt_g, prompt_l in SCENES:
        total_images += 1
        img_path = OUTPUT_ROOT / episode / "images" / f"{episode}_{shot}_key.png"
        if verify_output(img_path, IMAGE_MIN_BYTES, f"image {episode} {shot}"):
            pass_images += 1
        dialog_key = (episode, shot)
        if dialog_key in DIALOG:
            total_audio += 1
            audio_path = OUTPUT_ROOT / episode / "audio" / f"{episode}_{shot}_tts.wav"
            if verify_output(audio_path, AUDIO_MIN_BYTES, f"audio {episode} {shot}"):
                pass_audio += 1

    log(f"\n{'='*60}")
    log(f"最终结果: {pass_images}/{total_images} 图片, {pass_audio}/{total_audio} 配音")
    if pass_images == total_images and pass_audio == total_audio:
        log("全部通过! ✓")
    else:
        log("部分失败, 请检查以上日志")
    log(f"{'='*60}")

    return 0 if (pass_images == total_images and pass_audio == total_audio) else 1


if __name__ == "__main__":
    raise SystemExit(main())
