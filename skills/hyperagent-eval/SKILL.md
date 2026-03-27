---
name: hyperagent-eval
description: Two-stage evaluation of a code variant — cheap staged eval first, full evaluation only if promising. Matches Hyperagents' staged eval pattern, saving 50-80% compute budget.
disable-model-invocation: true
user-invocable: false
---

# Hyperagent Eval Skill

## When to Use
Use this skill when:
- A new code variant has been generated and needs evaluation
- You want staged evaluation (cheap eval → threshold check → full eval)

Do not use this skill when:
- No code variant exists to evaluate
- You need to modify code (use hyperagent-generate)

## What is Hyperagent Eval?
Two-stage evaluation matching Hyperagents' DGM framework staged eval pattern. Run a cheap quick evaluation first. Only proceed to full evaluation if the staged eval passes an adaptive threshold. This filters unpromising variants early, saving significant compute.

Repo and documentation: https://github.com/facebookresearch/Hyperagents

## Input Parameters

- `output_dir`: Path to the Hyperagent output directory
- `genid`: Generation ID for this variant
- `eval_command`: Command to evaluate the code variant (must output JSON metrics)
- `project_root`: Working directory for the eval command
- `primary_metric`: Metric name to evaluate (also set via `HYPERAGENT_METRIC` env var)
- `baseline_value`: Baseline metric value for comparison
- `best_so_far`: Best metric achieved so far in the archive

## Helper Script

```bash
export HYPERAGENT_METRIC=<metric_name>
python skills/hyperagent-eval/scripts/run_eval.py \
  --output-dir <output_dir> \
  --genid <genid> \
  --eval-command "<eval_command>" \
  [--project-root <dir>] \
  [--skip-staged-eval] \
  [--timeout 21600]
```

The script handles both stages automatically, using `get_domain_stagedeval_frac("ml")` for the staged budget fraction (configurable via `HYPERAGENT_STAGED_FRAC` env var, default 0.1).

## Stage 1: Cheap Staged Evaluation

### Step 1.1: Determine Staged Budget

The staged eval runs for a fraction of the full budget (default: 10%). The caller determines how to limit the budget:

- **Iteration-based**: Reduce epochs/iterations to ~10% of full budget
- **Time-based**: Limit wall-clock time to ~10% of full budget
- **Non-iterative models**: Use minimal iteration count (e.g., `n_estimators=10`)

### Step 1.2: Run Staged Evaluation

1. Checkout the code branch or switch to it
2. Run the evaluation command with limited budget
3. Parse metrics from the output (expects JSON on stdout)

### Step 1.3: Check for Early Divergence

If the metric contains NaN or extreme values, immediately mark as FAIL.

### Step 1.4: Judge Staged Result

Assess the staged eval result — **no hardcoded thresholds**. Consider:

- **Is the metric trending in the right direction?**
- **Is it in a reasonable range?** Compare to baseline and best-so-far
- **How far into the session are we?** Early = more permissive (explore). Late = more selective (exploit).
- **Did it diverge or flatline?** Clear failures should be filtered immediately.

**PASS**: Metric trending positively and within reasonable range. Proceed to full evaluation.
**FAIL**: Diverged, flat, or clearly unpromising. Archive as filtered and stop.

If FAIL, write a filtered result:
```json
{
  "genid": "<genid>",
  "status": "filtered",
  "staged_metric": 0.65,
  "reason": "Staged metric below adaptive threshold",
  "duration_seconds": 45
}
```

## Stage 2: Full Evaluation

If Stage 1 passes:

1. **Warm-start from staged checkpoint** when possible — continue from where staged eval left off. Don't restart from scratch. Warm-start depends on the eval command supporting checkpoint resumption (e.g., `--resume-from-checkpoint` for HuggingFace Trainer, `last.ckpt` for Lightning). If the eval command doesn't support it, the full eval restarts from scratch — less efficient but still correct.
2. **Run full evaluation** with the full budget.
3. **Write result** with additional fields linking back to the staged eval:
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
  "warm_started": true,
  "run_full_eval": true,
  "duration_seconds": 320
}
```

## Important Rules

- **Always run Stage 1 first.** Never skip directly to full evaluation in Hyperagent mode.
- **Warm-start when possible.** Reusing the staged checkpoint saves significant compute.
- **Log filtered candidates.** Even failed staged evals are valuable data — they prevent the archive from re-exploring dead paths.
- **Divergence = immediate fail.** Don't wait for the full staged budget if NaN/explosion detected.
