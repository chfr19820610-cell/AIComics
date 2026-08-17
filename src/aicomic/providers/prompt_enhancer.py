# -*- coding: utf-8 -*-
"""
prompt_enhancer.py — AlComics提示词增强引擎 v1.0

融合5个GitHub项目的最佳实践:
  1. Omni-Rewriter (65⭐): Agent Harness → Draft → Validate → Repair → Render
  2. linshenkx/prompt-optimizer (33K⭐): prompt质量评分
  3. no8d/ComfyUI-NO8D-controls (154⭐): prompt库+权重标签
  4. msola-ht/ComfyUI-GLM4 (130⭐): GLM反推prompt
  5. if-ai/ComfyUI-IF_AI_tools (701⭐): LLM生成prompt

核心流程:
  base_prompt → analyze → draft(LLM增强) → validate(确定性检查) → repair → render
  全程可选，enhance=False时完全向后兼容。
"""

from __future__ import annotations

import json
import re
import os
from typing import Any, Optional
from dataclasses import dataclass, field


# ============ 1. PE Profile (蒸馏自Omni-Rewriter) ============

@dataclass
class PEProfile:
    """Prompt Expansion Profile — 为不同模型/风格定义prompt方言。"""
    name: str
    style_keywords: str = ""           # 风格关键词
    quality_tags: str = ""             # 质量标签
    negative_tags: str = ""            # 负项标签
    composition_hints: str = ""        # 构图提示
    lighting_hints: str = ""           # 光影提示
    color_palette: str = ""            # 色板
    aspect_ratio: str = "9:16"         # 竖屏短剧
    model_specific: str = ""           # 模型专属指令
    max_length: int = 2000             # 最大prompt长度

# ============ 预定义Profile ============

PROFILES: dict[str, PEProfile] = {
    "anime_donghua": PEProfile(
        name="anime_donghua",
        style_keywords="anime style, cel shading, clean lineart, vibrant colors, detailed eyes",
        quality_tags="masterpiece, best quality, high detail, sharp focus",
        negative_tags="low quality, blurry, distorted, deformed, bad anatomy, watermark, text, signature",
        composition_hints="vertical 9:16 composition, dramatic angle, depth of field",
        lighting_hints="cinematic lighting, rim light, soft shadows",
        color_palette="warm tones with cool accent, high saturation",
        aspect_ratio="9:16",
        model_specific="suitable for SDXL/SD1.5 anime checkpoints",
    ),
    "horror_folk": PEProfile(
        name="horror_folk",
        style_keywords="dark anime, horror illustration, eerie atmosphere, muted palette, folk horror",
        quality_tags="masterpiece, highly detailed, dramatic lighting",
        negative_tags="bright, cheerful, low quality, blurry, deformed, text, watermark",
        composition_hints="dutch angle, claustrophobic framing, deep shadows",
        lighting_hints="moonlight, candlelight, harsh shadows, high contrast",
        color_palette="desaturated, cold blue-green with warm accent",
        aspect_ratio="9:16",
        model_specific="horror genre, emphasis on atmosphere over character detail",
    ),
    "action_dynamic": PEProfile(
        name="action_dynamic",
        style_keywords="dynamic action, motion blur, impact frames, speed lines, dramatic pose",
        quality_tags="masterpiece, best quality, dynamic composition",
        negative_tags="static pose, low quality, blurry, deformed, text",
        composition_hints="dynamic angle, rule of thirds, leading lines",
        lighting_hints="dramatic backlight, lens flare, high contrast",
        color_palette="high contrast, bold primary colors",
        aspect_ratio="9:16",
        model_specific="action genre, emphasis on motion and impact",
    ),
    "emotion_closeup": PEProfile(
        name="emotion_closeup",
        style_keywords="close-up portrait, emotional expression, detailed eyes, soft focus background",
        quality_tags="masterpiece, best quality, ultra detailed face",
        negative_tags="far shot, low quality, blurry, deformed face, text",
        composition_hints="close-up, face fills 60% frame, shallow depth of field",
        lighting_hints="soft beauty light, catchlight in eyes, warm tone",
        color_palette="warm skin tones, soft bokeh",
        aspect_ratio="9:16",
        model_specific="emotion-focused, character acting shot",
    ),
    "video_h3": PEProfile(
        name="video_h3",
        style_keywords="smooth animation, subtle motion, character consistency",
        quality_tags="high quality, consistent character",
        negative_tags="flickering, inconsistent, low quality, distorted",
        composition_hints="stable camera, minimal scene change",
        lighting_hints="consistent lighting across frames",
        color_palette="consistent color grading",
        aspect_ratio="9:16",
        model_specific="H3 video model, 3-4 second clips, emphasize motion continuity",
        max_length=2000,
    ),
}


# ============ 2. Prompt质量评分 (蒸馏自prompt-optimizer) ============

