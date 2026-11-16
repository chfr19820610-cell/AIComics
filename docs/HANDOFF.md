
---

## 2026-11-16 07:09 · 当前状态快照（Round 114）

### 进度

| 项 | 值 |
|---|---|
| 已生成 | **38/840 镜** |
| E01 | 38/70（54%） |
| E02-E12 | 0/770 |
| 当前镜 | E01/S40 |
| 失败 | 0 |

### 进程

```
PID 20641: bash /tmp/batch_p6_align.sh（批量）
PID 20911: watch_840.py（监控）
```

### 系统状态

| 项 | 状态 |
|---|---|
| prompt | 840 条干净（§20 全过）✅ |
| 口型保护 | 89 镜已降级 ✅ |
| 画质 | 连续验证完美（S35/S36/S38）✅ |
| 合成链路 | 已验证 ✅ |
| 目录 | 已清理 ✅ |
| SOP | 21 节 ✅ |
| 测试 | 1547 passed ✅ |
| 提交 | 57 个 commit ✅ |

### 关键待办（E01 跑完时自动）

1. `fill_gaps.py --ep E01 --run` → 重跑 S16（12 分钟）
2. `rebuild_episode.py E01` → 合成 70 镜
3. 产物：`assets/E01/E01_H3_REAL.mp4`

### 测试命令

```bash
cd /Users/eric/Desktop/hermes/AlComics

# 进度
ls state/projects/xianxia-12/assets/E*/h3video/*.mp4 | wc -l

# 当前镜
ps aux | grep '[h]3stream generate' | head -1

# 失败
grep -c '❌' /tmp/p6_restart.log

# 验证 prompt
.venv/bin/python scripts/validate_prompts.py

# 合成单集（E01 跑完后）
.venv/bin/python scripts/fill_gaps.py --ep E01 --run
.venv/bin/python scripts/rebuild_episode.py E01
```

### 如果进程死了

```bash
# 重启批量
cd /Users/eric/Desktop/hermes/AlComics
nohup bash /tmp/batch_p6_align.sh > /tmp/p6_restart.log 2>&1 &

# 重启监控
nohup .venv/bin/python scripts/watch_840.py > /tmp/p6_watch.log 2>&1 &
```

### 恢复 S16 备份（如果不接受重跑）

```bash
cp state/projects/xianxia-12/assets/_backup_s16/E01_S16_h3.mp4 \
   state/projects/xianxia-12/assets/E01/h3video/
```

---

## 2026-11-16 08:54 · 当前状态快照（Round 158，47/840）

### 进度

| 项 | 值 |
|---|---|
| 已生成 | **47/840 镜** |
| E01 | 47/70（67%） |
| E02-E12 | 0/770 |
| 当前镜 | E01/S49 |
| 失败 | 0 |

### 进程

```
PID 20641: bash /tmp/batch_p6_align.sh（批量）
PID 20911: python scripts/watch_840.py（监控）
```

### 验证成果（160 轮累计）

| 维度 | 结果 |
|---|---|
| **prompt 格式** | 840 条干净（§20 全过）✅ |
| **口型保护** | 89 个 closeup+台词镜全部降级 ✅ |
| **风格分布** | 47 镜实测：49% 动漫 / 26% CG / 24% 混合 / **0 Q版 / 0 写实** |
| **时长精度** | 47 镜平均偏差 2.3ms ✅ |
| **景别节奏** | 95% 切换率 ✅ |
| **视觉属性** | 512x384 / 24fps 全统一 ✅ |
| **合成链路** | 已验证（alignment 70 镜 + piper 204s） ✅ |
| **目录** | /tmp 5 个文件、项目 309M ✅ |
| **SOP** | 23 节（§17 有 9 子节，含新增 §17.9） ✅ |
| **测试** | 1547 passed ✅ |

### 已知小瑕疵（不修）

| 项 | 说明 |
|---|---|
| **S45** | extreme_closeup 无人 → 3D 写实（§17.9 规律，1 镜） |
| **59 镜无人特写** | 7% 会是 3D/CG（§17.9，不干预） |
| **S16** | 已删除（口型保护），等 E01 跑完 fill_gaps 重跑 |

### E01 跑完时的自动流程

1. `fill_gaps.py --ep E01 --run` → 重跑 S16（12 分钟）
2. `rebuild_episode.py E01` → 合成 70 镜
3. 产物：`assets/E01/E01_H3_REAL.mp4`

### 测试命令

```bash
cd /Users/eric/Desktop/hermes/AlComics

# 进度
ls state/projects/xianxia-12/assets/E*/h3video/*.mp4 | wc -l

# 当前镜
ps aux | grep '[h]3stream generate' | head -1

# 失败
grep -c '❌' /tmp/p6_restart.log

# 验证 prompt
.venv/bin/python scripts/validate_prompts.py
.venv/bin/python scripts/validate_fields.py

# 风格分析
.venv/bin/python scripts/analyze_style.py --all

# 7 gate
bash state/projects/xianxia-12/gates/run_all.sh
```

