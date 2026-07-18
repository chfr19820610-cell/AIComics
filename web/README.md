# Web 目录说明

更新时间：`2026-05-20 00:20:00 +0800`

`web` 目录包含三部分：

- `backend`：FastAPI API、鉴权、版本策略、Creator 服务层
- `frontend`：Ant Design Pro 控制台
- `static_preview`：静态预览兜底页

## 当前推荐用途

- 开发和试用阶段，优先走 `web` 的固定 Web 环境
- 当前不推荐先做桌面安装包分发

## 推荐入口

- 后端入口：`web/backend/app.py`
- 前端入口：`web/frontend/src/app.tsx`
- 本地联调一键启动：`scripts/manage_local_web_stack.sh up`
- 架构文档：[docs/技术架构文档.md](/Users/chenfengrui/Desktop/AIComics/10_System/docs/技术架构文档.md)
- 部署方案：[docs/部署方案.md](/Users/chenfengrui/Desktop/AIComics/10_System/docs/部署方案.md)

## 本地 Creator 联调

推荐命令：

```bash
cd /Users/chenfengrui/Desktop/AIComics/10_System
scripts/manage_local_web_stack.sh up
```

默认行为：

- 后端启动到 `http://127.0.0.1:7861`
- 前端启动到 `http://127.0.0.1:8001`
- 后端固定使用 `config/web.development.yaml`
- 前端固定把 `UMI_APP_API_BASE_URL` 指向 `7861`
- 登录密码优先读取当前 shell 的 `AICOMIC_NORMAL_USER_PASSWORD`，否则回退读取 `.env.production.local`
- 进程 PID 写入 `state/tmp/local_web_stack/`
- 日志写入 `logs/local_web_stack/`

常用命令：

```bash
scripts/manage_local_web_stack.sh status
scripts/manage_local_web_stack.sh logs
scripts/manage_local_web_stack.sh restart
scripts/manage_local_web_stack.sh down
```

## 验收命令

### 1. 项目页真实浏览器验收

```bash
.venv/bin/python scripts/validate_creator_project_browser.py --project-id horror_real_sample_20260513015958
```

### 2. route-aware 前端视觉 QA gate

```bash
.venv/bin/python scripts/validate_frontend_visual_qa_gate.py
```

### 3. Creator 主链固定 gate

```bash
.venv/bin/python scripts/validate_creator_main_chain_gate.py --project-id horror_real_sample_20260513015958
```

默认检查内容：

- 登录链路
- 目标项目工作台打开
- 关键动作按钮存在
- 浏览器错误分级
- 当前控制台视觉 QA 基线

## 当前真实项目入口

```text
http://127.0.0.1:8001/creator?project_id=horror_real_sample_20260513015958
```

## 当前放行判断

当前如果要判断“是否可以给人试用”，优先看：

1. `reports/creator_main_chain_gate_report.json`
2. `reports/frontend_visual_qa_gate_report.json`

如果两者都通过，则当前 Web 主链可以进入试用。

## 使用建议

- 调接口、看服务层逻辑时优先从 `backend` 入手
- 做页面交互和样片审核流程时优先从 `frontend` 入手
- 当前若要对外试用，优先部署固定 Web 环境，而不是打包安装包
