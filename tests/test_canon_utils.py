from autosedance.utils.canon import (
    CANON_SUMMARY_MARKER,
    MUSIC_STATE_MARKER,
    canon_compact_description,
    extract_marker_line,
    replace_canon_item,
)


def test_extract_marker_line_strict():
    text = "foo\n[[CANON_SUMMARY]] Ending frame: X MUSIC: Y\nbar"
    assert extract_marker_line(text, CANON_SUMMARY_MARKER) == "Ending frame: X MUSIC: Y"


def test_extract_marker_line_bullet():
    text = "- [[MUSIC_STATE]] genre=anime pop; bpm=120"
    assert extract_marker_line(text, MUSIC_STATE_MARKER) == "genre=anime pop; bpm=120"


def test_extract_marker_line_colon():
    text = "[[CANON_SUMMARY]]: hello"
    assert extract_marker_line(text, CANON_SUMMARY_MARKER) == "hello"


def test_canon_compact_description_prefers_marker():
    text = "Long analysis...\n[[CANON_SUMMARY]] Ending frame: A; MUSIC: B\nMore..."
    assert canon_compact_description(text, max_chars=240) == "Ending frame: A; MUSIC: B"


def test_canon_compact_description_fallback_first_line_and_truncate():
    text = "\n\nFirst line here\nSecond line"
    assert canon_compact_description(text, max_chars=10) == "First lin…"


def test_replace_canon_item_replaces_by_idx():
    canon = "\n---\n".join(
        [
            "[#IDX=0] #001 (0s-15s): A",
            "[#IDX=1] #002 (15s-30s): B",
        ]
    )
    out = replace_canon_item(canon, 1, "[#IDX=1] #002 (15s-30s): B2")
    assert "[#IDX=1] #002 (15s-30s): B2" in out
    assert " B\n" not in out


def test_replace_canon_item_appends_if_missing():
    canon = "[#IDX=0] #001 (0s-15s): A"
    out = replace_canon_item(canon, 2, "[#IDX=2] #003 (30s-45s): C")
    assert out.endswith("[#IDX=2] #003 (30s-45s): C")

