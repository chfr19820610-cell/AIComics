# AI漫剧生产控制台静态预览

该目录提供一个无需 `npm build` 的本地静态预览页，用于在 Ant Design Pro 工程受本机依赖环境影响时，仍然可以快速查看 Web 控制台效果。

## 使用方式

1. 启动后端 API：

```powershell
cd G:\AIComics\10_System
python -m uvicorn web.backend.app:app --host 127.0.0.1 --port 7860 --reload
```

2. 直接打开：

- `G:\AIComics\10_System\web\static_preview\login.html`
- `G:\AIComics\10_System\web\static_preview\index.html`

或使用任意静态服务器打开该目录。

## 当前能力

- 总览 Dashboard
- 剧集列表
- 任务列表与筛选
- 批次列表
- Provider 列表
- 命令白名单列表与执行结果面板
- 成员管理预览
- 审计中心预览
- 系统设置预览
- RBAC 角色矩阵预览
- 企业 OIDC 配置预览
- 复盘风险与建议
- Mock SSO 登录页
- JWT 本地访问令牌保存与退出登录

## 说明

- 静态预览直接请求 `http://127.0.0.1:7860`
- 页面会按当前 `edition` 自动隐藏 Creator 不可见的治理入口
- 仅用于本地预览和联调
- 正式工程仍以 `web\frontend` 的 Ant Design Pro 项目为主
