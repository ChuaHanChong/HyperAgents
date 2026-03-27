---
name: hyperagent-init
description: Create the evolutionary code archive from baseline results and optional seed entries for Hyperagent archive-based code search.
disable-model-invocation: true
user-invocable: false
---

# Hyperagent Init Skill

## When to Use
Use this skill when:
- Starting the first Hyperagent evolutionary run (archive doesn't exist)
- A baseline has been established and you need to seed the archive
- Existing code variants should be added as initial population members

Do not use this skill when:
- The archive already exists (init is idempotent but redundant)
- You're in the middle of an evolutionary run (use hyperagent-archive to add entries)

## What is Hyperagent Init?
This skill bootstraps the evolutionary archive for Hyperagents' DGM (Diversity-Generation-Merging) framework. It creates the initial population from a baseline entry and optionally seeds additional entries from prior work.

Repo and documentation: https://github.com/facebookresearch/Hyperagents

## Input Parameters

- `output_dir`: Path to the Hyperagent output directory (will contain `archive.jsonl` and `gen_X/` dirs)
- `baseline_path` (optional): Path to a JSON file with baseline metrics. If not provided, the script searches common locations relative to the output dir.

## Steps

### Step 1: Initialize Archive from Baseline

```bash
export HYPERAGENT_METRIC=<metric_name>
python skills/hyperagent-init/scripts/init_archive.py --output-dir <output_dir> [--baseline-path <path>]
```

The script reads the baseline JSON (expects `{"metrics": {...}}` format) and creates `gen_initial/` with metadata and an eval report containing the baseline metric values.

If a seeding manifest exists (the script checks `<output_dir>/../results/implementation-manifest.json`), validated entries are seeded as additional archive members. The manifest format expects `{"proposals": [{"status": "validated", "branch": "...", "name": "..."}]}`.

### Step 2: Verify Archive

```bash
python skills/hyperagent-archive/scripts/archive_utils.py stats --output-dir <output_dir>
```

Confirm the archive was created with the expected number of entries.

### Step 3: Seed from Existing Results (Optional)

If prior experiment results exist with different code branches, update the archive:

For each existing variant with an evaluation score:
```bash
python skills/hyperagent-archive/scripts/archive_utils.py add --output-dir <output_dir> '<json>'
```

This ensures the archive reflects all prior work.

## Output

```json
{
  "status": "initialized",
  "entries": 5
}
```

## Important Rules

- **Idempotent**: If the archive already exists, reports `already_initialized` and does not modify it.
- **Baseline recommended**: If no baseline file is found, initializes with `fitness=0.0` and emits a warning.
- **Branch validation**: When seeding from prior variants, only include branches that still exist in git. Skip deleted branches.
