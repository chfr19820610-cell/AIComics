#!/bin/bash
#
# build_e02.sh — 合成 E02 "九转丹霄 旁白版" 竖屏视频
#
# 输入: ~/Desktop/hermes/AI漫剧发布包/packages/E02/ (6场景图片+音频)
# 输出: ~/Desktop/hermes/AlComics/episodes/E02_九转丹霄_第2集_旁白版.mp4
# 规格: 1080x1920 竖屏, H.264+AAC, 30fps, Ken Burns + xfade 转场
#

set -euo pipefail

FFMPEG="/Users/eric/.local/bin/ffmpeg"
FFPROBE="/Users/eric/.local/bin/ffprobe"

SRC_DIR="$HOME/Desktop/hermes/AI漫剧发布包/packages/E02"
OUT_DIR="$HOME/Desktop/hermes/AlComics/episodes"
OUT_FILE="$OUT_DIR/E02_九转丹霄_第2集_旁白版.mp4"
TMP_DIR="/tmp/build_e02_$$"

mkdir -p "$TMP_DIR" "$OUT_DIR"
trap "rm -rf $TMP_DIR" EXIT

echo "============================================"
echo "  E02 旁白版视频合成脚本"
echo "============================================"

# ---- 场景定义 ----
# 格式: "场景编号|图片文件|音频文件|音频时长"
# 无音频的场景音频文件为 "NONE"，时长固定5秒

declare -a SCENES=(
  "S01|E02_S01_key.png|E02_S01_tts.wav|0"
  "S02|E02_S02_key.png|E02_S02_dub.wav|0"
  "S03|E02_S03_key.png|NONE|5.0"
  "S04|E02_S04_key.png|E02_S04_tts.wav|0"
  "S05|E02_S05_key.png|E02_S05_tts.wav|0"
  "S06|E02_S06_key.png|E02_S06_tts.wav|0"
)

XFADE_DUR=0.7    # 转场时长(秒)
TOTAL_DUR=0
CLIP_FILES=()
CLIP_DURS=()

# ---- Step 1: 为每个场景生成单独的片段 ----
echo ""
echo ">>> Step 1: 生成各场景片段"

for entry in "${SCENES[@]}"; do
  IFS='|' read -r scene img_file audio_file fixed_dur <<< "$entry"

  img_path="$SRC_DIR/$img_file"
  clip_file="$TMP_DIR/clip_${scene}.mp4"

  if [ "$audio_file" == "NONE" ]; then
    # 无音频 — 固定时长，静音
    dur=$fixed_dur
    echo "  [$scene] 图片+静音  ${dur}s"

    $FFMPEG -y -loglevel error \
      -loop 1 -framerate 30 -t "$dur" -i "$img_path" \
      -f lavfi -t "$dur" -i "anullsrc=channel_layout=stereo:sample_rate=44100" \
      -filter_complex "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,zoompan=z='min(zoom+0.0015,1.5)':d=1:s=1080x1920:fps=30[v]" \
      -map "[v]" -map "1:a" \
      -c:v libx264 -tune stillimage -preset medium -crf 20 \
      -c:a aac -b:a 192k -ar 44100 \
      -pix_fmt yuv420p -shortest -t "$dur" \
      "$clip_file"

  else
    audio_path="$SRC_DIR/$audio_file"
    # 获取音频时长
    dur=$($FFPROBE -v error -show_entries format=duration -of csv=p=0 "$audio_path")
    dur=$(printf "%.2f" "$dur")
    echo "  [$scene] 图片+$audio_file  ${dur}s"

    $FFMPEG -y -loglevel error \
      -loop 1 -framerate 30 -i "$img_path" \
      -i "$audio_path" \
      -filter_complex "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,zoompan=z='min(zoom+0.0015,1.5)':d=1:s=1080x1920:fps=30[v]" \
      -map "[v]" -map "1:a" \
      -c:v libx264 -tune stillimage -preset medium -crf 20 \
      -c:a aac -b:a 192k -ar 44100 \
      -pix_fmt yuv420p -shortest \
      "$clip_file"
  fi

  CLIP_FILES+=("$clip_file")
  CLIP_DURS+=("$dur")
  TOTAL_DUR=$(echo "$TOTAL_DUR + $dur" | bc)
  echo "    -> $clip_file ($(du -h "$clip_file" | cut -f1))"
