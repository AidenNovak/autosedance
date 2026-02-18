from __future__ import annotations

import re
from typing import List, Optional

IDX_TOKEN_RE = re.compile(r"^\[#IDX=(\d+)\]\s*")
LEGACY_ZH_RE = re.compile(r"^片段(\d+)\(")

CANON_SUMMARY_MARKER = "[[CANON_SUMMARY]]"
MUSIC_STATE_MARKER = "[[MUSIC_STATE]]"


def split_canon(canon_summaries: str) -> List[str]:
    canon_summaries = canon_summaries or ""
    parts = [p.strip() for p in canon_summaries.split("\n---\n") if p.strip()]
    return parts


def parse_canon_index(item: str) -> Optional[int]:
    m = IDX_TOKEN_RE.match(item or "")
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return None

    m = LEGACY_ZH_RE.match(item or "")
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return None

    return None


def canon_recent(canon_summaries: str, keep: int = 3) -> str:
    parts = split_canon(canon_summaries)
    if not parts:
        return ""
    return "\n---\n".join(parts[-keep:])


def append_canon(canon_summaries: str, summary: str) -> str:
    canon_summaries = canon_summaries or ""
    summary = (summary or "").strip()
    if not summary:
        return canon_summaries
    if not canon_summaries.strip():
        return summary
    return f"{canon_summaries}\n---\n{summary}"


def canon_before_index(canon_summaries: str, index: int) -> str:
    """Keep only canon summary items for segments strictly before `index` (0-based)."""
    kept: List[str] = []
    for item in split_canon(canon_summaries or ""):
        idx = parse_canon_index(item)
        if idx is None:
            # If the item doesn't match our format, keep it to avoid data loss.
            kept.append(item)
            continue
        if idx < index:
            kept.append(item)
    return "\n---\n".join(kept)

def extract_marker_line(text: str, marker: str) -> Optional[str]:
    """Extract a single-line payload that starts with `marker`.

    Example line:
        [[CANON_SUMMARY]] Ending frame... MUSIC: ...
    """
    raw = (text or "").strip()
    marker = (marker or "").strip()
    if not raw or not marker:
        return None

    # First pass: strict line-start match.
    for line in raw.splitlines():
        l = (line or "").strip()
        if not l:
            continue
        if l.startswith(marker):
            out = l[len(marker) :].strip()
            if out.startswith(":"):
                out = out[1:].strip()
            return out or None

    # Second pass: tolerate a bullet prefix like "- [[CANON_SUMMARY]] ...".
    for line in raw.splitlines():
        l = (line or "").strip()
        if not l:
            continue
        pos = l.find(marker)
        if pos < 0:
            continue
        out = l[pos + len(marker) :].strip()
        if out.startswith(":"):
            out = out[1:].strip()
        return out or None
    return None


def canon_compact_description(description: str, *, max_chars: int = 240) -> str:
    """Compact a verbose analyzer output into a short, stable canon string.

    Prefer an explicit marker line if the model emitted one; otherwise fall back
    to a trimmed single-line summary.
    """
    raw = (description or "").strip()
    if not raw:
        return ""

    picked = extract_marker_line(raw, CANON_SUMMARY_MARKER)
    if not picked:
        # Pick the first non-empty line, or the whole text flattened.
        for line in raw.splitlines():
            l = (line or "").strip()
            if l:
                picked = l
                break
    if not picked:
        picked = raw

    picked = " ".join(picked.split())
    if max_chars > 0 and len(picked) > max_chars:
        picked = picked[: max_chars - 1].rstrip() + "…"
    return picked


def replace_canon_item(canon_summaries: str, index: int, new_item: str) -> str:
    """Replace a canon summary item by IDX; append if not found."""
    new_item = (new_item or "").strip()
    if not new_item:
        return canon_summaries or ""

    parts = split_canon(canon_summaries or "")
    out: List[str] = []
    replaced = False
    for item in parts:
        idx = parse_canon_index(item)
        if idx is not None and idx == index:
            out.append(new_item)
            replaced = True
        else:
            out.append(item)
    if not replaced:
        out.append(new_item)
    return "\n---\n".join([p for p in out if (p or "").strip()])


def format_canon_summary(index: int, start_s: int, end_s: int, description: str) -> str:
    """Language-neutral canon line with a machine-readable 0-based IDX token.

    We include a 1-based, zero-padded display number for humans, but the IDX token
    is the source of truth for trimming/invalidation.
    """
    desc = (description or "").strip()
    seg_display = index + 1
    if desc:
        return f"[#IDX={index}] #{seg_display:03d} ({start_s}s-{end_s}s): {desc}"
    return f"[#IDX={index}] #{seg_display:03d} ({start_s}s-{end_s}s)"
