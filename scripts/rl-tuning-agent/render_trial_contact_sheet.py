"""
Build a contact sheet from a trial's video.mp4.

Selects 5 representative frames (first / 25% / 50% / 75% / final), tiles them
horizontally, and writes <trial_dir>/video_contact_sheet.jpg.

Used as a fallback if harbor/scripts/rl/render_policy.py couldn't write the sheet
itself (e.g. PIL not installed in the rl container but available on host).

Usage:
    python scripts/rl-tuning-agent/render_trial_contact_sheet.py \\
        --video <trial_dir>/video.mp4 --output <trial_dir>/video_contact_sheet.jpg
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--video", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--frames", type=int, default=5)
    return p.parse_args()


def main():
    args = parse_args()
    if not args.video.exists():
        print(f"[error] {args.video} not found", file=sys.stderr)
        sys.exit(2)
    try:
        import imageio.v2 as imageio
    except ImportError:
        import imageio
    try:
        from PIL import Image
    except ImportError:
        print("[error] PIL not installed: pip install pillow", file=sys.stderr)
        sys.exit(3)

    reader = imageio.get_reader(str(args.video))
    nframes = reader.count_frames() if hasattr(reader, "count_frames") else None
    if nframes is None or nframes <= 0:
        # Fall back: read every frame to count.
        all_frames = [f for f in reader]
        nframes = len(all_frames)
        if nframes == 0:
            print("[error] no frames in video", file=sys.stderr)
            sys.exit(4)
        sample_idx = [0, nframes // 4, nframes // 2, 3 * nframes // 4, nframes - 1][:args.frames]
        sampled = [all_frames[i] for i in sample_idx]
    else:
        sample_idx = [0, nframes // 4, nframes // 2, 3 * nframes // 4, nframes - 1][:args.frames]
        sampled = [reader.get_data(i) for i in sample_idx]

    pics = [Image.fromarray(f) for f in sampled]
    w, h = pics[0].size
    sheet = Image.new("RGB", (w * len(pics), h))
    for i, pic in enumerate(pics):
        sheet.paste(pic.resize((w, h)), (w * i, 0))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(str(args.output), quality=85)
    print(f"[ok] wrote {args.output}")


if __name__ == "__main__":
    main()
