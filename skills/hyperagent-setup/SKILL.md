---
name: hyperagent-setup
description: Initialize the Hyperagents submodule and verify the environment for evolutionary code search.
disable-model-invocation: true
user-invocable: false
---

# Hyperagent Setup Skill

## Overview

Initialize the Hyperagents submodule (facebookresearch/Hyperagents) and verify the environment is ready for archive-based evolutionary code search.

## Steps

### Step 1: Run Setup Script

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/setup_hyperagent.sh
```

This initializes the git submodule at `skills/hyperagent/Hyperagents/` and verifies Python can import from it.

### Step 2: Verify Adapter Script

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/hyperagent_adapter.py --help
```

Confirm the adapter script runs and displays usage information.

### Step 3: Report Status

If both steps succeed, report ready. If the submodule fails to initialize, report the error — the adapter script works standalone without the submodule (it reimplements the core algorithms in stdlib Python).

## Output

```json
{
  "status": "ready | setup_failed",
  "submodule_initialized": true,
  "adapter_available": true,
  "numpy_available": true,
  "error": null
}
```
