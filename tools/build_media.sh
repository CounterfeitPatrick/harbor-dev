#!/usr/bin/env bash
# Transcode the raw sim-recording archive into the web assets the README and docs site use.
#
# The raw recordings total ~465 MB — far too heavy for git. This script renders them down
# to looping animated WebP tiles (~50-800 KB each) plus one re-encoded walkthrough, which is
# what actually gets committed. The full-resolution originals belong in a GitHub Release.
#
# Tiles are WebP rather than MP4 because a README cannot autoplay a repo-relative <video> —
# only images animate — and WebP is 3-5x smaller than GIF at the same quality. The
# walkthrough stays an MP4 because it has narration and needs a scrubber.
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
mkdir -p "$OUT/gallery" "$OUT/hero"

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

# Poster for the walkthrough: the 14 s beat where the prompt and the trained G1 are both on
# screen, which states the whole premise in one frame. A still rather than a loop because the
# video is the thing being linked to — an animation here would just compete with it, and cost
# megabytes above the fold to do so.
echo "==> hero poster"
# The frame is dimmed and given a play triangle so it reads as a poster rather than as a
# screenshot someone forgot to crop. DejaVu Sans carries U+25B6; the Mono face's version is
# noticeably lighter, so the proportional face is the one to use here.
GLYPH=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf
ffmpeg -y -v error -ss 14 -i "$WORK/demo.mp4" -vf "\
scale=860:-2:flags=lanczos,\
drawbox=x=0:y=0:w=iw:h=ih:color=0x0B1220@0.30:t=fill,\
drawtext=fontfile=$GLYPH:text='▶':fontcolor=0x0B1220@0.55:fontsize=104:x=(w-tw)/2+5:y=(h-th)/2+5,\
drawtext=fontfile=$GLYPH:text='▶':fontcolor=white@0.96:fontsize=104:x=(w-tw)/2:y=(h-th)/2" \
    -frames:v 1 -c:v libwebp -q:v 86 "$OUT/hero/walkthrough-poster.webp"
echo "    $(printf '%-34s' "assets/hero/walkthrough-poster.webp") $(du -h "$OUT/hero/walkthrough-poster.webp" | cut -f1)"

# The walkthrough itself. Sized to clear GitHub's 10 MB attachment cap for video on free
# plans, because the README embeds it through user-attachments — the only way to get an
# inline player there — and that upload is what enforces the ceiling.
#
# The budget is spent on resolution, not frame rate: this is a screencast, so 1280px keeps
# the terminal text sharp while 12 fps costs almost nothing perceptually. -tune stillimage
# tells x264 the same thing. The result is visually indistinguishable from a 21 MB encode.
# H.264 is what GitHub recommends for cross-browser playback.
echo "==> walkthrough"
mkdir -p "$ROOT/docs/public"
ffmpeg -y -v error -i "$WORK/demo.mp4" -vf "fps=12,scale=1280:-2:flags=lanczos" \
    -c:v libx264 -crf 34 -preset slow -tune stillimage \
    -c:a aac -b:a 64k -movflags +faststart "$ROOT/docs/public/demo.mp4"
bytes=$(stat -c%s "$ROOT/docs/public/demo.mp4")
echo "    $(printf '%-34s' "docs/public/demo.mp4") $(du -h "$ROOT/docs/public/demo.mp4" | cut -f1)"
[ "$bytes" -lt 10485760 ] || echo "    WARNING: over GitHub's 10 MB video cap for free plans" >&2

echo "==> gallery: 8 tasks x 4 simulators"
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

# Locomotion sits in the same grid as manipulation: the harness is embodiment-agnostic, so
# splitting them into two galleries would imply a distinction that does not exist. These
# recordings run 33 s where the manipulation tiles are 2-5 s, so each is trimmed to a loop.
echo "==> locomotion (IsaacLab, trimmed to a 6 s loop each)"
encode g1_jump.mp4       gallery/g1-jump__isaaclab.webp       "" "-ss 2 -t 6"
encode g1-backflip.mp4   gallery/g1-backflip__isaaclab.webp   "" "-ss 2 -t 6"
encode g1_footstep.mp4   gallery/g1-footstep__isaaclab.webp   "" "-ss 2 -t 6"
encode g1_rough_jump.mp4 gallery/g1-rough-jump__isaaclab.webp "" "-ss 2 -t 6"

echo "==> extra IsaacLab tasks (not in the grid)"
encode stack_two_cube.mp4 gallery/stack-two-cube__isaaclab.webp
encode place_banana.mp4   gallery/place-banana__isaaclab.webp

# Cells not yet recorded: MJLab across the board, and the locomotion tasks everywhere but
# IsaacLab. A labelled tile keeps the grid rectangular and says which run is outstanding,
# rather than a ragged table that reads as though the coverage were complete.
echo "==> placeholders for unrecorded cells"
for task in stack-cube insert-drawer lift-box dex-grasp; do
    placeholder "gallery/${task}__mjlab.webp" "MJLab"
done
for task in g1-jump g1-backflip g1-footstep g1-rough-jump; do
    placeholder "gallery/${task}__maniskill.webp" "ManiSkill"
    placeholder "gallery/${task}__genesis.webp"   "Genesis"
    placeholder "gallery/${task}__mjlab.webp"     "MJLab"
done

echo "==> docs site assets"
DOCS="$ROOT/docs/public"
mkdir -p "$DOCS"
cp "$ROOT/assets/logo/harbor-mark.svg"      "$DOCS/logo.svg"
cp "$ROOT/assets/logo/harbor-mark-dark.svg" "$DOCS/logo-dark.svg"
cp "$ROOT/assets/logo/favicon.svg"          "$DOCS/favicon.svg"
cp "$OUT/hero/walkthrough-poster.webp"      "$DOCS/walkthrough-poster.webp"

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
echo "==> total committed: $(du -sch "$OUT" "$DOCS" | tail -1 | cut -f1)"
