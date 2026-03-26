---
name: hyperagent-archive
description: Update the evolutionary code archive with evaluation results and track lineage, operator effectiveness, and mutation outcomes.
disable-model-invocation: true
user-invocable: false
---

# Hyperagent Archive Skill

## Overview

Update the evolutionary code archive after a generation is evaluated. Records fitness scores, lineage, mutation type, and operator effectiveness. This maintains the population that drives parent selection for future generations.

## Input Parameters

- `exp_root`: Path to experiments directory
- `genid`: Generation ID of the evaluated variant
- `parent_genid`: Parent's genid
- `code_branch`: Git branch name
- `mutation_type`: `"llm_patch"` | `"shinka_evolve"` | `"research_implement"`
- `mutation_description`: Human-readable description of what was changed
- `fitness_score`: Final metric value (from full evaluation or staged eval)
- `staged_score`: Staged eval score (if Stage 1 was run)
- `status`: `"evaluated"` | `"filtered"` | `"failed"`
- `best_exp_id`: ID of the best experiment result for this variant
- `best_hp_config`: HP config that achieved the best result (if HP-tuned)

## Step 1: Add Archive Entry

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/hyperagent_adapter.py <exp_root> add '{
  "genid": "<genid>",
  "parent_genid": "<parent_genid>",
  "code_branch": "<code_branch>",
  "mutation_type": "<mutation_type>",
  "mutation_description": "<description>",
  "fitness_score": <score_or_null>,
  "staged_score": <staged_score_or_null>,
  "best_hp_config": <config_or_null>,
  "best_exp_id": "<exp_id_or_null>",
  "status": "<status>"
}'
```

The adapter auto-computes lineage (from parent's lineage + this genid), lineage_depth, created_at, and increments the parent's `num_children`.

## Step 1b: Update Fitness After HP Tuning

After HP tuning completes on a code variant and produces a better result than the initial staged eval, update the archive entry's fitness score:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/hyperagent_adapter.py <exp_root> update-fitness <genid> <new_fitness> [best_exp_id] [best_hp_config_json]
```

This ensures parent selection reflects HP-tuned results, not just initial staged eval scores. Without this, the archive is blind to HP improvements and may under-prioritize variants that became strong after tuning.

## Step 2: Log to Behavioral Memory

If the mutation improved over the parent, log the effective pattern:

```bash
python3 scripts/goal_memory.py <exp_root> log-behavior hyperagent_mutation '{
  "genid": "<genid>",
  "mutation_type": "<mutation_type>",
  "improvement_pct": <pct>,
  "parent_fitness": <parent_score>,
  "child_fitness": <child_score>,
  "insight": "<what made this mutation effective>"
}'
```

## Step 3: Update Research Agenda (if applicable)

If the mutation was based on a research technique:

```bash
python3 scripts/error_tracker.py <exp_root> agenda update '<technique_name>' '<status: tried|improved|dead_end>'
```

If the mutation failed completely, consider adding to the dead-end catalog:

```bash
python3 scripts/error_tracker.py <exp_root> dead-end add '<technique_name>' '<reason>'
```

## Step 4: Report Archive State

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/hyperagent_adapter.py <exp_root> stats
```

Report current archive statistics to the orchestrator for decision-making.

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
    "mean_score": 0.84,
    "max_lineage_depth": 3
  }
}
```

## Important Rules

- **Always archive, even failures.** Failed and filtered entries are valuable — they prevent the archive from re-exploring dead paths.
- **Lineage is automatic.** The adapter computes lineage from the parent. Don't construct it manually.
- **Concurrent safety.** The adapter uses file locks. Multiple agents can safely archive simultaneously.
- **Dead-end logging.** If ALL experiments on a branch fail (diverge, timeout, or error), add the technique to dead-ends to prevent future re-proposals.
