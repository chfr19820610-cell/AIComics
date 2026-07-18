# Deploy 目录说明

更新时间：`2026-05-20 00:20:00 +0800`

本目录保存部署辅助文件和 Secret 模板，不是当前试用阶段的唯一部署入口。

## 当前推荐部署顺序

1. 先使用 `scripts/manage_local_web_stack.sh` 启动固定 Web 环境
2. 先给真实用户试用 Creator 主链
3. 再评估是否进入 Docker / 公网 / 安装包阶段

详细方案见：

- [docs/部署方案.md](/Users/chenfengrui/Desktop/AIComics/10_System/docs/部署方案.md)

## 当前文件说明

- `aicomic-production-config.secret.example.yaml`：生产 Secret 模板
- `aicomic-production-config.secret.local.yaml`：本机导出的本地 Secret 文件

## 当前注意事项

- 当前项目的试用主链以 Web 部署为主，不建议优先投入安装包分发
- 如果后续进入 Kubernetes 或统一 Secret 管理，可继续复用本目录文件
