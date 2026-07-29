#!/usr/bin/env python3
"""
灯光预设 — 5种电影级灯光方案
从 aicg-handbook §1.3 光影设计 + pipeline-spec §3.4

调用方式: 在 render_shot.py 中 import 后调用 setup_lighting()
"""

import bpy
import math
from mathutils import Vector


# ============================================================
# Lighting Presets
# ============================================================

LIGHTING_PRESETS = {
    "overcast_moody": {
        "description": "阴天忧郁 — 雨天/悲伤场景",
        "world_color": (0.05, 0.06, 0.12, 1.0),
        "world_strength": 0.3,
        "lights": [
            {
                "type": "SUN",
                "name": "Key_Overcast",
                "location": (3.0, -3.0, 6.0),
                "rotation": (math.radians(45), math.radians(15), math.radians(30)),
                "color": (0.83, 0.77, 0.69),  # Warm gray
                "energy": 4.0,
                "angle": math.radians(30),  # Soft shadows
            },
            {
                "type": "AREA",
                "name": "Fill_Cool",
                "location": (-3.0, 0.0, 2.0),
                "color": (0.69, 0.77, 0.87),  # Cool blue
                "energy": 1.5,
                "size": 5.0,
            },
        ],
    },
    "cinematic_noir": {
        "description": "电影暗黑 — 悬疑/暗黑奇幻",
        "world_color": (0.02, 0.02, 0.05, 1.0),
        "world_strength": 0.15,
        "lights": [
            {
                "type": "SPOT",
                "name": "Key_Dramatic",
                "location": (2.0, -4.0, 5.0),
                "color": (1.0, 0.90, 0.71),  # Warm orange
                "energy": 800.0,
                "spot_size": math.radians(45),
                "spot_blend": 0.3,
            },
            {
                "type": "AREA",
                "name": "Fill_Cold",
                "location": (-2.0, 0.0, 2.0),
                "color": (0.42, 0.48, 0.55),  # Steel blue
                "energy": 2.0,
                "size": 3.0,
            },
            {
                "type": "SPOT",
                "name": "Rim_White",
                "location": (0.0, 4.0, 4.0),
                "color": (1.0, 1.0, 1.0),
                "energy": 400.0,
                "spot_size": math.radians(30),
                "spot_blend": 0.5,
            },
        ],
    },
    "bright_drama": {
        "description": "明亮戏剧 — 高潮/揭示场景",
        "world_color": (0.15, 0.18, 0.30, 1.0),
        "world_strength": 0.4,
        "lights": [
            {
                "type": "SUN",
                "name": "Key_Bright",
                "location": (5.0, -5.0, 8.0),
                "color": (1.0, 1.0, 1.0),
                "energy": 8.0,
                "angle": math.radians(10),
            },
            {
                "type": "AREA",
                "name": "Fill_Warm",
                "location": (-4.0, 0.0, 3.0),
                "color": (0.96, 0.90, 0.79),  # Warm cream
                "energy": 3.0,
                "size": 6.0,
            },
            {
                "type": "SPOT",
                "name": "Rim_Gold",
                "location": (0.0, 5.0, 5.0),
                "color": (1.0, 0.84, 0.0),  # Gold
                "energy": 500.0,
                "spot_size": math.radians(35),
                "spot_blend": 0.4,
            },
        ],
    },
    "horror_lowkey": {
        "description": "恐怖暗调 — 闪回/紧张场景",
        "world_color": (0.01, 0.01, 0.02, 1.0),
        "world_strength": 0.05,
        "lights": [
            {
                "type": "SPOT",
                "name": "Key_Green",
                "location": (1.0, -3.0, 2.0),
                "color": (0.10, 0.35, 0.15),  # Sickly green
                "energy": 500.0,
                "spot_size": math.radians(20),
                "spot_blend": 0.2,
            },
            {
                "type": "POINT",
                "name": "Accent_Red",
                "location": (-2.0, 0.0, 1.5),
                "color": (0.60, 0.05, 0.05),  # Deep red
                "energy": 200.0,
            },
        ],
    },
    "romance_warm": {
        "description": "温情暖调 — 温情/回忆场景",
        "world_color": (0.10, 0.08, 0.15, 1.0),
        "world_strength": 0.25,
        "lights": [
            {
                "type": "AREA",
                "name": "Key_Amber",
                "location": (3.0, -2.0, 4.0),
                "color": (1.0, 0.75, 0.50),  # Amber
                "energy": 5.0,
                "size": 4.0,
            },
            {
                "type": "AREA",
                "name": "Fill_Pink",
                "location": (-2.0, 0.0, 2.5),
                "color": (1.0, 0.82, 0.86),  # Soft pink
                "energy": 2.0,
                "size": 3.0,
            },
            {
                "type": "POINT",
                "name": "Rim_Warm",
                "location": (0.0, 3.0, 3.5),
                "color": (1.0, 1.0, 1.0),
                "energy": 300.0,
            },
        ],
    },
}


