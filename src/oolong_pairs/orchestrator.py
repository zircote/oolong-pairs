"""Orchestrator for hooks-based benchmark execution.

This module drives the benchmark by:
1. Loading tasks from the dataset
2. Writing task state files for hooks to read
3. Launching Claude sessions
4. Collecting results
"""

import json
import os
import subprocess
import time
from pathlib import Path

from .dataset import load_oolong_tasks
from .models import BenchmarkRun, ExecutionMode, Strategy
from .storage import Storage


class HooksOrchestrator:
    """Orchestrate benchmark execution using Claude Code hooks."""

    def __init__(
        self,
        strategy: Strategy,
        db_path: Path,
        state_dir: Path | None = None,
        model: str = "claude-sonnet-4-20250514",
    ):
        self.strategy = strategy
        self.storage = Storage(db_path)
        self.state_dir = state_dir or Path("/tmp/oolong-pairs")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.model = model

    def _write_task_state(
        self,
        task_id: str,
        run_id: str,
        context: str,
        question: str,
        expected_answer: str,
        answer_type: str,
    ) -> Path:
        """Write task state file for hooks to read."""
        state_file = self.state_dir / "current_task.json"
        state = {
            "task_id": task_id,
            "run_id": run_id,
            "context": context,
            "question": question,
            "expected_answer": expected_answer,
            "answer_type": answer_type,
            "strategy": self.strategy.value,
            "status": "pending",
            "start_time": time.time(),
        }
        with open(state_file, "w") as f:
            json.dump(state, f)
        return state_file

    def _clear_task_state(self) -> None:
        """Clear the task state file."""
        state_file = self.state_dir / "current_task.json"
        if state_file.exists():
            state_file.unlink()

    def _launch_session(self, prompt: str) -> subprocess.CompletedProcess:
        """Launch a Claude session with the benchmark prompt."""
        env = os.environ.copy()
        env["OOLONG_STATE_DIR"] = str(self.state_dir)
        env["OOLONG_DB_PATH"] = str(self.storage.db_path)

        result = subprocess.run(
            [
                "claude",
                "--print",
                "--model",
                self.model,
                "--output-format",
                "json",
            ],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=600,
            env=env,
        )
        return result

    def _wait_for_completion(self, timeout: float = 60.0) -> dict | None:
        """Wait for task to complete and return result."""
        state_file = self.state_dir / "current_task.json"
        start = time.time()

        while time.time() - start < timeout:
            if not state_file.exists():
                return None

            with open(state_file) as f:
                state = json.load(f)

            if state.get("status") == "completed":
                return state

            time.sleep(0.5)

        return None

    def run_benchmark(
        self,
        dataset_filter: str = "trec_coarse",
        split: str = "validation",
        min_context_length: int = 100_000,
        limit: int | None = None,
    ) -> str:
        """Run the benchmark and return the run ID."""
        import uuid
        from datetime import datetime

        # Create run record
        run_id = str(uuid.uuid4())[:8]
        run = BenchmarkRun(
            id=run_id,
            timestamp=datetime.now(),
            mode=ExecutionMode.HOOKS,
            strategy=self.strategy,
        )
        self.storage.save_run(run)

        # Load tasks
        tasks = load_oolong_tasks(
            dataset_filter=dataset_filter,
            split=split,
            min_context_length=min_context_length,
            limit=limit,
        )

        print(f"Running benchmark {run_id} with {len(tasks)} tasks")

        for i, task in enumerate(tasks):
            print(f"  Task {i + 1}/{len(tasks)}: {task.id[:16]}...")

            # Write task state
            self._write_task_state(
                task_id=task.id,
                run_id=run_id,
                context=task.context,
                question=task.question,
                expected_answer=task.expected_answer,
                answer_type=task.answer_type.value,
            )

            # Launch session - the hooks will handle injection and scoring
            # For hooks mode, we just trigger the session; hooks do the rest
            prompt = "Begin benchmark task."
            try:
                self._launch_session(prompt)
            except subprocess.TimeoutExpired:
                print(f"    Timeout for task {task.id}")
            except Exception as e:
                print(f"    Error for task {task.id}: {e}")

            # Wait for completion
            result = self._wait_for_completion()
            if result:
                score = result.get("score", 0.0)
                print(f"    Score: {score:.4f}")
            else:
                print("    No result captured")

            self._clear_task_state()

        # Update run stats
        self.storage.update_run_stats(run_id)

        return run_id
