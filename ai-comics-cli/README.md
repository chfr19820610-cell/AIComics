# AIComics CLI

> 一人公司漫画短视频工厂 — 命令行工具

基于 [AIComics](https://github.com/chfr19820610-cell/AIComics) 引擎，封装 ComfyUI 生成 + 视频合成管线的 CLI 工具。

## 安装

```bash
# 从本地源码安装
cd ai-comics-cli
pip install -e .

# 或直接从 GitHub 安装
pip install git+https://github.com/chfr19820610-cell/AIComics.git@main#subdirectory=ai-comics-cli
```

安装后可用 `aicomics` 命令：

```bash
aicomics --help
```

## 前置要求

- **Python >= 3.10**
- **ComfyUI** 运行中（默认连接 `http://127.0.0.1:8188`）
- **ffmpeg**（合成视频用，`brew install ffmpeg`）

### ComfyUI 启动

```bash
aicomics serve start                     # 启动 ComfyUI（自动查找目录）
aicomics serve start --comfyui-dir /path/to/ComfyUI
aicomics serve status                    # 查看状态
aicomics serve stop                      # 停止
```

或者手动启动 ComfyUI 后，用 `aicomics check` 确认连接。

## 使用

### 1. 单张图片生成

```bash
aicomics render "一个动漫少女站在樱花树下，日系风格，柔和的午后光线"
```

可选参数：
```bash
aicomics render "prompt" \
  --workflow my_workflow    # 指定工作流（根据文件名）
  --comfyui-url http://localhost:8188
  --output-dir ./output/images
  --no-wait                 # 不等待生成完成
```

### 2. 批量生成

创建一个文本文件 `prompts.txt`，每行一条提示词：

```text
# 第一集场景
一个动漫少女站在樱花树下，日系校园风格
少女在教学楼走廊奔跑，阳光透过窗户洒落
# 第二集场景
黄昏时分的学校天台，两个主角背靠背坐着
夕阳下的海岸线，海浪拍打礁石
```

批量执行：

```bash
aicomics batch prompts.txt
```

可选参数：

```bash
aicomics batch prompts.txt \
  --concurrent 2      # 并行任务数
  --delay 0.5         # 提交间隔秒数
  --workflow default
```

### 3. 合成视频

```bash
aicomics video
```

自动查找 `aicomics_output/` 下的图片合并为视频。

可选参数：

```bash
aicomics video \
  --input-dir ./output/batch   # 图片来源目录
  --output ./output/video.mp4  # 输出路径
  --fps 24                     # 帧率
  --duration 3                 # 每张图片显示秒数
  --resolution 1920x1080       # 分辨率
  --with-audio                 # 添加背景音频（自动查找 mp3/wav）
```

### 4. 诊断检查

```bash
aicomics check
```

显示 ComfyUI 连接状态、设备信息、可用工作流列表。

## 工作流

CLI 会自动在以下位置搜索 ComfyUI 工作流 JSON 文件：

1. `$COMFYUI_WORKFLOW_DIR` 或 `$AICOMICS_WORKFLOW_DIR` 环境变量指向的目录
2. `~/Desktop/herness/AIComics/templates/`
3. 当前目录下的 `templates/` 文件夹
4. `~/Desktop/herness/AIComics/` 下递归查找

工作流中使用 `CLIPTextEncode` 节点的 `text` 输入会被自动替换为你的提示词。

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `COMFYUI_URL` | `http://127.0.0.1:8188` | ComfyUI 服务地址 |
| `AICOMICS_OUTPUT_DIR` | `./aicomics_output/` | 输出根目录 |
| `COMFYUI_WORKFLOW_DIR` | — | 工作流文件目录 |
| `AICOMICS_WORKFLOW_DIR` | — | 工作流文件目录（别名） |

## 捐赠

如果你觉得这个工具有用，欢迎请作者喝杯咖啡 ☕

**BTC:** `1JDmYgWRJipA5ZHDmoVPfpfW8n3Gtbb92c`

## 许可证

MIT © 峰哥一人公司
