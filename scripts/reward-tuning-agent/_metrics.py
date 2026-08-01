"""Shared metrics.jsonl reader for the reward-tune scripts.

Both `curve_health.py` (live snapshot) and `score_iter.py` (final verdict) read the
same training log, so the format tolerance lives here once. Stdlib only.

Long format  — one {"key", "step", "value"} row per point.
Wide format  — one {"<key>": v, ..., "step": s} row per logging tick.
Both are accepted; a half-written trailing line is ignored so a LIVE file is safe to read.
"""
import json


def load_rows(path):
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # live file: ignore a half-written trailing line
    return rows


def series(rows):
    """Return {key: [(step, value), ...]} sorted by step, for long OR wide format."""
    out = {}
    if rows and "key" in rows[0] and "value" in rows[0]:  # long format
        for r in rows:
            k, s, v = r.get("key"), r.get("step"), r.get("value")
            if k is None or v is None:
                continue
            out.setdefault(k, []).append((s if s is not None else len(out.get(k, [])), v))
    else:  # wide format
        for i, r in enumerate(rows):
            s = r.get("step", r.get("global_step", i))
            for k, v in r.items():
                if k in ("step", "global_step") or not isinstance(v, (int, float)):
                    continue
                out.setdefault(k, []).append((s, v))
    for k in out:
        out[k].sort(key=lambda t: t[0])
    return out


def load_series(path):
    return series(load_rows(path))


def final_values(ser):
    """{key: last value} — the value at the largest step for each key."""
    return {k: pts[-1][1] for k, pts in ser.items() if pts}
