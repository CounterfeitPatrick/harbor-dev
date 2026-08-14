#!/usr/bin/env bash
# Transcode the raw sim-recording archive into the web assets the README and docs site use.
#
# The raw recordings are 1280x720 MP4s totalling ~465 MB — far too heavy for git. This
# script renders them down to looping animated WebP tiles (~50-800 KB each) under assets/,
# which is what actually gets committed. Full-resolution MP4s belong in a GitHub Release,
# and the narrated demo belongs on YouTube; neither is produced here.
#
# WebP rather than MP4 because a README cannot play a repo-relative <video> — only images
# animate. WebP rather than GIF because it is 3-5x smaller at the same quality.
#
# Usage: tools/build_media.sh [path/to/Archive.zip]
set -euo pipefail

ARCHIVE="${1:-$(dirname "$0")/../../Archive.zip}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/assets"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

FONT=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf
WIDTH=480          # tile width in the README grid; height follows the source aspect
FPS=12
Q=72               # libwebp quality: 72 keeps sim renders clean at ~150-250 KB

command -v ffmpeg >/dev/null || { echo "ffmpeg not found" >&2; exit 1; }
[ -f "$ARCHIVE" ] || { echo "archive not found: $ARCHIVE" >&2; exit 1; }

echo "==> extracting from $ARCHIVE"
unzip -q -o -j "$ARCHIVE" "sim videos/*/*.mp4" "demo.mp4" -d "$WORK" -x "__MACOSX/*"
mkdir -p "$OUT/gallery" "$OUT/locomotion" "$OUT/hero"

# encode <src> <dest> [extra filters] [trim args]
encode() {
    local src="$WORK/$1" dest="$OUT/$2" pre="${3:-}" trim="${4:-}"
    [ -f "$src" ] || { echo "    MISSING $1 — skipped"; return 0; }
    local vf="${pre:+$pre,}fps=$FPS,scale=$WIDTH:-2:flags=lanczos"
    # shellcheck disable=SC2086
    ffmpeg -y -v error $trim -i "$src" -vf "$vf" \
        -c:v libwebp_anim -lossless 0 -q:v $Q -loop 0 -an "$dest"
    echo "    $(printf '%-34s' "$2") $(du -h "$dest" | cut -f1)"
}

# A tile for a cell we cannot fill yet. Keeps the grid rectangular and says so honestly,
# rather than silently shipping a 3-wide grid the results table describes as 4-wide.
placeholder() {
    local dest="$OUT/$1" label="$2"
    ffmpeg -y -v error -f lavfi -i "color=c=0x11161d:s=${WIDTH}x270:d=1" \
        -vf "drawtext=fontfile=$FONT:text='$label':fontcolor=0x5b6673:fontsize=22:x=(w-tw)/2:y=(h-th)/2-14,\
drawtext=fontfile=$FONT:text='recording pending':fontcolor=0x39424e:fontsize=14:x=(w-tw)/2:y=(h-th)/2+18" \
        -frames:v 1 -c:v libwebp -q:v 80 "$dest"
    echo "    $(printf '%-34s' "$1") placeholder"
}

# The 9-17 s beat of the narrated demo: the prompt on screen, the trained G1 already
# jumping beside it. One loop that states the whole premise, so it leads the README.
echo "==> hero"
WIDTH_SAVE=$WIDTH; WIDTH=760
encode demo.mp4 hero/prompt-to-policy.webp "" "-ss 9 -t 8"
WIDTH=$WIDTH_SAVE

echo "==> gallery: 4 tasks x 4 simulators"
# IsaacLab. dex-grasp is recorded from far off and lasts 8 frames, so it is cropped to the
# workspace and motion-interpolated to a readable ~2 s loop instead of a 0.5 s twitch.
encode stack_three_cube.mp4          gallery/stack-cube__isaaclab.webp
encode insert_drawer.mp4             gallery/insert-drawer__isaaclab.webp
encode lift_box.mp4                  gallery/lift-box__isaaclab.webp
encode dex-grasp.mp4                 gallery/dex-grasp__isaaclab.webp \
    "crop=889:500:176:170,setpts=4*PTS,minterpolate=fps=24:mi_mode=mci:mc_mode=aobmc:me_mode=bilat:vsbmc=1"

encode maniskill_stack_three_cube.mp4 gallery/stack-cube__maniskill.webp
encode maniskill_insert_drawer.mp4    gallery/insert-drawer__maniskill.webp
encode maniskill_lift_box.mp4         gallery/lift-box__maniskill.webp
encode maniskill_dex_grasp.mp4        gallery/dex-grasp__maniskill.webp

