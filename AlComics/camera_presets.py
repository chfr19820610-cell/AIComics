#!/usr/bin/env python3
"""
摄像机预设 — 9种3D摄像机动画
从 aicg-handbook §3.7 分镜卡片映射到 Blender 3D 摄像机关键帧

调用方式: 在 render_shot.py 中 import 后调用 setup_camera_animation()
"""

import bpy
import math
from mathutils import Vector


# Camera preset mapping from storyboard shot_type to 3D position/look-at
SHOT_TYPE_CAMERAS = {
    "EW": {  # Extreme Wide — 环境建立
        "pos": (0.0, 2.5, 12.0),
        "look_at": (0.0, 0.8, 0.0),
        "fov": 60,
        "focal_length": 35,
    },
    "WS": {  # Wide Shot — 角色+环境
        "pos": (0.0, 1.4, 6.0),
        "look_at": (0.0, 0.8, 0.0),
        "fov": 45,
        "focal_length": 50,
    },
    "MS": {  # Medium Shot — 对话/动作
        "pos": (0.0, 1.2, 3.5),
        "look_at": (0.0, 0.8, 0.0),
        "fov": 35,
        "focal_length": 70,
    },
    "MCU": {  # Medium Close-up — 情绪/反应
        "pos": (0.0, 1.1, 2.0),
        "look_at": (0.0, 0.9, 0.0),
        "fov": 25,
        "focal_length": 85,
    },
    "CU": {  # Close-up — 细节/关键
        "pos": (0.0, 1.0, 1.2),
        "look_at": (0.0, 1.0, 0.0),
        "fov": 20,
        "focal_length": 100,
    },
    "ECU": {  # Extreme Close-up — 强调
        "pos": (0.0, 0.95, 0.5),
        "look_at": (0.0, 0.95, 0.0),
        "fov": 12,
        "focal_length": 150,
    },
    "OTS": {  # Over-the-Shoulder — 对话关系
        "pos": (-1.2, 1.2, 2.5),
        "look_at": (0.3, 0.8, 0.0),
        "fov": 35,
        "focal_length": 70,
    },
}


def create_camera(
    name: str = "PipelineCamera",
    shot_type: str = "MS",
    resolution: tuple = (1080, 1920),
) -> bpy.types.Object:
    """
    Create a camera with correct aspect ratio and sensor settings for 9:16 vertical.

    Args:
        name: Camera object name
        shot_type: EW/WS/MS/MCU/CU/ECU/OTS
        resolution: (width, height)

    Returns:
        Camera object
    """
    preset = SHOT_TYPE_CAMERAS.get(shot_type, SHOT_TYPE_CAMERAS["MS"])

    # Create camera data
    cam_data = bpy.data.cameras.new(name=name)
    cam_data.type = "PERSP"
    cam_data.lens = preset["focal_length"]
    cam_data.angle = math.radians(preset["fov"])
    cam_data.sensor_fit = "VERTICAL"
    cam_data.sensor_width = 36.0
    cam_data.sensor_height = 24.0

    # Create camera object
    cam_obj = bpy.data.objects.new(name, cam_data)

    # Position based on shot type
    cam_obj.location = Vector(preset["pos"])
    cam_obj.rotation_euler = (0, 0, 0)  # Will be set by track_to

    # Add to scene
    bpy.context.scene.collection.objects.link(cam_obj)

    # Add Track To constraint
    track = cam_obj.constraints.new(type="TRACK_TO")
    track.target = _get_or_create_empty("CameraTarget", preset["look_at"])
    track.track_axis = "TRACK_NEGATIVE_Z"
    track.up_axis = "UP_Y"

    # Set render resolution
    scene = bpy.context.scene
    scene.render.resolution_x = resolution[0]
    scene.render.resolution_y = resolution[1]
    scene.render.resolution_percentage = 100

    return cam_obj


def _get_or_create_empty(name: str, location: tuple) -> bpy.types.Object:
    """Get or create an empty object (used as camera target)."""
    obj = bpy.data.objects.get(name)
    if obj is None:
        obj = bpy.data.objects.new(name, None)
        bpy.context.scene.collection.objects.link(obj)
    obj.location = Vector(location)
    return obj


