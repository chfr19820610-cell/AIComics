# H3 真视频生成方案（M4 32GB 本地）

> 2026-11-15 制定。目标：用本地算力生成 12 集仙侠漫剧的真视频（角色有运动），
> 替代当前的"静态图 + 推拉"动态漫。

---

## 一、背景与结论

### 之前三次失败的原因

| 方案 | 失败原因 |
|---|---|
| ComfyUI 原生 H3 | **一次性加载全部权重**，不流式 → swap 37GB，每步 224s |
| h3.c-int8 | 用 **62GB 分片 text encoder**，暴力映射 → swap 63GB，进程卡死 |
| Wan 2.2 5B | 能跑但 VAE 解码 20min，2 秒视频 31 分钟 |

**根因不是硬件不够，是缺少"流式加载"实现。**

### 关键发现

`AIXF666/minimax-h3-stream-mac` 在 **Apple M4 / 16GB** 上真机验证成功：

- 分辨率 640×384
- 124 帧 / 24fps / **5.167 秒**
- 16 DiT steps
- AAC 32kHz 立体声
- **运行 50–52 分钟**
- 每步原子 checkpoint + **断点续传**

### 工作原理

1. 逐层流式加载 Qwen3-VL text encoder（不整体映射）
2. AdaLN 表只预计算一次
3. 每个采样步流式加载全部 50 个 DiT block
4. attention query 分块，K/V 保留完整
5. 每步存原子 checkpoint（可断点续传）
6. 最后才加载 Video VAE / Audio VAE（先释放 DiT）
7. ffmpeg 合成 MP4

**模型是单体 safetensors（非 ComfyUI 的分片版）**，这是能塞进 16GB 的原因：
```
transformer.safetensors      17.4 GiB
text_encoder.safetensors     14.7 GiB
video_vae.safetensors         4.9 GiB
audio_vae.safetensors       577.2 MiB
────────────────────────────────────
总计                         37.6 GiB
```

---

## 二、验收标准

| 阶段 | 通过标准 |
|---|---|
| P0 环境 | `h3stream doctor` 全绿 |
| P1 首次生成 | 512×384 / 61 帧 / 8 步，产出可播放 mp4 带音频 |
| P2 质量评估 | 抽帧可见角色运动（非静止），画面无崩坏 |
| P3 单集验证 | 生成 E01 全部 6 镜，合成一集 |
| P4 全量 | 12 集 × 6 镜 = 72 段，合成 12 集成片 |

---

## 三、执行步骤

### P0：环境准备（约 10 分钟）

```bash
cd /Users/eric/Desktop/hermes/tools
git clone https://github.com/AIXF666/minimax-h3-stream-mac.git
cd minimax-h3-stream-mac
./scripts/install.command          # 只建 venv，不下载模型
.venv/bin/h3stream doctor --model-dir models
```

检查项：架构、内存、磁盘、MLX、ffmpeg。

### P1：下载模型（约 30–60 分钟，37.6 GiB）

```bash
.venv/bin/h3stream manifest --audio
.venv/bin/h3stream download \
  --model-dir models --audio --accept-model-license
```

⚠️ **license 提醒**：MiniMax H3 是 **MiniMax H3 Community License**，
有地域/商用限制。本方案仅本地实验用，商用需自行确认授权。

### P2：参数标定（单镜测试，15–60 分钟）

先跑最小配置验证通路：
```bash
.venv/bin/h3stream plan --width 512 --height 384 --seconds 2 --steps 8 --audio
.venv/bin/h3stream run --model-dir models --width 512 --height 384 \
  --frames 61 --steps 8 --audio -o outputs/test.mp4
```

三档配置（按需选）：

| 档位 | 分辨率 | 帧数 | 步数 | 预估耗时 | 用途 |
|---|---|---|---|---|---|
| 快速预览 | 512×384 | 61 (2.5s) | 8 | ~15 min | 构图/动作验证 |
| 标准 | 640×384 | 124 (5.2s) | 16 | ~52 min | 成片 |
| 高质量 | 768×432 | 124 | 20 | ~80 min | 关键镜头 |

### P3：E01 单集验证

- 用 E01 六镜的关键帧作 first_frame
- 逐镜生成 → 抽帧检查连续性
- 与现有配音/字幕合成
- 人工验收

### P4：全量 12 集（后台长跑）

- 72 段视频，按"标准档"约 60 小时，按"快速预览档"约 18 小时
- 每步有 checkpoint，可中断续跑
- 后台 job 运行，定期汇报进度

---

## 四、风险与对策

