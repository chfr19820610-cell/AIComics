# 仙侠漫剧 12 集 · 交付说明

> 生成时间：2026-11-15
> 引擎：MiniMax H3 (4bit MLX) via `h3stream` 流式加载
> 硬件：Apple M4 / 32GB / macOS

---

## 一、成片清单

每集：`assets/{EP}/{EP}_H3_REAL.mp4`

| 集 | 时长 | 分辨率 | 视频 | 音频 | 字幕 |
|---|---|---|---|---|---|
| E01 | 18.25s | 512×384 | h264 24fps | AAC 22050Hz | 烧录 |
| E02 | 18.00s | 512×384 | h264 24fps | AAC 22050Hz | 烧录 |
| E03 | 18.00s | 512×384 | h264 24fps | AAC 22050Hz | 烧录 |
| E04 | 18.00s | 512×384 | h264 24fps | AAC 22050Hz | 烧录 |
| E05 | 18.00s | 512×384 | h264 24fps | AAC 22050Hz | 烧录 |
| E06 | 18.00s | 512×384 | h264 24fps | AAC 22050Hz | 烧录 |
| E07-E12 | 生成中 | — | — | — | — |

---

## 二、制作链路

```
1. 剧本+分镜（PM 军团，manifests/xianxia_12.json）
        ↓
2. 中→英 prompt 翻译（DeepSeek，docs/shot_prompts_en.json）
        ↓
3. H3 生成 6 段 3 秒视频（每段约 11 分钟）
        ↓
4. ffmpeg concat 拼接成 18 秒
        ↓
5. Piper TTS 配音（裁到 18 秒）
        ↓
6. SRT 字幕（3 秒/镜）+ 硬烧录
        ↓
7. 混音输出 final.mp4
```

---

## 三、技术参数

| 项 | 值 |
|---|---|
| 模型 | `ddalcu/MiniMax-H3-FL2VA-MLX-Serve-4bit`（37.6 GiB） |
| 分辨率 | 512×384 |
| 帧数 | 73 帧 / 24fps = 3.04 秒 |
| 采样步数 | 8 |
| 每镜耗时 | 11–15 分钟 |
| swap 峰值 | 3.4–3.7 GB |
| DiT active | 0.62 GiB |

### 风格 prompt（关键）

```
2d anime, flat cel shading, bold black outlines, hand-drawn animation,
Japanese anime style, xianxia wuxia, animation frames, <场景描述>
```

---

## 四、已知限制（如实记录）

### 1. 风格随镜头类型漂移

| 镜头类型 | 输出风格 |
|---|---|
| 大全景/俯视 | 电影级写实 CG |
| 中景 | 写实动漫 |
| 人像特写/群像 | Q 版卡通 |

**原因**：H3 训练数据分布导致，非配置问题。

### 2. 角色跨镜不一致

`h3stream` 无 first_frame/图生视频，无法用关键帧约束：
- 年龄偏小（生成 12-14 岁 vs 设定 16 岁）
- 服饰颜色不稳定

### 3. 偶发卡住

约每 27–40 镜卡一次（MLX 偶发），需 kill + 续传恢复。

---

## 五、可复现命令

```bash
cd /Users/eric/Desktop/hermes/tools/minimax-h3-stream-mac

# 单镜生成
.venv/bin/h3stream generate \
  --model-dir models --width 512 --height 384 \
  --seconds 3 --steps 8 --i-understand-experimental \
  --prompt "<STYLE>, <场景>" \
  --output out.mp4 --run-dir runs/xxx

# 批量生成
bash /tmp/p4_all.sh

# 合成成片
bash /tmp/composite_all.sh
```

---

## 六、素材来源

| 资产 | 位置 |
|---|---|
| 12 集剧本+分镜 | `manifests/xianxia_12.json` |
| 英文 prompt | `docs/shot_prompts_en.json` |
| 角色/场景/特效设定 | `docs/uiux_visual_spec.json` |
| 72 张关键帧（SDXL） | `assets/E01-E12/images/` |
| 配音 | `assets/E01-E12/audio/*.wav` |
| SRT 字幕 | `assets/E01-E12/subs/*.srt` |
| 6 秒视频段 | `assets/E01-E12/h3video/*_h3.mp4` |

---

## 七、待办

- [ ] E07–E12 生成（进行中）
- [ ] 12 集全部合成
- [ ] 可选：重跑 Q 版镜头（用 `not chibi` prompt）
- [ ] 可选：调色统一（ffmpeg LUT）
