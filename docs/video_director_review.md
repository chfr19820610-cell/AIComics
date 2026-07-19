# 🎬 Phase D 视频品质审查报告

> **导演:** agent-video-director  
> **审查对象:** `vf_master_loop.py` Phase D (line 835-1024)  
> **依赖资产:** aicg-handbook (峰哥动画手册) / pipeline.py / scene.py / subtitles.py / config.py  
> **审查日期:** 2026-07-19  
> **版本:** v3.0

---

## 目录

1. [Phase D 生产逻辑解析](#1-phase-d-生产逻辑解析)
2. [视频节奏剪辑建议](#2-视频节奏剪辑建议)
3. [风格一致性建议](#3-风格一致性建议)
4. [效率与品质平衡建议](#4-效率与品质平衡建议)
5. [优先级行动清单](#5-优先级行动清单)

---

## 1. Phase D 生产逻辑解析

### 1.1 当前流程总览

```
phase_self_produce()
├── 1. 检查 30/30 资产就绪 (total_img ≥ 30, total_aud ≥ 30)
│     └── 未就绪 → return False (跳过本轮)
│
├── 2. 风格轮换 (循环索引, 3种风格)
│     ├── Painterly 3D Noir (油画暗黑)
│     ├── Hybrid Comic Pop (漫画弹入)
│     └── Cinematic Liquid Glass (液态玻璃)
│
├── 3. 对每个剧集 (E01-E05, 每集6场):
│     ├── 构建场景列表 (_build_scene_list)
│     ├── 选择引擎: ComfyUI → Seedance → FFmpeg (fallback链)
│     ├── 调用合成函数
│     └── 输出 MP4 + label.json
│
├── 4. 写 round 摘要 JSON
│
└── 5. 自生产: init-project 创建下周期项目
```

### 1.2 三条合成路径对比

| 维度 | FFmpeg (当前实际) | ComfyUI AnimateDiff | Seedance 360 |
|------|------------------|---------------------|--------------|
| **运动** | Ken Burns 缩放 100%→105% | 真实 AI 视频帧生成 | AI 文生/图生视频 |
| **画质** | 原图分辨率 (依赖 Phase A 质量) | AnimateDiff 模型质量 | Seedance 云端模型 |
| **可用性** | ✅ 始终可用 | ❌ 不可用 (ComfyUI 未就绪) | ❌ 不可用 (无 API Key) |
| **实际产出** | E01-E05 全部 FFmpeg 模式 | 未命中 | 未命中 |

### 1.3 核心问题诊断

**问题 1: FFmpeg 标签元数据丢失**
- `label.json` 中 `duration: "?"`, `size_mb: 0` —— 但实际文件 3-11 MB
- 根因: `_run_synthesis()` 返回的报告来自 `pipeline.synthesize_episode()`，但 FFmpeg 回退路径 (`_run_synthesis` at line 940) 用的是 `synthesize_episode` 内部已经提取了 metadata。而 label.json 写的是 `report.get("duration", "?")` —— 但维度的 key 不对，`synthesize_episode` 返回的 dict 里 `duration` 是字符串格式如 `"00:00:30.00"`，而 label_data 期望字符串没问题，但实际 label 里是 `"?"` 说明 report 为 None 或字段缺失。

**问题 2: 风格轮换仅影响元数据，不影响视频内容**
- `STYLE_PALETTES` 中的色板/描述只写入 label.json，没有以任何方式影响画面
- 图片在 Phase A 已经用固定 prompt "动漫插画风" 生成
- LUT (cinematic_warm.cube) 存在于 assets/luts/ 且被 pipeline 引用，但 LUT 路径固定为同一个，风格轮换不切换 LUT

**问题 3: 纯硬切 —— 零转场**
- `phase_concat` 使用 `-c copy` (流复制)，不做任何重新编码 → 零转场
- 相邻镜头之间直接硬切，无 crossfade/dissolve/wipe

**问题 4: 单一运动 —— 只有 Ken Burns 缩放**
- 仅 `zoompan=z='1+0.05*on/{frames}'`，100% → 105%
- 无 pan/无 track/无 parallax/无镜头旋转
- 固定镜头和运动镜头没有交替 (违背 aicg-handbook "一静一动原则")

**问题 5: 无背景音乐**
- 输出仅 TTS 配音 + 静音背景
- `demo_bgm.wav` (4.4 MB) 已存在 `state/produced_videos/` 但未使用

---

## 2. 视频节奏剪辑建议

### 2.1 三拍法落地 (aicg-handbook §3.2)

每集6个场景需要按照三拍法的叙事单元重组。当前是纯顺序排列 (S01→S02→...→S06)，但台词表明有完整叙事弧。

**建议重构: 每集拆分为 2 个三拍单元**

```
单元1: 冲突引入
  拍1 定场拍 (EW/WS, 3s) → 场景空间、气氛
  拍2 推进拍 (MS, 2.5s) → 角色行动/对白
  拍3 情绪拍 (CU, 2s) → 角色反应、细节

单元2: 冲突升级
  拍4 定场拍 (WS, 2s) → 新情境
  拍5 推进拍 (MS/OTS, 2.5s) → 对峙/关键对白
  拍6 情绪拍 (CU/ECU, 2s) → 高潮瞬间
```

**受益**: 每个单元有起承转合，而不是6个等长的段落。

### 2.2 3-5-7 镜头定额法 (aicg-handbook §3.5)

当前视频时长约 30-35秒 (6场 × 5-6秒)。按 aicg-handbook:

| 时长 | 当前镜数 | 推荐镜数 | 每镜时长 |
|:----:|:--------:|:--------:|:--------:|
| 30s | 6 | 5-8 | 3.75-6s |
| 60s | 6 | 7-12 | 5-8.5s |

**问题**: 当前场景数固定为6 (EPISODES 的 scene_count)，无法根据时长灵活调整镜头数。每场 duration = max(5.0, audio_duration)，纯音频驱动无最大上限。

**建议:**
1. 设定目标时长 (30s/60s) → 计算理想镜头数
2. 每个场景 duration 加 cap: `min(max_duration, max(5.0, audio_duration))`
3. 对太长的音频场景拆分为2个镜头 (全景+近景)

### 2.3 景别节奏 (三步跳原则 §3.3)

当前 pipeline 不跟踪景别。每场只有一张 key image，镜头类型完全由 Phase A 的图片决定。

**建议在 Manifest 中增加 shot_type 字段:**

```json
{
  "shot_id": 1,
  "shot_type": "WS",  // EW/WS/MS/MCU/CU/ECU/OTS
  "duration": 3.5,
  "subtitle": "..."
}
```

然后 Phase D 合成时根据景别序列自动调整节奏:
- WS 可保留较长 (更多信息)
- CU 可稍短 (聚焦)
- WS→CU 跳两级时插入过渡帧

### 2.4 转场系统

**当前**: `-c copy` 硬切 → 零开销但零品质

**建议分层改进:**

| 优先级 | 转场 | 实现方式 | 性能影响 |
|:------:|------|----------|:--------:|
| P0 | Crossfade (淡入淡出) | FFmpeg `xfade` filter | 需 re-encode |
| P1 | 定时长 fade-in/fade-out (首尾) | `-vf "fade=t=in:st=0:d=0.5"` | 低 |
| P2 | Wipe/ slide | `xfade=transition=slideleft` | 需 re-encode |
| P3 | 风格特写转场 (黑屏+台词) | 黑帧插入 | 极低 |

**推荐立即实现**: 场景首尾 fade (0.3s) + Crossfade 过场 (0.5s)

```python
# scene.py 中 build_scene_video 加 fade
vf = f"fade=t=in:st=0:d=0.5,fade=t=out:st={duration-0.5}:d=0.5,..."
```

Phase 3 concat 从 `-c copy` 改为 `-vf xfade` 需要重新编码, 可以保留 concat 硬切 + 每场首尾 fade 的混合方案.

---

## 3. 风格一致性建议

### 3.1 色板真正落地 (当前最大品质瓶颈)

**现状**: 风格轮换只有 label.json 记录色板，画面本身完全不受影响。

**建议 3 层风格注入:**

#### 图层1: 图片生成时风格化 (Phase A)
Phase A 的 `_generate_one_image` prompt 加入当前风格的描述:

```python
STYLE_PROMPTS = {
    "Painterly 3D Noir": "painterly oil painting style, dramatic noir lighting, deep shadows, dark moody, rich dark tones, cinematic",
    "Hybrid Comic Pop": "bold comic book style, pop art colors, cel-shaded, high contrast, dynamic angular lines, Ben-Day dots",
    "Cinematic Liquid Glass": "translucent glass textures, refractive light effects, liquid flow, dreamy gradient, ethereal glow, bokeh",
}
```

#### 图层2: LUT 按风格切换
当前 `config.py` 固定 `LUT_PATH = assets/luts/cinematic_warm.cube`。

改为风格映射:

```python
STYLE_LUTS = {
    "Painterly 3D Noir": "assets/luts/noir_dark.cube",      # 增加暗部压暗
    "Hybrid Comic Pop": "assets/luts/comic_pop.cube",         # 提高饱和度
    "Cinematic Liquid Glass": "assets/luts/cinematic_warm.cube", # 现有暖调
}
```

并且每轮 Phase D 根据当前 palette 动态选择 LUT。

#### 图层3: 后期叠加 (颜色叠加/暗角/颗粒)

FFmpeg filter 链增加风格化叠加:

```python
STYLE_POST_FILTERS = {
    "Painterly 3D Noir": "curves=... , vignette=PI/4:500, noise=alls=3:allf=t+u",
    "Hybrid Comic Pop": "curves=... , eq=saturation=1.6, edgedetect=low=0.1:high=0.3",
    "Cinematic Liquid Glass": "curves=... , gblur=sigma=0.5, vignette=PI/4:400",
}
```

### 3.2 角色一致性

当前 pipeline 不涉及角色。如果后续有角色复用，建议:

1. **Phase A 图片生成时传递角色参考图** (已有 `_get_character_ref_map()`)
2. **Seedance 合成时传角色参考图** (已有 character consistency 支持)
3. **同一场景角色外观保持** — 用固定的 seed/ControlNet

### 3.3 背景音乐统一性

当前 pipeline 无 BGM。

**建议分3步:**

1. **立即**: 对所有输出叠加 `demo_bgm.wav` (已存在)
   ```python
   # phase_burn_subtitles 后或 concat 时
   ffmpeg -i video.mp4 -i bgm.wav -filter_complex "[1:a]volume=0.15[a1];[0:a][a1]amix=duration=first" ...
   ```

2. **短期**: BGM 也按风格切换
   - Painterly 3D Noir → 暗黑管弦/低音 drone
   - Hybrid Comic Pop → 快节奏电音/funk
   - Cinematic Liquid Glass → 环境电子/钢琴

3. **长期**: 用 Suno/AudioCraft 按风格自动生成 BGM

---

## 4. 效率与品质平衡建议

### 4.1 合成引擎优先级调优

当前 fallback 链: `ComfyUI → Seedance → FFmpeg`

**问题**: 
- ComfyUI/Seedance 经常不可用 → 每次都 fallback 到 FFmpeg
- 每次尝试 ComfyUI 要消耗 HTTP 请求 + provider 初始化时间
- Seedance API 调用会消耗额度

**建议: 健康缓存 + 跳过**

```python
# 在 phase_self_produce() 开始时
ENGINE_STATUS_CACHE = STATE / "engine_status.json"
# 缓存 5 分钟，避免每轮都去连 ComfyUI
```

### 4.2 FFmpeg 模式品质提升 (零成本/低成本)

| 改进 | 成本 | 效果 |
|------|:----:|------|
| Ken Burns 从固定 105% 改为随机 103%-115% | 零 | 视觉层次增加 |
| 增加镜头 pan (从左边/右边起始) | 零 | 运动多样性 |
| 场景首尾 fade 0.3s | 低 (需 re-encode audio) | 专业感 ↑ |
| 音频根据对话情绪调整语速 (TTS SSML) | 低 | 表演感 ↑ |
| 每场 Image prompt 加入风格描述 | 零 (Phase A 改) | 风格落地 |
| 叠加 BGM (demo_bgm.wav) | 零 (资产已有) | 氛围感 ↑ |
| 动态切换 LUT | 零 | 色彩风格化 |

### 4.3 并行度优化

当前 Phase D 是串行合成: 逐集处理 E01→E02→E03→E04→E05

**建议**: 用 ThreadPoolExecutor 并行合成多集 (受 FFmpeg CPU 限制, 建议 max_workers=2)

```python
with ThreadPoolExecutor(max_workers=2) as pool:
    futures = {pool.submit(_synthesize_one_ep, ep_code, ...): ep_code for ep_code in episodes_ready}
```

### 4.4 预览模式增强

当前 preview_mode 仅影响图片分辨率 (512x768)。

建议预览模式额外:
1. 使用更快的编码 preset (`ultrafast` 而非 `medium`)
2. 降低帧率 (15fps 而非 30fps)
3. 跳过 LUT 应用
4. 降低 CRF 到 35 (更低品质但更快)
5. 只在预览模式跳过复杂的 xfade 转场

### 4.5 画面抖动 / 防闪烁

当前 `zoompan` 不带 `smooth` 参数，在场景边界可能产生帧跳跃。

**建议**:

```python
# 改为带平滑的 zoompan
f"zoompan=z='{zoom_expr}':d={frames}:s={VIDEO_SIZE_X}:fps={FPS}:smooth=1"
```

---

## 5. 优先级行动清单

### P0 — 立即修复 (低投入高回报)

| # | 行动 | 修改位置 | 预估时间 |
|---|------|----------|:--------:|
| 1 | 修复 label.json 元数据字段 (duration/size_mb) | `label_data` 构造处 | 5min |
| 2 | Phase A 图片 prompt 注入当前风格描述 | `_generate_one_image` 的 prompt | 10min |
| 3 | 叠加 demo_bgm.wav 到所有输出 | `scene.py` 或 concat 后 | 15min |
| 4 | Ken Burns 范围扩大 + 随机 pan | `scene.py` zoom_expr | 15min |
| 5 | 场景首尾 fade | `scene.py` build_scene_video | 15min |

### P1 — 短期改进 (1-2天)

| # | 行动 | 依赖 | 预估时间 |
|---|------|------|:--------:|
| 6 | 风格切换 LUT | 需生成 noir_dark.cube, comic_pop.cube | 1h |
| 7 | 风格化后期滤镜 (颗粒/暗角/饱和度) | FFmpeg filter 链配置 | 30min |
| 8 | 引擎健康检查缓存 | 避免每轮连 ComfyUI | 30min |
| 9 | 多集并行合成 (max_workers=2) | ThreadPoolExecutor | 20min |
| 10 | 定时长场景 cap (max 8s) | `build_scene_list` | 10min |

### P2 — 中长期改进 (1周)

| # | 行动 | 预估时间 |
|---|------|:--------:|
| 11 | Manifest 增加 shot_type 字段 + 景别节奏编排 | 2h |
| 12 | 三拍法叙事单元重组 (每集2单元 × 3拍) | 4h |
| 13 | xfade 转场系统 (crossfade/slide) | 2h |
| 14 | 按情感类型切换 LUT (场景级而非整集级) | 3h |
| 15 | ComfyUI AnimateDiff 管线稳定化 | 1d+ |

---

## 附录: 代码级改动示例

### A. scene.py — 增强 Ken Burns + fade

```python
# 原代码
zoom_expr = f"1+0.05*on/{frames}"

# 改为: 随机缩放幅度 + 可选 pan
import random
zoom_max = random.uniform(1.08, 1.15)  # 8%-15%
zoom_min = 1.0
zoom_expr = f"{zoom_min}+({zoom_max}-{zoom_min})*on/{frames}"

# 加随机 pan 起始偏移
pan_x = random.choice([0, random.uniform(50, 150)])  # 0 或右偏移
pan_y = random.choice([0, random.uniform(30, 80)])   # 0 或下偏移
pan_expr = f"x={pan_x}+(iw-{pan_x}*2-(iw/ih)*ih/2)*on/{frames}:y={pan_y}+(ih-{pan_y}*2)*on/{frames}"

# 加 fade in/out
fade_in = f"fade=t=in:st=0:d=0.3"
fade_out = f"fade=t=out:st={duration-0.3}:d=0.3"
```

### B. pipeline.py — 正确提取 FFmpeg 元数据

```python
# verify_video 返回的 dict 中 duration 是字符串如 "00:00:30.50"
# label_data 构造处应直接使用该字符串
# 问题排查: 检查 FFmpeg fallback 路径是否确实调用了 verify_video
# _run_synthesis 内部调用了 synthesize_episode → verify_video
# 但 verify_video 的 info dict 里 key 是 "duration" (字符串)
# label.json 显示 "duration": "?" → 说明 report 为 None
# 根因: _run_synthesis 里 if info["passes"] 设置 status,
# 但 return info 的 duration 是字符串, label_data 那里没问题
# 需要检查 synthesize_episode 是否返回了 info
```

### C. vf_master_loop.py — 风格感知的图片生成

```python
# 在 phase_self_produce 的图片 prompt 中注入风格
STYLE_IMAGE_PROMPTS = {
    "Painterly 3D Noir": ", oil painting, dramatic noir lighting, deep shadows, dark moody atmosphere",
    "Hybrid Comic Pop": ", bold comic book art, pop colors, cel-shaded, high contrast, dynamic",
    "Cinematic Liquid Glass": ", translucent glass, refractive light, dreamy gradient, ethereal glow",
}
```

### D. phase_self_produce — BGM 叠加

```python
# 在 concat 之后, subtitle burn 之前
bgm_path = STATE / "produced_videos" / "demo_bgm.wav"
if bgm_path.exists():
    bgm_mixed = temp_ep_dir / "bgm_mixed.mp4"
    cmd = [
        str(FFMPEG), "-y",
        "-i", str(concat_path),
        "-i", str(bgm_path),
        "-filter_complex",
        "[1:a]volume=0.15[a1];[0:a][a1]amix=inputs=2:duration=first",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "128k",
        "-shortest",
        str(bgm_mixed),
    ]
    subprocess.run(cmd, capture_output=True)
    concat_path = bgm_mixed  # 替代为带 BGM 版本
```

---

## 总结: 当前 Phase D 品质评分

| 维度 | 评分 | 说明 |
|------|:----:|------|
| 技术架构 | ⭐⭐⭐⭐ | 干净的三层 fallback, 模块化好 |
| 画面运动 | ⭐⭐ | 仅有 Ken Burns 缩放, 单一 |
| 节奏编排 | ⭐ | 无三拍法/景别规划, 纯顺序 |
| 风格一致性 | ⭐ | 风格仅存于元数据, 不影响画面 |
| 声音设计 | ⭐⭐ | 无 BGM, TTS 质量可但单薄 |
| 转场 | ⭐ | 纯硬切, 零转场 |
| 字幕 | ⭐⭐⭐⭐ | ASS 格式 + 中文适配良好 |
| 元数据 | ⭐⭐ | label.json 字段缺失 |
| 色彩 | ⭐⭐⭐ | LUT 基础设施有, 但未按风格切换 |
| 自动化程度 | ⭐⭐⭐⭐⭐ | 轮询-自生产闭环完整 |

**整体评分: 6.5/10** — 自动化基建扎实, 但视频品质停留在"有画面+有声音"级别。P0 的5项改进 (约1小时工作) 可将评分提升至 8/10 水平。
