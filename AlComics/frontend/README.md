# AIComics Frontend

## Stack
Vue 3 + Vite + Axios + Tailwind CSS 极简

## Pages
- /login — 登录页
- /register — 注册页
- / — Dashboard: 项目列表 + "新建项目"按钮
- /projects/:id — 项目详情: 剧集列表 + "一键生成"按钮 + 进度条
- /episodes/:id — 播放页: 视频播放器

## Components
- App.vue — 路由+导航栏(登录状态显示)
- Login.vue — 登录表单
- Register.vue — 注册表单
- Dashboard.vue — 项目卡片列表 + 新建按钮
- ProjectDetail.vue — 剧集表格 + 生成按钮 + WebSocket进度条
- EpisodePlayer.vue — 视频播放
- api.js — Axios封装 + JWT拦截器
- ws.js — WebSocket连接管理

## Style
- Tailwind CSS, 干净暗色主题
- 移动端适配
- 不引入Element Plus/Ant Design（保持轻量）
