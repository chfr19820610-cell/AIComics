#!/usr/bin/env python3
"""Generate E03 S04-S06 images via ComfyUI API, then generate audio via Piper."""
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.parse
import urllib.error
import uuid

PROJECT_ROOT = "/Users/eric/Desktop/herness/AIComics/10_System"
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "state", "local_provider_output", "E03")
COMFYUI_URL = "http://localhost:8188"
PIPER_MODEL = os.path.join(PROJECT_ROOT, "local_providers", "piper", "models", "zh_CN-huayan-medium.onnx")
PIPER_PYTHON = os.path.join(PROJECT_ROOT, "local_providers", "piper", "python")
PIPER_EXEC = os.path.join(PROJECT_ROOT, "scripts", "run_local_piper.py")

# Scene data from the manifest
scenes = {
    "S04": {
        "prompt": "masterpiece, best quality, anime style, 日系动画风格, school playground, flag-raising ceremony, middle-aged man in suit running towards a girl, man's hand on girl's forehead, girl with red scarf, golden light radiating from hand, sunset sky, dramatic moment, heroic pose, warm golden hour lighting, anime school background, motion blur, crowd of students in background watching, emotional rescue scene, detailed anime style",
        "seed": 420000004,
        "narration": "按住我额头的不是男主不是校医——是教导主任。那个全校最凶的秃头大叔。他的手心在发光——微弱的金黄色光芒。原来他也是他们之一。原来我从来都不是一个人。"
    },
    "S05": {
        "prompt": "masterpiece, best quality, anime style, 日系青春动画风格, school office interior, afternoon sunlight through window, desks with papers, middle-aged man standing by window looking out, bookshelves, teenage girl sitting on chair holding a cup of water, warm cozy atmosphere, dust particles in light beams, nostalgic feeling, shadows stretching across floor, slice of life, detailed anime style",
        "seed": 420000005,
        "narration": "他告诉我他的女儿二十年前也变成了僵尸。但那时候没有人帮她，她最终放弃了。他说他在我身上看到了他女儿的眼睛——所以他发誓这次一定要做对的事。原来每个凶巴巴的大人心里都有一个没能保护好的孩子。"
    },
    "S06": {
        "prompt": "masterpiece, best quality, anime style, 日系青春动画风格, school gate at dusk, three black SUVs blocking the road, men in black suits with silver snake-cross badges, woman leader (short hair, 40s, strong presence) holding documents, car interior view, two people in car front seats, girl in back seat, tense confrontation scene, purple evening sky, headlight beams, cinematic composition, threat atmosphere, detailed anime style",
        "seed": 420000006,
        "narration": "我们被三辆黑色SUV拦住了。那些人胸口别着蛇缠十字架的徽章。男主的表情第一次出现了恐惧——他认识这些人。校医说他们是净化者——专门处理不稳定的感染体。而我在他们眼中就是那个需要被处理的感染体。"
    }
}


def queue_prompt(workflow):
    """Queue a prompt on ComfyUI and return the prompt_id."""
    data = json.dumps({"prompt": workflow}).encode("utf-8")
    req = urllib.request.Request(
        f"{COMFYUI_URL}/prompt",
        data=data,
        headers={"Content-Type": "application/json"}
    )
    resp = urllib.request.urlopen(req)
    result = json.loads(resp.read())
    return result.get("prompt_id")


def get_history(prompt_id):
    """Get the execution history for a prompt_id."""
    try:
        resp = urllib.request.urlopen(f"{COMFYUI_URL}/history/{prompt_id}")
        return json.loads(resp.read())
    except urllib.error.HTTPError:
        return None


def wait_for_completion(prompt_id, timeout=300):
    """Wait for a ComfyUI prompt to complete."""
    start = time.time()
    while time.time() - start < timeout:
        history = get_history(prompt_id)
        if history and prompt_id in history:
            return history[prompt_id]
        time.sleep(2)
    raise TimeoutError(f"Prompt {prompt_id} did not complete within {timeout}s")


def build_workflow(positive_prompt, filename_prefix, seed):
    """Build a ComfyUI workflow for the image generation."""
    return {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": 28,
                "cfg": 7.0,
                "sampler_name": "euler_ancestral",
                "scheduler": "normal",
                "denoise": 1.0,
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0]
            }
        },
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "animagine-xl-4.0-opt.safetensors"}
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": 832, "height": 1216, "batch_size": 1}
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": positive_prompt,
                "clip": ["4", 1]
            }
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry, ugly, deformed, disfigured, poorly drawn, bad proportions, extra limbs, distorted face",
                "clip": ["4", 1]
            }
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["3", 0], "vae": ["4", 2]}
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": filename_prefix, "images": ["8", 0]}
        }
    }


