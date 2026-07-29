#!/usr/bin/env python3
"""
赛璐璐材质 (Cel Shader) + 轮廓线 设置
用于 Blender 三渲二管线 — 在 render_shot.py 中调用
Blender 4.4+ Eevee Next 兼容
"""

import bpy
import math


def clear_all_materials():
    """Remove all existing materials from the scene."""
    for mat in bpy.data.materials:
        bpy.data.materials.remove(mat)


def create_cel_shader_material(
    name: str = "CelShader",
    shadow_color: tuple = (0.15, 0.15, 0.25, 1.0),
    mid_color: tuple = (0.40, 0.40, 0.60, 1.0),
    highlight_color: tuple = (0.80, 0.80, 1.00, 1.0),
    use_image_texture: bool = False,
    image_path: str = "",
) -> bpy.types.Material:
    """
    Create a 3-level cel shader material.

    Pipeline: Diffuse BSDF → Shader to RGB → ColorRamp (3 stops) → Material Output

    Args:
        name: Material name
        shadow_color: RGB for shadow regions
        mid_color: RGB for midtones
        highlight_color: RGB for highlights
        use_image_texture: If True, use image texture as base color
        image_path: Path to texture image

    Returns:
        The created material
    """
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    # Clear default nodes
    nodes.clear()

    # Create nodes
    output = nodes.new(type="ShaderNodeOutputMaterial")
    output.location = (600, 0)

    # --- Color input chain ---
    if use_image_texture and image_path:
        tex_node = nodes.new(type="ShaderNodeTexImage")
        tex_node.location = (-800, 0)
        # Load image
        img = bpy.data.images.load(image_path)
        tex_node.image = img
        color_source = tex_node
    else:
        # RGB input node
        rgb_node = nodes.new(type="ShaderNodeRGB")
        rgb_node.location = (-800, 0)
        rgb_node.outputs[0].default_value = mid_color
        color_source = rgb_node

    # Diffuse BSDF → Shader to RGB
    diffuse = nodes.new(type="ShaderNodeBsdfDiffuse")
    diffuse.location = (-400, 0)
    links.new(color_source.outputs[0], diffuse.inputs["Color"])

    shader_to_rgb = nodes.new(type="ShaderNodeShaderToRGB")
    shader_to_rgb.location = (-100, 0)
    links.new(diffuse.outputs[0], shader_to_rgb.inputs[0])

    # ColorRamp — 3 stops: shadow / mid / highlight
    color_ramp = nodes.new(type="ShaderNodeValToRGB")
    color_ramp.location = (200, 0)
    color_ramp.color_ramp.interpolation = "CONSTANT"  # Hard edges for cel shading

    # Clear default stops and create 3
    ramp = color_ramp.color_ramp
    # Remove all elements except the first 2 defaults, then set positions
    while len(ramp.elements) > 1:
        ramp.elements.remove(ramp.elements[1])

    # Shadow (0.0 → 0.33)
    ramp.elements[0].position = 0.0
    ramp.elements[0].color = shadow_color

    # Midtone (0.33 → 0.66)
    mid_stop = ramp.elements.new(0.33)
    mid_stop.color = mid_color

    # Highlight (0.66 → 1.0)
    high_stop = ramp.elements.new(0.66)
    high_stop.color = highlight_color

    # Second high stop at 1.0
    final_stop = ramp.elements.new(1.0)
    final_stop.color = highlight_color

    links.new(shader_to_rgb.outputs[0], color_ramp.inputs[0])
    links.new(color_ramp.outputs[0], output.inputs["Surface"])

    return mat


