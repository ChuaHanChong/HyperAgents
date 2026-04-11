#!/usr/bin/env python3
"""Archive management utilities for Hyperagent.

Provides subcommands: add, update-fitness, stats, best, lineage, operator-stats, prune.
All operations use gl_utils.py directly.

Usage:
    export HYPERAGENT_METRIC=accuracy
    python archive_utils.py add --output-dir <dir> '<json>'
    python archive_utils.py stats --output-dir <dir>
    python archive_utils.py best --output-dir <dir> [-n 5]
    python archive_utils.py lineage --output-dir <dir> <genid>
    python archive_utils.py update-fitness --output-dir <dir> <genid> <score>
    python archive_utils.py operator-stats --output-dir <dir>
    python archive_utils.py prune --output-dir <dir>
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from utils.gl_utils import (
    backpropagate_ucb,
    get_score,
    is_starting_node,
    load_archive_data,
    update_and_save_archive,
    update_node_metadata,
)


def _load_archive(output_dir: str) -> list:
    archive_file = os.path.join(output_dir, "archive.jsonl")
    if not os.path.exists(archive_file):
        return []
    data = load_archive_data(archive_file, last_only=True)
    if isinstance(data, dict):
        return data.get("archive", [])
    return []


def _read_all_metadata(output_dir: str) -> dict:
    """Return {genid: metadata} for every gen_<id>/ subdir.

    Important: keys are stored in BOTH string and int form when numeric,
    so that callers iterating `_load_archive()` (which may yield strings
    like "1" or ints like 1 depending on how archive.jsonl was written)
    can look up metadata without type-mismatch misses. The previous
    implementation stored only the int form for numeric genids, causing
    stats() and operator_stats() to see every lookup as empty and report
    mutation_type as "none".
    """
    result = {}
    if not os.path.isdir(output_dir):
        return result
    for name in os.listdir(output_dir):
        if not name.startswith("gen_"):
            continue
        meta_path = os.path.join(output_dir, name, "metadata.json")
        if os.path.exists(meta_path):
            with open(meta_path) as f:
                meta = json.load(f)
            raw = name[4:]
            result[raw] = meta  # always keyed by the string form
            try:
                result[int(raw)] = meta  # also the int form if numeric
            except ValueError:
                pass
    return result


def _write_eval_report(output_dir: str, genid, metrics: dict):
    eval_dir = os.path.join(output_dir, f"gen_{genid}", "ml_eval")
    os.makedirs(eval_dir, exist_ok=True)
    with open(os.path.join(eval_dir, "report.json"), "w") as f:
        json.dump(metrics, f, indent=4)


def _write_metadata(output_dir: str, genid, metadata: dict):
    gen_path = os.path.join(output_dir, f"gen_{genid}")
    os.makedirs(gen_path, exist_ok=True)
    with open(os.path.join(gen_path, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=4)


# --- Subcommands ---

def add(args):
    output_dir = args.output_dir
    metric = os.environ.get("HYPERAGENT_METRIC", "loss")
    entry = json.loads(args.entry_json)
    archive = _load_archive(output_dir)
    genid = entry.get("genid", len(archive))

    if os.path.exists(os.path.join(output_dir, f"gen_{genid}", "metadata.json")):
        print(json.dumps({"error": f"Duplicate genid: {genid}"}))
        sys.exit(1)

    _write_metadata(output_dir, genid, {
        "parent_genid": entry.get("parent_genid"),
        "valid_parent": entry.get("status") == "evaluated",
        "run_full_eval": entry.get("status") == "evaluated",
        "status": entry.get("status", "pending"),
        "mutation_type": entry.get("mutation_type"),
        "mutation_description": entry.get("mutation_description"),
        "code_branch": entry.get("code_branch"),
        "prev_patch_files": entry.get("prev_patch_files", []),
        "curr_patch_files": entry.get("curr_patch_files", []),
        "created_at": entry.get("created_at", datetime.now(timezone.utc).isoformat()),
    })

    score = entry.get("fitness_score")
    if score is not None:
        _write_eval_report(output_dir, genid, {metric: score})

    update_and_save_archive(output_dir, archive, genid)
    print(json.dumps({"status": "added", "genid": str(genid)}))


def update_fitness(args):
    output_dir = args.output_dir
    metric = os.environ.get("HYPERAGENT_METRIC", "loss")
    genid = args.genid
    try:
        genid = int(genid)
    except ValueError:
        pass

    meta_path = os.path.join(output_dir, f"gen_{genid}", "metadata.json")
    if not os.path.exists(meta_path):
        print(json.dumps({"error": f"genid {genid} not found"}))
        sys.exit(1)

    _write_eval_report(output_dir, genid, {metric: args.score})
    update_node_metadata(output_dir, genid, {
        "valid_parent": True,
        "run_full_eval": True,
    })
    if args.exp_id:
        update_node_metadata(output_dir, genid, {"best_exp_id": args.exp_id})

    print(json.dumps({"status": "updated", "genid": str(genid), "fitness_score": args.score}))


def stats(args):
    output_dir = args.output_dir
    archive = _load_archive(output_dir)
    if not archive:
        print(json.dumps({"entries": 0}))
        return

    all_meta = _read_all_metadata(output_dir)
    scores = []
    evaluated = failed = filtered = pending = 0
    mutation_types = {}

    for genid in archive:
        meta = all_meta.get(genid, {})
        score = get_score("ml", output_dir, genid)
        valid = meta.get("valid_parent", False)
        run_full = meta.get("run_full_eval", False)

        status = meta.get("status", "")
        if valid and score is not None:
            evaluated += 1
            scores.append(score)
        elif status == "filtered":
            filtered += 1
        elif not run_full and not is_starting_node(genid):
            pending += 1
        elif not valid and not is_starting_node(genid):
            failed += 1

        mt = meta.get("mutation_type", "none")
        mutation_types[mt] = mutation_types.get(mt, 0) + 1

    print(json.dumps({
        "total_entries": len(archive),
        "evaluated": evaluated,
        "failed": failed,
        "filtered": filtered,
        "pending": pending,
        "best_score": max(scores) if scores else None,
        "worst_score": min(scores) if scores else None,
        "mean_score": sum(scores) / len(scores) if scores else None,
        "mutation_types": mutation_types,
    }))


def best(args):
    output_dir = args.output_dir
    archive = _load_archive(output_dir)
    all_meta = _read_all_metadata(output_dir)
    scored = []
    for genid in archive:
        score = get_score("ml", output_dir, genid)
        if score is not None:
            meta = all_meta.get(genid, {})
            scored.append({
                "genid": str(genid),
                "fitness_score": score,
                "code_branch": meta.get("code_branch"),
                "mutation_type": meta.get("mutation_type"),
                "mutation_description": meta.get("mutation_description"),
            })
    scored.sort(key=lambda e: e["fitness_score"], reverse=True)
    print(json.dumps(scored[:args.n]))


def lineage(args):
    output_dir = args.output_dir
    genid = args.genid
    try:
        genid = int(genid)
    except ValueError:
        pass

    chain = []
    current = genid
    while current is not None:
        score = get_score("ml", output_dir, current)
        meta_path = os.path.join(output_dir, f"gen_{current}", "metadata.json")
        meta = {}
        if os.path.exists(meta_path):
            with open(meta_path) as f:
                meta = json.load(f)
        chain.append({
            "genid": str(current),
            "mutation_type": meta.get("mutation_type"),
            "mutation_description": meta.get("mutation_description"),
            "fitness_score": score,
            "code_branch": meta.get("code_branch"),
        })
        current = meta.get("parent_genid")
    chain.reverse()
    print(json.dumps({"genid": str(args.genid), "lineage": chain}))


def _resolve_baseline_for_operator_stats(output_dir: str, archive: list):
    """Return (baseline_score, lower_is_better) for operator_stats comparisons.

    Priority:
      1. ``<exp_root>/results/baseline.json`` via HYPERAGENT_METRIC env var.
         This is the ground truth — set at Phase 3 and checksum-protected.
      2. Fall back to the first archive entry's eval report (legacy behaviour).

    ``exp_root`` is resolved in this order so the experiment folder can live
    anywhere on disk:
      1. ``ML_OPT_EXP_ROOT`` env var (orchestrator may set explicitly when
         the layout differs from convention)
      2. Parent of ``output_dir`` (plugin convention: ``<exp_root>/hyperagent/``)

    Metric direction is resolved in this order:
      1. ``HYPERAGENT_METRIC_DIRECTION`` env var (``lower``/``higher``)
      2. ``<exp_root>/pipeline-state.json`` ``user_choices.lower_is_better``
      3. Fallback: ``lower`` (since ``loss`` is the default metric)
    This lets the orchestrator pass direction through user_choices without
    callers needing to set an extra env var.
    """
    metric = os.environ.get("HYPERAGENT_METRIC", "loss")
    exp_root = os.environ.get("ML_OPT_EXP_ROOT") or os.path.dirname(
        os.path.abspath(output_dir)
    )

    # Direction: env var wins, then pipeline-state.json, then default lower
    direction_env = os.environ.get("HYPERAGENT_METRIC_DIRECTION")
    lower_is_better = True  # default
    if direction_env:
        lower_is_better = direction_env.lower() != "higher"
    else:
        state_path = os.path.join(exp_root, "pipeline-state.json")
        if os.path.isfile(state_path):
            try:
                with open(state_path) as f:
                    state = json.load(f)
                lib = (state.get("user_choices") or {}).get("lower_is_better")
                if isinstance(lib, bool):
                    lower_is_better = lib
            except (json.JSONDecodeError, OSError):
                pass

    # Primary source: baseline.json
    baseline_json = os.path.join(exp_root, "results", "baseline.json")
    if os.path.isfile(baseline_json):
        try:
            with open(baseline_json) as f:
                data = json.load(f)
            metrics = data.get("metrics") or {}
            val = metrics.get(metric)
            if isinstance(val, (int, float)):
                return float(val), lower_is_better
        except (json.JSONDecodeError, OSError):
            pass

    # Legacy fallback: first archive entry
    if archive:
        legacy = get_score("ml", output_dir, archive[0])
        if legacy is not None:
            return legacy, lower_is_better
    return None, lower_is_better


def operator_stats(args):
    output_dir = args.output_dir
    archive = _load_archive(output_dir)
    all_meta = _read_all_metadata(output_dir)
    baseline_score, lower_is_better = _resolve_baseline_for_operator_stats(
        output_dir, archive
    )

    operators = {}
    for genid in archive:
        meta = all_meta.get(genid, {})
        mt = meta.get("mutation_type")
        if mt is None:
            continue
        if mt not in operators:
            operators[mt] = {"attempts": 0, "improvements": 0, "scores": []}
        operators[mt]["attempts"] += 1
        score = get_score("ml", output_dir, genid)
        if score is not None:
            operators[mt]["scores"].append(score)
            if baseline_score is not None:
                improved = (
                    score < baseline_score if lower_is_better
                    else score > baseline_score
                )
                if improved:
                    operators[mt]["improvements"] += 1

    result = {}
    for mt, data in operators.items():
        s = data["scores"]
        result[mt] = {
            "attempts": data["attempts"],
            "improvements": data["improvements"],
            "improvement_rate": data["improvements"] / data["attempts"] if data["attempts"] > 0 else 0,
            "mean_score": sum(s) / len(s) if s else None,
            "best_score": max(s) if s else None,
        }
    print(json.dumps(result))


def backpropagate(args):
    output_dir = args.output_dir
    metric = os.environ.get("HYPERAGENT_METRIC", "loss")
    archive = _load_archive(output_dir)

    # Collect all fitness scores for normalization
    all_scores = []
    for gid in archive:
        s = get_score("ml", output_dir, gid)
        if s is not None:
            all_scores.append(s)

    result = backpropagate_ucb(output_dir, args.genid, args.score, all_scores)
    print(json.dumps(result))


def prune(args):
    output_dir = args.output_dir
    archive = _load_archive(output_dir)
    all_meta = _read_all_metadata(output_dir)

    alive = set()
    for genid in archive:
        if all_meta.get(genid, {}).get("valid_parent", False) or is_starting_node(genid):
            current = genid
            while current is not None:
                alive.add(current)
                current = all_meta.get(current, {}).get("parent_genid")

    pruned = [str(g) for g in archive if g not in alive]
    print(json.dumps({"pruned": pruned, "remaining": len(archive) - len(pruned)}))


# --- CLI ---

def main():
    parser = argparse.ArgumentParser(description="Hyperagent archive utilities")
    subparsers = parser.add_subparsers(dest="command")

    p_add = subparsers.add_parser("add")
    p_add.add_argument("--output-dir", required=True)
    p_add.add_argument("entry_json")

    p_uf = subparsers.add_parser("update-fitness")
    p_uf.add_argument("--output-dir", required=True)
    p_uf.add_argument("genid")
    p_uf.add_argument("score", type=float)
    p_uf.add_argument("--exp-id", default=None)

    p_stats = subparsers.add_parser("stats")
    p_stats.add_argument("--output-dir", required=True)

    p_best = subparsers.add_parser("best")
    p_best.add_argument("--output-dir", required=True)
    p_best.add_argument("-n", type=int, default=5)

    p_lin = subparsers.add_parser("lineage")
    p_lin.add_argument("--output-dir", required=True)
    p_lin.add_argument("genid")

    p_ops = subparsers.add_parser("operator-stats")
    p_ops.add_argument("--output-dir", required=True)

    p_prune = subparsers.add_parser("prune")
    p_prune.add_argument("--output-dir", required=True)

    p_bp = subparsers.add_parser("backpropagate")
    p_bp.add_argument("--output-dir", required=True)
    p_bp.add_argument("genid")
    p_bp.add_argument("score", type=float)

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        sys.exit(0)

    {"add": add, "update-fitness": update_fitness, "stats": stats,
     "best": best, "lineage": lineage, "operator-stats": operator_stats,
     "prune": prune, "backpropagate": backpropagate}[args.command](args)


if __name__ == "__main__":
    main()