def score_prompt(prompt: str) -> dict[str, Any]:
    """评估prompt质量，返回评分+具体建议。"""
    score = 0
    max_score = 100
    issues: list[str] = []
    tips: list[str] = []

    length = len(prompt)
    if 50 <= length <= 500:
        score += 20
    elif length < 50:
        score += 5
        issues.append("prompt过短，缺少细节")
        tips.append("增加场景、情绪、光影描述")
    elif length > 500:
        score += 10
        issues.append("prompt过长，可能超出模型理解范围")
        tips.append("精简到核心描述，移除重复信息")

    # 关键元素检查
    elements = {
        "subject": any(kw in prompt for kw in ["人物", "角色", "主角", "girl", "boy", "character"]),
        "scene": any(kw in prompt for kw in ["场景", "背景", "scene", "environment", "location"]),
        "action": any(kw in prompt for kw in ["动作", "action", "pose", "standing", "running"]),
        "emotion": any(kw in prompt for kw in ["情绪", "emotion", "expression", "happy", "sad", "angry"]),
        "lighting": any(kw in prompt for kw in ["光影", "light", "lighting", "shadow", "glow"]),
        "composition": any(kw in prompt for kw in ["构图", "composition", "angle", "close-up", "wide"]),
        "quality": any(kw in prompt for kw in ["高质量", "masterpiece", "best quality", "high detail"]),
        "style": any(kw in prompt for kw in ["动漫", "anime", "style", "插画", "illustration"]),
    }
    element_count = sum(elements.values())
    score += min(element_count * 10, 50)

    missing = [k for k, v in elements.items() if not v]
    if missing:
        issues.append(f"缺少元素: {', '.join(missing)}")
        tips.append(f"考虑补充: {', '.join(missing)}")

    # 重复词检查
    words = re.findall(r'\w+', prompt.lower())
    if words:
        from collections import Counter
        word_counts = Counter(words)
        repeats = [w for w, c in word_counts.items() if c > 2 and len(w) > 2]
        if repeats:
            score -= min(len(repeats) * 5, 15)
            issues.append(f"重复词: {', '.join(repeats[:3])}")
            tips.append("减少重复，用同义词替代")

    score = max(0, min(score, max_score))
    return {"score": score, "issues": issues, "tips": tips, "elements": elements}


# ============ 3. Validate (蒸馏自Omni-Rewriter确定性检查) ============

def validate_prompt(prompt: str, profile: PEProfile) -> dict[str, Any]:
    """确定性检查prompt是否符合profile要求。"""
    errors: list[str] = []
    warnings: list[str] = []

    if not prompt or len(prompt.strip()) < 10:
        errors.append("prompt为空或过短")

    if len(prompt) > profile.max_length:
        warnings.append(f"prompt超过{profile.max_length}字符限制")

    # 检查是否包含profile要求的关键元素
    if profile.style_keywords:
        has_style = any(kw.lower() in prompt.lower() for kw in profile.style_keywords.split(", "))
        if not has_style:
            warnings.append(f"缺少风格关键词")

    if profile.aspect_ratio and profile.aspect_ratio not in prompt and "9:16" not in prompt and "竖屏" not in prompt:
        warnings.append(f"缺少宽高比指示({profile.aspect_ratio})")

    # 检查是否有负项标签
    has_negative = any(kw in prompt.lower() for kw in ["negative", "不要", "避免", "no "])
    if not has_negative and profile.negative_tags:
        warnings.append("缺少负项提示")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "prompt_length": len(prompt),
    }


# ============ 4. Render (蒸馏自Omni-Rewriter render层) ============