def create_outline_material(name: str = "Outline", color: tuple = (0.0, 0.0, 0.0, 1.0)) -> bpy.types.Material:
    """Create a simple black outline material."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()

    emission = nodes.new(type="ShaderNodeEmission")
    emission.location = (0, 0)
    emission.inputs["Color"].default_value = color
    emission.inputs["Strength"].default_value = 1.0

    output = nodes.new(type="ShaderNodeOutputMaterial")
    output.location = (300, 0)
    mat.node_tree.links.new(emission.outputs[0], output.inputs["Surface"])

    return mat


def setup_inverse_hull_outline(
    obj: bpy.types.Object,
    thickness: float = 0.015,
    outline_color: tuple = (0.0, 0.0, 0.0, 1.0),
) -> bpy.types.Object:
    """
    Create an inverse-hull outline for a mesh object.

    Uses Solidify modifier + flipped normals + backface culling.
    This is the recommended approach over Freestyle for animation.

    Returns the outline object.
    """
    # Duplicate the mesh
    outline_obj = obj.copy()
    outline_obj.data = obj.data.copy()
    outline_obj.name = f"{obj.name}_outline"

    # Link to same collection
    for col in obj.users_collection:
        col.objects.link(outline_obj)

    # Remove any modifiers from original data ref
    outline_obj.modifiers.clear()

    # Add solidify modifier (flip normals for inverse hull)
    solidify = outline_obj.modifiers.new(name="Outline", type="SOLIDIFY")
    solidify.thickness = thickness
    solidify.offset = -1.0  # Inward (hull around)
    solidify.use_flip_normals = True
    solidify.use_rim = True
    solidify.use_rim_only = False

    # Assign outline material
    outline_mat = create_outline_material(f"Outline_{obj.name}", outline_color)
    outline_obj.data.materials.clear()
    outline_obj.data.materials.append(outline_mat)

    # Parent to original (follows transforms)
    outline_obj.parent = obj

    return outline_obj


def apply_cel_shader_to_all_meshes(
    shadow_color: tuple = (0.15, 0.15, 0.25, 1.0),
    mid_color: tuple = (0.40, 0.40, 0.60, 1.0),
    highlight_color: tuple = (0.80, 0.80, 1.00, 1.0),
    outline_thickness: float = 0.015,
    outline_color: tuple = (0.0, 0.0, 0.0, 1.0),
    skip_outline: bool = False,
) -> list:
    """
    Apply cel shader material to all mesh objects in the scene.
    Create outline objects for each mesh.

    Args:
        shadow_color/mid_color/highlight_color: 3-level cel shading colors
        outline_thickness: Outline thickness in Blender units
        outline_color: Outline RGBA color
        skip_outline: If True, don't create outlines

    Returns:
        List of created outline objects
    """
    cel_mat = create_cel_shader_material(
        "CelShader_Main",
        shadow_color=shadow_color,
        mid_color=mid_color,
        highlight_color=highlight_color,
    )

    outline_objs = []

    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue

        # Skip outline objects
        if "_outline" in obj.name:
            continue

        # Apply cel shader
        if obj.data.materials:
            # Replace first material slot
            obj.data.materials[0] = cel_mat
        else:
            obj.data.materials.append(cel_mat)

        # Create outline
        if not skip_outline:
            try:
                out_obj = setup_inverse_hull_outline(
                    obj, thickness=outline_thickness, outline_color=outline_color
                )
                outline_objs.append(out_obj)
            except Exception as e:
                print(f"  ⚠️ Outline creation failed for {obj.name}: {e}")

    return outline_objs


def set_background_color(color: tuple = (0.05, 0.05, 0.10, 1.0)):
    """Set the world background color (for cel shader environment)."""
    world = bpy.context.scene.world
    if not world:
        world = bpy.data.worlds.new("World")
        bpy.context.scene.world = world

    world.use_nodes = True
    nodes = world.node_tree.nodes

    bg = nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = color
        bg.inputs["Strength"].default_value = 1.0


def setup_freestyle_outline(line_thickness: float = 1.5):
    """Setup Freestyle outline rendering (alternative to inverse hull)."""
    scene = bpy.context.scene
    scene.render.use_freestyle = True

    # Create line set
    if not scene.view_layers[0].freestyle_settings.linesets:
        lineset = scene.view_layers[0].freestyle_settings.linesets.new("CelOutline")
    else:
        lineset = scene.view_layers[0].freestyle_settings.linesets[0]

    lineset.linestyle.thickness = line_thickness
    lineset.select_silhouette = True
    lineset.select_border = True
    lineset.select_crease = True
    lineset.select_edge_mark = False
    lineset.select_external_contour = True
    lineset.select_material_boundary = True

    return lineset


if __name__ == "__main__":
    # Standalone test
    print("Applying cel shader to all meshes...")
    apply_cel_shader_to_all_meshes()
    set_background_color()
    print("Done!")
