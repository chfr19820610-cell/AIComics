# AI漫剧生产控制台前端

更新时间：`2026-05-01 22:48:43 +08:00`

该目录是 `10_System` 的 Web 前端控制台，技术栈基于 Ant Design Pro、React、TypeScript 和 Umi Max。

## 技术栈

- Ant Design Pro
- React
- TypeScript
- Umi Max
- ProComponents
- ECharts / Ant Design Charts

## 本地启动

```powershell
cd G:\AIComics\10_System\web\frontend
npm install
npm run dev
```

默认地址：

- 前端：`http://127.0.0.1:8000`
- 登录页：`http://127.0.0.1:8000/login`
- 后端 API：`http://127.0.0.1:7860`

## 主要页面

- `/login`
- `/login/callback`
- `/dashboard`
- `/episodes`
- `/jobs`
- `/batches`
- `/provider`
- `/commands`
- `/members`
- `/audit`
- `/settings`
- `/rbac`
- `/oidc`
- `/review`
- `/security`

## 版本能力边界

- `creator`
  - 默认隐藏 `/commands`
  - 默认隐藏 `/members`、`/audit`、`/settings`、`/rbac`、`/oidc`、`/security`
  - 允许按配置开放本地开发登录
- `studio`
  - 开放成员管理、基础审计、基础设置、基础 RBAC
  - 可显示命令台，但仍受后端白名单和安全开关控制
- `enterprise`
  - 开放完整治理能力
  - 显示 `/security`
  - 承载审计导出和 OIDC 配置草稿能力

## 登录方式

- 企业统一登录：`/api/auth/oidc/start`
- 本地开发登录：`/api/auth/dev-login`
- 统一回调页：`/login/callback`

## 当前验证口径

- 推荐浏览器级验证脚本：`G:\AIComics\10_System\scripts\verify_frontend_browser_login.py`
- 推荐恢复脚本：`G:\AIComics\10_System\scripts\recover_frontend_dev.ps1`
- 推荐类型检查：

```powershell
cd G:\AIComics\10_System\web\frontend
.\node_modules\.bin\tsc.cmd --noEmit
```

## 已知注意点

- Windows 下 `npm run build` 可能出现“构建成功但 shell 不及时退出”
- 若出现 `HTML 200` 但页面空白，优先参考：
  - `G:\AIComics\10_System\docs\前端开发态登录与空白页排障说明.md`
- `node_modules`、`dist`、`src\.umi`、`src\.umi-production` 均属于可重建产物
