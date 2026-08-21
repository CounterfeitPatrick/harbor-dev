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

# The whole narrated walkthrough as one self-playing loop. A README animates images and
# nothing else — a repo-relative <video> renders no player at all — so the full run has to be
# an animated WebP to play on its own. 860px keeps the terminal text sharp, which is the point
# of a screencast, and 24 fps matches the source so the scrolling reads as motion rather than
# as a slideshow. Those two are the priority in that order; q72 is what keeps 3m45s of them
# down to ~30 MB. This is the largest file in the repo — raising fps or width past here buys
# less than it costs, since every clone and every README visitor pays for it.
echo "==> hero: full walkthrough"
WIDTH_SAVE=$WIDTH; Q_SAVE=$Q; FPS_SAVE=$FPS
WIDTH=860; Q=72; FPS=24
encode demo.mp4 hero/walkthrough.webp
WIDTH=$WIDTH_SAVE; Q=$Q_SAVE; FPS=$FPS_SAVE

# Still of the same 14 s beat, used as the poster on the docs site's <video> element so a
# 9 MB file is not fetched before anyone presses play.
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

# The walkthrough itself, and the only copy that carries the narration audio. Its sole
# consumer is the docs site: docs/index.md plays it in a <video> element off GitHub Pages.
# The README does NOT embed it — the hero WebP above the fold is the walkthrough there —
# so no user-attachments upload happens and GitHub's 10 MB attachment cap does not apply.
#
# What does constrain it is repo weight: the file is committed (.gitignore un-ignores it
# by name), so its size is permanent for everyone who clones. preload="metadata" on the
# docs player means visitors only pay for it when they press play, so the ceiling below is
# a repo-size budget rather than a platform limit — raise it deliberately if the quality
# is worth the clone.
#
# The budget is spent on resolution, not frame rate: this is a screencast, so 1280px keeps
# the terminal text as sharp as the bitrate allows while 12 fps costs little perceptually.
# -tune stillimage tells x264 the same thing. H.264 is what GitHub recommends for
# cross-browser playback.
echo "==> walkthrough"
mkdir -p "$ROOT/docs/public"
ffmpeg -y -v error -i "$WORK/demo.mp4" -vf "fps=12,scale=1280:-2:flags=lanczos" \
    -c:v libx264 -crf 34 -preset slow -tune stillimage \
    -c:a aac -b:a 64k -movflags +faststart "$ROOT/docs/public/demo.mp4"
bytes=$(stat -c%s "$ROOT/docs/public/demo.mp4")
echo "    $(printf '%-34s' "docs/public/demo.mp4") $(du -h "$ROOT/docs/public/demo.mp4" | cut -f1)"
[ "$bytes" -lt 10485760 ] || echo "    WARNING: over the 10 MB repo-weight budget for this file" >&2

echo "==> gallery: 7 tasks x 3 simulators"
# IsaacLab. dex-grasp is recorded from far off and lasts 8 frames, so it is cropped to the
# workspace and motion-interpolated to a readable ~2 s loop instead of a 0.5 s twitch.
encode stack_three_cube.mp4          gallery/stack-cube__isaaclab.webp
encode insert_drawer.mp4             gallery/insert-drawer__isaaclab.webp
encode lift_box.mp4                  gallery/lift-box__isaaclab.webp
encode hang_mug.mp4                  gallery/hang-mug__isaaclab.webp
encode dex-grasp.mp4                 gallery/dex-grasp__isaaclab.webp \
    "crop=889:500:176:170,setpts=4*PTS,minterpolate=fps=24:mi_mode=mci:mc_mode=aobmc:me_mode=bilat:vsbmc=1"

encode maniskill_stack_three_cube.mp4 gallery/stack-cube__maniskill.webp
encode maniskill_insert_drawer.mp4    gallery/insert-drawer__maniskill.webp
encode maniskill_lift_box.mp4         gallery/lift-box__maniskill.webp
encode maniskill_dex_grasp.mp4        gallery/dex-grasp__maniskill.webp
encode maniskill_hang_mug.mp4         gallery/hang-mug__maniskill.webp

encode genesis_stack_three_cube.mp4   gallery/stack-cube__genesis.webp
# The Genesis insert-drawer take runs 33 s where every other tile is 2-5 s; trimmed so the
# grid loops in step rather than one cell drifting out of phase with the rest.
encode genesis_insert_drawer.mp4      gallery/insert-drawer__genesis.webp "" "-ss 1 -t 6"
encode genesis_lift_box.mp4           gallery/lift-box__genesis.webp
encode genesis_dex_grasp.mp4          gallery/dex-grasp__genesis.webp
encode genesis_hang_mug.mp4           gallery/hang-mug__genesis.webp

# Locomotion sits in the same grid as manipulation: the harness is embodiment-agnostic, so
# splitting them into two galleries would imply a distinction that does not exist. These
# recordings run 33 s where the manipulation tiles are 2-5 s, so each is trimmed to a loop.
echo "==> locomotion (trimmed to a 6 s loop each)"
encode g1_jump.mp4               gallery/g1-jump__isaaclab.webp       "" "-ss 2 -t 6"
encode g1_footstep.mp4           gallery/g1-footstep__isaaclab.webp   "" "-ss 2 -t 6"
encode maniskill_g1_jump.mp4     gallery/g1-jump__maniskill.webp      "" "-ss 2 -t 6"
encode maniskill_g1_footstep.mp4 gallery/g1-footstep__maniskill.webp  "" "-ss 2 -t 6"
encode genesis_g1_jump.mp4       gallery/g1-jump__genesis.webp        "" "-ss 2 -t 6"
encode genesis_g1_footstep.mp4   gallery/g1-footstep__genesis.webp    "" "-ss 2 -t 6"

echo "==> extra IsaacLab tasks (not in the grid)"
encode stack_two_cube.mp4 gallery/stack-two-cube__isaaclab.webp
encode place_banana.mp4   gallery/place-banana__isaaclab.webp

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
