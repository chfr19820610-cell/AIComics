#!/usr/bin/env python3
"""
E04 青云入门 — 旁白版视频生产管线
复用 source_frames/S1-S14+T1 作为视觉素材
使用 E04 旁白/字幕 via edge-tts + ffmpeg Ken Burns + drawtext
"""
import os, sys, subprocess, shutil, textwrap, time, json
from pathlib import Path
from datetime import datetime

# === Config ===
DONGHUA_DIR = Path("/Users/eric/Desktop/hermes/AlComics/10_System/state/produced_videos/donghua")
SOURCE_FRAMES = DONGHUA_DIR / "source_frames"
EP_WORK = DONGHUA_DIR / "episodes" / "E04_work"
FRAMES_DIR = EP_WORK / "frames"
AUDIO_DIR = EP_WORK / "audio"
SEGS_DIR = EP_WORK / "segments"
OUTPUT_DIR = Path("/Users/eric/Desktop/hermes/AlComics/episodes")

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
EDGE_TTS = shutil.which("edge-tts") or os.path.expanduser("~/.hermes/hermes-agent/venv/bin/edge-tts")
VOICE = "zh-CN-XiaoxiaoNeural"
FONT = "/System/Library/Fonts/Hiragino Sans GB.ttc"

W, H, FPS = 1080, 1920, 24

# E04 shots: (shot_id, frame_source, duration_sec, narration, motion)
# motion: still, gentle_float, zoom, pan
# Frame mapping: reuse E01 frames as placeholders for E04 scenes
SHOTS = [
    ("S1", "S1.png", 5,
     "白鹤真人在丹霞峰大殿正式收林霄为亲传弟子。这是青云宗百年来第一位无灵根的亲传弟子。",
     "still"),
    ("S2", "S2.png", 6,
     "白鹤真人没有教林霄普通的引气法门。他给了林霄一本——九转炼体诀。",
     "still"),
    ("S3", "S3.png", 4,
     "苏月对这位新来的师弟并不欢迎。在她看来，一个连灵根都没有的人，根本不配做白鹤真人的弟子。",
     "still"),
    ("S4", "S4.png", 6,
     "苏月奉师命教林霄基本功，但她的耐心显然非常有限。",
     "gentle_float"),
    ("S5", "S5.png", 5,
     "林霄什么也没说。白天训练结束后，他在月光下继续练。一遍不够，就一百遍。",
     "zoom"),
    ("S6", "S6.png", 4,
     "柱廊的阴影中，苏月默默地看了很久。她第一次觉得，这个师弟好像不太一样。",
     "still"),
    ("S7", "S7.png", 5,
     "第七天，林霄在瀑布下练功时，他终于感觉到了——那一丝若有若无的热流。那是灵气。",
     "zoom"),
    ("S8", "S8.png", 4,
     "林霄兴冲冲地跑回来，却看到苏月练剑的画面——那凌厉的剑意，让他意识到自己和她之间的差距有多大。",
     "still"),
    ("S9", "S9.png", 5,
     "苏月没有回头，但林霄听出了她语气中那一丝微不可察的认可。",
     "still"),
    ("S10", "S10.png", 5,
     "这天，一个铁塔般的壮汉闯入了丹霞峰——姜铁山，体修一脉的外门弟子，青云宗最不怕事的人。",
     "still"),
    ("S11", "S11.png", 5,
     "姜铁山自来熟地揽住了林霄的肩膀。这是林霄在青云宗的第一个朋友。",
     "gentle_float"),
    ("S12", "S12.png", 5,
     "那晚三人坐在山崖边喝酒，姜铁山讲着他在铸剑谷的糗事，苏月破天荒地没有打断。林霄第一次觉得——这里，也许是他的家了。",
     "still"),
    ("S13", "S13.png", 4,
     "白鹤真人看着他们的身影，低声自语：混沌灵根……天庭那边，应该也快察觉到了吧。",
     "still"),
    ("S14", "S14.png", 5,
     "林霄看着熟睡的同伴，在心中默默立下誓言——他要变强，不是为了证明什么，而是为了守护这些愿意接纳他的人。",
     "pan"),
    ("T1a", "T1.png", 3,
     "一个月后，林霄主动要求去铸剑谷淬体。九转炼体诀的下一阶段，需要在烈火和铁锤中完成。",
     "still"),
    ("T1b", "S11.png", 3,
     "打铁声中日复一日，林霄的炼体之路才刚刚开始。",
     "zoom"),
]

