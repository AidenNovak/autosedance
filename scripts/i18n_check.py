#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import string
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple


ROOT = Path(__file__).resolve().parents[1]

UI_DIR = ROOT / "apps" / "web" / "src" / "i18n" / "locales"
PROMPT_DIR = ROOT / "src" / "autosedance" / "prompts" / "i18n"

UI_BASE_LOCALE = "en"
PROMPT_BASE_LOCALE = "en"

PROMPT_FILES = [
    "scriptwriter_system.txt",
    "scriptwriter_user.txt",
    "segmenter_system.txt",
    "segmenter_user.txt",
    "analyzer_system.txt",
    "analyzer_user.txt",
]


UI_PARAM_RE = re.compile(r"\{([a-zA-Z0-9_]+)\}")


def _die(msg: str) -> None:
    print(msg, file=sys.stderr)
    sys.exit(1)


def _read_json(path: Path) -> Dict[str, str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        _die(f"[ui] failed to read json: {path} ({e})")
    if not isinstance(data, dict):
        _die(f"[ui] expected object at top-level: {path}")
    out: Dict[str, str] = {}
    for k, v in data.items():
        if not isinstance(k, str) or not isinstance(v, str):
            _die(f"[ui] expected string-to-string mapping: {path} (bad key/value: {k!r}={v!r})")
        out[k] = v
    return out


def _ui_placeholders(s: str) -> Set[str]:
    return set(UI_PARAM_RE.findall(s or ""))


def _template_placeholders(text: str) -> Set[str]:
    fmt = string.Formatter()
    fields: Set[str] = set()
    for _, field_name, _, _ in fmt.parse(text):
        if not field_name:
            continue
        # Normalize "a.b" / "a[0]" to "a" (we only use simple names).
        name = re.split(r"[.\[]", field_name, 1)[0]
        fields.add(name)
    return fields


def _list_locales(dir_path: Path) -> List[str]:
    if not dir_path.exists():
        _die(f"missing directory: {dir_path}")
    locales = sorted([p.name for p in dir_path.iterdir() if p.is_dir()])
    return locales


def check_ui() -> List[str]:
    issues: List[str] = []
    if not UI_DIR.exists():
        return [f"[ui] missing directory: {UI_DIR}"]

    files = sorted([p for p in UI_DIR.glob("*.json") if p.is_file()])
    if not files:
        return [f"[ui] no locale json files found under {UI_DIR}"]

    by_locale: Dict[str, Dict[str, str]] = {}
    for f in files:
        by_locale[f.stem] = _read_json(f)

    if UI_BASE_LOCALE not in by_locale:
        issues.append(f"[ui] base locale '{UI_BASE_LOCALE}' not found (have: {sorted(by_locale.keys())})")
        return issues

    base = by_locale[UI_BASE_LOCALE]
    base_keys = set(base.keys())

    for loc, data in sorted(by_locale.items()):
        keys = set(data.keys())
        missing = sorted(base_keys - keys)
        extra = sorted(keys - base_keys)
        if missing:
            issues.append(f"[ui] {loc}: missing keys ({len(missing)}): {missing[:8]}{' ...' if len(missing) > 8 else ''}")
        if extra:
            issues.append(f"[ui] {loc}: extra keys ({len(extra)}): {extra[:8]}{' ...' if len(extra) > 8 else ''}")

    # Placeholder consistency per key (only for keys present in base).
    for key, base_val in base.items():
        base_ph = _ui_placeholders(base_val)
        for loc, data in sorted(by_locale.items()):
            if loc == UI_BASE_LOCALE:
                continue
            if key not in data:
                continue
            ph = _ui_placeholders(data[key])
            if ph != base_ph:
                issues.append(f"[ui] {loc}: placeholder mismatch for '{key}': base={sorted(base_ph)} vs {sorted(ph)}")

    return issues


def check_prompts() -> List[str]:
    issues: List[str] = []
    if not PROMPT_DIR.exists():
        return [f"[prompt] missing directory: {PROMPT_DIR}"]

    locales = _list_locales(PROMPT_DIR)
    if not locales:
        return [f"[prompt] no locale directories found under {PROMPT_DIR}"]
    if PROMPT_BASE_LOCALE not in locales:
        return [f"[prompt] base locale '{PROMPT_BASE_LOCALE}' not found (have: {locales})"]

    base_dir = PROMPT_DIR / PROMPT_BASE_LOCALE
    base_text: Dict[str, str] = {}
    base_fields: Dict[str, Set[str]] = {}
    for name in PROMPT_FILES:
        p = base_dir / name
        if not p.exists():
            issues.append(f"[prompt] base missing file: {p}")
            continue
        txt = p.read_text(encoding="utf-8")
        base_text[name] = txt
        base_fields[name] = _template_placeholders(txt)

    for loc in locales:
        loc_dir = PROMPT_DIR / loc
        for name in PROMPT_FILES:
            p = loc_dir / name
            if not p.exists():
                issues.append(f"[prompt] {loc}: missing file: {p}")
                continue
            txt = p.read_text(encoding="utf-8")
            fields = _template_placeholders(txt)
            base = base_fields.get(name)
            if base is None:
                continue
            if fields != base:
                issues.append(f"[prompt] {loc}: placeholder mismatch in {name}: base={sorted(base)} vs {sorted(fields)}")

    return issues


def main() -> int:
    issues: List[str] = []
    issues.extend(check_ui())
    issues.extend(check_prompts())

    if issues:
        for i in issues:
            print(i, file=sys.stderr)
        print(f"\nFound {len(issues)} issue(s).", file=sys.stderr)
        return 1

    print("i18n check: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

