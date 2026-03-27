"""File-based handoff provider for Claude Code subagent dispatch.

Instead of calling LLM APIs directly (via litellm), writes prompts to a
pending directory and polls for responses from the Claude Code orchestrator.

Flow:
  1. Hyperagents calls get_response_from_llm() which routes here
  2. This writes {id, system_msg, user_msg} to hyperagent/pending/<id>.json
  3. Blocks polling for hyperagent/completed/<id>.json
  4. The orchestrator (running concurrently) picks up pending requests,
     dispatches a Claude Code Agent() with the prompt, and writes the
     response to completed/<id>.json
  5. This function reads the response and returns it

Follows the same pattern as ShinkaEvolve's file_handoff_provider.py.
"""

import json
import os
import time
import uuid
from pathlib import Path
from typing import Tuple


HANDOFF_DIR: Path | None = None


def set_handoff_dir(path: str) -> Path:
    """Configure the handoff directory. Call before starting the loop."""
    global HANDOFF_DIR
    HANDOFF_DIR = Path(path) / "hyperagent"
    (HANDOFF_DIR / "pending").mkdir(parents=True, exist_ok=True)
    (HANDOFF_DIR / "completed").mkdir(parents=True, exist_ok=True)
    return HANDOFF_DIR


def query_file_handoff(
    msg: str,
    system_msg: str = "",
    model_name: str = "claude_code",
    msg_history: list | None = None,
    timeout_seconds: int = 600,
) -> Tuple[str, list, dict]:
    """Write prompt to file, wait for orchestrator to dispatch and respond.

    Returns a tuple matching get_response_from_llm() signature:
    (response_text, new_msg_history, info_dict)
    """
    global HANDOFF_DIR
    if HANDOFF_DIR is None:
        env_dir = os.environ.get("HYPERAGENT_HANDOFF_DIR")
        if env_dir:
            set_handoff_dir(env_dir)
        else:
            raise RuntimeError(
                "Handoff directory not configured. Set HYPERAGENT_HANDOFF_DIR "
                "env var or call set_handoff_dir() first."
            )

    if msg_history is None:
        msg_history = []

    request_id = uuid.uuid4().hex[:8]

    # Write request
    handoff_dir = HANDOFF_DIR  # narrow type for Pyright
    assert handoff_dir is not None

    request = {
        "id": request_id,
        "system_msg": system_msg,
        "user_msg": msg,
        "model_name": model_name,
        "msg_history": msg_history,
    }
    pending_path = handoff_dir / "pending" / f"{request_id}.json"
    pending_path.write_text(json.dumps(request, indent=2))

    # Poll for response
    completed_path = handoff_dir / "completed" / f"{request_id}.json"
    for _ in range(timeout_seconds):
        if completed_path.exists():
            try:
                response = json.loads(completed_path.read_text())
            except json.JSONDecodeError:
                time.sleep(1)
                continue
            # Cleanup
            pending_path.unlink(missing_ok=True)
            completed_path.unlink(missing_ok=True)

            response_text = response.get("content", "")
            new_msg_history = msg_history + [
                {"role": "user", "text": msg},
                {"role": "assistant", "text": response_text},
            ]
            return response_text, new_msg_history, {}
        time.sleep(1)

    # Timeout — cleanup pending request
    pending_path.unlink(missing_ok=True)
    raise TimeoutError(
        f"No response for request {request_id} after {timeout_seconds}s"
    )