def run(cmd, timeout=120):
    """Run command, return (success, output)."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, r.stderr[-500:] if r.stderr else ""
    except Exception as e:
        return False, str(e)

def get_audio_duration(path):
    cmd = [FFMPEG, "-i", str(path), "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    for line in r.stderr.split("\n"):
        if "Duration" in line:
            try:
                p = line.split("Duration: ")[1].split(",")[0].split(":")
                return float(p[0])*3600 + float(p[1])*60 + float(p[2])
            except:
                pass
    return 0

def gen_tts(text, out_path):
    """Generate TTS audio with edge-tts."""
    txt_file = str(out_path) + ".txt"
    Path(txt_file).write_text(text, encoding="utf-8")
    ok, err = run([
        EDGE_TTS, "--voice", VOICE, "-f", txt_file,
        "--write-media", str(out_path)
    ], timeout=60)
    Path(txt_file).unlink(missing_ok=True)
    return out_path.exists() and out_path.stat().st_size > 100

def make_ken_burns(img_path, duration, out_path, motion="still"):
    """Create Ken Burns video segment from static image."""
    frames = max(int(duration * FPS), 1)

    if motion == "zoom":
        vf = (f"zoompan=z='min(zoom+0.0015,1.05)':d={frames}:"
              f"s={W}x{H}:fps={FPS},format=yuv420p")
    elif motion == "gentle_float":
        vf = (f"zoompan=z='1.02+0.005*sin(on/{FPS})':d={frames}:"
              f"x='iw/2-(iw/zoom/2)+5*sin(on/{FPS})':"
              f"y='ih/2-(ih/zoom/2)+3*cos(on/{FPS})':"
              f"s={W}x{H}:fps={FPS},format=yuv420p")
    elif motion == "pan":
        vf = (f"zoompan=z=1.03:d={frames}:"
              f"x='iw/2-(iw/zoom/2)+((iw-iw/zoom)/{frames})*on':"
              f"y='ih/2-(ih/zoom/2)':"
              f"s={W}x{H}:fps={FPS},format=yuv420p")
    else:  # still
        vf = (f"scale={W*2}:{H*2}:flags=lanczos,"
              f"crop={W*2}:{H*2},"
              f"scale={W}:{H}:flags=lanczos,format=yuv420p")

    cmd = [FFMPEG, "-y", "-loop", "1", "-i", str(img_path),
           "-vf", vf, "-c:v", "libx264", "-preset", "fast",
           "-crf", "20", "-t", str(duration), "-pix_fmt", "yuv420p",
           str(out_path)]
    ok, err = run(cmd, timeout=120)
    return out_path.exists() and out_path.stat().st_size > 1000, err

def wrap_text(text, width=16):
    """Wrap Chinese text for subtitles."""
    lines = []
    current = ""
    for ch in text:
        current += ch
        if len(current) >= width:
            lines.append(current)
            current = ""
    if current:
        lines.append(current)
    return lines[:2]  # Max 2 lines

def burn_subtitle(video_path, audio_path, subtitle_text, out_path):
    """Burn subtitle + audio into video segment."""
    lines = wrap_text(subtitle_text, 16)
    # Escape special chars for drawtext
    def escape(t):
        return (t.replace("\\", "\\\\").replace(":", "\\:")
                .replace("'", "\\'").replace("%", "\\%"))

    drawtexts = []
    for i, line in enumerate(lines):
        y_pos = f"h-text_h-{160 - i*50}"  # Bottom area, 2 lines
        dt = (f"drawtext=fontfile='{FONT}':text='{escape(line)}':"
              f"fontsize=44:fontcolor=white:borderw=3:bordercolor=black@0.7:"
              f"x=(w-text_w)/2:y={y_pos}")
        drawtexts.append(dt)

    vf = ",".join(drawtexts)

    cmd = [FFMPEG, "-y", "-i", str(video_path)]
    has_audio = audio_path and Path(audio_path).exists()
    if has_audio:
        cmd.extend(["-i", str(audio_path)])

    cmd.extend(["-vf", vf, "-c:v", "libx264", "-preset", "fast", "-crf", "20"])

    if has_audio:
        cmd.extend(["-c:a", "aac", "-b:a", "96k", "-shortest",
                     "-map", "0:v:0", "-map", "1:a:0"])
    else:
        cmd.append("-an")

    cmd.extend(["-pix_fmt", "yuv420p", str(out_path)])
    ok, err = run(cmd, timeout=120)
    return out_path.exists() and out_path.stat().st_size > 1000, err

def gen_bgm(duration, out_path):
    """Generate simple ambient BGM."""
    cmd = [FFMPEG, "-y", "-f", "lavfi",
           "-i", f"aevalsrc=sin(130.81*t)*0.25+sin(196.00*t)*0.15+sin(261.63*t)*0.1:d={duration}:c=stereo",
           "-af", "volume=0.12,lowpass=f=800",
           "-c:a", "aac", "-b:a", "64k", str(out_path)]
    ok, err = run(cmd, timeout=30)
    return out_path.exists()

def main():
    start = time.time()
    print("=" * 60)
    print("🎬 E04 青云入门 — 旁白版视频生产管线")
    print("=" * 60)

    # Setup dirs
    for d in [FRAMES_DIR, AUDIO_DIR, SEGS_DIR, OUTPUT_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    # Verify source frames exist
    print("\n📋 Phase 0: 检查源帧...")
    for sid, frame, dur, nar, motion in SHOTS:
        fp = SOURCE_FRAMES / frame
        if not fp.exists():
            print(f"  ❌ 源帧缺失: {frame}")
            sys.exit(1)
    print(f"  ✅ {len(SHOTS)} 个镜头源帧就绪")

    # Phase 1: TTS
    print("\n📢 Phase 1: 生成旁白 (edge-tts)...")
    narration_audio = {}
    total_narration_dur = 0
    for sid, frame, dur, nar, motion in SHOTS:
        audio_path = AUDIO_DIR / f"{sid}.mp3"
        if gen_tts(nar, audio_path):
            adur = get_audio_duration(audio_path)
            narration_audio[sid] = (audio_path, adur)
            total_narration_dur += adur
            print(f"  ✅ {sid}: {adur:.1f}s — {nar[:25]}...")
        else:
            print(f"  ❌ {sid}: TTS失败")
            narration_audio[sid] = (None, dur)
    print(f"  📊 总旁白时长: {total_narration_dur:.1f}s")

    # Phase 2: Ken Burns video segments
    print("\n🎥 Phase 2: 渲染Ken Burns视频片段...")
    raw_segs = []
    for sid, frame, dur, nar, motion in SHOTS:
        # Use actual narration duration if available (min 3s)
        actual_dur = max(narration_audio.get(sid, (None, dur))[1], 3.0)
        actual_dur = max(actual_dur, dur * 0.8)  # At least 80% of planned

        img_path = SOURCE_FRAMES / frame
        raw_path = SEGS_DIR / f"{sid}_raw.mp4"
        ok, err = make_ken_burns(img_path, actual_dur, raw_path, motion)
        if ok:
            raw_segs.append((sid, raw_path, actual_dur))
            print(f"  ✅ {sid}: {actual_dur:.1f}s [{motion}]")
        else:
            print(f"  ❌ {sid}: {err[:100]}")
            # Fallback: simple still
            ok2, err2 = make_ken_burns(img_path, actual_dur, raw_path, "still")
            if ok2:
                raw_segs.append((sid, raw_path, actual_dur))
                print(f"  ✅ {sid}: {actual_dur:.1f}s [still fallback]")

    # Phase 3: Burn subtitles + add audio
    print("\n📝 Phase 3: 烧录字幕 + 合并音频...")
    final_segs = []
    for sid, raw_path, dur in raw_segs:
        nar_text = next(s[3] for s in SHOTS if s[0] == sid)
        audio_path = narration_audio.get(sid, (None, 0))[0]
        final_path = SEGS_DIR / f"{sid}_final.mp4"
        ok, err = burn_subtitle(raw_path, audio_path, nar_text, final_path)
        if ok:
            final_segs.append(final_path)
            print(f"  ✅ {sid}")
        else:
            print(f"  ❌ {sid}: {err[:100]}")
            # Fallback: copy raw without subtitle
            shutil.copy2(raw_path, final_path)
            final_segs.append(final_path)

    # Phase 4: Concatenate all segments
    print("\n🔗 Phase 4: 合并视频片段...")
    concat_file = SEGS_DIR / "concat.txt"
    with open(concat_file, "w") as f:
        for seg in final_segs:
            f.write(f"file '{seg}'\n")

    merged_video = SEGS_DIR / "merged.mp4"
    # Use re-encode for safety
    ok, err = run([FFMPEG, "-y", "-f", "concat", "-safe", "0",
                    "-i", str(concat_file),
                    "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                    "-pix_fmt", "yuv420p", "-r", str(FPS),
                    str(merged_video)], timeout=300)
    concat_file.unlink(missing_ok=True)
    if not ok or not merged_video.exists():
        print(f"  ❌ 合并失败: {err[:200]}")
        sys.exit(1)

    merged_dur = get_audio_duration(merged_video)
    merged_size = merged_video.stat().st_size / (1024*1024)
    print(f"  ✅ 合并完成: {merged_dur:.1f}s, {merged_size:.1f}MB")

    # Phase 5: Generate BGM and mix audio
    print("\n🎵 Phase 5: 生成BGM + 混合音频...")
    # The merged video already has narration audio from segments
    # Extract existing audio (narration)
    narration_track = AUDIO_DIR / "narration_only.m4a"
    ok_ext, err_ext = run([FFMPEG, "-y", "-i", str(merged_video), "-vn",
         "-c:a", "aac", "-b:a", "96k", str(narration_track)], timeout=30)

    if not ok_ext or not narration_track.exists():
        print(f"  ⚠️ 无法提取音频，视频可能无音轨: {err_ext[:100]}")
        # Fallback: concat all narration MP3s
        concat_audio = AUDIO_DIR / "concat_nar.txt"
        with open(concat_audio, "w") as f:
            for sid, frame, dur, nar, motion in SHOTS:
                ap = narration_audio.get(sid, (None, 0))[0]
                if ap and Path(ap).exists():
                    f.write(f"file '{ap}'\n")
        run([FFMPEG, "-y", "-f", "concat", "-safe", "0",
             "-i", str(concat_audio), "-c:a", "aac", "-b:a", "96k",
             str(narration_track)], timeout=30)
        concat_audio.unlink(missing_ok=True)

    if not narration_track.exists():
        print("  ❌ 无音频可用，输出无音频视频")
        final_output = OUTPUT_DIR / "E04_九转丹霄_第4集_旁白版.mp4"
        shutil.copy2(merged_video, final_output)
        return

    final_output = OUTPUT_DIR / "E04_九转丹霄_第4集_旁白版.mp4"

    # Generate BGM
    bgm_path = AUDIO_DIR / "bgm.m4a"
    gen_bgm(merged_dur + 2, bgm_path)

    # Mix narration + BGM
    mixed_audio = AUDIO_DIR / "mixed_audio.m4a"
    if narration_track.exists() and bgm_path.exists():
        ok, err = run([FFMPEG, "-y",
                        "-i", str(narration_track),
                        "-i", str(bgm_path),
                        "-filter_complex",
                        "[1:a]volume=0.08[bgm];[0:a][bgm]amix=inputs=2:duration=first[aout]",
                        "-map", "[aout]", "-c:a", "aac", "-b:a", "96k",
                        str(mixed_audio)], timeout=60)
        if not ok or not mixed_audio.exists():
            print(f"  ⚠️ 混音失败，使用纯旁白: {err[:100]}")
            shutil.copy2(narration_track, mixed_audio)
    else:
        shutil.copy2(narration_track, mixed_audio)
    print(f"  ✅ 音频混合完成")

    # Phase 6: Final encode
    print("\n📦 Phase 6: 最终封装...")
    ok, err = run([FFMPEG, "-y", "-i", str(merged_video), "-i", str(mixed_audio),
                    "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                    "-c:a", "aac", "-b:a", "96k",
                    "-shortest", "-movflags", "+faststart",
                    "-pix_fmt", "yuv420p",
                    str(final_output)], timeout=300)

    if not ok or not final_output.exists():
        print(f"  ❌ 最终封装失败: {err[:200]}")
        sys.exit(1)

    # Verify
    final_dur = get_audio_duration(final_output)
    final_size = final_output.stat().st_size / (1024*1024)
    # Get resolution
    r = subprocess.run([FFMPEG, "-i", str(final_output), "-f", "null", "-"],
                       capture_output=True, text=True, timeout=10)
    res_line = ""
    for line in r.stderr.split("\n"):
        if "Video:" in line and "h264" in line:
            res_line = line
            break

    elapsed = time.time() - start
    print(f"""
╔══════════════════════════════════════════════╗
║  ✅ E04 视频生成完成！                        ║
╠══════════════════════════════════════════════╣
║  标题: 青云入门 (第4集)
║  路径: {final_output}
║  时长: {final_dur:.1f}s
║  大小: {final_size:.1f}MB
║  镜头: {len(SHOTS)} 个
║  编码: H.264/AAC
║  分辨率: {W}x{H} 竖屏
║  耗时: {elapsed/60:.1f} 分钟
╚══════════════════════════════════════════════╝
""")

if __name__ == "__main__":
    main()
