#!/usr/bin/env python3
"""Build a compact Markdown context bundle from the best Hyperagent archive entries.

Follows the same pattern as shinka-inspect/scripts/inspect_best_programs.py.

Usage:
    export HYPERAGENT_METRIC=accuracy
    python inspect_best.py --output-dir <dir> [--k 5] [--out <path>] [--include-lineage]
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from utils.gl_utils import get_score, is_starting_node, load_archive_data


def _load_archive(output_dir: str) -> list:
    archive_file = os.path.join(output_dir, "archive.jsonl")
    if not os.path.exists(archive_file):
        return []
    data = load_archive_data(archive_file, last_only=True)
    if isinstance(data, dict):
        return data.get("archive", [])
    return []


def _read_metadata(output_dir: str, genid) -> dict:
    meta_path = os.path.join(output_dir, f"gen_{genid}", "metadata.json")
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            return json.load(f)
    return {}


def _trace_lineage(output_dir: str, genid) -> list:
    chain = []
    current = genid
    while current is not None:
        chain.append(str(current))
        meta = _read_metadata(output_dir, current)
        current = meta.get("parent_genid")
    chain.reverse()
    return chain


def main():
    parser = argparse.ArgumentParser(
        description="Extract top Hyperagent archive entries as Markdown context bundle"
    )
    parser.add_argument("--output-dir", required=True,
                        help="Path to Hyperagent output directory with gen_X/ dirs")
    parser.add_argument("--k", type=int, default=5,
                        help="Number of top entries to include")
    parser.add_argument("--out", default=None,
                        help="Output Markdown file path (default: <output-dir>/hyperagent_inspect.md)")
    parser.add_argument("--include-lineage", action="store_true", default=True,
                        help="Include lineage chains in output")
    parser.add_argument("--no-include-lineage", dest="include_lineage", action="store_false")
    args = parser.parse_args()

    output_dir = args.output_dir
    archive = _load_archive(output_dir)
    if not archive:
        print("No archive found.", file=sys.stderr)
        sys.exit(1)

    # Collect scored entries
    scored = []
    for genid in archive:
        score = get_score("ml", output_dir, genid)
        if score is not None:
            meta = _read_metadata(output_dir, genid)
            scored.append({
                "genid": genid,
                "score": score,
                "mutation_type": meta.get("mutation_type"),
                "mutation_description": meta.get("mutation_description"),
                "code_branch": meta.get("code_branch"),
                "parent_genid": meta.get("parent_genid"),
                "valid": meta.get("valid_parent", False),
            })

    scored.sort(key=lambda e: e["score"], reverse=True)
    selected = scored[:args.k]

    # Build Markdown
    now = datetime.now(timezone.utc).isoformat()
    lines = []
    lines.append("# Hyperagent Inspect Context Bundle")
    lines.append("")
    lines.append("## Run Metadata")
    lines.append(f"- Generated (UTC): `{now}`")
    lines.append(f"- Source: `{output_dir}`")
    lines.append(f"- Archive size: `{len(archive)}`")
    lines.append(f"- Scored entries: `{len(scored)}`")
    lines.append(f"- Requested k: `{args.k}`")
    lines.append(f"- Included: `{len(selected)}`")
    if scored:
        lines.append(f"- Best score: `{scored[0]['score']}`")
    lines.append("")

    # Ranking table
    lines.append("## Ranking")
    lines.append("")
    lines.append("| Rank | GenID | Score | Mutation | Parent |")
    lines.append("|---:|---|---:|---|---|")
    for rank, entry in enumerate(selected, start=1):
        lines.append(
            f"| {rank} | {entry['genid']} | {entry['score']:.6f} "
            f"| {entry.get('mutation_type', 'N/A')} "
            f"| {entry.get('parent_genid', 'N/A')} |"
        )
    lines.append("")

    # Per-entry details
    lines.append("## Variant Details")
    lines.append("")
    for rank, entry in enumerate(selected, start=1):
        lines.append(f"### Rank {rank} - {entry['genid']}")
        lines.append(f"- Score: `{entry['score']:.6f}`")
        lines.append(f"- Mutation type: `{entry.get('mutation_type', 'N/A')}`")
        lines.append(f"- Description: {entry.get('mutation_description', 'N/A')}")
        lines.append(f"- Code branch: `{entry.get('code_branch', 'N/A')}`")
        lines.append(f"- Parent: `{entry.get('parent_genid', 'N/A')}`")

        if args.include_lineage:
            lineage = _trace_lineage(output_dir, entry["genid"])
            lines.append(f"- Lineage: {' → '.join(lineage)}")
        lines.append("")

    markdown = "\n".join(lines)

    # Write output
    out_path = args.out or os.path.join(output_dir, "hyperagent_inspect.md")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(markdown, encoding="utf-8")

    print(f"Hyperagent Inspect complete: archive={len(archive)}, scored={len(scored)}, "
          f"selected={len(selected)}, out={out_path}")


if __name__ == "__main__":
    main()
