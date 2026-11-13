# Phase G 实现计划：文件总线 / 任务契约 / 投流编号 / 废片截帧

日期：2026-10-18 · 来源：SOP 全文深度排查未落面条文 §7.1、§6.3、§11、§4⑤。

## 范围

1. **G1 文件总线骨架**（§7.1+§7.2）
   - `core/bus_layout.py`：`ensure_series_layout(series_dir)` 担保骨架（specs/assets/shots/route/runs/E01/shots/E01S01/{keyframes,clips,salvage}/audio/cut/compliance.json/handoff.md）；`validate_series_layout(series_dir, episode) -> {ok, missing[], present[]}`——gate「文件存在」的可执行命令底座（SSOT 原则：不生成内容只验坐标）
2. **G2 任务级交接契约**（§6.3，机器可读）
   - `core/task_contract.py`：`build_task_contract(...)` + `validate_task_contract(dict) -> {ok, violations[]}`；必填：from/to/artifact/payload{shot_id,duration_s,refs,style_tokens,motion_prompt,budget{max_roll,model_route}}/acceptance[]/failure_policy；duration_s>8s 违红线（§4④ 一镜一动作）
3. **G3 投流编号**（§11）
   - `publish/ad_code.py`：`build_ad_code(series, character, selling_point, version, channel, date, auditor) -> str`（`剧名-角色-卖点-版本-渠道-YYYYMMDD-审核人`，段空/带 `-`/日期非法 → 拒绝可回溯红线）；`attach_to_compliance(pack, ad_code) -> dict`（compliance.json 联接）
4. **G4 废片截帧 salvage**（§4⑤）
   - `video_synthesis/salvage.py`：`salvage_frames(video, out_dir, *, count=3) -> {saved: [Path]}`——ffmpeg 均匀抽帧入库 `runs/.../salvage/`；文件缺失/ffmpeg 失败 → 结构化 error 不假绿；`_run_ffmpeg` seam 沿 ai_label 族
5. **G5 收尾**：变异×2（contract 恒过 / 编号劈段失明）红过即还原；全套 pytest（≥1464+新量）+ pyflakes 零告警；真机 ffmpeg 截帧抽验

## 纪律（沿用 Phase B–F 七红线）
红→绿分记；无新依赖；CLI 不新增（库层完成，供后续 orchestrator 调用）；docs/superpowers 保持 untracked；不 push。

## 执行进度

✅ 全部完成（untracked）：G5 真机 salvage 复盘——select/nb_frames 表达式在 lavfi mp4 rc=234 → 换 fps 滤镜 4/4 帧全好、尺寸 >512B；probe seam 全族统一（'ffprobe 不可得' 结构化中止）。变异×2 红过还原（契约恒过 3 红 / 编号劈段失明 1 红）。全套 1481+1 / pyflakes 零告警。
