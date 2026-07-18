# Scripts 目录说明

更新时间：`2026-05-20 00:20:00 +0800`

`scripts` 目录承载验证脚本、本地联调脚本、部署辅助脚本和浏览器巡检脚本。

## Python 口径

- 固定版本：`Python 3.12.13`
- 项目解释器：`10_System/.venv/bin/python`
- 不使用系统自带 `python3 3.9.x` 执行本目录脚本

示例：

```bash
cd /Users/chenfengrui/Desktop/AIComics/10_System
PYTHONPATH="$PWD/src:$PWD" .venv/bin/python scripts/run_demo_validation.py
PYTHONPATH="$PWD/src:$PWD" .venv/bin/python scripts/validate_full_system_suite.py
```

## 当前核心入口

### 本地联调

- `manage_local_web_stack.sh`：统一管理本地 Creator Web 栈
- `validate_creator_project_browser.py`：真实浏览器登录并打开目标项目页

### 当前推荐 gate

- `validate_frontend_visual_qa_gate.py`：登录本地 Creator，执行 route-aware 前端视觉 QA，并按当前控制台基线判通过
- `validate_creator_main_chain_gate.py`：Creator 主链固定 gate，串联编译、联调栈重启、项目页浏览器验收和视觉 QA gate

### 数据与全量验证

- `run_demo_validation.py`：写入模拟数据并跑一轮 Creator 主链路
- `validate_full_system_suite.py`：自动发现并执行全部 `validate_*.py`
- `validation_runtime.py`：全量验证运行时支撑

### 浏览器巡检底层脚本

- `run_frontend_visual_qa_chrome.mjs`：Chrome 全站巡检、截图和页面指标导出

## Provider 与 sidecar

- `manage_comfyui_service.py`：管理 ComfyUI 服务
- `run_local_provider_live_smoke.py`：执行本地图片、视频、TTS smoke
- `run_piper_http_server.py`：Piper HTTP sidecar
- `run_comfyui_sidecar.py`：Docker sidecar 启动 ComfyUI
- `manage_local_provider_stack.sh`：管理本地 Provider 联调栈

## 推荐用法

### 看当前 Creator 主链是否可用

```bash
.venv/bin/python scripts/validate_creator_main_chain_gate.py --project-id horror_real_sample_20260513015958
```

### 单独跑前端视觉 QA gate

```bash
.venv/bin/python scripts/validate_frontend_visual_qa_gate.py
```

### 看浏览器是否真能打开并登录

```bash
.venv/bin/python scripts/validate_creator_project_browser.py --project-id horror_real_sample_20260513015958
```

### 重写 demo 数据并验证主链

```bash
PYTHONPATH="$PWD/src:$PWD" .venv/bin/python scripts/run_demo_validation.py
```

### 跑自动发现式全量验证

```bash
PYTHONPATH="$PWD/src:$PWD" .venv/bin/python scripts/validate_full_system_suite.py
```

## 当前建议

- 对“是否可以给人试用”的判断，优先看 `validate_creator_main_chain_gate.py`
- 对工程完整性和历史回归的扫描，补看 `validate_full_system_suite.py`
- 当前阶段不要把安装包分发当成脚本体系的首要目标，优先保证 Web 主链
