#!/usr/bin/env python3
"""
Blender 单镜头渲染脚本 — 3D管线 Phase 4
======================================
命令行: /path/to/blender --background --python render_shot.py -- [args]

Args:
  --fbx <path>           FBX model path (required)
  --env-fbx <path>       Environment FBX path (optional)
  --output <dir>         PNG sequence output directory (required)
  --shot-type <str>      EW|WS|MS|MCU|CU|ECU|OTS (default: MS)
  --camera <str>         dolly_in|dolly_out|pan_left|pan_right|boom_up|boom_down|track_left|track_right|static|orbit (default: static)
  --duration <float>     Shot duration in seconds (default: 5)
  --fps <int>            Frames per second (default: 24)
  --lighting <str>       Lighting preset name (default: cinematic_noir)
  --resolution <str>     WidthxHeight (default: 1080x1920)
  --samples <int>        Render samples (default: 32)
  --engine <str>         Render engine (default: BLENDER_EEVEE_NEXT)
  --no-cel-shader        Skip cel shader setup (use material as-is)
  --no-outline           Skip outline creation

Example:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
    --python render_shot.py -- \
    --fbx /path/to/character.fbx \
    --output /path/to/output/ \
    --shot-type CU --camera static --duration 6 --lighting cinematic_noir
"""

import bpy
import sys
import os
import argparse
import json
from pathlib import Path
from mathutils import Vector

# ============================================================
# CLI Argument Parsing (inside Blender)
# ============================================================


def parse_args():
    """Parse CLI args from Blender's -- separator."""
    # Blender passes everything after '--' as sys.argv
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []

    parser = argparse.ArgumentParser(description="Blender 3D Shot Renderer")
    parser.add_argument("--fbx", type=str, required=True, help="Character FBX path")
    parser.add_argument("--env-fbx", type=str, default="", help="Environment FBX path")
    parser.add_argument("--output", type=str, required=True, help="Output directory for PNG sequence")
    parser.add_argument("--shot-type", type=str, default="MS",
                        choices=["EW", "WS", "MS", "MCU", "CU", "ECU", "OTS"])
    parser.add_argument("--camera", type=str, default="static",
                        choices=["dolly_in", "dolly_out", "pan_left", "pan_right",
                                 "boom_up", "boom_down", "track_left", "track_right",
                                 "static", "orbit"])
    parser.add_argument("--duration", type=float, default=5.0)
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--lighting", type=str, default="cinematic_noir",
                        choices=["overcast_moody", "cinematic_noir", "bright_drama",
                                 "horror_lowkey", "romance_warm"])
    parser.add_argument("--resolution", type=str, default="1080x1920")
    parser.add_argument("--samples", type=int, default=32)
    parser.add_argument("--engine", type=str, default="BLENDER_EEVEE_NEXT",
                        choices=["BLENDER_EEVEE_NEXT", "CYCLES"])
    parser.add_argument("--no-cel-shader", action="store_true")
    parser.add_argument("--no-outline", action="store_true")
    parser.add_argument("--cel-shadow", type=str, default="0.15,0.15,0.25,1.0")
    parser.add_argument("--cel-mid", type=str, default="0.40,0.40,0.60,1.0")
    parser.add_argument("--cel-highlight", type=str, default="0.80,0.80,1.00,1.0")

    return parser.parse_args(argv)


def parse_color(color_str: str) -> tuple:
    """Parse 'r,g,b,a' string to tuple."""
    parts = [float(x) for x in color_str.split(",")]
    while len(parts) < 4:
        parts.append(1.0)
    return tuple(parts[:4])


# ============================================================
# Scene Cleanup
# ============================================================


def clear_scene():
    """Remove all objects from the default scene."""
    for obj in bpy.data.objects:
        bpy.data.objects.remove(obj, do_unlink=True)

    # Clean orphan data
    for block in bpy.data.meshes:
        bpy.data.meshes.remove(block)
    for block in bpy.data.materials:
        bpy.data.materials.remove(block)
    for block in bpy.data.lights:
        bpy.data.lights.remove(block)
    for block in bpy.data.cameras:
        bpy.data.cameras.remove(block)


# ============================================================
# FBX Import
# ============================================================


def import_fbx(fbx_path: str, scale: float = 1.0) -> list:
    """
    Import an FBX file into the scene.

    Args:
        fbx_path: Path to .fbx file
        scale: Import scale factor (for Mixamo compatibility)

    Returns:
        List of imported object names
    """
    if not os.path.exists(fbx_path):
        print(f"  ❌ FBX not found: {fbx_path}")
        return []

    # Record existing objects
    existing = set(bpy.data.objects.keys())

    try:
        bpy.ops.import_scene.fbx(
            filepath=fbx_path,
            use_anim=False,
            global_scale=scale,
            use_custom_normals=True,
        )
    except Exception as e:
        print(f"  ❌ FBX import failed: {e}")
        return []

    # Find new objects
    new_objs = [obj for obj in bpy.data.objects if obj.name not in existing]
    print(f"  📦 导入 FBX: {os.path.basename(fbx_path)} ({len(new_objs)} 对象)")

    # Select all imported objects
    bpy.ops.object.select_all(action="DESELECT")
    for obj in new_objs:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = new_objs[0] if new_objs else None

    return new_objs


# ============================================================
# Main Render Pipeline
# ============================================================


