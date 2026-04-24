from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def find_dvc_snapshot_for_path(path: str | Path) -> Path | None:
    target = Path(path).resolve()
    candidate = target.with_suffix(target.suffix + ".dvc") if target.suffix else target.parent / f"{target.name}.dvc"
    if candidate.exists():
        return candidate
    sibling = target.parent / f"{target.name}.dvc"
    if sibling.exists():
        return sibling
    return None


def read_dvc_snapshot_metadata(path: str | Path) -> dict[str, Any] | None:
    snapshot_path = find_dvc_snapshot_for_path(path)
    if snapshot_path is None or not snapshot_path.exists():
        return None
    payload = yaml.safe_load(snapshot_path.read_text(encoding="utf-8")) or {}
    outs = payload.get("outs") or []
    if not outs:
        return {
            "snapshot_path": str(snapshot_path),
            "tracked_path": None,
            "md5": None,
            "size": None,
            "nfiles": None,
        }
    first = outs[0]
    tracked_path = first.get("path")
    if tracked_path and not Path(tracked_path).is_absolute():
        tracked_path = str((snapshot_path.parent / tracked_path).resolve())
    return {
        "snapshot_path": str(snapshot_path),
        "tracked_path": tracked_path,
        "md5": first.get("md5"),
        "size": first.get("size"),
        "nfiles": first.get("nfiles"),
    }