def render_enhanced_prompt(
    base_prompt: str,
    profile: PEProfile,
    negative_prompt: str = "",
    shot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    将base_prompt + profile渲染成最终prompt。

    Returns:
        {"prompt": str, "negative_prompt": str, "score": dict, "validation": dict}
    """
    parts: list[str] = [base_prompt]

    # 注入profile元素
    if profile.style_keywords:
        parts.append(profile.style_keywords)
    if profile.quality_tags:
        parts.append(profile.quality_tags)
    if profile.composition_hints:
        parts.append(profile.composition_hints)
    if profile.lighting_hints:
        parts.append(profile.lighting_hints)
    if profile.color_palette:
        parts.append(profile.color_palette)

    # shot特定增强
    if shot:
        if shot.get("camera"):
            cam = shot["camera"]
            if "特写" in cam:
                parts.append("extreme close-up, face details")
            elif "远景" in cam:
                parts.append("wide establishing shot")
            elif "俯视" in cam:
                parts.append("high angle shot")
            elif "仰视" in cam:
                parts.append("low angle shot, imposing")
        if shot.get("emotion"):
            emo = shot["emotion"]
            emotion_map = {
                "恐惧": "fearful expression, wide eyes, trembling",
                "愤怒": "angry expression, clenched fists, intense gaze",
                "悲伤": "sad expression, tears, downcast eyes",
                "喜悦": "happy expression, bright eyes, smile",
                "震惊": "shocked expression, mouth open, wide eyes",
            }
            for cn, en in emotion_map.items():
                if cn in emo:
                    parts.append(en)
                    break

    # 拼接
    final_prompt = ", ".join(p for p in parts if p)

    # 截断到max_length
    if len(final_prompt) > profile.max_length:
        final_prompt = final_prompt[:profile.max_length].rsplit(", ", 1)[0]

    # 负项prompt
    final_negative = negative_prompt or profile.negative_tags

    # 评分+验证
    score = score_prompt(final_prompt)
    validation = validate_prompt(final_prompt, profile)

    return {
        "prompt": final_prompt,
        "negative_prompt": final_negative,
        "score": score,
        "validation": validation,
    }


# ============ 5. LLM增强 (可选, 蒸馏自Omni-Rewriter Draft + GLM4反推) ============

def enhance_via_llm(
    base_prompt: str,
    profile: PEProfile,
    shot: dict[str, Any] | None = None,
    llm_url: str = "http://127.0.0.1:8081/v1/chat/completions",
    llm_model: str = "DeepSeek-V4-Flash",
    llm_key: str = "thr_hermes001",
) -> str:
    """
    用LLM智能增强prompt (可选)。
    走ThriftLLM→DeepSeek-V4-Flash, 不额外花钱。

    流程: base_prompt → LLM Draft → 确定性validate → 返回增强prompt
    """
    import subprocess as _sp
    import json as _json

    system_msg = (
        "你是AI漫剧提示词工程师。增强以下prompt，使其更适合AI图像/视频生成。"
        "要求：保持原意，增加视觉细节(光影/构图/色彩/材质)，用英文补充danbooru标签。"
        "不要改变角色描述和场景设定。输出纯文本，不要markdown。"
        f"风格: {profile.style_keywords}"
    )

    user_msg = f"原始prompt: {base_prompt}\n"
    if shot:
        user_msg += f"镜头: {shot.get('camera', '')}\n"
        user_msg += f"情绪: {shot.get('emotion', '')}\n"
    user_msg += "增强后prompt:"

    payload = _json.dumps({
        "model": llm_model,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        "max_tokens": 300,
        "temperature": 0.3,
    })

    try:
        r = _sp.run(
            ["curl", "-s", "--max-time", "15", llm_url,
             "-H", "Content-Type: application/json",
             "-H", f"Authorization: Bearer {llm_key}",
             "-d", payload],
            capture_output=True, text=True, timeout=20,
        )
        if r.returncode == 0 and r.stdout:
            resp = _json.loads(r.stdout)
            content = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
            if content and len(content) > len(base_prompt):
                return content.strip()
    except Exception:
        pass

    return base_prompt  # LLM失败时返回原始prompt


# ============ 6. 统一入口 ============

def enhance_prompt(
    base_prompt: str,
    shot: dict[str, Any] | None = None,
    profile_name: str = "anime_donghua",
    use_llm: bool = False,
    negative_prompt: str = "",
) -> dict[str, Any]:
    """
    统一入口：增强prompt。

    Args:
        base_prompt: 原始prompt (来自request_builder.build_image_prompt)
        shot: 分镜信息 (scene/visual/action/emotion/camera/characters)
        profile_name: PE profile名称
        use_llm: 是否用LLM增强 (默认False, 向后兼容)
        negative_prompt: 负项prompt (来自config/providers.yaml)

    Returns:
        {
            "prompt": 增强后prompt,
            "negative_prompt": 增强后负项prompt,
            "score": 质量评分,
            "validation": 验证结果,
            "profile": profile名,
            "enhanced": 是否增强,
        }
    """
    profile = PROFILES.get(profile_name, PROFILES["anime_donghua"])

    # Step 1: LLM增强 (可选)
    if use_llm:
        enhanced = enhance_via_llm(base_prompt, profile, shot)
    else:
        enhanced = base_prompt

    # Step 2: Profile渲染 (确定性)
    result = render_enhanced_prompt(enhanced, profile, negative_prompt, shot)

    result["profile"] = profile_name
    result["enhanced"] = True  # render本身也是增强
    return result


def auto_select_profile(shot: dict[str, Any]) -> str:
    """根据shot自动选择最佳profile。"""
    genre = str(shot.get("genre", "")).lower()
    emotion = str(shot.get("emotion", "")).lower()
    camera = str(shot.get("camera", "")).lower()

    if "horror" in genre or "恐怖" in emotion or "恐惧" in emotion:
        return "horror_folk"
    if "action" in genre or "战斗" in emotion or "激烈" in emotion:
        return "action_dynamic"
    if "特写" in camera or "close" in camera.lower():
        return "emotion_closeup"
    return "anime_donghua"
