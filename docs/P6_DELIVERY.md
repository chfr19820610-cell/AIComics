# P6 交付说明（12 集 × 3-4 分钟音画对齐版）

> 生成时间：2026-11-16
> 目标：12 集 × 70 镜 × 3-4 分钟 = 840 镜全真视频
> 状态：**进行中**（P6 批量运行，预计 168-200 小时）

---

## 一、与旧版（6 镜 × 18 秒）的关键差异

| 项 | 旧版（P5） | 新版（P6） |
|---|---|---|
| 单集时长 | 18 秒 | **3-4 分钟** |
| 单集镜数 | 6 | **70** |
| 镜长决定 | 固定 3 秒 | **按 TTS 实测时长** |
| 字幕时间 | 按镜位估算 | **TTS 精确时长（误差 <0.05s）** |
| 配音对齐 | `-shortest` 硬裁 | **天然对齐** |
| 有台词镜景别 | 不限（会露嘴型） | **禁 closeup，降级 medium** |
| 生成参数 | `--seconds 3`（近似） | **`--frames 73`（精确）** |

---

## 二、技术栈

| 环节 | 工具 | 说明 |
|---|---|---|
| 剧本扩写 | DeepSeek-chat | 6 镜骨架 → 70 镜分镜表 |
| Prompt 翻译 | DeepSeek-chat | 840 条中文 → 英文 |
| 时长测量 | Piper TTS | 毫秒级精确 |
| 视频生成 | h3stream (MiniMax-H3-FL2VA 4bit MLX) | 512×384, 8 步 |
| 字幕 | TTS 实测时长 | 零误差 |
| 合成 | ffmpeg | 烧录字幕 + AAC 混音 |

---

## 三、目录结构

```
state/projects/xianxia-12/
├── specs/                        # SOP 规格（4 文档）
├── assets/
│   ├── bible.json                # 角色/场景/道具 SSOT
│   └── E01-E12/
│       ├── h3video/              # 70 镜视频
│       └── {EP}_H3_REAL.mp4      # 成片
├── scripts/E01-E12.json          # 四表一纲
├── shots/
│   ├── E01-E12.json              # 旧 6 镜
│   └── E01-E12_70.json           # 新 70 镜
├── prompts/E01-E12_70_en.json    # 840 条英文 prompt
├── runs/E01-E12/
│   ├── alignment.json            # 对齐计划（时长/帧数/字幕）
│   ├── audio_new/                # 配音
│   ├── cut/                      # SRT + 成片
│   ├── compliance.json
│   ├── metrics.json
│   └── handoff.md
├── reviews/ccv/                  # CCV 三轮评审
├── evals/                        # rubric + golden
├── gates/                        # 7 个可执行 gate
├── logs/                         # 运行日志（软链）
└── reports/                      # 验收报告
```

---

## 四、验收标准（12 集全部完成后）

### 4.1 硬指标（必须全过）

| 项 | 标准 | 检查命令 |
|---|---|---|
| 镜数 | 每集 70 镜 | `ls assets/E01/h3video/*.mp4 \| wc -l` |
| 分辨率 | 512×384 | `ffmpeg -i <file>` |
| 成片时长 | 180-240 秒（3-4 分钟） | `ffprobe` 或 `ffmpeg -i` |
| 音视频轨 | 齐全 | `ffmpeg -i <final>` 查 Stream |
| 字幕条数 | = 台词数 | `grep -c "-->" runs/E01/cut/E01_r2.srt` |
| 字幕精度 | TTS 实测（误差 <0.05s） | 对比 alignment.json 的 srt |

### 4.2 软指标（抽检）

| 项 | 方法 |
|---|---|
| 口型不暴露 | 抽 3 个台词镜看景别是否 medium 以上 |
| 风格统一 | 抽 5 个镜看是否赛璐璐动漫（非 Q 版） |
| 叙事连贯 | 整集看一遍 |

### 4.3 自动验收脚本

```bash
cd /Users/eric/Desktop/hermes/AlComics
.venv/bin/python scripts/accept_12ep.py
```

预期输出：`验收结果: 12/12 集通过`

---

## 五、已知限制（如实）

| # | 限制 | 影响 | 应对 |
|---|---|---|---|
| 1 | h3stream 不支持音频输入驱动 | 无法让口型精确匹配 TTS | 用镜头语言"藏"（禁 closeup） |
| 2 | environment/wide 镜偏写实 CG | 与人物镜风格不完全统一 | 可接受（CG 感有气势） |
| 3 | 单镜 12-14 分钟 | 840 镜 ≈ 168-200 小时 | 已接受（峰哥选方案 B） |
| 4 | 中文 prompt 会卡死 | 必须用英文 | 已翻译 840 条 |
| 5 | 角色跨镜形象可能漂移 | 无人脸锁定 | 用视觉锚点 prompt + not chibi |

---

## 六、监控与自愈

| 机制 | 频率 | 动作 |
|---|---|---|
| 进程存活检查 | 5 分钟 | 死了自动重启 |
| 卡住检测 | 5 分钟 | 超 40 分钟无新文件 → kill 重试 |
| 每集合成 | 70 镜齐时 | 自动 TTS+SRT+烧录+混音 |
| 进度日志 | 实时 | `logs/watch.log` |

**查看进度**：
```bash
tail -f state/projects/xianxia-12/logs/watch.log
```

---

## 七、提交记录

| commit | 内容 |
|---|---|
| `03be422` | P6 音画对齐工作流 |
| `11d5f31` | 修复监控 current_shot |
| `e5b510f` | 去除 /tmp 硬编码 |

---

## 八、下一步（P6 完成后）

1. 跑 `scripts/accept_12ep.py` 验收
2. 跑 CCV 三轮评审（用新 70 镜分镜表）
3. 跑 7 个 gate
4. 对比新旧版效果，写复盘