def animate_camera(
    cam_obj: bpy.types.Object,
    camera_type: str,
    duration_sec: float,
    fps: int = 24,
    target_obj: bpy.types.Object = None,
) -> None:
    """
    Animate camera movement over the shot duration.

    Camera animation types (from aicg-handbook §3.7):
      dolly_in   — Move camera forward along Z (local)
      dolly_out  — Move camera backward along Z
      pan_left   — Rotate camera Y-axis left
      pan_right  — Rotate camera Y-axis right
      boom_up    — Move camera Z up
      boom_down  — Move camera Z down
      track_left — Move camera X left
      track_right— Move camera X right
      static     — No animation (lock in place)
      orbit      — Orbit around target

    Args:
        cam_obj: Camera object to animate
        camera_type: Animation type string
        duration_sec: Duration in seconds
        fps: Frames per second
        target_obj: Target for orbit animation (optional)
    """
    total_frames = int(duration_sec * fps)
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = total_frames

    # Movement magnitude per camera type
    move_amounts = {
        "dolly_in": (0.0, 0.0, 2.5),       # Move forward 2.5 units
        "dolly_out": (0.0, 0.0, -2.5),      # Move backward
        "boom_up": (0.0, 0.0, 1.5),         # Rise 1.5 units
        "boom_down": (0.0, 0.0, -1.5),      # Descend
        "track_left": (-1.5, 0.0, 0.0),     # Slide left
        "track_right": (1.5, 0.0, 0.0),     # Slide right
        "pan_left": None,                     # Rotation-based (handled below)
        "pan_right": None,
        "orbit": None,
        "static": (0.0, 0.0, 0.0),
    }

    if camera_type in ("pan_left", "pan_right"):
        # Rotation animation
        start_rot = cam_obj.rotation_euler.copy()
        end_rot = start_rot.copy()
        angle = math.radians(15)  # 15 degrees pan
        if camera_type == "pan_left":
            end_rot[2] += angle
        else:
            end_rot[2] -= angle

        # Keyframes
        cam_obj.rotation_euler = start_rot
        cam_obj.keyframe_insert(data_path="rotation_euler", frame=1)

        cam_obj.rotation_euler = end_rot
        cam_obj.keyframe_insert(data_path="rotation_euler", frame=total_frames)

    elif camera_type == "orbit" and target_obj:
        # Orbit: create an empty at target, parent camera to it, rotate empty
        orbit_center = _get_or_create_empty("OrbitCenter", target_obj.location)
        cam_obj.parent = orbit_center

        start_rot = orbit_center.rotation_euler.copy()
        end_rot = start_rot.copy()
        end_rot[2] += math.radians(30)  # 30 degrees orbit

        orbit_center.rotation_euler = start_rot
        orbit_center.keyframe_insert(data_path="rotation_euler", frame=1)

        orbit_center.rotation_euler = end_rot
        orbit_center.keyframe_insert(data_path="rotation_euler", frame=total_frames)

    elif camera_type in move_amounts:
        movement = move_amounts[camera_type]
        start_pos = cam_obj.location.copy()

        # Move in local Z (forward/backward) for dolly
        if camera_type.startswith("dolly"):
            # Get camera's local forward direction
            forward = cam_obj.matrix_world.to_quaternion() @ Vector((0, 0, -1))
            end_pos = start_pos + forward * movement[2]
        elif camera_type.startswith("boom"):
            end_pos = start_pos + Vector((0, 0, movement[2]))
        elif camera_type.startswith("track"):
            right = cam_obj.matrix_world.to_quaternion() @ Vector((1, 0, 0))
            end_pos = start_pos + right * movement[0]
        else:
            end_pos = start_pos + Vector(movement)

        # Keyframes
        cam_obj.location = start_pos
        cam_obj.keyframe_insert(data_path="location", frame=1)

        cam_obj.location = end_pos
        cam_obj.keyframe_insert(data_path="location", frame=total_frames)

    else:
        # Static — just keyframe the starting position
        cam_obj.keyframe_insert(data_path="location", frame=1)

    # Set interpolation to linear for smooth motion
    for fc in cam_obj.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

    scene.frame_set(1)


def setup_render_settings(
    engine: str = "BLENDER_EEVEE_NEXT",
    samples: int = 32,
    resolution: tuple = (1080, 1920),
    fps: int = 24,
    output_format: str = "PNG",
    color_mode: str = "RGBA",
    color_depth: str = "8",
):
    """
    Configure Blender render settings for the pipeline.

    Args:
        engine: BLENDER_EEVEE_NEXT or CYCLES
        samples: Render samples
        resolution: (width, height)
        fps: Frames per second
        output_format: PNG, OPEN_EXR, etc.
        color_mode: RGBA or RGB
        color_depth: 8 or 16
    """
    scene = bpy.context.scene

    # Render engine
    scene.render.engine = engine
    if engine == "BLENDER_EEVEE_NEXT":
        scene.eevee.taa_render_samples = samples
    elif engine == "CYCLES":
        scene.cycles.samples = samples

    # Resolution
    scene.render.resolution_x = resolution[0]
    scene.render.resolution_y = resolution[1]
    scene.render.resolution_percentage = 100

    # FPS
    scene.render.fps = fps
    scene.frame_start = 1

    # Output format
    scene.render.image_settings.file_format = output_format
    scene.render.image_settings.color_mode = color_mode
    scene.render.image_settings.color_depth = color_depth

    # Transparency
    scene.render.film_transparent = True

    # Simplify for performance
    scene.render.use_simplify = False
    scene.render.use_persistent_data = True

    # View transform
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"


if __name__ == "__main__":
    import sys

    # Test: setup camera with orbit animation
    print("Testing camera presets...")
    shot_type = sys.argv[1] if len(sys.argv) > 1 else "MS"
    camera_type = sys.argv[2] if len(sys.argv) > 2 else "static"

    cam = create_camera(shot_type=shot_type)
    animate_camera(cam, camera_type, 5.0, 24)
    setup_render_settings()
    print(f"Camera '{shot_type}' with animation '{camera_type}' setup complete.")
