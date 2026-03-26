---
name: hyperagent-generate
description: Generate a new code variant by modifying the selected parent using LLM patches, ShinkaEvolve, or research-implement. The core mutation skill of the Hyperagent evolutionary loop.
disable-model-invocation: true
user-invocable: false
---

# Hyperagent Generate Skill

Use extended thinking for all reasoning. Ultrathink.

## Overview

Generate a new code variant by modifying a selected parent from the evolutionary archive. This is the **core mutation operation** of the Hyperagent loop — it replaces Hyperagents' litellm-based meta-agent with Claude Code's native capabilities.

You have three mutation operators available. Choose the one most likely to produce improvement based on the archive history and analysis insights.

## Input Parameters

- `project_root`: Path to the user's project
- `exp_root`: Path to experiments directory
- `parent_genid`: Selected parent's genid (from hyperagent-select)
- `parent_branch`: Git branch of the selected parent
- `archive_history`: Top 5 archive entries with descriptions (what worked, what didn't)
- `analysis_insights`: From analyze skill — correlations, failure patterns, suggestions
- `dead_ends`: From dead-end catalog — techniques to avoid
- `behavioral_memory`: From learned-behaviors.json
- `primary_metric`: Metric being optimized
- `lower_is_better`: Metric direction
- `scope_level`: Constraint on changes (`"training"`, `"architecture"`, `"full"`)
- `generation_number`: Current generation count
- `mutation_operator`: Recommended operator (`"llm_patch"`, `"shinka_evolve"`, `"research_implement"`, or `"auto"`)

## Step 0: Read Context

1. Read goal summary: `python3 scripts/goal_memory.py <exp_root> summary`
2. Read archive history: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/hyperagent_adapter.py <exp_root> best 5`
3. Read operator stats: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/hyperagent_adapter.py <exp_root> operator-stats`
4. Read parent lineage: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/hyperagent_adapter.py <exp_root> lineage <parent_genid>`

Understand: what did the parent do well? What did its ancestors change? Where is the improvement trend heading?

## Step 1: Choose Mutation Operator

If `mutation_operator` is `"auto"`, choose based on the analysis-agent's recommendation, operator stats, and archive state. **No hardcoded thresholds** — the analysis agent decides when strategies have plateaued or when to switch. You read its output and act.

**Core principle: Standing on the shoulders of giants.** Research-implement is a first-class strategy, not a last resort. The best ML improvements often come from proven techniques in papers — prioritize finding and applying them.

**Default behavior: autonomous, never stops.** The loop runs until the target is reached or the user manually stops. There is no automatic stop — only the user can end the run. Even in extreme cases, keep pushing for breakthroughs.

**Available operators (analysis agent recommends, you decide):**

| Operator | When analysis agent recommends | Reasoning |
|---|---|---|
| `hp_tune` | "Continue HP exploration" / "narrow search" / "add regularization" / after any code mutation | Cheapest per iteration. Always HP-tune new code variants. |
| `research_implement` | "Try new techniques" / user provided papers / no research done yet / analysis sees a gap | **Standing on the shoulders of giants.** User papers highest priority. Research finds proven techniques the LLM wouldn't invent. Dispatches research-agent + implement-agent FROM selected parent (not baseline). |
| `llm_patch` | "HP plateaued, try code changes" / research explored but more structural changes needed | Structural/architectural changes. Select parent from archive, generate semantic modification. |
| `shinka_evolve` | "Fine-tune current best" / code structure is good but constants need optimization | Fine-grained AST-level mutations. Numerical constants, layer dimensions, dropout rates. |
| `meta_improve` | "All approaches stalling, consider strategy change" AND `meta_improvement_count < 3` | Self-referential — modify skill instructions. Safety cap: max 3 per session. |

**After every code mutation (llm_patch, shinka_evolve, research_implement):** follow up with HP tuning iterations on the new code. The code change is only half the story — new code may need different HPs.

**Operator stats inform your choice:** Read `operator-stats` output. If one operator has a significantly higher improvement rate, prefer it. You learn what works for this specific task.

**Research is always available:** Even if research was used recently, if you identify a specific gap, dispatch research-implement at any time.

## Step 2: Execute Mutation

### Operator A: LLM Patch (default)

You directly modify the code. This is the most powerful operator — you can make semantic, architectural changes.

1. **Checkout parent**: `git checkout <parent_branch>`
2. **Create new branch**: `git checkout -b ml-opt/gen-<N>-<slug>`
   - If branch exists, append suffix: `-2`, `-3`, etc.
3. **Read the parent's code** — understand the model architecture, training loop, data pipeline
4. **Analyze what would improve it** based on:
   - Archive history: what changes produced the biggest improvements?
   - Analysis insights: which HP correlations suggest structural changes?
   - Dead-end catalog: what NOT to try
   - Lineage: what did ancestors already try?
5. **Make targeted code changes** respecting `scope_level`:
   - `"training"`: optimizer, scheduler, loss, augmentation, regularization only
   - `"architecture"`: + model layers, attention, normalization
   - `"full"`: any code
6. **Mark changes**: `# [ml-opt] gen-<N>: <description>`

### Operator B: ShinkaEvolve

Dispatch ShinkaEvolve for fine-grained code mutations on the parent branch.

```
Skill("ml-optimizer:evolve")
```

Pass the parent branch and feedback context. ShinkaEvolve handles the convert → run → inspect pipeline internally. The result is a new branch `ml-opt/evolved-<slug>`.

After `Skill("ml-optimizer:evolve")` returns:
1. Check the return status. If `status: "shinkaevolve_unavailable"`: **fall back to LLM patch** (Operator A) instead.
2. Verify the branch exists: `git rev-parse --verify ml-opt/evolved-<slug>`
3. Rename to Hyperagent naming convention:
   ```bash
   git branch -m ml-opt/evolved-<slug> ml-opt/gen-<N>-evolved-<slug>
   ```
4. If rename fails (branch `ml-opt/gen-<N>-evolved-<slug>` already exists): append suffix `-2`, `-3`, etc.
5. If the evolve skill modified architecture parameters, verify eval.py consistency (the evolve skill documents this in Step 5).

### Operator C: Research-Implement

Dispatch research and implementation for paper-informed changes.

1. Have the orchestrator dispatch the research-agent with `source: "both"` for new technique proposals
2. Have the orchestrator dispatch the implement-agent with selected proposals, starting from the **parent branch** (not main)

The key difference from Phase 5-6 research-implement: here we build ON TOP of the parent branch, inheriting its improvements.

## Step 3: Validate

After code modification, validate:

```bash
# Syntax check
python3 -c "import py_compile; py_compile.compile('<modified_file>', doraise=True)"

# Import check
python3 -c "import sys; sys.path.insert(0, '<project_root>'); import <main_module>"
```

If validation fails:
- For LLM patch: attempt to fix (up to 2 retries)
- For ShinkaEvolve: the evolve skill handles validation internally
- For research-implement: the implement skill handles validation

## Step 4: Commit

```bash
git add -A
git commit -m "gen-<N>: <description of mutation>"
```

## Step 5: Return to Original Branch

```bash
git checkout <original_branch>
```

## Step 6: Self-Referential Meta-Improvement (Phase C Only)

When dispatched specifically for meta-improvement (the orchestrator indicates `meta_improvement_mode: true`):

In addition to code modifications, analyze what optimization strategies have been effective and generate **skill patches**:

1. Read current skill files: `hp-tune/SKILL.md`, `analyze/SKILL.md`, `research/SKILL.md`
2. Analyze: which skill instructions led to good decisions? Which led to dead ends?
3. Generate patched skill files to `experiments/meta-patches/`:
   - `experiments/meta-patches/hp-tune-SKILL.md`
   - `experiments/meta-patches/analyze-SKILL.md`
   - etc.
4. Write changelog: `experiments/meta-patches/meta-changelog.json`

```json
{
  "patches": [
    {
      "skill": "hp-tune",
      "change": "Weight recent experiments 2x in correlation analysis",
      "reason": "Last 3 experiments more informative than earlier ones",
      "expected_impact": "Better HP proposals in exploitation phase"
    }
  ],
  "generation_triggered": 15,
  "archive_state_summary": "..."
}
```

**Constraints:**
- Cannot modify orchestrator skill (prevents runaway self-modification)
- Cannot modify its own skill (prevents loops)
- Maximum 3 meta-improvement runs per session
- Each patch must include reason and expected impact

## Output Format

```json
{
  "status": "validated | validation_failed | operator_unavailable",
  "genid": "gen-007",
  "code_branch": "ml-opt/gen-007-attention-v3",
  "parent_genid": "gen-003",
  "mutation_type": "llm_patch | shinka_evolve | research_implement",
  "mutation_description": "Added residual connections to attention layer",
  "files_modified": ["model.py", "train.py"],
  "operator_reasoning": "LLM patch chosen — attention lineage shows 5.7% improvement trend",
  "meta_patches": []
}
```

## Important Rules

- **Respect scope_level.** Training scope = only optimizer, scheduler, loss, augmentation, regularization.
- **Check dead ends.** If a technique is in the dead-end catalog, do NOT use it.
- **Build on parent.** Always create the new branch FROM the parent branch, not from main. The lineage must be preserved.
- **Mark changes.** All code must have `# [ml-opt] gen-<N>: <description>` comments.
- **Return to original branch.** Never leave the repo on the new branch.
- **One mutation per generation.** Don't combine multiple independent changes — each generation should test one hypothesis.
- **Log operator choice.** Include `operator_reasoning` explaining why this operator was chosen over alternatives.
