# AIComics 统一品质 Prompt 模板

> 目标：为 DALL-E 3 / gpt-image-1.5 生成最高质量的漫画帧图片。
> 策略：quality=high + 构图/光影/画风指令嵌入 prompt + 负提示词。

## 1. 单帧完整 Prompt 结构

```
[风格前缀]，剧集《{标题}》。
场景：{scene}。
人物：{characters}。
画面：{visual}。
动作：{action}。
情绪：{emotion}。
镜头：{camera}。
{恐怖/玄学上下文}
{构图指令}
{光影指令}
{画风指令}
{负提示词}
{品质收尾}
```

### 1.1 风格前缀

| 类型 | 前缀 |
|------|------|
| 常规动漫 | `动漫插画风` |
| 恐怖/玄学 | `Vertical 9:16 anime folk horror scene` |
| 热血/战斗 | `热血动漫插画风，高动态` |
| 梦幻/浪漫 | `梦幻动漫水彩风，柔和光效` |

### 1.2 构图策略层

| 镜头类型 | 构图指令 |
|----------|----------|
| **特写/近景** | `构图：浅景深主体突出，三分法将角色眼睛置于上三分线；背景虚化柔焦。` |
| **中景/双人** | `构图：中景双人对称/斜线构图，视线引导利用角色目光方向；前景留呼吸空间。` |
| **远景/全景** | `构图：环境主导，运用引导线（道路/建筑/自然轮廓）牵引视线至主体；前景框架（门框/窗/树枝）增加层次纵深。` |
| **默认(无明确镜头)** | `构图：三分法主体偏离中心，运用引导线强化视觉流向；前景/背景层次分明。` |

其他可选构图要素：
- 黄金螺旋：`黄金螺旋构图，趣味中心位于螺旋焦点。`
- 对角线：`对角线构图，画面张力沿斜线展开。`
- 框架式：`前景框架（窗/门/树叶）包围主体，增强空间纵深感。`
- 对称式：`镜像对称构图，强调庄重感或诡异氛围。`

### 1.3 光影策略层

| 情绪/场景 | 光影指令 |
|-----------|----------|
| **恐怖/紧张/诡异/阴冷** | `光影：低调戏剧光，伦勃朗式侧光勾勒面部轮廓；背光边缘光分离主体与背景；暗部保留细节不漆黑。` |
| **浪漫/温馨/柔和/平静** | `光影：柔光漫射照明，逆光金色边缘轮廓光；面部补光柔和，高光扩散，阴影柔和过渡。` |
| **愤怒/激烈/战斗/爆发** | `光影：硬光高对比，三点布光（主光+侧逆光+补光）提升立体感；强阴影增加戏剧张力，高光区域提示细节。` |
| **默认/日常对话** | `光影：专业三点布光，主光塑造主体形态，侧逆光勾勒轮廓边缘，补光保留暗部细节；整体光比适中，层次丰富不扁平。` |

其他可选光影要素：
- 剪影：`逆光剪影，前景全黑，背景高亮。`
- 月光：`冷色月光主光源，环境呈蓝紫调，阴影偏冷。`
- 暖光：`暖色钨丝灯主光源，环境呈橙黄调，高光偏暖。`
- 侧光：`90度侧光，半脸照亮半脸阴影，突出情绪转折。`
- 顶光：`顶光强调骨骼结构，眼窝和下巴形成深阴影。`

### 1.4 画风与渲染层

| 场景类型 | 画风指令 |
|----------|----------|
| **夜景/暗场景** | `画风：高精度动漫插画，夜间场景注意色温偏冷（蓝紫调），光源色温偏暖（橙黄调）形成色彩对比；暗部保留细节不漆黑，避免AI常见噪点和色块。` |
| **白天/户外** | `画风：高精度动漫插画，日光场景注意色温偏暖，高光不过曝，阴影有色彩倾向（冷蓝反射）；天空渐变平滑，无带状色阶。` |
| **默认/室内** | `画风：高精度动漫插画，色彩和谐统一，光影过渡细腻，线条干净利落，背景细节丰富不杂乱。` |

### 1.5 负提示词（嵌入 prompt 内）

由于 gpt-image-1.5 和 DALL-E 3 API **不支持独立 `negative_prompt` 参数**，负项必须用自然语言嵌入在 prompt 结尾：

```
注意：画面中不要出现文字、字幕、标题、气泡对话框、logo、水印；
不要出现扭曲的手部、多余的手指或脚趾；
不要出现畸形面部、错位五官；
不要出现模糊、像素化、色块噪点、带状色阶；
不要出现镜像翻转或画面切割失调；
角色面容、发色、服装等关键特征在本集内保持一致。
```

### 1.6 品质收尾

```
高对比、强戏剧张力、短剧封面级质感。
```

---

## 2. providers.yaml 配置参考

```yaml
openai_image:
  model: gpt-image-1.5
  # 竖屏 9:16 漫画帧最佳分辨率
  # gpt-image-1.5 支持: 1024x1024, 1024x1536, 1536x1024
  size: 1024x1536
  # quality=high 启用最高质量渲染（每张约 $0.20，4× medium 价格）
  quality: high
  output_format: png
```

### 2.1 模型规格速查

