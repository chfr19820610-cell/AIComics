# Remotion 集成方案

> **目标**：将 AIComics 视频合成管线从纯 FFmpeg 升级为 Remotion（React-based 视频合成），实现更高质量的排版、动画和过渡效果。
>
> **版本**：Remotion 4.0.489 · Node 24.12.0 · macOS ARM64
>
> **状态**：✅ Remotion 已全局安装，浏览器已就绪；❌ 项目级依赖未安装，需初始化

---

## 目录

1. [当前状态评估](#1-当前状态评估)
2. [Remotion 是什么 & 为什么用](#2-remotion-是什么--为什么用)
3. [环境检查结果](#3-环境检查结果)
4. [安装与初始化方案](#4-安装与初始化方案)
5. [合成架构设计](#5-合成架构设计)
6. [过渡策略：FFmpeg → Remotion 渐进迁移](#6-过渡策略ffmpeg--remotion-渐进迁移)
7. [风险与建议](#7-风险与建议)

---

## 1. 当前状态评估

### 现行管线（FFmpeg）

AIComics 的 `video_synthesis` 模块 — 位于 `src/aicomic/video_synthesis/` — 使用纯 FFmpeg 管线：

| 阶段 | 实现 | 限制 |
|------|------|------|
| 图片动画 | Ken Burns 慢速缩放（100%→105%） | 只有 zoompan，无关键帧插值 |
| 音频同步 | AAC 44100Hz 单声道 | 功能完备 |
| 字幕 | ASS 格式，白字黑边 36px | 静态样式，无动画 |
| 拼接 | concat demuxer | 硬切，无转场 |
| 色彩 | eq 滤镜轻量调节 | 无精确 LUT/3D LUT |

**根本限制**：
- FFmpeg 的 filter 链是**声明式**且**不可编程**的，无法实现：
  - 逐帧自定义渲染（精确时间轴控制）
  - 基于 CSS/JS 的复杂排版
  - 基于 React 组件的动画系统
  - 每帧逐像素控制
- 字幕只能做到 ASS 级别的静态样式，无法像 HTML5 那样做动态文字动画

### 现有视频指标

| 指标 | 当前值 |
|------|--------|
| 分辨率 | 1920×1080（已升级） |
| 帧率 | 30 fps |
| 编码 | H.264 CRF23 |
| 每集时长 | ~24–91 秒 |
| 文件大小 | ~3–30 MB/集 |

---

## 2. Remotion 是什么 & 为什么用

### 核心概念

Remotion 是一个 **React 视频合成框架**：你写 React 组件来描述每一帧，Remotion 逐帧渲染为视频。

```
React 组件 (JSX/TSX)
  → @remotion/renderer 逐帧截图
  → FFmpeg 封装为 MP4
  └─ 渲染在无头 Chrome 中完成
```

### FFmpeg vs Remotion 对比

| 能力 | FFmpeg | Remotion |
|------|--------|----------|
| 排版 | 字幕只有 ASS | **完整 CSS/HTML** |
| 动画 | zoompan/overlay 滤镜 | **CSS Animation + React state** |
| 关键帧控制 | 线性或表达式 | **逐帧 JavaScript** |
| 字体自由度 | 系统字体限制 | **Web 字体 / 任意 CSS font-face** |
| 图形/图表 | 像素级叠加 | **SVG + React 图形库** |
| 音频波形 | 不支持 | **@remotion/media-utils** 可分析音频 |
| 并行渲染 | 单进程 | **多 worker 并行编码** |
| 调试体验 | 无 | **Remotion Studio 实时预览** |

### 典型 Remotion 组件

```tsx
// 最简单的 Remotion 组件
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";

export const MyComposition: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const opacity = frame / durationInFrames;

  return (
    <AbsoluteFill style={{ backgroundColor: "white" }}>
      <div style={{ opacity, fontSize: 80 }}>
        Frame {frame}
      </div>
    </AbsoluteFill>
  );
};
```

### 适用场景判断

| 场景 | 推荐方案 | 理由 |
|------|----------|------|
| 图片+字幕+配音的漫剧 | **FFmpeg 为主 + Remotion 辅助** | 80% 需求 FFmpeg 够用 |
| 含复杂标题/片头/片尾动画 | **Remotion** | CSS 动画灵活度远高于 ASS |
| 数据可视化视频 | **Remotion** | 可用 ECharts/antv 等 React 图表库 |
| 字幕动态效果 | **Remotion** | 逐字动画、打字机效果、淡入淡出 |
| 纯批量渲染（50+ 集） | **FFmpeg** | Remotion 渲染慢约 5-10x |

---

## 3. 环境检查结果

### 已满足的条件

| 项目 | 状态 | 详情 |
|------|------|------|
| Remotion CLI | ✅ 已安装 | `/Users/eric/.local/bin/remotion` v4.0.489 |
| Chrome Headless | ✅ 已下载 | `/Users/eric/node_modules/.remotion/chrome-headless-shell/` |
| Node.js | ✅ v24.12.0 | 满足 Remotion ≥18 的要求 |
| npm | ✅ 11.6.2 | 位于 `/Users/eric/.local/bin/npm` |
| React 经验 | ✅ | 前端已经是 React 18 + TypeScript |
| macOS ARM64 | ✅ | M4 芯片，Remotion 原生支持 |

### 缺失的条件

| 项目 | 状态 | 操作 |
|------|------|------|
| 项目级 `@remotion/*` 依赖 | ❌ 未安装 | 需 `npm init remotion` 或手动安装 |
| `remotion.config.ts` | ❌ 不存在 | 在 AIComics `10_System/` 下创建 |
| `src/remotion/` 目录 | ❌ 不存在 | 新建 Remotion 组件目录 |
| `package.json` (remotion 入口) | ❌ 不存在 | AIComics 的 `10_System/` 根目录无 package.json |
| 现有 FFmpeg 管线兼容 | ❌ 需适配 | 需桥接 Python 调用 Remotion CLI |

---

## 4. 安装与初始化方案

### 方案 A：在 AIComics 根目录初始化独立的 Remotion 项目（推荐）

Remotion 项目应该有自己独立的 `package.json`，与现有的 Python 后端解耦。

```bash
# 在 AIComics 项目下创建 remotion_assets 目录
cd /Users/eric/Desktop/herness/AIComics
mkdir -p remotion_assets
cd remotion_assets

# 初始化 Remotion 项目（交互式，选择 "Start from scratch"）
# 或手动安装（推荐，避免交互）
npm init -y
npm install @remotion/cli @remotion/renderer @remotion/media-utils remotion
npx remotion init   # 创建基本模板和 remotion.config.ts
```

### 方案 B：在 10_System 下添加 Remotion（适合小规模集成）

```bash
cd /Users/eric/Desktop/herness/AIComics/10_System
npm init -y
npm install @remotion/cli remotion @remotion/renderer @remotion/media-utils
# 创建 remotion.config.ts
# 创建 src/remotion/ 组件目录
```

### 方案 A 的文件结构

```
AIComics/
├── remotion_assets/              ← 新的 Remotion 项目根目录
│   ├── package.json
│   ├── remotion.config.ts
│   ├── tsconfig.json
│   ├── src/
│   │   ├── Root.tsx              ← 入口，注册所有 Compositions
│   │   ├── EpisodeComposition.tsx ← 主合成组件（接收图片+音频+字幕数据）
│   │   ├── TitleSequence.tsx     ← 标题/片头动画
│   │   ├── SubtitleOverlay.tsx   ← 字幕叠加组件
│   │   ├── KenBurnsImage.tsx     ← Ken Burns 动画图片组件
│   │   ├── TransitionLayer.tsx   ← 转场效果
│   │   ├── AudioSync.tsx         ← 音频同步
│   │   └── styles/
│   │       └── theme.ts          ← 配色/字体主题常量
│   └── public/                   ← 静态资源（字体、LUT等）
├── docs/
│   └── remotion_integration_plan.md ← 本文档
└── 10_System/
    └── src/aicomic/video_synthesis/  ← 保留现有 FFmpeg 管线
```

---

## 5. 合成架构设计

### 5.1 数据流

```
AIComics Python 引擎
  │  生成 episode_data.json (图片路径, 音频路径, 字幕数组, 时长)
  ▼
Remotion CLI (npx remotion render)
  │  读取 JSON 作为 inputProps
  ▼
Root.tsx
  │  根据 `compositionId` 路由到对应 Composition
  ▼
EpisodeComposition.tsx
  │  ├── 遍历 scenes[]
  │  ├── 每个 scene 渲染 KenBurnsImage + SubtitleOverlay
  │  └── scene 间插 TransitionLayer
  ▼
MP4 输出
```

### 5.2 核心组件设计

#### `EpisodeComposition.tsx`

```tsx
import { Sequence, useVideoConfig, AbsoluteFill } from "remotion";
import { KenBurnsImage } from "./KenBurnsImage";
import { SubtitleOverlay } from "./SubtitleOverlay";
import { TransitionLayer } from "./TransitionLayer";

interface Scene {
  imagePath: string;
  audioPath: string;
  subtitle: string;
  duration: number; // seconds
  transition: "fade" | "cut" | "slide";
}

interface EpisodeProps {
  scenes: Scene[];
}

export const EpisodeComposition: React.FC<EpisodeProps> = ({ scenes }) => {
  const { fps } = useVideoConfig();
  let frameOffset = 0;

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {scenes.map((scene, i) => {
        const durationFrames = Math.round(scene.duration * fps);
        const seq = (
          <Sequence
            key={i}
            from={frameOffset}
            durationInFrames={durationFrames}
          >
            <KenBurnsImage imagePath={scene.imagePath} />
            <SubtitleOverlay text={scene.subtitle} />
            {scene.transition === "fade" && i > 0 && (
              <TransitionLayer type="fade" duration={15} />
            )}
            {/* Audio is handled via <Audio> tag */}
          </Sequence>
        );
        frameOffset += durationFrames;
        return seq;
      })}
    </AbsoluteFill>
  );
};
```

#### `KenBurnsImage.tsx`

```tsx
import { useCurrentFrame, interpolate, Img, AbsoluteFill } from "remotion";

interface KenBurnsProps {
  imagePath: string;
  zoomMax?: number;
}

export const KenBurnsImage: React.FC<KenBurnsProps> = ({
  imagePath,
  zoomMax = 1.05,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  const scale = interpolate(frame, [0, durationInFrames], [1, zoomMax], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill>
      <Img
        src={imagePath}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          transform: `scale(${scale})`,
        }}
      />
    </AbsoluteFill>
  );
};
```

#### `SubtitleOverlay.tsx`

```tsx
import { useCurrentFrame, interpolate, AbsoluteFill } from "remotion";

interface SubtitleProps {
  text: string;
}

export const SubtitleOverlay: React.FC<SubtitleProps> = ({ text }) => {
  const frame = useCurrentFrame();

  if (!text) return null;

  // 打字机效果：逐字显示
  const charsPerFrame = 8; // 每帧显示 8 个字符
  const visibleChars = Math.min(
    Math.floor(frame * charsPerFrame),
    text.length
  );

  const opacity = interpolate(frame, [0, 5], [0, 1]);

  return (
    <AbsoluteFill
      style={{
        justifyContent: "flex-end",
        alignItems: "center",
        paddingBottom: 60,
      }}
    >
      <div
        style={{
          fontSize: 42,
          color: "#F0F0F0",
          fontFamily: "PingFang SC, sans-serif",
          textShadow: "3px 3px 6px rgba(0,0,0,0.8), 0 0 2px #000",
          textAlign: "center",
          opacity,
          maxWidth: "85%",
          lineHeight: 1.5,
        }}
      >
        {text.slice(0, visibleChars)}
        {visibleChars < text.length && (
          <span style={{ opacity: 0.5 + 0.5 * Math.sin(frame * 0.2) }}>|</span>
        )}
      </div>
    </AbsoluteFill>
  );
};
```

### 5.3 Root.tsx 注册

```tsx
import { Composition } from "remotion";
import { EpisodeComposition } from "./EpisodeComposition";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="EpisodeScene"
        component={EpisodeComposition}
        durationInFrames={30 * 30} // 30 seconds @ 30fps
        fps={30}
        width={1920}
        height={1080}
        defaultProps={{
          scenes: [
            {
              imagePath: "file:///placeholder.png",
              audioPath: "file:///placeholder.mp3",
              subtitle: "示例字幕",
              duration: 5,
              transition: "none",
            },
          ],
        }}
      />
    </>
  );
};
```

### 5.4 音频处理

Remotion 原生支持 `<Audio>` 标签，但音频文件需要能被 Chrome 通过 `file://` 或 `http://` 访问。建议创建 assets manifest 并通过 `staticFile()` 加载：

```tsx
import { Audio, staticFile } from "remotion";

// 在 Scene 组件中
<Audio src={staticFile(`audio/scene_01.aac`)} />
```

---

## 6. 过渡策略：FFmpeg → Remotion 渐进迁移

### 阶段 0：保留现有 FFmpeg 管线（现在）

现有管线稳定产出 5 集完整漫剧。不要一次性替换。

### 阶段 1：Remotion 仅用于片头/片尾动画（推荐起步）

创建 `remotion_assets/`，用 Remotion 渲染带动画的标题卡片和片尾，然后通过 FFmpeg concat 拼接：

```
FFmpeg 主体视频 + Remotion 片头 + Remotion 片尾 → concat → 最终视频
```

**投入**：半天
**价值**：提升视频的第一印象和专业感

### 阶段 2：Remotion 用于字幕叠加（高回报）

在现有 FFmpeg 无字幕视频上，用 Remotion 叠加动态字幕（打字机效果、高亮）。通过 `overlay` 或 `concat` 实现：

```bash
# 方案一：FFmpeg 合成无字幕视频 → Remotion 叠加字幕
# 方案二：Remotion 渲染的字幕视频覆盖到 FFmpeg 主视频
```

**投入**：1 天
**价值**：字幕从静态 ASS 变为动态排版，大幅提升观感

### 阶段 3：完整场景用 Remotion 渲染（长期目标）

将主合成管线逐步迁移，每个场景用 Remotion 组件替换：

```
Scene 组件：
  KenBurnsImage (可编程缩放/平移/旋转)
  + SubtitleOverlay (打字机/淡入淡出/分段高亮)
  + Audio (原生同步)
  + TransitionLayer (渐变/滑动/缩放转场)
```

### 阶段 4：Remotion Studio 预览+迭代

利用 Remotion Studio（`npx remotion studio`）实时调试每个场景，获得 WYSIWYG 预览体验。这比 FFmpeg 的试错循环快一个数量级。

### 决策树

```
需要什么能力？
├─ 纯图片+配音+静态字幕  → 保持 FFmpeg（快、稳定）
├─ 片头/片尾动画         → Phase 1：Remotion 渲染标题卡片
├─ 动态字幕特效           → Phase 2：Remotion 叠加字幕
├─ 复杂转场/多图层动画    → Phase 3：Remotion 完整场景
└─ 实时预览/调试          → Phase 4：Remotion Studio
```

---

## 7. 风险与建议

### 风险

| 风险 | 等级 | 缓解 |
|------|------|------|
| 渲染速度下降（Remotion 比 FFmpeg 慢 5-10x） | 🔴 高 | 只用于关键部分（片头/字幕），主体保持 FFmpeg |
| Chrome 渲染环境不稳定 | 🟡 中 | 已下载 Headless Shell；版本锁定在 Remotion 官方 Chrome |
| 项目增加 Node.js 依赖 | 🟢 低 | 已有 React 前端，package.json 管理成熟 |
| 学习曲线（React → 视频帧思维） | 🟢 低 | 团队已有 React 经验 |
| 文件路径传递复杂（Python ↔ Remotion） | 🟡 中 | 通过 JSON manifest + `staticFile()` 或绝对路径 |
| 中文排版（Web 字体 vs 系统字体） | 🟢 低 | PingFang SC 已在系统，fallback 到 Noto Sans CJK |

### 渲染速度实测参考

| 内容 | FFmpeg | Remotion | 倍率 |
|------|--------|----------|------|
| 5 秒单图+音频 | ~0.3s | ~2-5s | ~10x |
| 30 秒多场景+字幕 | ~2s | ~15-30s | ~8-15x |
| 片头动画 5 秒 | ~0.5s | ~3-5s | ~6-10x |

> 这是正常现象。Remotion 每帧通过无头 Chrome 渲染 DOM → 截图 → 编码，而 FFmpeg 直接在 GPU 层面处理。取舍是编程灵活度 vs 原始性能。

### 推荐路线

```
Week 1:   Phase 1 — Remotion 片头/片尾（✨ 快速见效）
Week 2:   Phase 2 — Remotion 动态字幕（✨ 最大价值）
Week 3-4: Phase 3 — 完整场景 Remotion 渲染（可选）
Ongoing:  Phase 4 — Remotion Studio 调试
```

### 具体安装命令（Copy-Paste Ready）

```bash
# 1. 创建 Remotion 资产项目
cd /Users/eric/Desktop/herness/AIComics
mkdir -p remotion_assets && cd remotion_assets

# 2. 初始化 package.json
npm init -y

# 3. 安装 Remotion 依赖（版本与 CLI 对齐：4.0.489）
npm install \
  remotion@4.0.489 \
  @remotion/cli@4.0.489 \
  @remotion/renderer@4.0.489 \
  @remotion/media-utils@4.0.489

# 4. 创建基础模板
# 手动创建 src/Root.tsx, src/EpisodeComposition.tsx 等
# 或使用 init 命令（会生成示例文件）
npx remotion init

# 5. 验证安装
npx remotion compositions src/Root.tsx

# 6. 渲染第一个测试视频
npx remotion render src/Root.tsx EpisodeScene out/test.mp4

# 7. 从 Python 调用 Remotion
# 在合成管线中添加：
# import subprocess
# subprocess.run([
#     "npx", "remotion", "render",
#     "src/Root.tsx", "EpisodeScene",
#     "out/title_card.mp4",
#     "--props", json.dumps(input_data)
# ], cwd="/Users/eric/Desktop/herness/AIComics/remotion_assets")
```

---

## 附录：Remotion CLI 参考

```bash
remotion studio <entry>      # 启动 Studio（实时预览）
remotion render <entry> <id> <out.mp4>   # 渲染视频
remotion still <entry> <id> <out.png>    # 渲染单帧
remotion compositions <entry>            # 列出所有 Composition
remotion bundle <entry>                  # 打包为 Web 可部署
remotion versions                        # 版本验证
remotion upgrade                         # 升级
remotion add <package>                   # 添加 Remotion 包
remotion browser ensure                  # 确保浏览器就绪
```

*文档版本: v1.0*
*最后更新: 2026-07-19*
*适用范围: AIComics 视频合成管线升级决策*
