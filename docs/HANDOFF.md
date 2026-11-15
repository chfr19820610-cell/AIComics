# xianxia-12 P6 无人值守交接文档

> 写于 2026-11-16 02:02
> 原因：840 镜需要 161 小时（6.7 天），远超单次会话能覆盖的时长。
> 本文档确保：**即使小h 的会话结束，峰哥也能自己接管。**

---

## 一、当前在跑什么

| 组件 | PID（会变） | 作用 |
|---|---|---|
| P6 批量 | `pgrep -f batch_p6_align` | 串行生成 840 镜 |
| 监控 | `pgrep -f watch_840` | 每 5 分钟自检，卡住/崩溃自动重启 |
| h3stream | `pgrep -f "h3stream generate"` | 实际生成的模型进程 |

**它们都在后台用 nohup 跑，不依赖小h 的会话。**

---

## 二、怎么看进度

### 最快（一行）
```bash
cd /Users/eric/Desktop/hermes/AlComics
echo "$(ls state/projects/xianxia-12/assets/E*/h3video/*.mp4 2>/dev/null | wc -l | tr -d ' ')/840"
```

### 看监控日志（实时）
```bash
tail -f state/projects/xianxia-12/logs/watch.log
```

### 看单集进度
```bash
for ep in E01 E02 E03 E04 E05 E06 E07 E08 E09 E10 E11 E12; do
  n=$(ls state/projects/xianxia-12/assets/$ep/h3video/*.mp4 2>/dev/null | wc -l | tr -d ' ')
  echo "$ep: $n/70"
done
```

---

## 三、出问题时怎么办

### 情况 1：进度停了（几分钟没涨）

```bash
# 查进程
pgrep -f batch_p6_align || echo "批量死了"
pgrep -f watch_840 || echo "监控死了"
pgrep -f "h3stream generate" || echo "h3stream 死了"
```

**修复**：
```bash
# 重启监控（它会自动重启批量）
pkill -f watch_840
nohup .venv/bin/python scripts/watch_840.py >> /tmp/p6_watch.log 2>&1 &
```

### 情况 2：某镜反复失败

```bash
# 检查缺失
.venv/bin/python scripts/fill_gaps.py
# 补跑
.venv/bin/python scripts/fill_gaps.py --run
```

### 情况 3：想跳过某集

编辑 `/tmp/batch_p6_align.sh`，把 `for ep in E01 ... E12` 改成不含那集。

### 情况 4：磁盘满了

```bash
# 清理已完成的 checkpoint（视频已生成，checkpoint 无用）
cd /Users/eric/Desktop/hermes/tools/minimax-h3-stream-mac/runs
# 只保留正在跑的
```

### 情况 5：彻底重来

```bash
# 停所有
pkill -f batch_p6_align; pkill -f watch_840; pkill -f "h3stream generate"
# 重启（会跳过已生成的镜，从断点继续）
nohup bash /tmp/batch_p6_align.sh > /tmp/p6_restart.log 2>&1 &
nohup .venv/bin/python scripts/watch_840.py >> /tmp/p6_watch.log 2>&1 &
```

---

## 四、关键规则（违反会出问题）

1. **禁止并行跑两个 h3stream**
   - 会互相拖慢一倍（实测 69s/step → 137s/step）
   - 瓶颈是模型权重读取带宽

2. **重启 h3stream 必须用 `kill`（SIGTERM），不要 `kill -9`**
   - `kill -9` 破坏 checkpoint → 从头跑
   - `kill` 能续传（实测省 3.5 分钟）

3. **不要改正在跑的 `/tmp/batch_p6_align.sh`**
   - bash 已读入内存，改了不生效
   - 要改就改 `scripts/batch_p6_align.sh`，然后重启

4. **E01 跑完后先验收再继续**
   - 见 `docs/E01_ACCEPTANCE.md`

---

## 五、每集完成时会自动发生什么

```
70 镜跑完
   ↓
fill_gaps.py --ep EXX --run（补漏）
   ↓
rebuild_episode.py EXX（TTS+SRT+烧录+混音）
   ↓
cp runs/EXX/cut/final_r2.mp4 assets/EXX/EXX_H3_REAL.mp4
```

**成片位置**：`state/projects/xianxia-12/assets/EXX/EXX_H3_REAL.mp4`

---

## 六、时间预估

| 项 | 值 |
|---|---|
| 单镜 | 11-12 分钟（frames=73） |
| 单集 | 约 13 小时（70 镜） |
| 全季 | **约 161 小时（6.7 天）** |
| 当前进度 | 11/840（截至 02:02） |
| 预计完成 | 2026-11-22 前后 |

---

## 七、已修的问题（不要再踩）

| # | 问题 | 修复 |
|---|---|---|
| 1 | /tmp 硬编码 | 移到项目内 |
| 2 | 监控无异常兜底 | try/except |
| 3 | int() 截断丢尾音 | +1 |
| 4 | E11 台词 5 句 | 扩到 16 句 |
| 5 | 台词占比 94% | ≤85% 约束 |
| 6 | 失败镜无重试 | 3 次重试 |
| 7 | 合成前无补漏 | fill_gaps |
| 8 | kill -9 破坏 checkpoint | SIGTERM |

---

## 八、关键文件索引

| 文件 | 用途 |
|---|---|
| `docs/AI漫剧多Agent工业化SOP.md` | 完整方法论（804 行，不入 git） |
| `docs/SOP_CHANGELOG.md` | SOP 变更日志（入 git） |
| `docs/P6_DELIVERY.md` | 交付说明 |
| `docs/P6_MEASUREMENTS.md` | 实测数据 |
| `docs/E01_ACCEPTANCE.md` | E01 验收清单 |
| `docs/DIALOGUE_AUDIT.md` | 台词密度审计 |
| `scripts/batch_p6_align.sh` | 批量生成脚本 |
| `scripts/watch_840.py` | 监控自愈 |
| `scripts/fill_gaps.py` | 补漏 |
| `scripts/rebuild_episode.py` | 单集合成 |
| `scripts/accept_12ep.py` | 12 集验收 |

---

## 2026-11-16 03:17 · E01/S16 重跑记录

### 背景
E01/S16 是唯一"口型保护失效"的已生成镜：
- 原 shot_type: extreme_closeup（特写）
- 有台词："赵乾：废物的手，也只配擦地。"
- 生成为 extreme_closeup（应该降级为 medium）
- 原因：prompt 里写死 "Extreme close-up"，align_episode 的降级没传播到 prompt（SOP §20）

### 处理
1. 备份原视频：`assets/_backup_s16/E01_S16_h3.mp4`（178K）
2. 删除 `assets/E01/h3video/E01_S16_h3.mp4`
3. prompt 已修正为 `Medium shot of Zhao Qian's fingers squeezing Lin Zhao's chin...`

### 自动重跑机制
E01 剩余 53 镜跑完后（约 10 小时后），P6 脚本会：
1. `fill_gaps.py --ep E01 --run` 检测到 S16 缺失
2. 用新 prompt（Medium shot）重跑 S16（12 分钟）
3. `rebuild_episode.py` 合成 70 镜

**无需人工干预。**

### 如果 fill_gaps 失败
手动重跑：
```bash
cd /Users/eric/Desktop/hermes/AlComics
.venv/bin/python scripts/fill_gaps.py --ep E01 --run
```

### 或恢复原视频（如果不接受重跑）
```bash
cp state/projects/xianxia-12/assets/_backup_s16/E01_S16_h3.mp4 \
   state/projects/xianxia-12/assets/E01/h3video/
```