| 参数 | gpt-image-1.5 | DALL-E 3 (传统) |
|------|---------------|-----------------|
| 支持尺寸 | 1024×1024, 1024×1536, 1536×1024 | 1024×1024, 1024×1792, 1792×1024 |
| quality | low / medium / high | standard / hd (注: 名称不同) |
| style | 不支持 | vivid / natural |
| negative_prompt | 不支持 | 不支持 |
| max prompt tokens | ~2000 | ~4000 |

### 2.2 quality 级别影响

| quality | 1024×1536 价格 | token 数 | 适用场景 |
|---------|----------------|----------|----------|
| low     | $0.013         | 408      | 快速预览/草稿 |
| medium  | $0.05          | 1584     | 常规出图（旧默认） |
| **high**| **$0.20**      | **6240** | **最终成片/封面** |

---

## 3. 使用示例

### 3.1 完整 Prompt 示例（常规动漫帧）

```
动漫插画风，剧集《暗夜追踪》。
场景：废弃地铁站。
人物：林夜、神秘女子。
画面：昏暗站台上两人对峙，头顶日光灯闪烁。
动作：林夜缓缓举起手中的证件。
情绪：紧张、猜疑。
镜头：中景双人。
构图：中景双人对称/斜线构图，视线引导利用角色目光方向；前景留呼吸空间。
光影：低调戏剧光，伦勃朗式侧光勾勒面部轮廓；背光边缘光分离主体与背景；暗部保留细节不漆黑。
画风：高精度动漫插画，夜间场景注意色温偏冷（蓝紫调），光源色温偏暖（橙黄调）形成色彩对比；暗部保留细节不漆黑，避免AI常见噪点和色块。
注意：画面中不要出现文字、字幕、标题、气泡对话框、logo、水印；不要出现扭曲的手部、多余的手指或脚趾；不要出现畸形面部、错位五官；不要出现模糊、像素化、色块噪点、带状色阶；不要出现镜像翻转或画面切割失调；角色面容、发色、服装等关键特征在本集内保持一致。
高对比、强戏剧张力、短剧封面级质感。
```

### 3.2 完整 Prompt 示例（恐怖帧）

```
Vertical 9:16 anime folk horror scene, no text, no subtitles, no captions, no Chinese characters, no letters, no logos, no watermark. Single vertical keyframe illustration.
Location: an abandoned ancestral house interior.
Visual direction: a single cold flashlight beam cutting through darkness.
Action: after the protagonist touches the ritual object, distant footsteps appear.
Emotion: terrified, escalating, out of control.
Camera: dark handheld flashlight sweep.
Horror beat: escalation.
Continuity anchor object: a white porcelain offering bowl.
Character consistency avoidance strategy: dark_light.
Use darkness, fog, back view, silhouettes, object close-ups, door gaps, low contrast moonlight.
If ritual paper, photographs, bowls, door frames, grave markers, shrine plaques, wall notices, posted sheets, paper scraps, hanging labels, or any flat surface appear, keep all markings blank, abstract, torn, blurred, aged, or fully obscured.
Do not draw readable words, calligraphy, talisman script, labels, stamps, seals, symbols, numbers, signage, inscriptions, or printed notices anywhere in the frame.
构图：环境主导，运用引导线（建筑轮廓）牵引视线至光源中心；前景暗影增加纵深感。
光影：低调戏剧光，伦勃朗式侧光勾勒面部轮廓；背光边缘光分离主体与背景；暗部保留细节不漆黑。
画风：高精度动漫插画，夜间场景注意色温偏冷（蓝紫调），光源色温偏暖（橙黄调）形成色彩对比；暗部保留细节不漆黑，避免AI常见噪点和色块。
注意：画面中不要出现文字、字幕、标题、气泡对话框、logo、水印；不要出现扭曲的手部、多余的手指或脚趾；不要出现畸形面部、错位五官；不要出现模糊、像素化、色块噪点、带状色阶；不要出现镜像翻转或画面切割失调；角色面容、发色、服装等关键特征在本集内保持一致。
高对比、强戏剧张力、短剧封面级质感。
```

---

## 4. 代码集成（request_builder.py）

`build_image_prompt()` 函数已将 `_build_quality_suffix()` 追加到每个非恐怖帧的 prompt 结尾。
`build_horror_visual_prompt()` 已在英文 prompt 结尾附加相同的中文品质指令块。

如需扩展或调整品质模板，编辑 `_build_quality_suffix()` 函数：

```python
def _build_quality_suffix(shot: dict[str, Any]) -> str:
    # 根据 shot['camera'] 选择 → 构图指令
    # 根据 shot['emotion'] 选择 → 光影指令
    # 根据 shot['scene'] 选择 → 画风指令
    # 固定嵌入 → 负提示词
```

---

## 5. 调优备忘

| 问题 | 可能原因 | 调整建议 |
|------|----------|----------|
| 手部变形 | 负项不够强 | 增加 `多余手指、扭曲手掌` 提示 |
| 角色不一致 | 缺少角色特征约束 | 在 prompt 中强化 `发色、发型、服装颜色` |
| 文字残留 | 负项忽略特定文字类型 | 补充 `标签、标志、路牌` 等 |
| 色彩扁平 | 光影指令未生效 | 检查 emotion 字段是否匹配光影分支 |
| 构图松散 | 未指定镜头类型 | 在 shot 中填入 camera 字段 |
