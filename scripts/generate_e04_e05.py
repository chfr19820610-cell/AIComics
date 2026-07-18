#!/usr/bin/env python3
"""Generate E04 + E05 images via ComfyUI and audio via Piper TTS."""

import json
import os
import random
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

BASE = Path("/Users/eric/Desktop/herness/AIComics/10_System")
COMFY_API = "http://127.0.0.1:8188"
VENV_PY = BASE / ".venv" / "bin" / "python3"

# ── Scene prompts (Chinese scenes for context, English for stable diffusion) ──

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

# ── Dialogue for TTS ──
E04_DIALOGUE = {
    "S01": "校门口，男主独自面对净化者先锋队。他握紧拳头，眼神坚定：\"我绝不会让你们伤害这里的任何人！\"",
    "S02": "停车场内，净化者主力正在集结。装甲车辆缓缓驶入，全副武装的战士们列队整齐，空气中弥漫着肃杀的气息。",
    "S03": "锅炉房里，男主掩护着受伤的同伴撤退。蒸汽管道不断爆裂，白色的雾气中，他的身影显得格外英勇。",
    "S04": "男主孤身逃亡在空无一人的街道上。身后追兵越来越近，前方却是死胡同。他咬着牙：\"只能拼了...\"",
    "S05": "教堂内，小林摘下伪装的面具。女主难以置信地后退两步：\"小林...怎么会是你？\"小林低下头：\"对不起，我别无选择。\"",
    "S06": "净化者首领高举手臂：\"全员听令——天亮之前，把整个学校给我夷为平地！\"身后的军队整齐前进，大地为之震动。",
}

E05_DIALOGUE = {
    "S01": "女主轻轻握住小林的手：\"我原谅你了。每个人都会有身不由己的时候，欢迎回来。\"小林泪流满面，紧紧抱住了她。",
    "S02": "突击队冲破净化者总部的大门！男主一马当先：\"跟我冲——救人要紧！\"身后，战友们紧随其后，气势如虹。",
    "S03": "实验室内，主任的女儿被关在玻璃容器中。男主砸碎控制台：\"找到你了！别怕，我带你回家！\"蓝光闪烁中，她睁开了眼睛。",
    "S04": "净化者首领缓缓摘下面罩。女主震惊地后退：\"你是...已故校长的女儿？！\"首领眼中含泪：\"我只是想...为父亲报仇。\"",
    "S05": "天台上，全校师生站了出来，将女主护在身后。班长高喊：\"谁敢动她，先过我们这关！\"几百人齐声响应，气势磅礴。",
    "S06": "黎明破晓，樱花纷飞。男主体内的僵尸毒素完全清除，恢复了正常人的体温。两人在樱花树下紧紧相拥，新的一天终于来临。",
}


def comfyui_submit(workflow: dict, output_dir: Path) -> list[str]:
    """Submit workflow to ComfyUI and download generated images."""
    # Randomize seed
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
        resp = urllib.request.urlopen(req, timeout=120)
        result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        print(f"  ERROR: HTTP {e.code}: {body[:300]}")
        return []

    prompt_id = result.get("prompt_id")
    if not prompt_id:
        print(f"  ERROR: no prompt_id: {result}")
        return []

    if result.get("node_errors"):
        print(f"  WARN: node_errors: {result['node_errors']}")
        # Continue anyway

    print(f"  Submitted prompt_id={prompt_id}, seed={seed}")

    # Poll for completion
    timeout = 300
    start = time.time()
    interval = 2
    files_downloaded = []

    while time.time() - start < timeout:
        time.sleep(interval)
        interval = min(8, interval * 1.3)

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
            outputs = entry.get("outputs", {})
            output_dir.mkdir(parents=True, exist_ok=True)

            for node_id, node_out in outputs.items():
                if not isinstance(node_out, dict):
                    continue
                for key in ("images", "gifs", "videos", "audio", "files"):
                    files_list = node_out.get(key, [])
                    if not isinstance(files_list, list):
                        files_list = [files_list]
                    for fi in files_list:
                        if isinstance(fi, dict) and fi.get("filename"):
                            fn = fi["filename"]
                            sf = fi.get("subfolder", "")
                            ft = fi.get("type", "output")
                            dl_url = f"{COMFY_API}/view?filename={fn}&subfolder={sf}&type={ft}"
                            try:
                                dl_resp = urllib.request.urlopen(dl_url, timeout=60)
                                out_path = output_dir / fn
                                with open(out_path, "wb") as outf:
                                    outf.write(dl_resp.read())
                                files_downloaded.append(str(out_path))
                                print(f"    Downloaded: {out_path.name}")
                            except Exception as e:
                                print(f"    WARN: download {fn} failed: {e}")
            return files_downloaded

        if st.get("status_str") == "error":
            err_msg = st.get("error_messages", "Unknown error")
            print(f"  ERROR: {err_msg}")
            return []

    print(f"  TIMEOUT after {timeout}s")
    return []