| 风险 | 概率 | 对策 |
|---|---|---|
| 32GB 内存仍 OOM | 低（16GB 已验证） | 降分辨率/帧数；关掉其他占内存服务 |
| 下载 37.6GB 失败 | 中 | 断点续传；hf-mirror |
| 生成速度慢于预期 | 中 | 用快速预览档先出全量，再挑重点镜重跑高质量 |
| 画质不如 ComfyUI 版 | 中 | 关键帧仍用 ComfyUI SDXL 生成，H3 只负责"动起来" |
| 授权问题 | — | 本地实验可，商用需确认 license |

---

## 五、与现有资产的关系

**保留**：
- PM 军团的 12 集剧本 + 72 分镜（`manifests/xianxia_12.json`）
- UIUX 的角色/场景/特效设定（`docs/uiux_visual_spec.json`）
- 72 张关键帧（`assets/E01-E12/images/`）→ **作 H3 的 first_frame**
- 12 集配音（`assets/*/audio/*.wav`）
- 12 集字幕（`assets/*/subs/*.srt`）

**替换**：
- 成片视频源从"静态图推拉"换成"H3 真运动"

**流程**：
```
关键帧 (SDXL, 已有)
   ↓ first_frame
H3 stream-mac 生成 5 秒运动视频
   ↓
替换原 release_*.mp4
   ↓
叠加配音 + 字幕
   ↓
final_*.mp4（真运动版）
```

---

## 六、时间预算

| 阶段 | 耗时 |
|---|---|
| P0 环境 | 10 分钟 |
| P1 下载 | 30–60 分钟 |
| P2 单镜标定 | 15–60 分钟 |
| P3 E01 验证 | 2–6 小时 |
| P4 全量 72 镜 | 18–60 小时（后台） |

**总计：约 1 天（含后台长跑）**

---

## 七、回退方案

若 stream-mac 在我们机器上失败：
1. 先试 ComfyUI + BlockSwap 节点（`xiaolibai-sys/ComfyUI-MiniMaxH3`）
2. 再降级到 Wan 2.2（已验证能出片，只是慢）
3. 最后用官方 API（需 API key）

**当前已交付的 12 集动态漫成片不受影响，可随时发布。**

---

## 八、实际执行记录（2026-11-15 凌晨）

### 实测数据（修正预期）

| 项 | 计划值 | 实测值 |
|---|---|---|
| 单镜耗时 | 11.4 分钟 | **11–15 分钟**（prompt 越长越慢） |
| 3 秒视频 swap | 3.7 GB | **3.4–3.7 GB** 稳定 |
| DiT active | 0.62 GiB | **0.62 GiB** 稳定 |
| 每步耗时 | 69 秒 | **60–69 秒** |

### 完成的成片

| 集 | 文件 | 大小 | 状态 |
|---|---|---|---|
| E01 | `assets/E01/E01_H3_REAL.mp4` | 1.8M | ✅ |
| E02 | `assets/E02/E02_H3_REAL.mp4` | 1.2M | ✅ |
| E03 | `assets/E03/E03_H3_REAL.mp4` | 1.7M | ✅ |
| E04 | `assets/E04/E04_H3_REAL.mp4` | 2.2M | ✅ |

规格：18 秒 / 512×384 / 24fps / h264 + AAC / 烧录中文字幕

### 关键 prompt（有效）

```
2d anime, flat cel shading, bold black outlines, hand-drawn animation,
Japanese anime style, xianxia wuxia, animation frames, <场景描述>
```

### 已知问题（实测）

**1. 风格漂移**
同一组风格词配不同场景，输出子风格会变：
- 单人/特写场景 → 写实向动漫（正常）
- **多人群像+冲突场景 → Q 版卡通**（E03/S01 实测）
- 巨兽特写 → 正常动漫

**缓解方案（待验证）**：prompt 加 `serious tone, dramatic, not chibi, realistic proportions`

**2. 角色跨镜漂移（硬限制）**
h3stream 无 first_frame/图生视频，无法用关键帧约束：
- 年龄偏小（生成 12-14 岁 vs 设定 16 岁）
- 服饰颜色不稳定（灰 vs 绿）
- 同一角色在不同镜的形象不一致

**这是模型能力边界，不是配置问题。**

**3. 偶发卡住**
E03/S01 曾 35 分钟只走 1 步（正常 1 分钟/步）。
处理：kill → `--run-dir` 续传重跑 → 恢复。
h3stream 有原子 checkpoint，卡住重启不丢进度。

### 自动化脚本

| 脚本 | 用途 |
|---|---|
| `/tmp/p4_all.sh` | 批量生成 72 镜 |
| `/tmp/composite_all.sh` | 六镜拼接 + 裁配音 + 重算 SRT + 烧录混音 |
| `/tmp/watch_p4.sh` | 守护：P4 结束后自动触发合成 |
