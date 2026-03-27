#!/usr/bin/env python3
"""Staged evaluation for Hyperagent generations.

Mirrors generate_loop.py's evaluation logic:
1. Staged eval: run cheap eval (fraction of budget) → check threshold
2. Full eval: if staged eval passes, run full evaluation
3. Update metadata with results

Usage:
    export HYPERAGENT_METRIC=accuracy
    python run_eval.py --output-dir <dir> --genid <genid> \
        --eval-command "python eval.py" [--project-root <dir>] \
        [--skip-staged-eval] [--timeout 21600]
"""

import argparse
import json
import math
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from utils.gl_utils import get_score, update_node_metadata
from utils.domain_utils import get_domain_stagedeval_frac


def _write_eval_report(output_dir: str, genid, metrics: dict):
    eval_dir = os.path.join(output_dir, f"gen_{genid}", "ml_eval")
    os.makedirs(eval_dir, exist_ok=True)
    with open(os.path.join(eval_dir, "report.json"), "w") as f:
        json.dump(metrics, f, indent=4)


def _run_command(cmd: str, cwd: str, timeout: int, env: dict | None = None) -> dict | None:
    """Run a command, parse JSON metrics from last line of stdout."""
    run_env = {**os.environ, **(env or {})}
    try:
        result = subprocess.run(
            cmd, shell=True, cwd=cwd, env=run_env,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return None
    if result.returncode != 0:
        return None
    for line in reversed(result.stdout.strip().split("\n")):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None


def main():
    parser = argparse.ArgumentParser(description="Staged evaluation for a generation")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--genid", required=True)
    parser.add_argument("--eval-command", required=True)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--skip-staged-eval", action="store_true")
    parser.add_argument("--timeout", type=int, default=21600, help="Eval timeout in seconds")
    parser.add_argument("--max-attempts", type=int, default=3, help="Retry count on eval failure")
    args = parser.parse_args()

    metric = os.environ.get("HYPERAGENT_METRIC", "loss")
    genid = args.genid
    try:
        genid = int(genid)
    except ValueError:
        pass

    staged_frac = get_domain_stagedeval_frac("ml")
    run_full_eval = False
    metrics = None

    # Stage 1: Staged evaluation (cheap, fraction of budget)
    if not args.skip_staged_eval:
        staged_env = {"HYPERAGENT_EVAL_FRAC": str(staged_frac)}
        for attempt in range(args.max_attempts):
            staged_metrics = _run_command(
                args.eval_command, args.project_root, args.timeout, env=staged_env
            )
            if staged_metrics is not None:
                break
        else:
            staged_metrics = None

        if staged_metrics and metric in staged_metrics:
            staged_score = staged_metrics[metric]
            # Check threshold: score must be non-null and > 0
            # (mirrors generate_loop.py: `x is not None and x > 0`)
            if staged_score is not None and not math.isnan(staged_score) and staged_score > 0:
                run_full_eval = True
            _write_eval_report(args.output_dir, genid, staged_metrics)
        else:
            # Staged eval failed — skip full eval
            update_node_metadata(args.output_dir, genid, {
                "valid_parent": False,
                "run_full_eval": False,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            print(json.dumps({
                "genid": str(genid),
                "status": "staged_eval_failed",
                "run_full_eval": False,
            }))
            return
    else:
        run_full_eval = True

    # Stage 2: Full evaluation
    if run_full_eval:
        for attempt in range(args.max_attempts):
            metrics = _run_command(
                args.eval_command, args.project_root, args.timeout
            )
            if metrics is not None:
                break
        else:
            metrics = None

    valid = metrics is not None and metric in (metrics or {})
    score = metrics.get(metric) if metrics else None
    if score is not None and isinstance(score, float) and math.isnan(score):
        score = None
        valid = False

    if metrics:
        _write_eval_report(args.output_dir, genid, metrics)

    update_node_metadata(args.output_dir, genid, {
        "valid_parent": valid,
        "run_full_eval": run_full_eval,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })

    print(json.dumps({
        "genid": str(genid),
        "status": "evaluated" if valid else "failed",
        "score": score,
        "run_full_eval": run_full_eval,
    }))


if __name__ == "__main__":
    main()
