"""
Blender 单帧/动画渲染脚本
==========================
由 blender_provider 通过 subprocess 调用。

参数通过环境变量传递 (避免 Blender 4.4 argparse 冲突):
    BLENDER_SCENE_OUTDIR    输出目录 (默认: /tmp/blender_frames)
    BLENDER_ENGINE          渲染引擎: BLENDER_EEVEE_NEXT | CYCLES (默认: BLENDER_EEVEE_NEXT)
    BLENDER_RESOLUTION_X    水平分辨率 (默认: 1280)
    BLENDER_RESOLUTION_Y    垂直分辨率 (默认: 720)
    BLENDER_FPS             帧率 (默认: 24)
    BLENDER_FRAME_START     起始帧 (默认: 1)
    BLENDER_FRAME_END       结束帧 (默认: 1)
    BLENDER_OUTPUT_PREFIX   输出文件名前缀 (默认: "blender_scene")
    BLENDER_RENDER_SAMPLES  采样数 (默认: 64)
    BLENDER_USE_FREESTYLE   是否启用 Freestyle 线稿 (1/0, 默认: 1)
"""

import os
from pathlib import Path

import bpy  # noqa: F401


def get_env_config() -> dict:
    """Read config from environment variables with defaults."""
    return {
        "scene_outdir": os.environ.get("BLENDER_SCENE_OUTDIR", "/tmp/blender_frames"),
        "engine": os.environ.get("BLENDER_ENGINE", "BLENDER_EEVEE_NEXT"),
        "resolution_x": int(os.environ.get("BLENDER_RESOLUTION_X", "1280")),
        "resolution_y": int(os.environ.get("BLENDER_RESOLUTION_Y", "720")),
        "fps": int(os.environ.get("BLENDER_FPS", "24")),
        "frame_start": int(os.environ.get("BLENDER_FRAME_START", "1")),
        "frame_end": int(os.environ.get("BLENDER_FRAME_END", "1")),
        "output_prefix": os.environ.get("BLENDER_OUTPUT_PREFIX", "blender_scene"),
        "render_samples": int(os.environ.get("BLENDER_RENDER_SAMPLES", "64")),
        "use_freestyle": int(os.environ.get("BLENDER_USE_FREESTYLE", "1")),
    }


def configure_render(cfg: dict) -> None:
    """Configure Blender render settings from env config."""
    scene = bpy.context.scene

    # Resolution
    scene.render.resolution_x = cfg["resolution_x"]
    scene.render.resolution_y = cfg["resolution_y"]
    scene.render.resolution_percentage = 100

    # Frame range
    scene.frame_start = cfg["frame_start"]
    scene.frame_end = cfg["frame_end"]
    scene.frame_step = 1

    # FPS
    scene.render.fps = cfg["fps"]

    # Engine
    engine = cfg["engine"]
    scene.render.engine = engine
    if engine == "CYCLES":
        scene.cycles.samples = cfg["render_samples"]
        # Apple Silicon Metal device
        cycles_prefs = bpy.context.preferences.addons["cycles"].preferences
        cycles_prefs.compute_device_type = "METAL"
        cycles_prefs.get_devices()
        for device in cycles_prefs.devices:
            if device.type == "METAL":
                device.use = True
    elif engine == "BLENDER_EEVEE_NEXT":
        scene.eevee.taa_samples = cfg["render_samples"]

    # Output
    outdir = Path(cfg["scene_outdir"])
    outdir.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(outdir / f"{cfg['output_prefix']}_####")
    scene.render.image_settings.file_format = "PNG"

    # Freestyle
    scene.render.use_freestyle = bool(cfg["use_freestyle"])


def ensure_scene_setup() -> None:
    """Ensure the scene has basic light + camera."""
    if not any(obj.type == "LIGHT" for obj in bpy.data.objects):
        light_data = bpy.data.lights.new(name="DefaultLight", type="SUN")
        light_obj = bpy.data.objects.new(name="DefaultLight", object_data=light_data)
        bpy.context.collection.objects.link(light_obj)
        light_obj.location = (5.0, -5.0, 10.0)
        light_obj.rotation_euler = (0.5, 0.0, 0.5)
        light_data.energy = 3.0

    if not any(obj.type == "CAMERA" for obj in bpy.data.objects):
        cam_data = bpy.data.cameras.new(name="DefaultCamera")
        cam_obj = bpy.data.objects.new(name="Camera", object_data=cam_data)
        bpy.context.collection.objects.link(cam_obj)
        cam_obj.location = (0.0, -8.0, 3.0)
        cam_obj.rotation_euler = (0.3, 0.0, 0.0)
        bpy.context.scene.camera = cam_obj


def render(cfg: dict) -> dict:
    """Run the actual render and return metadata."""
    configure_render(cfg)
    ensure_scene_setup()

    total_frames = cfg["frame_end"] - cfg["frame_start"] + 1
    is_animation = total_frames > 1

    if is_animation:
        bpy.ops.render.render(animation=True)
    else:
        bpy.ops.render.render(write_still=True)

    return {
        "engine": cfg["engine"],
        "resolution": f'{cfg["resolution_x"]}x{cfg["resolution_y"]}',
        "fps": cfg["fps"],
        "frame_start": cfg["frame_start"],
        "frame_end": cfg["frame_end"],
        "total_frames": total_frames,
        "output_dir": str(Path(cfg["scene_outdir"]).resolve()),
        "output_prefix": cfg["output_prefix"],
    }


if __name__ == "__main__":
    config = get_env_config()
    result = render(config)
    print(f"RENDER_RESULT: {result}")
