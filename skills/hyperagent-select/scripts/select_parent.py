#!/usr/bin/env python3
"""Select a parent from the Hyperagent archive.

Wraps gl_utils.select_parent() with retry logic matching generate_loop.py.

Usage:
    export HYPERAGENT_METRIC=accuracy
    python select_parent.py --output-dir <dir> [--strategy score_child_prop] [--max-attempts 10]
"""

import argparse
import json
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from utils.gl_utils import get_score, load_archive_data, select_parent


def _load_archive(output_dir: str) -> list:
    archive_file = os.path.join(output_dir, "archive.jsonl")
    if not os.path.exists(archive_file):
        return []
    data = load_archive_data(archive_file, last_only=True)
    if isinstance(data, dict):
        return data.get("archive", [])
    return []


def main():
    parser = argparse.ArgumentParser(description="Select parent from archive")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--strategy", default="score_child_prop",
                        choices=["best", "latest", "random", "score_prop", "score_child_prop"])
    parser.add_argument("--max-attempts", type=int, default=10,
                        help="Retry count if selection fails (mirrors generate_loop.py)")
    args = parser.parse_args()

    archive = _load_archive(args.output_dir)
    if not archive:
        print(json.dumps({"error": "Archive is empty. Run init first."}))
        sys.exit(1)

    # Retry logic from generate_loop.py select_next_parent_container
    selected = None
    for attempt in range(args.max_attempts):
        try:
            selected = select_parent(archive, args.output_dir, ["ml"], method=args.strategy)
            if selected is not None:
                break
        except Exception:
            if attempt == args.max_attempts - 1:
                raise
            continue

    if selected is None:
        print(json.dumps({"error": "Parent selection failed after max attempts"}))
        sys.exit(1)

    score = get_score("ml", args.output_dir, selected)

    # Read metadata for extra info
    meta_path = os.path.join(args.output_dir, f"gen_{selected}", "metadata.json")
    code_branch = "main"
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            meta = json.load(f)
        code_branch = meta.get("code_branch", "main")

    print(json.dumps({
        "genid": str(selected),
        "code_branch": code_branch,
        "fitness_score": score,
        "strategy": args.strategy,
    }))


if __name__ == "__main__":
    main()
