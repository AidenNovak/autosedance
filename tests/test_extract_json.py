import json

from autosedance.nodes.segmenter import extract_json


def test_extract_json_direct():
    text = json.dumps({"script": "s", "video_prompt": "p"})
    out = extract_json(text)
    assert out["script"] == "s"
    assert out["video_prompt"] == "p"


def test_extract_json_fenced_block():
    text = "here\n```json\n{\"script\":\"s1\",\"video_prompt\":\"p1\"}\n```\nthere"
    out = extract_json(text)
    assert out["script"] == "s1"
    assert out["video_prompt"] == "p1"


def test_extract_json_brace_match():
    text = "noise {\"script\":\"s2\",\"video_prompt\":\"p2\"} tail"
    out = extract_json(text)
    assert out["script"] == "s2"
    assert out["video_prompt"] == "p2"


def test_extract_json_fallback():
    text = "not json at all"
    out = extract_json(text)
    assert out["script"] == text
    assert out["video_prompt"] == text[:200]