def render_shot(args):
    """Execute the full shot rendering pipeline."""
    print(f"\n{'='*60}")
    print(f"🎬 Blender 3D Shot Renderer")
    print(f"  镜头类型: {args.shot_type} | 摄像机: {args.camera}")
    print(f"  时长: {args.duration}s @ {args.fps}fps")
    print(f"  灯光: {args.lighting} | 引擎: {args.engine}")
    print(f"  分辨率: {args.resolution} | 采样: {args.samples}")
    print(f"{'='*60}\n")

    # ---- Step 1: Clear scene -------------------------------------------------
    print("Step 1/6: 清理场景...")
    clear_scene()

    # ---- Step 2: Import FBX models -------------------------------------------
    print("\nStep 2/6: 导入FBX模型...")
    all_objects = []

    # Import environment first (if provided)
    if args.env_fbx:
        env_objs = import_fbx(args.env_fbx, scale=0.01)  # Environment typically smaller scale
        all_objects.extend(env_objs)

    # Import character
    char_objs = import_fbx(args.fbx, scale=1.0)
    all_objects.extend(char_objs)

    if not all_objects:
        print("  ⚠️  无有效3D对象，使用默认Cube作为占位")
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0))

    # ---- Step 3: Cel Shader --------------------------------------------------
    print("\nStep 3/6: 设置赛璐璐材质...")
    if not args.no_cel_shader:
        # Import cel shader module
        script_dir = os.path.dirname(os.path.abspath(__file__))
        if script_dir not in sys.path:
            sys.path.insert(0, script_dir)

        try:
            from cel_shader_setup import apply_cel_shader_to_all_meshes, set_background_color, setup_freestyle_outline

            shadow = parse_color(args.cel_shadow)
            mid = parse_color(args.cel_mid)
            highlight = parse_color(args.cel_highlight)

            apply_cel_shader_to_all_meshes(
                shadow_color=shadow,
                mid_color=mid,
                highlight_color=highlight,
                skip_outline=args.no_outline,
            )
            set_background_color(color=(0.05, 0.05, 0.10, 1.0))

            if not args.no_outline:
                setup_freestyle_outline(line_thickness=1.5)
                print("  ✅ Cel Shader + Freestyle Outline 已配置")
            else:
                print("  ✅ Cel Shader 已配置 (无轮廓线)")
        except ImportError as e:
            print(f"  ⚠️  Cel shader module not found: {e}")
            print("  💡  将使用模型自带材质")
    else:
        print("  ⏭️  跳过Cel Shader (--no-cel-shader)")

    # ---- Step 4: Lighting ----------------------------------------------------
    print("\nStep 4/6: 设置灯光...")
    try:
        from lighting_presets import setup_lighting
        setup_lighting(args.lighting)
    except ImportError as e:
        print(f"  ⚠️  Lighting module not found: {e}")
        print("  💡  使用默认灯光")

    # ---- Step 5: Camera ------------------------------------------------------
    print("\nStep 5/6: 设置摄像机...")
    try:
        from camera_presets import create_camera, animate_camera, setup_render_settings

        res_w, res_h = [int(x) for x in args.resolution.split("x")]
        setup_render_settings(
            engine=args.engine,
            samples=args.samples,
            resolution=(res_w, res_h),
            fps=args.fps,
        )

        cam = create_camera(shot_type=args.shot_type, resolution=(res_w, res_h))

        # Find the main character mesh as camera target
        char_obj = None
        for obj in all_objects:
            if obj.type == "MESH" and "_outline" not in obj.name:
                # Try to find the armature (rig) instead
                for parent_obj in bpy.data.objects:
                    if parent_obj.type == "ARMATURE" and obj.parent == parent_obj:
                        char_obj = parent_obj
                        break
                if not char_obj:
                    char_obj = obj
                break

        animate_camera(cam, args.camera, args.duration, args.fps, char_obj)
        print(f"  ✅ 摄像机: {args.shot_type} + {args.camera} 动画")
    except ImportError as e:
        print(f"  ⚠️  Camera module not found: {e}")
        print("  💡  使用默认摄像机")

    # ---- Step 6: Render ------------------------------------------------------
    print(f"\nStep 6/6: 渲染输出...")

    total_frames = int(args.duration * args.fps)
    scene = bpy.context.scene
    scene.frame_end = total_frames

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Set output path
    scene.render.filepath = str(output_dir / "")  # Trailing slash for sequence
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"

    # Use frame padding for sequence
    scene.render.use_overwrite = False
    scene.render.use_file_extension = True

    print(f"  输出目录: {output_dir}")
    print(f"  总帧数: {total_frames} (帧1→{total_frames})")
    print(f"  开始渲染...")

    try:
        bpy.ops.render.render(animation=True, write_still=True)
        print(f"\n  ✅ 渲染完成! {total_frames} 帧 → {output_dir}")
    except Exception as e:
        print(f"\n  ❌ 渲染失败: {e}")
        # Try to save the blend file for debugging
        debug_path = output_dir / "debug_scene.blend"
        try:
            bpy.ops.wm.save_as_mainfile(filepath=str(debug_path))
            print(f"  💾 调试场景已保存: {debug_path}")
        except Exception:
            pass
        return False

    return True


# ============================================================
# Entry Point
# ============================================================


def main():
    args = parse_args()
    success = render_shot(args)

    if success:
        print(f"\n{'='*60}")
        print(f"✅ 镜头渲染成功!")
        print(f"{'='*60}")
    else:
        print(f"\n{'='*60}")
        print(f"❌ 镜头渲染失败!")
        print(f"{'='*60}")
        sys.exit(1)


if __name__ == "__main__":
    main()