# ============================================================
# Lighting Functions
# ============================================================


def clear_all_lights():
    """Remove all existing light objects from the scene."""
    for obj in bpy.data.objects:
        if obj.type == "LIGHT":
            bpy.data.objects.remove(obj, do_unlink=True)


def clear_all_world():
    """Remove world lighting."""
    for world in bpy.data.worlds:
        bpy.data.worlds.remove(world)


def setup_lighting(preset_name: str = "cinematic_noir") -> dict:
    """
    Setup scene lighting from a preset.

    Args:
        preset_name: One of 'overcast_moody', 'cinematic_noir', 'bright_drama',
                    'horror_lowkey', 'romance_warm'

    Returns:
        Dict with created light objects summary
    """
    preset = LIGHTING_PRESETS.get(preset_name, LIGHTING_PRESETS["cinematic_noir"])

    # Clear existing lights
    clear_all_lights()

    # Setup world
    world = bpy.context.scene.world
    if not world:
        world = bpy.data.worlds.new("World")
        bpy.context.scene.world = world

    world.use_nodes = True
    nodes = world.node_tree.nodes

    bg = nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = preset["world_color"]
        bg.inputs["Strength"].default_value = preset["world_strength"]

    # Create lights
    created_lights = []

    for light_def in preset["lights"]:
        light_type = light_def["type"]
        light_data = bpy.data.lights.new(name=light_def["name"], type=light_type)
        light_data.color = light_def["color"]
        light_data.energy = light_def["energy"]

        # Type-specific settings
        if light_type == "SUN":
            light_data.angle = light_def.get("angle", math.radians(10))
        elif light_type == "SPOT":
            light_data.spot_size = light_def.get("spot_size", math.radians(45))
            light_data.spot_blend = light_def.get("spot_blend", 0.15)
        elif light_type == "AREA":
            sz = light_def.get("size", 5.0)
            light_data.size = sz
            light_data.shape = "RECTANGLE"
            light_data.size_y = sz

        # Create object
        light_obj = bpy.data.objects.new(name=light_def["name"], object_data=light_data)
        light_obj.location = light_def["location"]

        if "rotation" in light_def:
            light_obj.rotation_euler = light_def["rotation"]

        bpy.context.scene.collection.objects.link(light_obj)
        created_lights.append(light_obj.name)

    print(
        f"  💡 灯光预设 '{preset_name}' ({preset['description']}): "
        f"创建 {len(created_lights)} 个灯光源"
    )

    return {
        "preset": preset_name,
        "lights": created_lights,
        "world_color": preset["world_color"],
    }


def setup_three_point_lighting(
    key_pos: tuple = (3.0, -3.0, 5.0),
    key_color: tuple = (1.0, 0.90, 0.71),
    key_energy: float = 800.0,
    fill_pos: tuple = (-3.0, 0.0, 2.0),
    fill_color: tuple = (0.42, 0.48, 0.55),
    fill_energy: float = 200.0,
    rim_pos: tuple = (0.0, 4.0, 4.0),
    rim_color: tuple = (1.0, 1.0, 1.0),
    rim_energy: float = 400.0,
) -> list:
    """
    Manual three-point lighting setup.

    Key light (主光): defines the primary illumination
    Fill light (辅光): reduces shadows
    Rim light (背光): creates contour separation
    """
    clear_all_lights()

    lights = []

    # Key light
    key_data = bpy.data.lights.new(name="KeyLight", type="SPOT")
    key_data.color = key_color
    key_data.energy = key_energy
    key_data.spot_size = math.radians(45)
    key_data.spot_blend = 0.3
    key_obj = bpy.data.objects.new("KeyLight", key_data)
    key_obj.location = key_pos
    bpy.context.scene.collection.objects.link(key_obj)
    lights.append(key_obj)

    # Fill light
    fill_data = bpy.data.lights.new(name="FillLight", type="AREA")
    fill_data.color = fill_color
    fill_data.energy = fill_energy
    fill_data.size = 5.0
    fill_data.shape = "RECTANGLE"
    fill_data.size_y = 5.0
    fill_obj = bpy.data.objects.new("FillLight", fill_data)
    fill_obj.location = fill_pos
    bpy.context.scene.collection.objects.link(fill_obj)
    lights.append(fill_obj)

    # Rim light
    rim_data = bpy.data.lights.new(name="RimLight", type="SPOT")
    rim_data.color = rim_color
    rim_data.energy = rim_energy
    rim_data.spot_size = math.radians(30)
    rim_data.spot_blend = 0.5
    rim_obj = bpy.data.objects.new("RimLight", rim_data)
    rim_obj.location = rim_pos
    bpy.context.scene.collection.objects.link(rim_obj)
    lights.append(rim_obj)

    return lights


if __name__ == "__main__":
    import sys

    preset = sys.argv[1] if len(sys.argv) > 1 else "cinematic_noir"
    print(f"Testing lighting preset: {preset}")
    setup_lighting(preset)
    print("Done!")
