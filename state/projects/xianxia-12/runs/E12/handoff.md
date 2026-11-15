# 交接卡 — E12

> SOP §7 文件总线：本集所有产物的入口。

## 集信息

| 项 | 值 |
|---|---|
| 集号 | E12 |
| 幕 | 第四幕 真相 |
| 镜数 | 6 |
| 总时长 | 42.0s |
| 情绪曲线 | 碾压→震撼 |

## 产物位置

| 类型 | 路径 |
|---|---|
| 分镜表 | `shots/E12.json` |
| 剧本 | `scripts/E12.json` |
| 路由 | `routes/E12.json` |
| 镜视频 | `runs/E12/shots/_link/` |
| 关键帧 | `runs/E12/images/_link/` |
| 配音 | `runs/E12/audio/_link/` |
| 字幕 | `runs/E12/cut/_link_subs/` |
| 成片 | `runs/E12/cut/final.mp4` |

## 验收状态

| Gate | 状态 |
|---|---|
| G1 剧本 | ✅ PASS |
| G2 资产 | ✅ PASS |
| G3 分镜 | ✅ PASS |
| G4 生成 | ✅ PASS |
| G5 音频 | ✅ PASS |
| G6 导出 | ✅ PASS |
| G7 合规 | ⚠️ CONDITIONAL（备案号待填） |

## 已知问题
- **CCV R2**: 台词已按剧本医生建议修改（详见 `reviews/ccv_r2/E12_r2.json`）
- **成片版本**: `final_r2.mp4`（旧版备份 `assets/_backup_r1/`）

- R7 备案号未填（如平台要求）
- **CCV 判决：CONCERNS**（详见 `reviews/ccv/E12_review.json`）
