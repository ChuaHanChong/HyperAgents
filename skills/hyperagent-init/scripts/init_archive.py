#!/usr/bin/env python3
"""Initialize Hyperagent archive from baseline metrics.

Creates gen_initial/ with metadata and eval report, seeds archive.jsonl.
Optionally seeds from an implementation manifest.

Usage:
    export HYPERAGENT_METRIC=accuracy
    python init_archive.py --output-dir <dir> [--baseline-path <path>]
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow import from submodule root
_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from utils.gl_utils import load_archive_data, update_and_save_archive


def _load_archive(output_dir: str) -> list:
    archive_file = os.path.join(output_dir, "archive.jsonl")
    if not os.path.exists(archive_file):
        return []
    data = load_archive_data(archive_file, last_only=True)
    if isinstance(data, dict):
        return data.get("archive", [])
    return []


def _write_metadata(output_dir: str, genid, metadata: dict):
    gen_path = os.path.join(output_dir, f"gen_{genid}")
    os.makedirs(gen_path, exist_ok=True)
    with open(os.path.join(gen_path, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=4)


def _write_eval_report(output_dir: str, genid, metrics: dict):
    eval_dir = os.path.join(output_dir, f"gen_{genid}", "ml_eval")
    os.makedirs(eval_dir, exist_ok=True)
    with open(os.path.join(eval_dir, "report.json"), "w") as f:
        json.dump(metrics, f, indent=4)


def main():
    parser = argparse.ArgumentParser(description="Initialize Hyperagent archive")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--baseline-path", default=None)
    args = parser.parse_args()

    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)
    metric = os.environ.get("HYPERAGENT_METRIC", "loss")

    archive = _load_archive(output_dir)
    if archive:
        print(json.dumps({"status": "already_initialized", "entries": len(archive)}))
        return

    # Find baseline
    baseline_path = args.baseline_path
    if not baseline_path:
        for candidate in [
            os.path.join(output_dir, "..", "results", "baseline.json"),
            os.path.join(output_dir, "results", "baseline.json"),
        ]:
            if os.path.exists(candidate):
                baseline_path = candidate
                break

    baseline_metrics = {}
    warning = None
    if baseline_path and os.path.exists(baseline_path):
        with open(baseline_path) as f:
            baseline = json.load(f)
        baseline_metrics = baseline.get("metrics", {})
    else:
        warning = "baseline.json not found — using fitness=0.0"
        baseline_metrics = {metric: 0.0}

    _write_metadata(output_dir, "initial", {
        "parent_genid": None,
        "valid_parent": True,
        "run_full_eval": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    _write_eval_report(output_dir, "initial", baseline_metrics)

    archive = []
    update_and_save_archive(output_dir, archive, "initial")

    # Seed from implementation manifest
    manifest_path = os.path.join(output_dir, "..", "results", "implementation-manifest.json")
    if os.path.exists(manifest_path):
        with open(manifest_path) as f:
            manifest = json.load(f)
        for i, prop in enumerate(manifest.get("proposals", []), start=1):
            if prop.get("status") != "validated":
                continue
            _write_metadata(output_dir, i, {
                "parent_genid": "initial",
                "valid_parent": False,
                "run_full_eval": False,
                "mutation_type": "research_implement",
                "code_branch": prop.get("branch", prop.get("slug", "unknown")),
                "mutation_description": prop.get("name", "Research proposal"),
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            update_and_save_archive(output_dir, archive, i)

    result = {"status": "initialized", "entries": len(archive)}
    if warning:
        result["warning"] = warning
    print(json.dumps(result))


if __name__ == "__main__":
    main()