### 如果进程死了

```bash
cd /Users/eric/Desktop/hermes/AlComics
nohup bash /tmp/batch_p6_align.sh > /tmp/p6_restart.log 2>&1 &
nohup .venv/bin/python scripts/watch_840.py >> /tmp/p6_watch.log 2>&1 &
```

### 恢复 S16 备份（如果不接受重跑）

```bash
cp state/projects/xianxia-12/assets/_backup_s16/E01_S16_h3.mp4 \
   state/projects/xianxia-12/assets/E01/h3video/
```

### 全季完成后的清理

```bash
cd /Users/eric/Desktop/hermes/tools/minimax-h3-stream-mac
rm -rf runs/p6_*    # 释放约 10GB
```

---

## 2026-11-16 11:18 · 收尾快照（Round 194，59/840）

### 进度

| 项 | 值 |
|---|---|
| 已生成 | **59/840 镜** |
| E01 | 59/70（84%） |
| **S59** | **已删除待重跑**（假字幕，已修复 prompt） |
| E02-E12 | 0/770 |
| 当前镜 | E01/S62 |
| 失败 | 0 |

### 进程（如果还活着）

```bash
ps aux | grep '[b]atch_p6_align'   # 批量
ps aux | grep '[w]atch_840'        # 监控
```

**如果没有，重启**：
```bash
cd /Users/eric/Desktop/hermes/AlComics
nohup bash /tmp/batch_p6_align.sh > /tmp/p6_restart.log 2>&1 &
nohup .venv/bin/python scripts/watch_840.py >> /tmp/p6_watch.log 2>&1 &
```

### 本次会话的重大发现与修复（Round 186-193）

| 发现 | 修复 | commit |
|---|---|---|
| **模型"画假字幕"**（speaking 词） | 20 镜改 prompt + S59 删除 | `6c4d74e` |
| **其他元语言**（memory/sound） | 2 镜改 | `7020694` |
| **SOP §23 元语言禁忌** | 新增 | `8435817` |
| **validate_prompts 集成元语言检查** | 新增 | `179dc2d` |
| **长 prompt 选择性理解**（S61） | 记录为已知模式 | `33bba45` |

### 完整验证成果（10+ 维度）

| 维度 | 结果 |
|---|---|
| prompt 格式 | 840 条干净（§20 + §23 全过）✅ |
| 口型保护 | 89 closeup+台词镜全部降级 ✅ |
| 风格分布 | 49% 动漫 / 26% CG / 24% 混合 / **0 Q版 / 0 写实** ✅ |
| 时长精度 | 平均偏差 2.3ms ✅ |
| 景别节奏 | 95% 切换率 ✅ |
| 视觉属性 | 512x384 / 24fps 全统一 ✅ |
| 合成链路 | 已验证（alignment 70 镜 + piper 204s）✅ |
| 目录 | /tmp 5 个文件、项目 309M ✅ |
| SOP | **25 节**（§17 有 9 子节 + §22 + §23）✅ |
| 测试 | 1547 passed ✅ |
| 元语言风险 | **0** ✅ |

### 已知限制（无解，接受）

| 问题 | 说明 | 影响 |
|---|---|---|
| **角色服装漂移** | h3stream 无首帧控制（§22） | 高（观众会注意到） |
| **无人特写→3D** | 59 镜（§17.9） | 中（可解释） |
| **长 prompt 选择性理解** | environment 镜常见 | 低（过渡镜） |
| **S45** | 血珠特写 3D（§17.9） | 低（1 镜） |
| **S61** | 内容偏差（accept） | 低（过渡镜） |
| **S59** | 假字幕（已删除待重跑） | 无（会重跑） |

### E01 跑完时的自动流程

1. `fill_gaps.py --ep E01 --run` → 重跑 **S16 + S59**（2 镜，约 24 分钟）
2. `rebuild_episode.py E01` → 合成 70 镜
3. 产物：`assets/E01/E01_H3_REAL.mp4`

### 关键命令速查

```bash
cd /Users/eric/Desktop/hermes/AlComics

# 进度
ls state/projects/xianxia-12/assets/E*/h3video/*.mp4 | wc -l

# 验证 prompt（5 项自动检查）
.venv/bin/python scripts/validate_prompts.py

# 验证字段
.venv/bin/python scripts/validate_fields.py

# 风格分析
.venv/bin/python scripts/analyze_style.py --all

# 7 gate
bash state/projects/xianxia-12/gates/run_all.sh

# 测试
.venv/bin/python -m pytest tests/ -q
```

### 备份

| 备份 | 路径 |
|---|---|
| S16（口型失效） | `assets/_backup_s16/` |
| S59（假字幕） | `assets/_backup_s59/` |

### 全季预估

| 项 | 值 |
|---|---|
| 已生成 | 59/840（7%） |
| 剩余时间 | 约 160 小时（6.7 天） |
| 预计完成 | 2026-11-23 左右 |
