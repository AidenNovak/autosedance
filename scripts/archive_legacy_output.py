#!/usr/bin/env python3

from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path


def main() -> int:
    out_dir = Path(os.getenv("OUTPUT_DIR") or "output")
    out_dir.mkdir(parents=True, exist_ok=True)

    legacy_names = ["videos", "frames", "final", "segments", "input_videos"]
    legacy_paths = [out_dir / n for n in legacy_names if (out_dir / n).exists()]

    if not legacy_paths:
        print("No legacy output directories found.")
        return 0

    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    dest = out_dir / f"_legacy_{stamp}"
    dest.mkdir(parents=True, exist_ok=True)

    for p in legacy_paths:
        target = dest / p.name
        print(f"Move {p} -> {target}")
        shutil.move(str(p), str(target))

    print(f"Archived {len(legacy_paths)} dirs into {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

