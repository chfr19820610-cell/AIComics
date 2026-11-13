# 《封印之下》— 仙侠 AI 漫剧（xianxia-12）

**12 集 × 6 镜 = 72 分镜｜9:16 竖屏｜单集 42 秒**

> logline：全宗都笑他是丹田被封的废物，直到天雷降下、封印替他挡下第一击——
> 他才明白那道锁不是困住他的枷锁，而是天道要抹杀他之前，最后一道护命的屏障。

---

## 目录结构

```
state/projects/xianxia-12/
├── docs/
│   ├── deliverable.md          # PM 军团完整交付（立项 + 12 集 JSON）
│   ├── 立项文档.md              # 仅立项文档
│   ├── episodes.json           # 12 集大纲（机器可读）
│   ├── uiux_visual_spec.json   # UIUX 视觉设定（8 角色/6 场景/5 特效）
│   └── shot_prompts_en.json    # 72 镜英文 SDXL prompt（LLM 翻译产物）
├── assets/
│   ├── characters/             # 角色视图（林昭/苏璃/玄尘子/老墨…）
│   └── E01..E12/images/        # 每集六镜关键帧（{EP}_{SID}_key.png）
└── reports/                    # 渲染报告
```

## 制作管线

```
PM 军团（12 集大纲 + 72 分镜）
   ↓
UIUX 军团（角色 identity / 场景 / 特效视觉设定）
   ↓
LLM 翻译（中文 scene → 英文 SDXL prompt，72 条）
   ↓
ComfyUI（SDXL Base + anime-cel-shaded LoRA，768x1152）
   ↓
关键帧（每集 6 张）
   ↓
render-release（ffmpeg 合成 + AI 标签）→ 成片 mp4
```

## 复现命令

```bash
# 1) 生成某集关键帧（走裁剪链路，避免 CLIP 77 token 卡死）
PYTHONPATH=src .venv/bin/python /tmp/gen_ep_keyframes.py \
  --manifest manifests/xianxia_12.json \
  --prompts state/projects/xianxia-12/docs/shot_prompts_en.json \
  --episode E01 --asset-root state/projects/xianxia-12/assets

# 2) 合成成片（默认 768x1152 竖屏）
PYTHONPATH=src .venv/bin/python -m aicomic.cli.main render-release \
  --episode-manifest manifests/xianxia_12.json \
  --episode-code E01 \
  --asset-root state/projects/xianxia-12/assets \
  --output state/projects/xianxia-12/assets/E01/release_E01.mp4
```

## 三条硬约束（踩坑后固化）

1. **prompt 必须 ≤ 77 token** —— 超了会让 ComfyUI 卡在 3/28 步不返回；
   走 `local_adapter.limit_clip_tokens()` 自动裁剪。
2. **prompt 必须英文** —— SDXL 的 CLIP 只认英文，中文会出随机噪点。
3. **角色名必须跨军团一致** —— PM 用「苏璃/老墨/玄尘子」，UIUX 用「苏清音/无名老者/玄阳长老」，
   曾导致角色图被跳过；现已按剧本统一。

## 视觉锚点

- **暗金锁链纹** + **雷纹** + **金瞳** 三个符号贯穿 72 镜
- 色彩分区：宗门段冷青灰+雾白 / 封印雷段暗金+电紫 / 天道段高饱和金
- 角色道具：林昭右腕旧布条、苏璃剑柄缠绳、老墨眼布、玄尘子断指玉扳指
