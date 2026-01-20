#!/usr/bin/env python3
"""SessionStart hook for OOLONG-Pairs benchmark.

This hook injects the benchmark task context and question into the Claude session.
It reads the current task from the benchmark state file.
"""

import json
import os
from pathlib import Path


def get_state_file() -> Path:
    """Get the benchmark state file path."""
    state_dir = Path(os.environ.get("OOLONG_STATE_DIR", "/tmp/oolong-pairs"))
    return state_dir / "current_task.json"


def main() -> None:
    """Inject benchmark context if a task is queued."""
    state_file = get_state_file()

    if not state_file.exists():
        # No benchmark running, exit silently
        return

    try:
        with open(state_file) as f:
            task_data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return

    # Check if task is active
    if task_data.get("status") != "pending":
        return

    # Mark task as in progress
    task_data["status"] = "in_progress"
    with open(state_file, "w") as f:
        json.dump(task_data, f)

    # Build the injection prompt
    context = task_data.get("context", "")
    question = task_data.get("question", "")
    task_id = task_data.get("task_id", "unknown")
    strategy = task_data.get("strategy", "truncation")

    # Write context to a temp file for rlm-rs to load
    state_dir = get_state_file().parent
    context_file = state_dir / f"context_{task_id}.txt"
    context_file.write_text(context)

    if strategy == "rlm_rs":
        # Prompt Claude to use the rlm-rs plugin
        injection = f"""<benchmark-task id="{task_id}">
You are being evaluated on a long-context reasoning benchmark using the RLM pattern.

The context document is located at: {context_file}

Use the rlm-rs plugin to process this large document:
1. Load the file: `/rlm-load file={context_file}`
2. Query it: `/rlm-query query="{question}"`

The plugin will chunk the document, run subcalls on relevant chunks, and synthesize an answer.

After getting the synthesized answer, output ONLY the final answer on a single line prefixed with "ANSWER: "
</benchmark-task>"""
    else:
        # Truncation strategy - direct context injection
        # Truncate to ~180k chars, keeping first 60% and last 40%
        max_chars = 180_000
        if len(context) > max_chars:
            first_part = int(max_chars * 0.6)
            last_part = max_chars - first_part
            context = context[:first_part] + "\n\n[... content truncated ...]\n\n" + context[-last_part:]

        injection = f"""<benchmark-task id="{task_id}">
You are being evaluated on a long-context reasoning benchmark.

<context>
{context}
</context>

<question>
{question}
</question>

Analyze the context above and answer the question.
Output ONLY the final answer on a single line prefixed with "ANSWER: "
</benchmark-task>"""

    print(injection)


if __name__ == "__main__":
    main()
