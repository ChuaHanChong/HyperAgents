---
name: hyperagent-select
description: Select a parent from the evolutionary code archive using Hyperagents' parent selection algorithms.
disable-model-invocation: true
user-invocable: false
---

# Hyperagent Select Skill

## Overview

Select a parent code variant from the archive for the next generation of evolutionary code search. Uses Hyperagents' exact parent selection algorithms (sigmoid score weighting + diversity penalty).

## Input Parameters

- `exp_root`: Path to experiments directory
- `strategy`: Selection strategy (default: `score_child_prop`)
- `archive_stats`: Optional stats from analyze skill to inform strategy choice

## Step 1: Choose Strategy

If no strategy is specified, choose based on archive size (recommended by analyze skill):

| Archive Size | Recommended Strategy | Rationale |
|---|---|---|
| < 5 entries | `random` | Too few data points for score weighting |
| 5–15 entries | `score_prop` | Enough data for exploitation |
| > 15 entries | `score_child_prop` | Need diversity to prevent convergence |

## Step 2: Select Parent

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/hyperagent_adapter.py <exp_root> select-parent <strategy>
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

## Step 3: Return Selection

Output the selected parent's genid, code branch, and fitness score for use by `hyperagent-generate`.

## Output

```json
{
  "genid": "gen-003",
  "code_branch": "ml-opt/gen-003-attention-v2",
  "fitness_score": 0.87,
  "strategy": "score_child_prop"
}
```
