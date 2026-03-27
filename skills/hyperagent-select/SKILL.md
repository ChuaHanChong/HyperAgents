---
name: hyperagent-select
description: Select a parent from the evolutionary code archive using Hyperagents' parent selection algorithms (sigmoid score weighting + diversity penalty).
disable-model-invocation: true
user-invocable: false
---

# Hyperagent Select Skill

## When to Use
Use this skill when:
- Starting a new generation and need to pick a parent variant
- The archive has been initialized and contains evaluated entries

Do not use this skill when:
- The archive is empty (use hyperagent-init first)
- You're evaluating or archiving results (use hyperagent-eval or hyperagent-archive)

## What is Hyperagent Select?
This is the **Diversity** operation of the DGM (Diversity-Generation-Merging) framework. It selects a parent code variant from the archive using Hyperagents' exact parent selection algorithms — sigmoid score weighting with optional diversity penalty to prevent lineage collapse.

Repo and documentation: https://github.com/facebookresearch/Hyperagents

## Input Parameters

- `output_dir`: Path to the Hyperagent output directory
- `strategy`: Selection strategy (default: `score_child_prop`)

## Step 1: Choose Strategy

If no strategy is specified, choose based on archive size:

| Archive Size | Recommended Strategy | Rationale |
|---|---|---|
| < 5 entries | `random` | Too few data points for score weighting |
| 5–15 entries | `score_prop` | Enough data for exploitation |
| > 15 entries | `score_child_prop` | Need diversity to prevent convergence |

## Step 2: Select Parent

```bash
export HYPERAGENT_METRIC=<metric_name>
python skills/hyperagent-select/scripts/select_parent.py --output-dir <output_dir> --strategy <strategy>
```

### Five Selection Strategies

| Strategy | Algorithm | When to Use |
|---|---|---|
| `best` | Highest fitness score (greedy) | Exploitation only |
| `latest` | Most recently added entry | Sequential exploration |
| `random` | Uniform random choice | Maximum exploration |
| `score_prop` | `sigmoid(10(s - μ)) / Σ` where μ = top-3 mean | Balanced exploitation |
| `score_child_prop` | `sigmoid(10(s - μ)) × exp(-(children/8)³) / Σ` | Exploitation + diversity (default) |

The sigmoid function concentrates probability on above-average entries while giving some chance to lower-scoring variants. The diversity penalty (`exp(-(children/8)³)`) reduces the probability of parents that already have many children, preventing the archive from collapsing to a single lineage.

Child counts are dynamically computed by scanning metadata for entries whose `parent_genid` matches each candidate — they are not stored separately. Example impact: 0 children → penalty 1.0 (full weight), 8 children → penalty ~0.37, 16 children → penalty ~0.008 (strongly disfavored).

## Step 3: Return Selection

Output the selected parent's genid, code branch, and fitness score for use by `hyperagent-generate`.

## Output

```json
{
  "genid": "gen-003",
  "code_branch": "gen-003-attention-v2",
  "fitness_score": 0.87,
  "strategy": "score_child_prop"
}
```
