---
name: hyperagent-generate
description: Generate a new code variant by modifying the selected parent using LLM patches, external mutation tools, or delegation. The core Generation skill of the Hyperagent DGM evolutionary loop.
disable-model-invocation: true
user-invocable: false
---

# Hyperagent Generate Skill

## When to Use
Use this skill when:
- A parent has been selected via hyperagent-select
- You need to produce a code mutation for the next generation

Do not use this skill when:
- No parent is selected yet (use hyperagent-select first)
- You only need to evaluate code (use hyperagent-eval)
- You only need to query the archive (use hyperagent-archive)

Use extended thinking for all reasoning. Ultrathink.

## What is Hyperagent Generate?
This is the core **Generation** operation of the DGM (Diversity-Generation-Merging) framework. It replaces Hyperagents' litellm-based meta-agent with Claude Code's native capabilities — persistent memory, rich tools, and accumulated context.

Repo and documentation: https://github.com/facebookresearch/Hyperagents

## Input Parameters

- `project_root`: Path to the user's project
- `output_dir`: Path to the Hyperagent output directory
- `parent_genid`: Selected parent's genid (from hyperagent-select)
- `parent_branch`: Git branch of the selected parent
- `archive_history`: Top N archive entries with descriptions (what worked, what didn't)
- `analysis_insights`: Correlations, failure patterns, suggestions from analysis
- `dead_ends`: Techniques to avoid (from dead-end catalog)
- `generation_number`: Current generation count
- `mutation_operator`: Recommended operator (`"llm_patch"`, `"external_tool"`, `"delegation"`, or `"auto"`)
- Domain-specific parameters as needed (e.g., `scope_level`, `primary_metric`)

## Step 0: Read Context

Read the archive state to inform mutation decisions:

1. Read archive history: `python skills/hyperagent-archive/scripts/archive_utils.py best --output-dir <output_dir> -n 5`
2. Read operator stats: `python skills/hyperagent-archive/scripts/archive_utils.py operator-stats --output-dir <output_dir>`
3. Read parent lineage: `python skills/hyperagent-archive/scripts/archive_utils.py lineage --output-dir <output_dir> <parent_genid>`

Understand: what did the parent do well? What did its ancestors change? Where is the improvement trend heading?

## Step 1: Choose Mutation Operator

If `mutation_operator` is `"auto"`, choose based on analysis recommendations, operator stats, and archive state. **No hardcoded thresholds** — use evidence to decide when strategies have plateaued or when to switch.

**Available operators:**

| Operator | When to Use | Description |
|---|---|---|
| `llm_patch` | Default. Analysis says structural changes needed, or parameter tuning plateaued. | Direct code modification by the agent. Most powerful — can make semantic, architectural changes. |
| `external_tool` | Fine-grained mutation tool available. Code structure is good but constants/parameters need local optimization. | Dispatch to a configured external code mutation tool (e.g., ShinkaEvolve). |
| `delegation` | Novel approaches needed. External research or implementation agents available. | Return a delegation request for the caller to route to specialized agents. |
| `meta_improve` | All approaches stalling, strategy change needed. Safety cap applies. | Modify skill instructions based on evidence of what works. |

**Operator stats inform your choice:** Read `operator-stats` output. If one operator has a significantly higher improvement rate, prefer it. Learn what works for this specific task.

**After every code mutation:** follow up with parameter tuning iterations on the new code. The code change is only half the story — new code may need different parameters.

## Step 2: Execute Mutation

### Operator A: LLM Patch (default)

You directly modify the code.

1. **Checkout parent**: `git checkout <parent_branch>`
2. **Create new branch**: `git checkout -b gen-<N>-<slug>`
   - If branch exists, append suffix: `-2`, `-3`, etc.
3. **Read the parent's code** — understand the codebase structure and logic
4. **Analyze what would improve it** based on:
   - Archive history: what changes produced the biggest improvements?
   - Analysis insights: which correlations suggest structural changes?
   - Dead-end catalog: what NOT to try
   - Lineage: what did ancestors already try?
5. **Make targeted code changes** respecting any scope constraints provided by the caller
6. **Mark changes** with generation comments: `# gen-<N>: <description>`

### Operator B: External Mutation Tool

Dispatch an external code mutation tool for fine-grained mutations on the parent branch.

If a mutation tool is configured (e.g., ShinkaEvolve), invoke it with the parent branch and feedback context. The tool handles its internal pipeline (convert → run → inspect).

After the external tool returns:
1. Check the return status. If the tool is unavailable, **fall back to LLM patch** (Operator A).
2. Verify the result branch exists.
3. Rename to Hyperagent naming convention: `gen-<N>-<tool>-<slug>`
4. If rename fails (branch already exists), append suffix: `-2`, `-3`, etc.

### Operator C: Delegation

Return a delegation request for the caller to route to specialized agents (e.g., research agents, implementation agents).

1. Return a delegation response:
   ```json
   {
     "status": "delegating",
     "operator": "delegation",
     "parent_genid": "<parent>",
     "parent_branch": "<branch>",
     "delegation_type": "<type>"
   }
   ```
2. The caller dispatches appropriate agents on the **parent branch** (not main)
3. Once the caller has the result, it creates the archive entry via hyperagent-archive

Key: delegated work builds ON TOP of the parent branch, inheriting its improvements.

## Step 3: Validate

After code modification, validate:

```bash
# Syntax check (Python example)
python3 -c "import py_compile; py_compile.compile('<modified_file>', doraise=True)"

# Import check
python3 -c "import sys; sys.path.insert(0, '<project_root>'); import <main_module>"
```

If validation fails:
- For LLM patch: attempt to fix (up to 2 retries)
- For external tool: the tool handles validation internally
- For delegation: the delegated agent handles validation

## Step 4: Commit

```bash
git add -A
git commit -m "gen-<N>: <description of mutation>"
```

## Step 5: Return to Original Branch

```bash
git checkout <original_branch>
```

## Step 6: Meta-Improvement (optional)

When dispatched with `meta_improvement_mode: true`:

Analyze which optimization strategies have been effective and generate **skill patches**:

1. Read current skill instruction files used by the optimization pipeline
2. Analyze: which instructions led to good decisions? Which led to dead ends?
3. Generate patched versions to a designated meta-patches directory
4. Write a changelog documenting each patch with reason and expected impact

```json
{
  "patches": [
    {
      "skill": "<skill_name>",
      "change": "<description>",
      "reason": "<evidence-based justification>",
      "expected_impact": "<predicted improvement>"
    }
  ],
  "generation_triggered": 15,
  "archive_state_summary": "..."
}
```

**Constraints:**
- Cannot modify orchestrator-level instructions (prevents runaway self-modification)
- Cannot modify its own skill (prevents loops)
- Maximum N meta-improvement runs per session (caller enforces the cap)
- Each patch must include reason and expected impact

## Output Format

```json
{
  "status": "validated | validation_failed | operator_unavailable | delegating",
  "genid": "gen-007",
  "code_branch": "gen-007-attention-v3",
  "parent_genid": "gen-003",
  "mutation_type": "llm_patch | external_tool | delegation",
  "mutation_description": "Added residual connections to attention layer",
  "files_modified": ["model.py", "train.py"],
  "operator_reasoning": "LLM patch chosen — attention lineage shows 5.7% improvement trend",
  "meta_patches": []
}
```

## Important Rules

- **Check dead ends.** If a technique is in the dead-end catalog, do NOT use it.
- **Build on parent.** Always create the new branch FROM the parent branch, not from main. Lineage must be preserved.
- **Mark changes.** Add generation comments to modified code for traceability.
- **Return to original branch.** Never leave the repo on the new branch.
- **One mutation per generation.** Don't combine multiple independent changes — each generation tests one hypothesis.
- **Log operator choice.** Include `operator_reasoning` explaining why this operator was chosen over alternatives.
- **Respect scope constraints.** If the caller provides scope restrictions, honor them strictly.
