---
name: hyperagent-init
description: Create the evolutionary code archive from baseline results and existing implementation branches.
disable-model-invocation: true
user-invocable: false
---

# Hyperagent Init Skill

## Overview

Create the initial code archive (`experiments/code-archive.jsonl`) from baseline results and any existing implementation branches from Phase 6. This seeds the evolutionary population for archive-based code search.

## Input Parameters

- `project_root`: Path to the user's project
- `exp_root`: Path to experiments directory (e.g., `<project_root>/experiments`)

## Steps

### Step 1: Initialize Archive from Baseline

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/hyperagent_adapter.py <exp_root> init
```

This reads `experiments/results/baseline.json` to create gen-000, and seeds any validated branches from `experiments/results/implementation-manifest.json` as gen-001, gen-002, etc.

### Step 2: Verify Archive

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/hyperagent_adapter.py <exp_root> stats
```

Confirm the archive was created and has the expected number of entries.

### Step 3: Seed from Existing Experiment Results (Optional)

If Phase 7 HP tuning has already produced experiment results with different code branches, update the archive with fitness scores:

For each unique `code_branch` in `experiments/results/exp-*.json`:
1. Find the best experiment result for that branch
2. Call `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/hyperagent_adapter.py <exp_root> add '<json>'` with the branch info and best metric as `fitness_score`

This ensures the archive reflects all prior work, not just Phase 6 branches.

## Output

```json
{
  "status": "initialized",
  "entries": 5,
  "archive_path": "experiments/code-archive.jsonl"
}
```

## Important Rules

- **Idempotent**: If the archive already exists, report `already_initialized` and do not modify it.
- **Baseline required**: If `baseline.json` doesn't exist, report an error. The archive needs a gen-000 reference point.
- **Branch validation**: Only seed branches that still exist in git (`git branch --list 'ml-opt/*'`). Skip deleted branches.
