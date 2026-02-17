from __future__ import annotations

import re
from typing import List, Optional

IDX_TOKEN_RE = re.compile(r"^\[#IDX=(\d+)\]\s*")
LEGACY_ZH_RE = re.compile(r"^片段(\d+)\(")


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