def generate_images(episode: str, prompts: dict):
    """Generate 6 images for an episode."""
    images_dir = BASE / "state" / "demo_assets" / episode / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    # Load workflow template
    workflow_path = Path("/Users/eric/Desktop/herness/saas-project/assets/workflows/animagine_xl4_txt2img.json")
    if not workflow_path.exists():
        # Fallback to the simple workflow
        workflow_path = Path("/Users/eric/Desktop/herness/anime_campus_workflow.json")
        if not workflow_path.exists():
            print(f"ERROR: No workflow found!")
            return False

    print(f"\n{'='*60}")
    print(f"Generating {episode} images...")
    print(f"{'='*60}")

    with open(workflow_path) as f:
        workflow_template = json.load(f)

    total_success = 0
    for scene in sorted(prompts.keys()):
        output_path = images_dir / f"{episode}_{scene}_key.png"
        if output_path.exists():
            print(f"  {episode}_{scene}: already exists, skipping")
            total_success += 1
            continue

        prompt_data = prompts[scene]
        print(f"\n  [{episode}_{scene}] Generating...")

        # Deep copy workflow
        wf = json.loads(json.dumps(workflow_template))

        # Check if this is SDXL workflow (with CLIPTextEncodeSDXL)
        has_sdxl = any(
            node.get("class_type") == "CLIPTextEncodeSDXL"
            for node in wf.values()
        )

        if has_sdxl:
            # SDXL workflow
            for nid, node in wf.items():
                if node.get("class_type") == "CLIPTextEncodeSDXL":
                    if node["_meta"].get("title") == "CLIP Text Encode (Positive)":
                        node["inputs"]["text_g"] = prompt_data.get("prompt_g", prompt_data.get("prompt_l", ""))
                        node["inputs"]["text_l"] = prompt_data.get("prompt_l", "")
                elif node.get("class_type") == "SaveImage":
                    node["inputs"]["filename_prefix"] = f"{episode}_{scene}_key"
        else:
            # SD1.5 workflow
            for nid, node in wf.items():
                if node.get("class_type") == "CLIPTextEncode":
                    # First text encode is positive
                    node["inputs"]["text"] = prompt_data.get("prompt_g", "")
                elif node.get("class_type") == "SaveImage":
                    node["inputs"]["filename_prefix"] = f"{episode}_{scene}_key"

        files = comfyui_submit(wf, images_dir)
        if files:
            total_success += 1
            # Rename if needed
            for f in files:
                p = Path(f)
                if p.exists() and p.name != f"{episode}_{scene}_key.png":
                    if not output_path.exists():
                        p.rename(output_path)
                        print(f"    Renamed to {output_path.name}")
        else:
            print(f"  FAILED: {episode}_{scene}")

    print(f"\n  {episode}: {total_success}/{len(prompts)} images generated")
    return total_success == len(prompts)


def generate_audio(episode: str, dialogues: dict):
    """Generate 6 audio files using Piper TTS."""
    audio_dir = BASE / "state" / "demo_assets" / episode / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    model_path = str(BASE / "local_providers" / "piper" / "models" / "zh_CN-huayan-medium.onnx")
    config_path = str(BASE / "local_providers" / "piper" / "models" / "zh_CN-huayan-medium.onnx.json")

    print(f"\n{'='*60}")
    print(f"Generating {episode} audio...")
    print(f"{'='*60}")

    total_success = 0
    for scene in sorted(dialogues.keys()):
        output_path = audio_dir / f"{episode}_{scene}_tts.wav"
        if output_path.exists():
            print(f"  {episode}_{scene}: already exists, skipping")
            total_success += 1
            continue

        text = dialogues[scene]
        print(f"\n  [{episode}_{scene}] Generating TTS: \"{text[:50]}...\"")

        cmd = [
            str(VENV_PY),
            str(BASE / "scripts" / "run_local_piper.py"),
            "--model", model_path,
            "--config", config_path,
            "--output_file", str(output_path),
        ]

        try:
            result = subprocess.run(
                cmd,
                input=text,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(BASE),
            )
            if result.returncode == 0 and output_path.exists():
                size = output_path.stat().st_size
                print(f"    OK: {output_path.name} ({size} bytes)")
                total_success += 1
            else:
                print(f"    FAILED (rc={result.returncode}): {result.stderr[:200]}")
        except subprocess.TimeoutExpired:
            print(f"    TIMEOUT after 120s")
        except Exception as e:
            print(f"    ERROR: {e}")

    print(f"\n  {episode}: {total_success}/{len(dialogues)} audio files generated")
    return total_success == len(dialogues)


