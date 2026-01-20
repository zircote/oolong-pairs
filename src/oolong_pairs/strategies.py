"""Execution strategies for benchmark tasks."""

import json
import re
import subprocess
import tempfile
import time
from abc import ABC, abstractmethod
from pathlib import Path

from .models import ExecutionMode, Result, Strategy, Task
from .scoring import score_answer


class BaseStrategy(ABC):
    """Base class for execution strategies."""

    strategy: Strategy

    @abstractmethod
    def execute(self, task: Task, run_id: str) -> Result:
        """Execute a task and return result."""
        pass


class TruncationStrategy(BaseStrategy):
    """Strategy that truncates context to fit in window."""

    strategy = Strategy.TRUNCATION

    def __init__(
        self,
        mode: ExecutionMode = ExecutionMode.SDK,
        max_context_chars: int = 180_000,
        model: str = "claude-sonnet-4-20250514",
    ):
        self.mode = mode
        self.max_context_chars = max_context_chars
        self.model = model

    def _truncate_context(self, context: str) -> str:
        """Truncate context to max length, preserving beginning and end."""
        if len(context) <= self.max_context_chars:
            return context

        # Keep first 60% and last 40%
        first_part = int(self.max_context_chars * 0.6)
        last_part = self.max_context_chars - first_part

        return (
            context[:first_part]
            + "\n\n[... content truncated ...]\n\n"
            + context[-last_part:]
        )

    def _build_prompt(self, task: Task) -> str:
        """Build prompt for Claude."""
        truncated = self._truncate_context(task.context)
        return f"""Analyze the following data and answer the question.

<context>
{truncated}
</context>

Question: {task.question}

Provide only the answer, nothing else. Be concise."""

    def execute(self, task: Task, run_id: str) -> Result:
        """Execute task using truncated context."""
        start_time = time.time()
        error = None
        actual_answer = ""
        tokens_used = 0

        try:
            if self.mode == ExecutionMode.SDK:
                actual_answer, tokens_used = self._execute_sdk(task)
            else:
                actual_answer, tokens_used = self._execute_hooks(task)
        except Exception as e:
            error = str(e)

        latency_ms = (time.time() - start_time) * 1000
        score = score_answer(task.expected_answer, actual_answer, task.answer_type) if not error else 0.0

        return Result(
            task_id=task.id,
            run_id=run_id,
            strategy=self.strategy,
            actual_answer=actual_answer,
            expected_answer=task.expected_answer,
            score=score,
            latency_ms=latency_ms,
            tokens_used=tokens_used,
            error=error,
        )

    def _execute_sdk(self, task: Task) -> tuple[str, int]:
        """Execute using Claude CLI in SDK mode."""
        prompt = self._build_prompt(task)

        # Use claude CLI with --print for non-interactive mode
        result = subprocess.run(
            ["claude", "--print", "--model", self.model, "--output-format", "json"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Claude CLI failed: {result.stderr}")

        # Parse JSON output
        try:
            output = json.loads(result.stdout)
            answer = output.get("result", "").strip()
            tokens = output.get("usage", {}).get("output_tokens", 0)
            return answer, tokens
        except json.JSONDecodeError:
            # Fall back to raw output
            return result.stdout.strip(), 0

    def _execute_hooks(self, task: Task) -> tuple[str, int]:
        """Execute using hooks mode (placeholder)."""
        # Hooks mode uses SessionStart/Stop hooks to inject context
        # This is orchestrated externally; this method is a placeholder
        raise NotImplementedError("Hooks mode requires external orchestration")


class RLMRSStrategy(BaseStrategy):
    """Strategy using RLM-RS plugin for chunking."""

    strategy = Strategy.RLM_RS

    def __init__(
        self,
        mode: ExecutionMode = ExecutionMode.SDK,
        chunker: str = "semantic",
        chunk_size: int = 150_000,
        model: str = "claude-sonnet-4-20250514",
        subcall_model: str = "claude-haiku-3-5-20241022",
    ):
        self.mode = mode
        self.chunker = chunker
        self.chunk_size = chunk_size
        self.model = model
        self.subcall_model = subcall_model

    def execute(self, task: Task, run_id: str) -> Result:
        """Execute task using RLM-RS chunking."""
        start_time = time.time()
        error = None
        actual_answer = ""
        tokens_used = 0

        try:
            if self.mode == ExecutionMode.SDK:
                actual_answer, tokens_used = self._execute_sdk(task)
            else:
                actual_answer, tokens_used = self._execute_hooks(task)
        except Exception as e:
            error = str(e)

        latency_ms = (time.time() - start_time) * 1000
        score = score_answer(task.expected_answer, actual_answer, task.answer_type) if not error else 0.0

        return Result(
            task_id=task.id,
            run_id=run_id,
            strategy=self.strategy,
            actual_answer=actual_answer,
            expected_answer=task.expected_answer,
            score=score,
            latency_ms=latency_ms,
            tokens_used=tokens_used,
            error=error,
        )

    def _execute_sdk(self, task: Task) -> tuple[str, int]:
        """Execute using RLM-RS CLI + Claude."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Write context to temp file
            context_file = tmpdir / "context.txt"
            context_file.write_text(task.context)

            # Initialize RLM-RS
            subprocess.run(
                ["rlm-rs", "init", "--db-path", str(tmpdir / "rlm.db")],
                check=True,
                capture_output=True,
            )

            # Load context with chunking
            subprocess.run(
                [
                    "rlm-rs",
                    "load",
                    str(context_file),
                    "--name",
                    "context",
                    "--chunker",
                    self.chunker,
                    "--chunk-size",
                    str(self.chunk_size),
                    "--db-path",
                    str(tmpdir / "rlm.db"),
                ],
                check=True,
                capture_output=True,
            )

            # Write chunks to files
            chunks_dir = tmpdir / "chunks"
            chunks_dir.mkdir()
            subprocess.run(
                [
                    "rlm-rs",
                    "write-chunks",
                    "context",
                    "--out-dir",
                    str(chunks_dir),
                    "--db-path",
                    str(tmpdir / "rlm.db"),
                ],
                check=True,
                capture_output=True,
            )

            # Process each chunk with subcall
            chunk_files = sorted(chunks_dir.glob("*.txt"))
            findings = []

            for chunk_file in chunk_files:
                chunk_result = self._process_chunk(chunk_file, task.question)
                findings.append(chunk_result)

            # Synthesize final answer
            answer, tokens = self._synthesize(task.question, findings)
            return answer, tokens

    def _process_chunk(self, chunk_file: Path, question: str) -> dict:
        """Process a single chunk with subcall model."""
        chunk_content = chunk_file.read_text()

        prompt = f"""Analyze this chunk and extract any information relevant to the question.

<chunk>
{chunk_content}
</chunk>

Question: {question}

Respond with JSON: {{"relevant": true/false, "findings": "brief summary of relevant info or null"}}"""

        result = subprocess.run(
            ["claude", "--print", "--model", self.subcall_model, "--output-format", "text"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=60,
        )

        try:
            # Extract JSON from response
            text = result.stdout.strip()
            json_match = re.search(r"\{[^}]+\}", text)
            if json_match:
                return json.loads(json_match.group())
        except (json.JSONDecodeError, AttributeError):
            pass

        return {"relevant": False, "findings": None}

    def _synthesize(self, question: str, findings: list[dict]) -> tuple[str, int]:
        """Synthesize final answer from chunk findings."""
        relevant_findings = [f["findings"] for f in findings if f.get("relevant") and f.get("findings")]

        if not relevant_findings:
            return "Unable to determine from context", 0

        findings_text = "\n".join(f"- {f}" for f in relevant_findings)

        prompt = f"""Based on these findings from analyzing a large document, answer the question.

Findings:
{findings_text}

Question: {question}

Provide only the answer, nothing else. Be concise."""

        result = subprocess.run(
            ["claude", "--print", "--model", self.model, "--output-format", "json"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=120,
        )

        try:
            output = json.loads(result.stdout)
            answer = output.get("result", "").strip()
            tokens = output.get("usage", {}).get("output_tokens", 0)
            return answer, tokens
        except json.JSONDecodeError:
            return result.stdout.strip(), 0

    def _execute_hooks(self, task: Task) -> tuple[str, int]:
        """Execute using hooks mode (placeholder)."""
        raise NotImplementedError("Hooks mode requires external orchestration")


def get_strategy(
    strategy: Strategy,
    mode: ExecutionMode = ExecutionMode.SDK,
    **kwargs,
) -> BaseStrategy:
    """Factory function to get a strategy instance."""
    strategies = {
        Strategy.TRUNCATION: TruncationStrategy,
        Strategy.RLM_RS: RLMRSStrategy,
    }

    strategy_class = strategies.get(strategy)
    if not strategy_class:
        raise ValueError(f"Unknown strategy: {strategy}")

    return strategy_class(mode=mode, **kwargs)