def get_latest_image(prefix):
    """Find the most recent image with the given prefix in ComfyUI output."""
    output_path = os.path.join(PROJECT_ROOT, "state", "comfyui_output")
    if not os.path.exists(output_path):
        return None
    candidates = [f for f in os.listdir(output_path) if f.startswith(prefix) and f.endswith(".png")]
    if not candidates:
        return None
    candidates.sort(key=lambda f: os.path.getmtime(os.path.join(output_path, f)), reverse=True)
    return os.path.join(output_path, candidates[0])


def generate_image(shot_id, scene_data):
    """Generate a single image via ComfyUI."""
    print(f"\n{'='*60}")
    print(f"Generating E03_{shot_id} image...")
    print(f"{'='*60}")
    
    prefix = f"E03_{shot_id}"
    out_path = os.path.join(OUTPUT_DIR, "images", f"E03_{shot_id}_key.png")
    
    workflow = build_workflow(scene_data["prompt"], prefix, scene_data["seed"])
    prompt_id = queue_prompt(workflow)
    print(f"  Queued prompt_id: {prompt_id}")
    
    result = wait_for_completion(prompt_id)
    print(f"  Completed!")
    
    # Find the generated image
    latest = get_latest_image(prefix)
    if latest and os.path.exists(latest):
        import shutil
        shutil.copy2(latest, out_path)
        file_size = os.path.getsize(out_path)
        print(f"  Image saved to: {out_path} ({file_size} bytes)")
        return True
    else:
        print(f"  WARNING: Could not find generated image for {prefix}")
        return False


def generate_audio(shot_id, scene_data):
    """Generate audio via Piper TTS for the narration text."""
    print(f"\nGenerating E03_{shot_id} audio...")
    
    narration = scene_data.get("narration", "")
    if not narration:
        print(f"  SKIP: No narration text for {shot_id}")
        return False
    
    out_path = os.path.join(OUTPUT_DIR, "audio", f"E03_{shot_id}_tts.wav")
    
    cmd = [
        sys.executable,
        PIPER_EXEC,
        "--model", PIPER_MODEL,
        "--output_file", out_path,
    ]
    
    try:
        result = subprocess.run(
            cmd,
            input=narration,
            capture_output=True,
            text=True,
            timeout=120,
            check=False
        )
        if result.returncode == 0 and os.path.exists(out_path):
            file_size = os.path.getsize(out_path)
            print(f"  Audio saved to: {out_path} ({file_size} bytes)")
            return True
        else:
            print(f"  Piper failed (rc={result.returncode}): {result.stderr[:200]}")
            return False
    except Exception as e:
        print(f"  Error: {e}")
        return False


def main():
    os.makedirs(os.path.join(OUTPUT_DIR, "images"), exist_ok=True)
    os.makedirs(os.path.join(OUTPUT_DIR, "audio"), exist_ok=True)
    
    for shot_id in ["S04", "S05", "S06"]:
        scene_data = scenes[shot_id]
        
        # Generate image
        img_success = generate_image(shot_id, scene_data)
        
        # Generate audio
        audio_success = generate_audio(shot_id, scene_data)
        
        print(f"  Result: image={'OK' if img_success else 'FAIL'}, audio={'OK' if audio_success else 'FAIL'}")
    
    print("\n" + "="*60)
    print("E03 S04-S06 generation complete!")
    print("="*60)
    
    # Final check
    for shot_id in ["S04", "S05", "S06"]:
        img = os.path.join(OUTPUT_DIR, "images", f"E03_{shot_id}_key.png")
        aud = os.path.join(OUTPUT_DIR, "audio", f"E03_{shot_id}_tts.wav")
        img_ok = os.path.exists(img) and os.path.getsize(img) > 1000
        aud_ok = os.path.exists(aud) and os.path.getsize(aud) > 1000
        print(f"  E03_{shot_id}: image={'OK' if img_ok else 'MISSING'} ({os.path.getsize(img) if os.path.exists(img) else 0}B), audio={'OK' if aud_ok else 'MISSING'} ({os.path.getsize(aud) if os.path.exists(aud) else 0}B)")


if __name__ == "__main__":
    main()
