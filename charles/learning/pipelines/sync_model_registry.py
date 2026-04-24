from __future__ import annotations

import argparse
import json
from pathlib import Path

from learning.model_registry import sync_model_registry


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate CHARLES model cards and registry from local run artifacts.")
    parser.add_argument(
        "--workspace-root",
        default=None,
        help="Optional path to the learning workspace root. Defaults to the local learning/ directory.",
    )
    args = parser.parse_args()

    summary = sync_model_registry(Path(args.workspace_root) if args.workspace_root else None)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
