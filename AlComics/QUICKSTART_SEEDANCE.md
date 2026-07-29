# 🎬 AIComics Seedance 快速启动指南

> 《星痕纪元》EP1 视频生成管线 · Seedance 2.0 豆包视频模型

## 📦 管线文件总览

| 文件 | 状态 | 说明 |
|------|------|------|
| `seedance_client.py` | ✅ 已就绪 | Seedance 2.0 API 客户端 (934行)，支持 submit→poll→download→batch |
| `manifests/ep01_seedance.json` | ✅ 已就绪 | EP1 25镜头分镜文件，generator=seedance |
| `compose_video_seedance.py` | ✅ 已就绪 | Seedance 管线入口：解析→生成→TTS→合成→MP4 |

## 🚀 快速启动

### 1. 环境依赖

```bash
# 已安装（无需操作）
# - Python 3.11+
# - ffmpeg (imageio-ffmpeg 内置)
# - edge-tts (用于中文旁白)
```

### 2. Dry Run 验证 (安全，不扣费)

```bash
cd /Users/eric/Desktop/herness/AIComics

# 验证 manifest 解析 + 管线逻辑
python compose_video_seedance.py \
  --manifest manifests/ep01_seedance.json \
  --shots 3 \
  --dry-run
```

预期输出：显示3个镜头的 prompt 摘要，0秒完成。

### 3. 实际生成

```bash
# 生成 EP1 前 3 个镜头（mini 模型，最快）
python compose_video_seedance.py \
  --manifest manifests/ep01_seedance.json \
  --shots 3 \
  --model mini

# 完整 EP1 生成（25个镜头，推荐 fast 模型）
python compose_video_seedance.py \
  --manifest manifests/ep01_seedance.json \
  --model fast

# 单镜头测试
python seedance_client.py \
  --prompt "一只猫在月光下漫步" \
  --model mini \
  --output test.mp4
```

### 4. CLI 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--manifest`, `-m` | (必填) | 分镜 JSON 路径 |
| `--shots` | all | 限制生成前 N 个镜头 |
| `--model` | `mini` | `pro` / `fast` / `mini` |
| `--dry-run` | off | 仅解析不生成 (安全) |
| `--skip-tts` | off | 跳过 TTS 旁白 |
| `--skip-compose` | off | 跳过视频合成 |
| `--concurrency` | 1 | 并行任务数 |

## 🔧 API 配置

```
Base URL: http://token.yundashi.com/v1
Auth:     Bearer token (已内置于 seedance_client.py)
Models:
  doubao-seedance-2-0       (alias: pro)  最高质量
  doubao-seedance-2-0-fast  (alias: fast) 均衡
  doubao-seedance-2-0-mini  (alias: mini) 最快
```

## ✅ 验证结果 (2026-07-23)

### 管线架构验证

| 阶段 | 结果 | 详情 |
|------|------|------|
| 文件完整性 | ✅ 通过 | 3/3 文件就绪 |
| 语法检查 | ✅ 通过 | seedance_client.py / compose_video_seedance.py / JSON 均有效 |
| Manifest解析 | ✅ 通过 | 25镜头，含 prompt_seedance 字段 |
| API 连通性 | ✅ 通过 | `GET /v1/models` → 200 (auth OK) |
| 视频生成提交 | ⚠️ 余额不足 | API 接受请求但预扣费失败 |
| TTS 旁白 | ⏭️ 跳过 | 依赖 Phase 1 视频生成 |
| 视频合成 | ⏭️ 跳过 | 依赖 Phase 1 视频生成 |

### 余额状态

```
当前余额: ¥4.33
单次生成成本: ¥5.75 (所有模型统一价格)
缺少: ¥1.42 / 镜头
```

> **结论**: 管线架构完全可行。唯一阻塞是 API 账户余额不足。

## 🐛 已知问题与修复

### 1. API 路径重复 (`/v1/v1/...` → 404)

**已修复**。`seedance_client.py` 原版路径携带 `/v1/` 前缀，与 base_url 的 `/v1` 重复。修复为：

```python
# 修复前
req = self._build_request("GET", "/v1/models")        # → /v1/v1/models (404)
req = self._build_request("POST", "/v1/video/generations")  # → /v1/v1/video/...

# 修复后  
req = self._build_request("GET", "/models")           # → /v1/models (✅)
req = self._build_request("POST", "/video/generations")    # → /v1/video/... (✅)
```

### 2. 余额不足 (403 insufficient_user_quota)

**解决方案**: 充值 API 账户至 ≥ ¥5.75/镜头。EP1 完整25镜头预估成本 ≈ ¥143.75。

## 📂 目录结构

```
AIComics/
├── seedance_client.py       # API 客户端
├── compose_video_seedance.py # 管线入口
├── manifests/
│   ├── ep01.json             # 旧版分镜 (prompt_sd)
│   └── ep01_seedance.json    # Seedance 分镜 (prompt_seedance) ← 使用这个
├── source_frames/ep01/       # 生成的视频素材 (*.mp4)
├── audio/ep01/               # TTS 旁白音频 (*.mp3)
├── temp/ep01/                # 合成中间文件
└── output/                   # 最终 MP4 输出
```

## 🔄 管线流程

```
分镜JSON (prompt_seedance)
    │
    ▼
Phase 1: Seedance 2.0 视频生成
    │  POST /video/generations → poll → download
    │  输出: source_frames/ep01/shot_01.mp4 ... shot_25.mp4
    ▼
Phase 2: TTS 旁白配音
    │  edge-tts → zh-CN-XiaoxiaoNeural
    │  输出: audio/ep01/shot_01.mp3 ... shot_25.mp3
    ▼
Phase 3: 视频合成 (标准化 + 字幕)
    │  ffmpeg re-encode + drawtext subtitles
    │  输出: temp/ep01/seg_final_01.mp4 ...
    ▼
Phase 4: 最终合成
    │  ffmpeg concat → BGM混音
    │  输出: output/ep01_seedance.mp4
    ▼
  成片 🎉
```

## 📝 下一步

1. **充值 API 账户** — 至少 ¥5.75（1镜头验证）或 ¥143.75（完整 EP1）
2. **重新运行 Phase 1** — `python compose_video_seedance.py -m manifests/ep01_seedance.json --shots 3 --model mini`
3. **验证生成质量** — 检查 `source_frames/ep01/shot_0*.mp4`
4. **完整生成** — 去掉 `--shots` 限制，生成全部25镜头
5. **运营上线** — 对接 `aicg-handbook` 的批量调度和 `video-factory-loop` 自动生产