encode genesis_stack_three_cube.mp4   gallery/stack-cube__genesis.webp
# The Genesis insert-drawer take runs 33 s where every other tile is 2-5 s; trimmed so the
# grid loops in step rather than one cell drifting out of phase with the rest.
encode genesis_insert_drawer.mp4      gallery/insert-drawer__genesis.webp "" "-ss 1 -t 6"
encode genesis_lift_box.mp4           gallery/lift-box__genesis.webp
encode genesis_dex_grasp.mp4          gallery/dex-grasp__genesis.webp

# MJLab is the paper's fourth simulator but no recordings shipped in the archive.
placeholder gallery/stack-cube__mjlab.webp    "MJLab"
placeholder gallery/insert-drawer__mjlab.webp "MJLab"
placeholder gallery/lift-box__mjlab.webp      "MJLab"
placeholder gallery/dex-grasp__mjlab.webp     "MJLab"

echo "==> extra IsaacLab tasks"
encode stack_two_cube.mp4 gallery/stack-two-cube__isaaclab.webp
encode place_banana.mp4   gallery/place-banana__isaaclab.webp

echo "==> locomotion (33 s recordings, trimmed to a 6 s loop each)"
encode g1-backflip.mp4   locomotion/g1-backflip.webp   "" "-ss 2 -t 6"
encode g1_jump.mp4       locomotion/g1-jump.webp       "" "-ss 2 -t 6"
encode g1_footstep.mp4   locomotion/g1-footstep.webp   "" "-ss 2 -t 6"
encode g1_rough_jump.mp4 locomotion/g1-rough-jump.webp "" "-ss 2 -t 6"

echo "==> docs site assets"
DOCS="$ROOT/docs/public"
mkdir -p "$DOCS"
cp "$ROOT/assets/logo/harbor-mark.svg" "$DOCS/logo.svg"
cp "$ROOT/assets/logo/favicon.svg"     "$DOCS/favicon.svg"

# One strip of all four tasks for the docs landing page. Each clip is looped to a common
# 4 s so hstack gets equal frame counts — without that the shortest clip truncates the row.
strip_in=()
for f in stack_three_cube insert_drawer lift_box dex-grasp; do
    strip_in+=(-stream_loop -1 -t 4 -i "$WORK/$f.mp4")
done
ffmpeg -y -v error "${strip_in[@]}" -filter_complex \
    "[0:v]scale=240:135[a];[1:v]scale=240:135[b];[2:v]scale=240:135[c];\
     [3:v]crop=889:500:176:170,scale=240:135[d];\
     [a][b][c][d]hstack=inputs=4,fps=$FPS[o]" \
    -map "[o]" -c:v libwebp_anim -q:v 70 -loop 0 -an "$DOCS/gallery-strip.webp"
echo "    $(printf '%-34s' "docs/public/gallery-strip.webp") $(du -h "$DOCS/gallery-strip.webp" | cut -f1)"

# GitHub link unfurl and the docs og:image. 1280x640 is the ratio both platforms crop to.
# Stills are extracted first: selecting a frame inside the compose graph gives the overlay
# no timestamp to land on, and the thumbnails silently vanish while the text still renders.
i=1
for f in stack_three_cube insert_drawer lift_box maniskill_dex_grasp; do
    ffmpeg -y -v error -ss 1 -i "$WORK/$f.mp4" -vf "scale=272:153" -frames:v 1 "$WORK/sp$i.png"
    i=$((i + 1))
done
ffmpeg -y -v error -f lavfi -i "color=c=0x0B1220:s=1280x640:d=1" \
    -i "$WORK/sp1.png" -i "$WORK/sp2.png" -i "$WORK/sp3.png" -i "$WORK/sp4.png" -filter_complex \
    "[0:v][1:v]overlay=64:410[o1];[o1][2:v]overlay=352:410[o2];\
     [o2][3:v]overlay=640:410[o3];[o3][4:v]overlay=928:410[o4];\
     [o4]drawtext=fontfile=$FONT:text='HARBOR':fontcolor=0xE8F6F8:fontsize=92:x=64:y=150,\
     drawtext=fontfile=$FONT:text='Point it at a simulator. Describe a task. Get a trained policy.':\
fontcolor=0x0FB6C9:fontsize=31:x=68:y=272[out]" \
    -map "[out]" -frames:v 1 "$OUT/social-preview.png"
cp "$OUT/social-preview.png" "$DOCS/social-preview.png"
echo "    $(printf '%-34s' "assets/social-preview.png") $(du -h "$OUT/social-preview.png" | cut -f1)"

echo
echo "==> total committed: $(du -sh "$OUT" "$DOCS" | awk '{s=$1} END {print s}')"