def build_batch_pipeline():
    """Run build-season-jobs → build-provider-requests → execute-provider-requests."""
    print(f"\n{'='*60}")
    print(f"Building batch pipeline...")
    print(f"{'='*60}")

    os.chdir(str(BASE))

    steps = [
        ("build-season-jobs", [
            str(VENV_PY), "main.py", "build-season-jobs",
            "--project-id", "我变成僵尸后全校跪求我别死",
        ]),
        ("build-provider-requests", [
            str(VENV_PY), "main.py", "build-provider-requests",
        ]),
        ("execute-provider-requests", [
            str(VENV_PY), "main.py", "execute-provider-requests",
            "--confirm-live",
        ]),
    ]

    for name, cmd in steps:
        print(f"\n  [{name}] Running...")
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=str(BASE))
            print(f"    Exit: {r.returncode}")
            if r.stdout:
                for line in r.stdout.strip().split("\n")[-5:]:
                    print(f"    {line}")
            if r.returncode != 0 and r.stderr:
                for line in r.stderr.strip().split("\n")[-5:]:
                    print(f"    ERR: {line}")
        except subprocess.TimeoutExpired:
            print(f"    TIMEOUT")
        except Exception as e:
            print(f"    ERROR: {e}")


def verify_assets():
    """Verify all generated files exist."""
    print(f"\n{'='*60}")
    print(f"Verification")
    print(f"{'='*60}")

    all_ok = True
    for ep in ["E04", "E05"]:
        for sn in range(1, 7):
            scene = f"S{sn:02d}"
            img = BASE / "state" / "demo_assets" / ep / "images" / f"{ep}_{scene}_key.png"
            aud = BASE / "state" / "demo_assets" / ep / "audio" / f"{ep}_{scene}_tts.wav"

            img_ok = img.exists()
            aud_ok = aud.exists()

            if not img_ok:
                print(f"  MISSING: {ep}_{scene} image")
                all_ok = False
            if not aud_ok:
                print(f"  MISSING: {ep}_{scene} audio")
                all_ok = False

    if all_ok:
        print(f"  ✅ ALL 12 images + 12 audio files present!")
    else:
        print(f"  ❌ Some files missing")

    # Summary
    for ep in ["E04", "E05"]:
        img_count = len(list((BASE / "state" / "demo_assets" / ep / "images").glob("*.png")))
        aud_count = len(list((BASE / "state" / "demo_assets" / ep / "audio").glob("*.wav")))
        print(f"  {ep}: {img_count}/6 images, {aud_count}/6 audio")

    return all_ok


if __name__ == "__main__":
    print("=" * 60)
    print("E04 + E05 全量生产引擎启动")
    print("=" * 60)

    # Step 1: Generate E04 images
    ok1 = generate_images("E04", E04_PROMPTS)

    # Step 2: Generate E04 audio
    ok2 = generate_audio("E04", E04_DIALOGUE)

    # Step 3: Generate E05 images
    ok3 = generate_images("E05", E05_PROMPTS)

    # Step 4: Generate E05 audio
    ok4 = generate_audio("E05", E05_DIALOGUE)

    # Step 5: Build batch pipeline
    build_batch_pipeline()

    # Step 6: Verify
    verify_assets()

    print(f"\n{'='*60}")
    print(f"Production complete!")
    print(f"  E04 images: {'✅' if ok1 else '❌'}")
    print(f"  E04 audio:  {'✅' if ok2 else '❌'}")
    print(f"  E05 images: {'✅' if ok3 else '❌'}")
    print(f"  E05 audio:  {'✅' if ok4 else '❌'}")
    print(f"{'='*60}")
