# AIComics v0.2.0 — AI 漫剧自动生成系统

> Release date: 2026-07-19
> Repository: `chfr19820610-cell/AIComics`
> Tag: `v0.2.0`

---

## 🎯 概述

v0.2.0 是一次重大功能迭代，覆盖供应商层、角色系统、分镜管理、视频工厂和前端UX五大领域，共 **17 个 commits**。代码精简 **-49%**，测试全绿 **640/640**。

---

## ✨ 主要功能

### 1️⃣ 云端优先 + 本地备用供应商层
- **默认云端**：openai_image + seedance + openai_tts via JieYou(GPT-5.5)
- **故障自动降级**：openai 不可用时自动切换到 `local_comfyui` / `piper`
- **Seedance 2.0 视频集成**：云端生图→视频，替代 FFmpeg 纯拼接，无 key 时自动降级
- **Kling AI (快手可灵) 视频 Provider**：`text2video` + `image2video` + JWT 认证
- **云端优先同步重构**：统一 Provider 抽象层

### 2️⃣ 角色管理系统
- 角色 workshop 编辑
- 角色一致性校验
- 角色多视图管理

### 3️⃣ 分镜版本管理
- 分镜 diff 对比
- 版本回滚 (rollback)
- 分镜面板 (board) 浏览

### 4️⃣ 视频工厂 v3.2
- **FFmpeg 管线合成**：自动拼接视频片段
- **AnimateDiff (ComfyUI) 集成**：AI 动画生成
- **风格轮换**：`vf_master_loop v3.0` 无限循环合成 + 自动风格切换
- **视频工厂实际产出 MP4**：E01_full 33秒 1280×720
- **Phase B 自动发布**：social-auto-upload 推小红书/抖音，未安装时优雅降级
- **Phase D 合成管线修复**

### 5️⃣ 前端 UX 修复
- 空态提示（空白状态展示）
- Review 版本对比功能
- 导航高亮
- 页面标题差异化

### 6️⃣ 极简重构
- 代码精简 **-49%**
- 技术债务清理：删除 `video_factory_loop` 旧脚本 + Windows 路径修复 + 旧引用清理
- `VidGenMixin` 提取合并 Seedance/Kling，路径硬编码修复，`NAME_MAP` 去重

### 7️⃣ 基础设施
- **CI/CD**：新增 CI workflow + issue templates
- **每日升级检测**：auto CI + dep check 工作流
- **README 增强**：Mermaid 架构图 + 演示截图 + 安装指南 + 640测试徽章

---

## 📜 完整 Commit 日志

```
5b2c15b docs: 增强 README — Mermaid 架构图+演示截图+安装指南+640测试徽章
89f58ad P1代码审查修复: 提取VidGenMixin合并Seedance/Kling+路径硬编码修复+NAME_MAP去重
98c832c 技术债务清理: 删video_factory_loop旧脚本+修global.yaml Windows路径+更新旧main.py引用
ce66cdd fix(video-factory): repair Phase D synthesis pipeline
ae690fc 视频工厂实际产出MP4: E01_full 33秒 1280×720 + Provider配置微调
a62bb16 Phase B自动发布: social-auto-upload推小红书/抖音,未安装优雅降级
1e05a4d Kling AI视频Provider: 快手可灵接入, text2video+image2video+JWT认证
a3db42e 前端UX修复: 空态提示+Review版本对比+导航高亮+页面标题差异化(正确目录)
ae892a5 前端UX修复: 空态提示+Review版本对比+导航高亮+页面标题差异化
01d38e7 Seedance 2.0视频集成: 云端生图→视频替换FFmpeg拼接,无key自动降级
2e74711 vf_master_loop v3.0: 视频合成无限循环+风格轮换+FFmpeg管线
625bc58 云端优先+本地备用: openai不可用时自动切local_comfyui/piper
889ea9c 默认云端: openai_image + seedance + openai_tts via JieYou(GPT-5.5)
af9caca 默认切换到云端模型: openai_image + seedance + openai_tts
0eb07ad v0.2.0: 极简重构+角色系统+供应商层+分镜管理+640测试
91d5ca5 Add daily upgrade workflow (auto CI + dep check)
49f4b9a Add CI workflow + issue templates for open source
```

---

## 🔧 如何创建正式 GitHub Release

gh CLI 未在本地认证，无法通过 API 创建 Release。要手动创建：

### 方式一：Web UI
1. 访问 https://github.com/chfr19820610-cell/AIComics/releases
2. 点击 "Draft a new release"
3. Tag: `v0.2.0`（已有标签）
4. 将本文内容粘贴到 Release notes 中
5. 点击 "Publish release"

### 方式二：认证 gh CLI 后运行
```bash
gh auth login
gh release create v0.2.0 \
  --title "AIComics v0.2.0 — AI 漫剧自动生成系统" \
  --notes-file release_notes_v020.md
```

---

## ✅ 验证

- ✅ 测试: 640/640 全绿
- ✅ 代码精简: -49%
- ✅ 标签 v0.2.0: 已推送至远程
