"""Unit: mcp/harbor/server.py — read-only registry tools + fuzzy match.

Skips where the `mcp` package isn't installed (e.g. this dev box); runs in CI /
on the registry host where the MCP runtime is present.
"""
import importlib.util

import pytest

from _pluginmeta import ROOT

pytest.importorskip("mcp.server.fastmcp")


def _load_server():
    spec = importlib.util.spec_from_file_location("harbor_server", ROOT / "mcp" / "harbor" / "server.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SRV = _load_server()


def test_url_basename():
    assert SRV._url_basename("https://github.com/foo/bar.git") == "bar"
    assert SRV._url_basename("git@github.com:foo/bar.git") == "bar"
    assert SRV._url_basename("bar") == "bar"


def test_normalize_strips_trailing_digits_and_nonalnum():
    assert SRV._normalize("ManiSkill3") == "maniskill"
    assert SRV._normalize("mani-skill") == "maniskill"


def test_match_entry_priority():
    entry = {"name": "maniskill", "github": "https://github.com/haosulab/ManiSkill"}
    assert SRV._match_entry(entry, "maniskill") == "exact_name"
    assert SRV._match_entry(entry, "https://github.com/haosulab/ManiSkill") == "exact_url"
    # a fork URL fuzzily resolves to the verified entry
    assert SRV._match_entry({"name": "maniskill"}, "https://github.com/someone/ManiSkill3") == "fuzzy_normalized"
    assert SRV._match_entry(entry, "totally-unrelated") is None


def test_list_benchmarks_shape():
    out = SRV.list_benchmarks()
    assert "count" in out and isinstance(out["benchmarks"], list)
    assert out["count"] == len(out["benchmarks"])


def test_list_tasks_shape():
    out = SRV.list_tasks()
    assert "count" in out and isinstance(out["tasks"], list)