done

echo ""
echo "  片段总时长(无转场重叠): ${TOTAL_DUR}s"

# ---- Step 2: 用 xfade 链式转场合并所有片段 ----
echo ""
echo ">>> Step 2: xfade 转场合并"

# 构建 ffmpeg 输入参数
INPUT_ARGS=""
for f in "${CLIP_FILES[@]}"; do
  INPUT_ARGS="$INPUT_ARGS -i \"$f\""
done

# 构建 filter_complex xfade 链
# xfade 偏移 = 前面所有片段时长之和 - 当前转场时长
FILTER=""
PREV_LABEL="[0:v][1:v]xfade=transition=fade:duration=${XFADE_DUR}:offset=$(echo "${CLIP_DURS[0]} - ${XFADE_DUR}" | bc)[v1];"
FILTER="$FILTER [0:a][1:a]acrossfade=d=${XFADE_DUR}[a1];"

for i in $(seq 2 $((${#CLIP_FILES[@]} - 1))); do
  # 计算偏移: 前面所有片段时长之和 - (i-1)*XFADE_DUR - XFADE_DUR
  # 即前面有效视频流位置 + 当前片段时长 - 转场时长
  offset=0
  for j in $(seq 0 $((i - 1))); do
    offset=$(echo "$offset + ${CLIP_DURS[$j]}" | bc)
  done
  # 减去已重叠的转场
  overlap=$(echo "($i) * ${XFADE_DUR}" | bc)
  offset=$(echo "$offset - $overlap" | bc)
  offset=$(printf "%.2f" "$offset")

  vi=$((i - 1))
  FILTER="$FILTER [v${vi}][${i}:v]xfade=transition=fade:duration=${XFADE_DUR}:offset=${offset}[v${i}];"
  FILTER="$FILTER [a${vi}][${i}:a]acrossfade=d=${XFADE_DUR}[a${i}];"
done

LAST_IDX=$((${#CLIP_FILES[@]} - 1))
# 去掉最后的分号
FILTER="${FILTER%;}"

echo "  转场时长: ${XFADE_DUR}s"
echo "  合并 ${#CLIP_FILES[@]} 个片段..."

# 执行合并
eval $FFMPEG -y -loglevel warning \
  $INPUT_ARGS \
  -filter_complex "\"$FILTER\"" \
  -map "\"[v${LAST_IDX}]\"" -map "\"[a${LAST_IDX}]\"" \
  -c:v libx264 -preset medium -crf 20 \
  -c:a aac -b:a 192k -ar 44100 \
  -pix_fmt yuv420p -movflags +faststart \
  "\"$OUT_FILE\""

# ---- Step 3: 验证输出 ----
echo ""
echo ">>> Step 3: 验证输出"

if [ -f "$OUT_FILE" ]; then
  SIZE=$(du -h "$OUT_FILE" | cut -f1)
  DUR=$($FFPROBE -v error -show_entries format=duration -of csv=p=0 "$OUT_FILE")
  W=$($FFPROBE -v error -select_streams v:0 -show_entries stream=width -of csv=p=0 "$OUT_FILE")
  H=$($FFPROBE -v error -select_streams v:0 -show_entries stream=height -of csv=p=0 "$OUT_FILE")
  VC=$($FFPROBE -v error -select_streams v:0 -show_entries stream=codec_name -of csv=p=0 "$OUT_FILE")
  AC=$($FFPROBE -v error -select_streams a:0 -show_entries stream=codec_name -of csv=p=0 "$OUT_FILE")
  FR=$($FFPROBE -v error -select_streams v:0 -show_entries stream=r_frame_rate -of csv=p=0 "$OUT_FILE")

  echo "  ┌───────────────────────────────────────┐"
  echo "  │ ✅ 输出文件: $OUT_FILE"
  echo "  │    文件大小: $SIZE"
  echo "  │    时长:     ${DUR}s"
  echo "  │    分辨率:   ${W}x${H}"
  echo "  │    视频编码: $VC"
  echo "  │    音频编码: $AC"
  echo "  │    帧率:     $FR"
  echo "  └───────────────────────────────────────┘"
else
  echo "  ❌ 输出文件不存在!"
  exit 1
fi

echo ""
echo "============================================"
echo "  ✅ E02 旁白版视频合成完成!"
echo "============================================"
