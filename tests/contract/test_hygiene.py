"""Contract: open-source hygiene — no personal abs paths, no identity leaks.

Permanently guards the cleanups done before open-sourcing (personal home paths,
the pql / ddiffpg / bidex / W&B-handle references). tests/ itself is not scanned
(this file legitimately contains the identity tokens in its regex).

`supersglzc` stays on the denylist because it must not reappear as a stray home
path or W&B handle — but the plugin's own marketplace URL is exempted: a
published plugin has to name the repo it is installed from.
"""
import re

import pytest

from _pluginmeta import ROOT, iter_text_files

FILES = sorted(iter_text_files(), key=lambda p: p.as_posix())

_ABS_RE = re.compile(r"/(?:home|Users)/([^/\s`\"')]+)")
_ALLOWED_USERS = {"me", "you", "user", "USER"}
_IDENTITY_RE = re.compile(
    r"(?<![A-Za-z])(?:pql|ddiffpg|supersglzc\w*)(?![A-Za-z])"
    r"|(?<![A-Za-z])bidex(?!hands)(?![A-Za-z])",
    re.IGNORECASE,
)


# The plugin's own published URLs — marketplace / clone, and the GitHub Pages host the
# README and docs site link to. These are the only places the publisher handle is
# expected. Stripped before the identity scan so any OTHER use of the handle (home
# paths, W&B entities) still fails.
_PUBLISHER_URL_RE = re.compile(
    r"(?:github\.com/)?supersglzc/harbor(?:-dev)?(?:\.git)?"
    r"|supersglzc\.github\.io"
)


def _is_placeholder_user(u):
    return u.startswith("<") or set(u) <= {"."}


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_no_personal_abs_paths(path):
    bad = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        for user in _ABS_RE.findall(line):
            if user in _ALLOWED_USERS or _is_placeholder_user(user):
                continue
            bad.append(line.strip()[:120])
    assert not bad, f"{path.relative_to(ROOT)}: personal absolute path(s): {bad[:3]}"


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_no_identity_leaks(path):
    text = _PUBLISHER_URL_RE.sub("", path.read_text(encoding="utf-8", errors="ignore"))
    hits = {m.group(0) for m in _IDENTITY_RE.finditer(text)}
    assert not hits, f"{path.relative_to(ROOT)}: identity token(s): {sorted(hits)}"
