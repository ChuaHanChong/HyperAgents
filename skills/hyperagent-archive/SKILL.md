---
name: hyperagent-archive
description: Update the Hyperagent evolutionary code archive with evaluation results and track lineage, operator effectiveness, and mutation outcomes.
disable-model-invocation: true
user-invocable: false
---

# Hyperagent Archive Skill

## When to Use
Use this skill when:
- Adding a new evaluated variant to the archive
- Updating fitness scores after parameter tuning
- Querying archive statistics, top entries, or lineage
- Pruning dead lineages to keep the archive focused

Do not use this skill when:
- The archive doesn't exist yet (use hyperagent-init first)
- You need to evaluate code (use hyperagent-eval)

## What is Hyperagent Archive?
This is the **Merging** operation of the DGM (Diversity-Generation-Merging) framework. It maintains the evolutionary population by recording fitness scores, lineage, mutation types, and operator effectiveness. The archive drives parent selection for future generations.

Repo and documentation: https://github.com/facebookresearch/Hyperagents

## Input Parameters

- `output_dir`: Path to the Hyperagent output directory
- `genid`: Generation ID of the evaluated variant
- `parent_genid`: Parent's genid
- `code_branch`: Git branch name
- `mutation_type`: The mutation operator used (e.g., `"llm_patch"`, `"external_tool"`, `"delegation"`)
- `mutation_description`: Human-readable description of what was changed
- `fitness_score`: Final metric value (from full evaluation or staged eval)
- `status`: `"evaluated"` | `"filtered"` | `"failed"`

## Helper Script

The `archive_utils.py` script provides 7 subcommands:

```bash
export HYPERAGENT_METRIC=<metric_name>

# Add a new entry
python skills/hyperagent-archive/scripts/archive_utils.py add --output-dir <output_dir> '<json>'

# Update fitness after parameter tuning
python skills/hyperagent-archive/scripts/archive_utils.py update-fitness --output-dir <output_dir> <genid> <score> [--exp-id <id>]

# Query archive statistics
python skills/hyperagent-archive/scripts/archive_utils.py stats --output-dir <output_dir>

# Get top N entries by fitness
python skills/hyperagent-archive/scripts/archive_utils.py best --output-dir <output_dir> [-n 5]

# Trace lineage chain
python skills/hyperagent-archive/scripts/archive_utils.py lineage --output-dir <output_dir> <genid>

# Operator effectiveness stats (used by hyperagent-generate to choose mutation operator)
python skills/hyperagent-archive/scripts/archive_utils.py operator-stats --output-dir <output_dir>
# Output: {"llm_patch": {"attempts": 5, "improvements": 3, "improvement_rate": 0.6, "mean_score": 0.82, "best_score": 0.87}, ...}

# Prune dead lineages
python skills/hyperagent-archive/scripts/archive_utils.py prune --output-dir <output_dir>
```

## Step 1: Add Archive Entry

```bash
python skills/hyperagent-archive/scripts/archive_utils.py add --output-dir <output_dir> '{
  "genid": "<genid>",
  "parent_genid": "<parent_genid>",
  "code_branch": "<code_branch>",
  "mutation_type": "<mutation_type>",
  "mutation_description": "<description>",
  "fitness_score": <score_or_null>,
  "status": "<status>"
}'
```

The script auto-computes lineage from the parent, sets `created_at`, and increments the parent's `num_children`.

## Step 1b: Update Fitness After Tuning

After parameter tuning produces a better result than the initial evaluation, update the archive entry's fitness:

```bash
python skills/hyperagent-archive/scripts/archive_utils.py update-fitness --output-dir <output_dir> <genid> <new_fitness> [--exp-id <best_exp_id>]
```

This ensures parent selection reflects tuned results, not just initial scores. Without this, the archive may under-prioritize variants that improved after tuning.

## Step 2: Report Improvement Context

If the mutation improved over the parent, include in the output: `genid`, `mutation_type`, `improvement_pct`, `parent_fitness`, `child_fitness`, and `insight`. The caller can use this for behavioral logging.

## Step 3: Report Archive State

```bash
python skills/hyperagent-archive/scripts/archive_utils.py stats --output-dir <output_dir>
```

## Output Format

```json
{
  "status": "archived",
  "genid": "gen-007",
  "archive_stats": {
    "total_entries": 8,
    "evaluated": 6,
    "filtered": 1,
    "failed": 1,
    "best_score": 0.87,
    "mean_score": 0.84
  }
}
```

## Entry Status and Parent Eligibility

The `status` field determines whether an entry can be selected as a parent in future generations:

- **`evaluated`** — Full evaluation completed. **Can be selected as parent.**
- **`filtered`** — Staged eval failed (below adaptive threshold). Archived for reference but **cannot be selected as parent.**
- **`failed`** — Training crashed or diverged. Archived for debugging but **cannot be selected as parent.**

Filtered and failed entries are still valuable — they prevent the archive from re-exploring the same dead paths.

## Important Rules

- **Always archive, even failures.** Failed and filtered entries prevent re-exploring dead paths.
- **Lineage is automatic.** The script computes lineage from the parent. Don't construct it manually.
- **Concurrent safety.** The script uses file locks for atomic updates.
- **Update fitness after tuning.** Call `update-fitness` so parent selection reflects the best known result for each variant.
