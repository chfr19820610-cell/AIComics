#!/usr/bin/env python3
"""
character_sheet_builder.py — 角色设定图(character sheet) prompt生成器 v1.0

融合全网最佳实践:
  - 知乎NanoBanana三视图模板 (正面+侧面+背面+表情+比例)
  - vocus SDXL character sheet教程 (提示词控制法+画布尺寸)
  - Reddit r/dndai turnaround测试 (四视图+正交相机)
  - 峰哥发的人物形象提示词 (7分区: 主视觉+补充+细节+比例+背景+风格)

7分区结构:
  1. 主视觉区(上方): 正面+侧面+背面 三视角全身
  2. 补充信息区(左侧): 面部特写 + 配色板(色值)
  3. 局部细节区(底部): 关键配饰/身份识别元素
  4. 全身比例照(右侧): 黄金比例参考物+身高对比
  5. 背景白色
  6. 画风材质描述
  7. 角色外观详细设定

使用:
  from aicomic.characters.character_sheet_builder import build_character_sheet_prompt
  
  prompt = build_character_sheet_prompt(
      name="古风帅哥",
      appearance="狭长双眼，眼尾细长，锦衣华服貂裘，金丝描边，金质发冠",
      style="超写实国风，8K高清纹理，质感光照",
      ...
  )
  # → 返回结构化prompt给SDXL生成角色设定图
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CharacterAppearance:
    """角色外观结构化定义 — 10+维度精确描述"""
    name: str = ""
    gender: str = ""                    # 男/女/其他
    age_group: str = ""                 # 少年/青年/中年/老年
    body_type: str = ""                 # 体型: 高挑/健壮/纤细/丰满
    height_ratio: str = ""              # 身高比例: "7.5头身" / "8头身"
    
    # 五官
    face_shape: str = ""                # 脸型: 瓜子脸/方脸/圆脸
    eyes: str = ""                      # 眼睛: "狭长双眼，眼尾细长"
    nose: str = ""                      # 鼻子
    mouth: str = ""                     # 嘴
    skin: str = ""                      # 肤色: "清透瓷白肌肤"
    
    # 发型
    hairstyle: str = ""                 # "长发凌乱发丝拂面"
    hair_color: str = ""                # "墨黑"
    hair_accessory: str = ""            # "金质华丽的发冠"
    
    # 服饰
    outfit: str = ""                    # "锦衣华服貂裘"
    outfit_details: str = ""            # "丰富的花纹，金丝描边"
    outfit_color: str = ""              # "玄色底金纹"
    accessories: str = ""               # "玉佩，金丝绶带"
    
    # 气质
    temperament: str = ""               # "疯批感，阴郁感，潇洒"
    aura: str = ""                      # "有柔和感情的眼神"
    
    # 配色 (hex色值)
    color_palette: dict[str, str] = field(default_factory=dict)
    # 例: {"hair": "#1a1a2e", "skin": "#f5e6d3", "outfit_primary": "#1a0d2e", "outfit_accent": "#d4af37"}
    
    # 标志性特征
    signature_features: list[str] = field(default_factory=list)
    # 例: ["左眼下方泪痣", "右手腕疤痕", "腰间玉佩"]


def build_character_sheet_prompt(
    appearance: CharacterAppearance | None = None,
    name: str = "",
    appearance_text: str = "",           # 自由文本外观描述 (替代结构化)
    style: str = "",                     # 画风材质
    art_style: str = "anime_donghua",    # 艺术风格profile
    aspect_ratio: str = "16:9",          # 设定图通常是横版
    extra_negative: str = "",
) -> dict[str, Any]:
    """
    生成角色设定图prompt — 7分区结构。
    
    Args:
        appearance: 结构化角色外观 (优先使用)
        name: 角色名
        appearance_text: 自由文本外观 (无结构化时用)
        style: 画风材质描述
        art_style: 艺术风格 (anime_donghua/realistic_cn/horror_folk)
        aspect_ratio: 画布比例
        extra_negative: 额外负项
        
    Returns:
        {"prompt": str, "negative_prompt": str, "layout": str, "config": dict}
    """
    
    # ── 自动从appearance提取name ──
    if not name and appearance and appearance.name:
        name = appearance.name
    
    # ── 构建角色描述段 ──
    if appearance and appearance.outfit:
        desc_parts = []
        if appearance.gender:
            desc_parts.append(appearance.gender)
        if appearance.age_group:
            desc_parts.append(appearance.age_group)
        if appearance.body_type:
            desc_parts.append(appearance.body_type)
        if appearance.face_shape:
            desc_parts.append(appearance.face_shape)
        if appearance.eyes:
            desc_parts.append(f"eyes: {appearance.eyes}")
        if appearance.skin:
            desc_parts.append(f"skin: {appearance.skin}")
        if appearance.hairstyle:
            desc_parts.append(f"hair: {appearance.hairstyle}")
        if appearance.hair_color:
            desc_parts.append(f"hair color: {appearance.hair_color}")
        if appearance.hair_accessory:
            desc_parts.append(f"hair accessory: {appearance.hair_accessory}")
        if appearance.outfit:
            desc_parts.append(f"outfit: {appearance.outfit}")
        if appearance.outfit_details:
            desc_parts.append(f"outfit details: {appearance.outfit_details}")
        if appearance.outfit_color:
            desc_parts.append(f"outfit color: {appearance.outfit_color}")
        if appearance.accessories:
            desc_parts.append(f"accessories: {appearance.accessories}")
        if appearance.temperament:
            desc_parts.append(f"temperament: {appearance.temperament}")
        if appearance.aura:
            desc_parts.append(f"aura: {appearance.aura}")
        if appearance.signature_features:
            desc_parts.append(f"signature: {', '.join(appearance.signature_features)}")
        character_desc = ", ".join(desc_parts)
    elif appearance_text:
        character_desc = appearance_text
    else:
        character_desc = "character"
    
    if name:
        character_desc = f"{name}, {character_desc}"
    
    # ── 构建配色板段 ──
    color_block = ""
    if appearance and appearance.color_palette:
        color_lines = []
        for part, hex_val in appearance.color_palette.items():
            color_lines.append(f"{part}: {hex_val}")
        color_block = "Color palette: " + ", ".join(color_lines) + ". "
    
    # ── 构建标志细节段 ──
    detail_block = ""
    if appearance and appearance.signature_features:
        detail_block = f"Detail close-ups: {', '.join(appearance.signature_features)}. "
    
    # ── 构建比例段 ──
    ratio_block = ""
    if appearance and appearance.height_ratio:
        ratio_block = f"Golden ratio reference, {appearance.height_ratio} body proportion, height measurement bar at bottom. "
    else:
        ratio_block = "Golden ratio reference, height measurement bar at bottom. "
    
    # ── 画风风格段 ──
    style_block = style if style else _default_style(art_style)
    
    # ── 组装7分区prompt ──
    prompt = (
        f"Character design reference sheet, character sheet, turnaround sheet. "
        f"Multiple views layout: "
        f"TOP: full-body front view, side view (facing right), back view — three core perspectives showing overall silhouette, costume and signature features. "
        f"LEFT: facial close-up showing detailed features, {color_block}"
        f"BOTTOM: detail modules showing key accessories and identity elements. "
        f"RIGHT: {ratio_block}"
        f"WHITE BACKGROUND, clean simple background, no environment. "
        f"Orthographic camera, consistent lighting across all views, consistent proportions. "
        f"Character: {character_desc}. "
        f"{detail_block}"
        f"Style: {style_block}. "
        f"Masterpiece, best quality, highest detail, sharp focus, 8K resolution, professional character design."
    )
    
    # ── 负项 ──
    negative = (
        "low quality, blurry, distorted, deformed, bad anatomy, "
        "extra limbs, missing limbs, fused fingers, "
        "watermark, text, signature, logo, "
        "colored background, environment, scenery, "
        "inconsistent proportions, different character across views, "
        "asymmetric eyes, mismatched colors"
    )
    if extra_negative:
        negative = negative + ", " + extra_negative
    
    return {
        "prompt": prompt,
        "negative_prompt": negative,
        "layout": "7-zone character sheet (top:3views, left:face+colors, bottom:details, right:ratio, white bg)",
        "aspect_ratio": aspect_ratio,
        "art_style": art_style,
        "character_desc": character_desc,
    }


def _default_style(art_style: str) -> str:
    """默认画风材质描述"""
    styles = {
        "anime_donghua": "anime style, cel shading, clean lineart, vibrant colors, detailed eyes, high-detail anime illustration",
        "realistic_cn": "ultra-realistic Chinese style, modern realistic, texture lighting, natural light, 8K HD texture, natural fabric folds, artistic realistic, dramatic visual effect",
        "horror_folk": "dark anime, horror illustration, eerie atmosphere, muted palette, folk horror",
        "action_dynamic": "dynamic anime, bold lines, high contrast, motion energy, dramatic angle",
        "emotion_closeup": "soft focus, gentle lighting, emotional atmosphere, delicate features",
    }
    return styles.get(art_style, styles["anime_donghua"])


def build_sheet_from_character(
    character: Any,
    style: str = "",
    art_style: str = "anime_donghua",
) -> dict[str, Any]:
    """
    从AlComics Character对象构建设定图prompt。
    
    自动从character.description/reference_prompt提取信息，
    构建结构化设定图prompt。
    """
    name = getattr(character, "name", "")
    desc = getattr(character, "reference_prompt", "") or getattr(character, "description", "")
    
    return build_character_sheet_prompt(
        name=name,
        appearance_text=desc,
        style=style,
        art_style=art_style,
    )


# ── 预设模板 ──

PRESETS: dict[str, dict] = {
    "ancient_hero": {
        "name": "古风帅哥",
        "appearance_text": "狭长双眼，眼尾细长，锦衣华服貂裘，丰富的花纹，金丝描边，金质华丽的发冠，极致妖孽的容貌，长发凌乱发丝拂面，清透瓷白肌肤，疯批感，有柔和感情的眼神，阴郁感，潇洒",
        "style": "超写实国风，现代风格，写实风格，质感光照，自然光线，质感十足，8K高清纹理，布料褶皱自然，艺术写实风格，营造出震撼的视觉效果。饱和度较高，高级构图，细节丰富，清晰精致，精致细腻，高清画质，面部聚焦，面部阴影，绝美眼睛，线条清晰，高级感、朦胧感，明暗对比，超高清、最高画质、高质量，丰富细节、细腻肌理，超细节，超丰富，写实逼真",
        "art_style": "realistic_cn",
    },
    "anime_girl": {
        "name": "动漫少女",
        "appearance_text": "大眼睛，圆脸，粉色长发双马尾，身穿水手服校服，白色衬衫蓝色领结，迷你裙，黑色过膝袜，可爱的笑容，元气满满",
        "style": "anime style, cel shading, clean lineart, vibrant colors, detailed eyes, high-detail anime illustration",
        "art_style": "anime_donghua",
    },
    "horror_ghost": {
        "name": "民俗恐怖角色",
        "appearance_text": "苍白的面孔，黑色长发遮脸，红色绣花鞋，白色丧服，阴森的气息，空洞的眼神",
        "style": "dark anime, horror illustration, eerie atmosphere, muted palette, folk horror, high contrast dramatic lighting",
        "art_style": "horror_folk",
    },
}


def build_from_preset(preset_name: str) -> dict[str, Any]:
    """使用预设模板快速生成设定图prompt"""
    preset = PRESETS.get(preset_name, PRESETS["ancient_hero"])
    return build_character_sheet_prompt(
        name=preset.get("name", ""),
        appearance_text=preset.get("appearance_text", ""),
        style=preset.get("style", ""),
        art_style=preset.get("art_style", "anime_donghua"),
    )
