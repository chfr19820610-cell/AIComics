"""
Blender 测试场景搭建脚本
========================
创建一个简单 3D 场景并输出 .blend 文件，包含默认摄像机动画（绕 Y 轴旋转弧线）。

通过环境变量传递参数（避免 Blender argparse 冲突）:
    BLENDER_OUTPUT     输出的 .blend 文件路径 (默认: /tmp/blender_test_scene.blend)
    BLENDER_DURATION   动画持续时间(秒) (默认: 3)
    BLENDER_FPS        帧率 (默认: 24)
"""

import math
import os
from pathlib import Path

import bpy  # noqa: F401


def get_env_args() -> dict:
    return {
        "output": os.environ.get("BLENDER_OUTPUT", "/tmp/blender_test_scene.blend"),
        "duration": int(os.environ.get("BLENDER_DURATION", "3")),
        "fps": int(os.environ.get("BLENDER_FPS", "24")),
    }


def create_test_scene(output: str, duration: int, fps: int) -> None:
    """Create a simple 3D scene with camera animation."""
    # Clear existing mesh objects
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    # ── Ground plane ─────────────────────────────────────
    bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, 0))
    ground = bpy.context.active_object
    ground.name = "Ground"

    # Ground material
    mat_ground = bpy.data.materials.new(name="GroundMat")
    mat_ground.use_nodes = True
    bsdf = mat_ground.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.1, 0.1, 0.15, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.4
    ground.data.materials.append(mat_ground)

    # ── Center object: torus ──────────────────────────────
    bpy.ops.mesh.primitive_torus_add(
        location=(0, 0, 1.5), major_radius=1.5, minor_radius=0.4
    )
    torus = bpy.context.active_object
    torus.name = "CenterTorus"
    bpy.ops.object.shade_smooth()

    # Torus material
    mat_torus = bpy.data.materials.new(name="TorusMat")
    mat_torus.use_nodes = True
    nodes = mat_torus.node_tree.nodes
    bsdf = nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.2, 0.5, 0.8, 1.0)
    bsdf.inputs["Metallic"].default_value = 0.3
    bsdf.inputs["Roughness"].default_value = 0.2
    torus.data.materials.append(mat_torus)

    # ── Pillars around the scene ──────────────────────────
    pillar_positions = [
        (6, 6, 0),
        (-6, 6, 0),
        (6, -6, 0),
        (-6, -6, 0),
    ]
    pillar_mat = bpy.data.materials.new(name="PillarMat")
    pillar_mat.use_nodes = True
    p_bsdf = pillar_mat.node_tree.nodes["Principled BSDF"]
    p_bsdf.inputs["Base Color"].default_value = (0.8, 0.6, 0.2, 1.0)
    p_bsdf.inputs["Roughness"].default_value = 0.6

    for pos in pillar_positions:
        bpy.ops.mesh.primitive_cylinder_add(
            location=(pos[0], pos[1], 1.5), radius=0.3, depth=3
        )
        pillar = bpy.context.active_object
        pillar.name = f"Pillar_{pos[0]}_{pos[1]}"
        pillar.data.materials.append(pillar_mat)

    # ── Small floating spheres ────────────────────────────
    sphere_mat = bpy.data.materials.new(name="SphereMat")
    sphere_mat.use_nodes = True
    s_bsdf = sphere_mat.node_tree.nodes["Principled BSDF"]
    s_bsdf.inputs["Base Color"].default_value = (0.9, 0.2, 0.3, 1.0)
    s_bsdf.inputs["Metallic"].default_value = 0.8
    s_bsdf.inputs["Roughness"].default_value = 0.1

    for i in range(8):
        angle = (math.pi * 2 / 8) * i
        x = 4.0 * math.cos(angle)
        y = 4.0 * math.sin(angle)
        bpy.ops.mesh.primitive_uv_sphere_add(
            location=(x, y, 2.5), radius=0.3
        )
        sphere = bpy.context.active_object
        sphere.name = f"Sphere_{i}"
        sphere.data.materials.append(sphere_mat)

    # ── Lighting: Three-point ─────────────────────────────
    # Key light
    key_data = bpy.data.lights.new(name="KeyLight", type="AREA")
    key_obj = bpy.data.objects.new(name="KeyLight", object_data=key_data)
    bpy.context.collection.objects.link(key_obj)
    key_obj.location = (5, -5, 6)
    key_obj.rotation_euler = (0.6, 0.1, 0.4)
    key_data.energy = 200
    key_data.size = 2

    # Fill light
    fill_data = bpy.data.lights.new(name="FillLight", type="AREA")
    fill_obj = bpy.data.objects.new(name="FillLight", object_data=fill_data)
    bpy.context.collection.objects.link(fill_obj)
    fill_obj.location = (-4, 3, 4)
    fill_obj.rotation_euler = (0.4, 0.0, -0.5)
    fill_data.energy = 100
    fill_data.size = 2
    fill_data.color = (0.8, 0.9, 1.0)

    # Rim light
    rim_data = bpy.data.lights.new(name="RimLight", type="AREA")
    rim_obj = bpy.data.objects.new(name="RimLight", object_data=rim_data)
    bpy.context.collection.objects.link(rim_obj)
    rim_obj.location = (-2, 6, 3)
    rim_obj.rotation_euler = (0.3, 0.0, 0.8)
    rim_data.energy = 80
    rim_data.size = 1.5

    # ── Camera animation ──────────────────────────────────
    total_frames = duration * fps

    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = total_frames
    scene.render.fps = fps
    scene.render.fps_base = 1.0

    # Create camera
    cam_data = bpy.data.cameras.new(name="MainCamera")
    cam_obj = bpy.data.objects.new(name="Camera", object_data=cam_data)
    bpy.context.collection.objects.link(cam_obj)
    scene.camera = cam_obj
    cam_data.lens = 50
    cam_data.clip_end = 100

    # Camera path: semi-circle arc looking at origin
    arc_radius = 10.0
    start_angle = math.radians(60)
    end_angle = math.radians(120)

    for frame in range(1, total_frames + 1):
        t = (frame - 1) / max(total_frames - 1, 1)
        angle = start_angle + (end_angle - start_angle) * t

        x = arc_radius * math.cos(angle)
        y = arc_radius * math.sin(angle)

        cam_obj.location = (x, y, 2.0 + 1.0 * math.sin(t * math.pi))
        cam_obj.keyframe_insert(data_path="location", frame=frame)

        # Track To constraint (set once)
        if frame == 1:
            track = cam_obj.constraints.new(type="TRACK_TO")
            empty = bpy.data.objects.new(name="CameraTarget", object_data=None)
            bpy.context.collection.objects.link(empty)
            empty.location = (0, 0, 0)
            track.target = empty
            track.track_axis = "TRACK_NEGATIVE_Z"
            track.up_axis = "UP_Y"

    # ── Render settings ───────────────────────────────────
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    scene.render.resolution_percentage = 100
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.use_freestyle = True
    scene.render.image_settings.file_format = "PNG"


if __name__ == "__main__":
    args = get_env_args()
    output_path = args["output"]
    duration = args["duration"]
    fps = args["fps"]

    create_test_scene(output_path, duration, fps)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output_path))
    print(f"Scene saved to: {output_path}")
    print(f"Duration: {duration}s, FPS: {fps}, Frames: {duration * fps}")
