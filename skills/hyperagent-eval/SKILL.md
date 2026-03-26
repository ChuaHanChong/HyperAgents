---
name: hyperagent-eval
description: Two-stage evaluation of a code variant — cheap staged eval first, full training only if promising. Saves 50-80% compute budget.
disable-model-invocation: true
user-invocable: false
---

# Hyperagent Eval Skill

## Overview

Two-stage evaluation matching Hyperagents' staged eval pattern. Run a cheap quick evaluation first. Only proceed to full training if the staged eval passes an adaptive threshold. This saves significant compute by filtering unpromising code variants early.

## Input Parameters

- `project_root`: Path to the user's project
- `exp_root`: Path to experiments directory
- `code_branch`: Branch to evaluate
- `genid`: Generation ID for this variant
- `train_command`: Training command (from pipeline state)
- `eval_command`: Evaluation command (if separate)
- `primary_metric`: Metric to evaluate
- `lower_is_better`: Metric direction
- `baseline_value`: Baseline metric value
- `best_so_far`: Best metric achieved so far in the archive
- `remaining_ratio`: `remaining_budget / total_budget` (0.0 to 1.0)
- `fixed_time_budget`: Time budget per experiment (if set)
- `fixed_epoch_budget`: Epoch budget per experiment (if set)
- `env_manager`: Environment manager (conda/venv/none)
- `env_name`: Environment name

## Stage 1: Cheap Staged Evaluation

### Step 1.1: Determine Staged Budget

The staged eval runs training for a fraction of the full budget:

| Budget Type | Staged Amount |
|---|---|
| `fixed_epoch_budget` set | `max(1, fixed_epoch_budget // 10)` epochs |
| `fixed_time_budget` set | `fixed_time_budget * 0.1` seconds |
| Neither set | 3 epochs (or framework equivalent) |
| Tabular ML (sklearn/XGBoost/LightGBM) | `n_estimators=10` or `max_iter=10` |

### Step 1.2: Run Staged Training

1. Checkout the code branch in a worktree or switch to it
2. Modify training command to limit budget:
   - Add `--max-epochs 3` or equivalent framework flag
   - Or wrap with `timeout <staged_seconds>` for time-based budget
3. Run training, capturing output to `experiments/logs/<genid>/staged_train.log`
4. Parse metrics: `python3 scripts/parse_logs.py experiments/logs/<genid>/staged_train.log`

### Step 1.3: Check for Early Divergence

```bash
python3 scripts/detect_divergence.py '<metric_values_json>' [--higher-is-better]
```

If divergence detected (NaN, explosion), immediately mark as FAIL.

### Step 1.4: Judge Staged Result

Assess the staged eval result using your judgment — **no hardcoded thresholds**. Consider:

- **Is the metric trending in the right direction?** (improving over the staged epochs)
- **Is it in a reasonable range?** Compare to baseline and best-so-far from the archive
- **How far into the session are we?** Early = be more permissive (explore). Late = be more selective (exploit).
- **Did it diverge or flatline?** Clear failures should be filtered immediately.

**PASS**: Metric trending positively and within a reasonable range of best-so-far. Proceed to full training.
**FAIL**: Diverged, flat, or clearly unpromising compared to what the archive already has.

### Step 1.5: Decision

- **PASS**: Metric meets threshold and trending in right direction → proceed to Stage 2
- **FAIL**: Diverged, flat, or below threshold → write `staged-exp-<genid>.json` and stop

If FAIL, write result:
```json
{
  "exp_id": "staged-<genid>",
  "genid": "<genid>",
  "status": "filtered",
  "staged_metric": 0.65,
  "threshold": 0.72,
  "adaptive_factor": 0.85,
  "reason": "Staged metric below adaptive threshold",
  "duration_seconds": 45
}
```

Save to `experiments/results/staged-exp-<genid>.json`.

## Stage 2: Full Training

If Stage 1 passes:

1. **Warm-start from staged checkpoint**: Continue training from where staged eval left off. Do NOT restart from scratch — the staged compute is reused.
   - If framework supports checkpoint resumption (Lightning, HuggingFace): use `--resume-from-checkpoint`
   - Otherwise: run full training (staged compute wasted, but still saves on failed candidates)

2. **Run full experiment**: Use the standard experiment execution flow:
   - Full epoch/time budget
   - Capture to `experiments/logs/<genid>/train.log`
   - Parse final metrics

3. **Write result**: Standard `experiments/results/exp-<id>.json` format with additional fields:
   ```json
   {
     "genid": "<genid>",
     "staged_score": 0.78,
     "staged_passed": true,
     "warm_started": true
   }
   ```

## Output Format

```json
{
  "status": "evaluated | filtered | failed",
  "genid": "gen-007",
  "staged_score": 0.78,
  "staged_passed": true,
  "final_score": 0.85,
  "threshold": 0.72,
  "adaptive_factor": 0.85,
  "warm_started": true,
  "exp_id": "exp-042",
  "duration_seconds": 320
}
```

## Important Rules

- **Always run Stage 1 first.** Never skip directly to full training in Hyperagent mode.
- **Warm-start when possible.** Reusing the staged checkpoint saves significant compute.
- **Log filtered candidates.** Even failed staged evals are valuable data — they tell the archive what doesn't work.
- **Divergence = immediate fail.** Don't wait for the full staged budget if NaN/explosion detected.
- **Tabular ML: stricter threshold.** For non-iterative frameworks, use `baseline * 0.9` (a model that can't beat 90% of baseline with 10 trees won't improve with 100).
