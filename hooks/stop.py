#!/usr/bin/env python3
"""Stop hook for OOLONG-Pairs benchmark.

This hook captures the final answer from the Claude session and scores it.
It reads from stdin the session data passed by Claude Code.
"""

import json
import os
import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from oolong_pairs.models import Result, Strategy
from oolong_pairs.scoring import score_answer, map_answer_type_str
from oolong_pairs.storage import Storage


def get_state_file() -> Path:
    """Get the benchmark state file path."""
    state_dir = Path(os.environ.get("OOLONG_STATE_DIR", "/tmp/oolong-pairs"))
    return state_dir / "current_task.json"


def get_db_path() -> Path:
    """Get the database path from environment."""
    return Path(os.environ.get("OOLONG_DB_PATH", "data/benchmark.db"))


def extract_answer(session_data: dict) -> str:
    """Extract the answer from session data.

    Looks for "ANSWER: " prefix in the response, or falls back to final_summary.
    """

    def find_answer_line(text: str) -> str | None:
        """Find line with ANSWER: prefix."""
        for line in text.split("\n"):
            line = line.strip()
            if line.upper().startswith("ANSWER:"):
                return line[7:].strip()  # Remove "ANSWER:" prefix
        return None

    # Try final_summary first
    final_summary = session_data.get("final_summary", "")
    if final_summary:
        answer = find_answer_line(final_summary)
        if answer:
            return answer
        return final_summary.strip()

    # Fall back to last assistant message in transcript
    transcript = session_data.get("transcript", [])
    for msg in reversed(transcript):
        if msg.get("role") == "assistant":
            content = msg.get("content", "")
            text = ""
            if isinstance(content, list):
                # Handle content blocks
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text", "")
                        break
            elif isinstance(content, str):
                text = content

            if text:
                answer = find_answer_line(text)
                if answer:
                    return answer
                return text.strip()

    return ""


def main() -> None:
    """Process the completed benchmark task."""
    state_file = get_state_file()

    if not state_file.exists():
        # No benchmark running
        return

    try:
        with open(state_file) as f:
            task_data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return

    # Check if task is in progress
    if task_data.get("status") != "in_progress":
        return

    # Read session data from stdin
    try:
        session_input = sys.stdin.read()
        session_data = json.loads(session_input) if session_input else {}
    except json.JSONDecodeError:
        session_data = {}

    # Extract the actual answer
    actual_answer = extract_answer(session_data)

    # Get task info
    task_id = task_data.get("task_id", "unknown")
    run_id = task_data.get("run_id", "unknown")
    expected_answer = task_data.get("expected_answer", "")
    answer_type_str = task_data.get("answer_type", "LABEL")
    start_time = task_data.get("start_time", time.time())

    # Score the answer
    answer_type = map_answer_type_str(answer_type_str)
    score = score_answer(expected_answer, actual_answer, answer_type)
    latency_ms = (time.time() - start_time) * 1000

    # Create result
    result = Result(
        task_id=task_id,
        run_id=run_id,
        strategy=Strategy(task_data.get("strategy", "truncation")),
        actual_answer=actual_answer,
        expected_answer=expected_answer,
        score=score,
        latency_ms=latency_ms,
        tokens_used=session_data.get("usage", {}).get("output_tokens", 0),
        error=None,
    )

    # Save to database
    db_path = get_db_path()
    storage = Storage(db_path)
    storage.save_result(result)

    # Mark task as completed
    task_data["status"] = "completed"
    task_data["actual_answer"] = actual_answer
    task_data["score"] = score
    with open(state_file, "w") as f:
        json.dump(task_data, f)

    # Output result summary
    print(f"[oolong-pairs] Task {task_id}: score={score:.4f}")


if __name__ == "__main__":
    main()
