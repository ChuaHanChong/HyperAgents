---
name: hyperagent-inspect
description: Extract the best archive entries from a Hyperagent run and produce a compact Markdown context bundle for iteration planning and reporting.
disable-model-invocation: true
user-invocable: false
---

# Hyperagent Inspect Skill

Extract the strongest code variants from a Hyperagent evolutionary archive and package them into a context bundle that agents can load directly.

## When to Use
Use this skill when:
- An evolutionary run has produced results in the archive
- You want to inspect top-performing variants before the next batch
- You want a compact context artifact for reporting or planning
- You need to summarize the archive for a human or another agent

Do not use this skill when:
- The archive hasn't been initialized (use `hyperagent-init` first)
- You need to modify the archive (use `hyperagent-archive` instead)

## What is Hyperagent Inspect?
This skill reads the Hyperagent archive (gen_X/ directories + archive.jsonl) and produces a Markdown summary of the top-performing variants, including their code changes, fitness scores, lineage, and mutation history.

Repo and documentation: https://github.com/facebookresearch/Hyperagents

## Workflow

1. Run the inspect script:
```bash
python skills/hyperagent-inspect/scripts/inspect_best.py \
  --output-dir <output_dir> \
  --k 5 \
  [--out <output_path>] \
  [--include-lineage]
```

2. The script outputs a Markdown file with:
   - Run metadata (archive size, generation count, best score)
   - Ranking table (top K entries by fitness)
   - Per-entry details (genid, parent, mutation type, description, score)
   - Lineage chains (if `--include-lineage`)

3. Load the output file for planning next steps or generating reports.

## Output Format

The Markdown bundle follows this structure:
```markdown
# Hyperagent Inspect Context Bundle

## Run Metadata
- Archive size: 15
- Generations: 12
- Best score: 0.912

## Ranking
| Rank | GenID | Score | Mutation | Parent |
|---:|---|---:|---|---|
| 1 | gen-12 | 0.912 | llm_patch | gen-8 |
| 2 | gen-8 | 0.895 | research_implement | gen-3 |
...

## Variant Details
### Rank 1 - gen-12
- Mutation: Added residual connections
- Parent: gen-8 (score: 0.895)
- Lineage: initial → gen-3 → gen-8 → gen-12
```
