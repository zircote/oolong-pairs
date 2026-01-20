# Customization Guide

This guide explains how to extend and customize the OOLONG-Pairs benchmark harness for your specific needs.

## Table of Contents

1. [Adding Custom Strategies](#adding-custom-strategies)
2. [Customizing Scoring Logic](#customizing-scoring-logic)
3. [Using Different Datasets](#using-different-datasets)
4. [Modifying Hooks Behavior](#modifying-hooks-behavior)
5. [Custom Storage Backends](#custom-storage-backends)
6. [Extending the CLI](#extending-the-cli)

---

## Adding Custom Strategies

Strategies define how context is processed before sending to Claude. You can create custom strategies for different approaches.

### Step 1: Create Strategy Class

Create a new file or add to `src/oolong_pairs/strategies.py`:

```python
from .models import ExecutionMode, Result, Strategy, Task
from .scoring import score_answer
import time

class MyCustomStrategy(BaseStrategy):
    """Custom strategy for context processing."""

    # Define a unique strategy identifier
    strategy = Strategy.CUSTOM  # You'll need to add this to the Strategy enum

    def __init__(
        self,
        mode: ExecutionMode = ExecutionMode.SDK,
        # Add your custom parameters here
        custom_param: str = "default",
    ):
        self.mode = mode
        self.custom_param = custom_param

    def execute(self, task: Task, run_id: str) -> Result:
        """Execute task using custom strategy."""
        start_time = time.time()
        error = None
        actual_answer = ""
        tokens_used = 0

        try:
            # Implement your custom logic here
            processed_context = self._process_context(task.context)
            actual_answer, tokens_used = self._call_claude(processed_context, task.question)
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

    def _process_context(self, context: str) -> str:
        """Apply custom context processing."""
        # Example: Extract key sentences
        sentences = context.split(". ")
        important = [s for s in sentences if len(s) > 50]
        return ". ".join(important[:100])

    def _call_claude(self, context: str, question: str) -> tuple[str, int]:
        """Send processed context to Claude."""
        import subprocess
        import json

        prompt = f"""<context>
{context}
</context>

Question: {question}

Answer concisely."""

        result = subprocess.run(
            ["claude", "--print", "--output-format", "json"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=300,
        )

        output = json.loads(result.stdout)
        return output.get("result", "").strip(), output.get("usage", {}).get("output_tokens", 0)
```

### Step 2: Add to Strategy Enum

In `src/oolong_pairs/models.py`:

```python
class Strategy(str, Enum):
    """Execution strategy for benchmark."""
    TRUNCATION = "truncation"
    RLM_RS = "rlm_rs"
    CUSTOM = "custom"  # Add your strategy
```

### Step 3: Register in Factory

In `src/oolong_pairs/strategies.py`, update `get_strategy()`:

```python
def get_strategy(
    strategy: Strategy,
    mode: ExecutionMode = ExecutionMode.SDK,
    **kwargs,
) -> BaseStrategy:
    """Factory function to get a strategy instance."""
    strategies = {
        Strategy.TRUNCATION: TruncationStrategy,
        Strategy.RLM_RS: RLMRSStrategy,
        Strategy.CUSTOM: MyCustomStrategy,  # Add your strategy
    }

    strategy_class = strategies.get(strategy)
    if not strategy_class:
        raise ValueError(f"Unknown strategy: {strategy}")

    return strategy_class(mode=mode, **kwargs)
```

### Step 4: Update CLI (Optional)

In `src/oolong_pairs/cli.py`, add to the choices:

```python
@click.option(
    "--strategy",
    type=click.Choice(["rlm_rs", "truncation", "custom"]),  # Add here
    required=True,
    help="Execution strategy",
)
```

---

## Customizing Scoring Logic

### Adding New Answer Types

In `src/oolong_pairs/models.py`:

```python
class AnswerType(str, Enum):
    """Type of expected answer."""
    NUMERIC = "NUMERIC"
    LABEL = "LABEL"
    COMPARISON = "COMPARISON"
    DATE = "DATE"
    PERCENTAGE = "PERCENTAGE"  # New type
```

In `src/oolong_pairs/scoring.py`:

```python
def percentage_score(expected: str, actual: str) -> float:
    """Score percentage answers with tolerance."""
    # Extract percentages
    def extract_pct(s: str) -> float | None:
        import re
        match = re.search(r'(\d+(?:\.\d+)?)\s*%', s)
        if match:
            return float(match.group(1))
        return None

    exp_pct = extract_pct(expected)
    act_pct = extract_pct(actual)

    if exp_pct is None or act_pct is None:
        return label_score(expected, actual)

    # Allow 2% tolerance
    tolerance = 2.0
    if abs(exp_pct - act_pct) <= tolerance:
        return 1.0
    else:
        # Gradual falloff
        diff = abs(exp_pct - act_pct)
        return max(0.0, 1.0 - (diff - tolerance) / 10.0)


# Update get_scorer()
def get_scorer(answer_type: AnswerType) -> Callable[[str, str], float]:
    """Get scoring function for answer type."""
    scorers: dict[AnswerType, Callable[[str, str], float]] = {
        AnswerType.NUMERIC: _score_numeric,
        AnswerType.LABEL: label_score,
        AnswerType.COMPARISON: comparison_score,
        AnswerType.DATE: label_score,
        AnswerType.PERCENTAGE: percentage_score,  # Add here
    }
    return scorers.get(answer_type, label_score)
```

### Custom Scoring Functions

You can also create scoring functions for specific domains:

```python
def scientific_notation_score(expected: str, actual: str) -> float:
    """Score scientific notation answers with order-of-magnitude tolerance."""
    import re

    def parse_sci(s: str) -> float | None:
        # Match patterns like "1.5e6", "1.5 x 10^6", "1.5 × 10^6"
        patterns = [
            r'(\d+(?:\.\d+)?)[eE]([+-]?\d+)',
            r'(\d+(?:\.\d+)?)\s*[x×]\s*10\^([+-]?\d+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, s)
            if match:
                base, exp = match.groups()
                return float(base) * (10 ** int(exp))
        try:
            return float(s.replace(',', ''))
        except ValueError:
            return None

    exp_val = parse_sci(expected)
    act_val = parse_sci(actual)

    if exp_val is None or act_val is None:
        return label_score(expected, actual)

    # Score based on order of magnitude difference
    import math
    exp_mag = math.floor(math.log10(abs(exp_val))) if exp_val != 0 else 0
    act_mag = math.floor(math.log10(abs(act_val))) if act_val != 0 else 0

    mag_diff = abs(exp_mag - act_mag)
    if mag_diff == 0:
        return 1.0
    elif mag_diff == 1:
        return 0.5
    else:
        return 0.0
```

---

## Using Different Datasets

### Custom Dataset Filters

The OOLONG dataset contains multiple task types. Filter by the `dataset` column:

```bash
# Available datasets in OOLONG
oolong-pairs stats --dataset trec_coarse   # TREC topic classification
oolong-pairs stats --dataset banking77     # Banking intent classification
oolong-pairs stats --dataset clinic150     # Clinical NLP
```

### Loading Custom Datasets

Modify `src/oolong_pairs/dataset.py` to support custom datasets:

```python
def load_custom_tasks(
    source: str,
    context_key: str = "context",
    question_key: str = "question",
    answer_key: str = "answer",
    min_context_length: int = 100_000,
) -> list[Task]:
    """Load tasks from a custom dataset source.

    Args:
        source: Path to JSON/JSONL file or HuggingFace dataset ID
        context_key: Key for context field
        question_key: Key for question field
        answer_key: Key for expected answer field
        min_context_length: Minimum context length filter
    """
    from pathlib import Path
    import json

    tasks = []

    if Path(source).exists():
        # Load from local file
        with open(source) as f:
            if source.endswith('.jsonl'):
                data = [json.loads(line) for line in f]
            else:
                data = json.load(f)
    else:
        # Load from HuggingFace
        from datasets import load_dataset
        ds = load_dataset(source, split="validation")
        data = list(ds)

    for i, item in enumerate(data):
        context = item.get(context_key, "")
        if len(context) < min_context_length:
            continue

        task = Task(
            id=item.get("id", f"custom_{i}"),
            context=context,
            question=item.get(question_key, ""),
            expected_answer=item.get(answer_key, ""),
            answer_type=AnswerType.LABEL,  # Or detect automatically
            dataset_source=source,
        )
        tasks.append(task)

    return tasks
```

### Custom Task Format

Create your own benchmark tasks in JSONL format:

```json
{"id": "task_001", "context": "...", "question": "What is...?", "answer": "42", "answer_type": "NUMERIC"}
{"id": "task_002", "context": "...", "question": "Which...?", "answer": "Option A", "answer_type": "LABEL"}
```

Load with:
```python
tasks = load_custom_tasks("my_tasks.jsonl")
```

---

## Modifying Hooks Behavior

### Custom SessionStart Hook

Create alternative injection strategies:

```python
#!/usr/bin/env python3
"""Custom SessionStart hook with chain-of-thought prompting."""

import json
import os
from pathlib import Path

def main():
    state_file = Path(os.environ.get("OOLONG_STATE_DIR", "/tmp/oolong-pairs")) / "current_task.json"

    if not state_file.exists():
        return

    with open(state_file) as f:
        task_data = json.load(f)

    if task_data.get("status") != "pending":
        return

    task_data["status"] = "in_progress"
    with open(state_file, "w") as f:
        json.dump(task_data, f)

    context = task_data.get("context", "")
    question = task_data.get("question", "")
    task_id = task_data.get("task_id", "unknown")

    # Custom: Chain-of-thought prompting
    injection = f"""<benchmark-task id="{task_id}">
You are being evaluated on a long-context reasoning benchmark.

<context>
{context[:180000]}
</context>

<question>
{question}
</question>

Think through this step-by-step:
1. Identify key information in the context relevant to the question
2. Analyze patterns or relationships in the data
3. Reason about the answer based on your analysis
4. State your final answer

After your reasoning, output ONLY the final answer on a single line prefixed with "ANSWER: "
</benchmark-task>"""

    print(injection)

if __name__ == "__main__":
    main()
```

### Custom Stop Hook with Logging

```python
#!/usr/bin/env python3
"""Custom Stop hook with detailed logging."""

import json
import logging
import os
import sys
import time
from pathlib import Path

# Configure logging
logging.basicConfig(
    filename='/tmp/oolong-pairs/benchmark.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def main():
    state_file = Path(os.environ.get("OOLONG_STATE_DIR", "/tmp/oolong-pairs")) / "current_task.json"

    if not state_file.exists():
        return

    with open(state_file) as f:
        task_data = json.load(f)

    if task_data.get("status") != "in_progress":
        return

    # Read session data
    try:
        session_input = sys.stdin.read()
        session_data = json.loads(session_input) if session_input else {}
    except json.JSONDecodeError:
        session_data = {}

    # Extract answer
    actual_answer = extract_answer(session_data)

    # Log detailed info
    logging.info(f"Task: {task_data.get('task_id')}")
    logging.info(f"Expected: {task_data.get('expected_answer')}")
    logging.info(f"Actual: {actual_answer}")
    logging.info(f"Transcript length: {len(session_data.get('transcript', []))}")

    # ... rest of scoring logic

def extract_answer(session_data: dict) -> str:
    # ... same as before
    pass

if __name__ == "__main__":
    main()
```

---

## Custom Storage Backends

### PostgreSQL Backend

```python
"""PostgreSQL storage backend for production use."""

import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from .models import BenchmarkRun, Result, RunSummary

class PostgresStorage:
    """PostgreSQL-backed storage for benchmark results."""

    def __init__(self, connection_string: str):
        self.conn = psycopg2.connect(connection_string)
        self._init_schema()

    def _init_schema(self):
        with self.conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    id VARCHAR(8) PRIMARY KEY,
                    timestamp TIMESTAMPTZ NOT NULL,
                    mode VARCHAR(20) NOT NULL,
                    strategy VARCHAR(20) NOT NULL,
                    tasks_completed INT DEFAULT 0,
                    tasks_failed INT DEFAULT 0,
                    avg_score FLOAT DEFAULT 0.0,
                    metadata JSONB
                );

                CREATE TABLE IF NOT EXISTS results (
                    id SERIAL PRIMARY KEY,
                    run_id VARCHAR(8) REFERENCES runs(id),
                    task_id VARCHAR(64) NOT NULL,
                    strategy VARCHAR(20) NOT NULL,
                    actual_answer TEXT,
                    expected_answer TEXT,
                    score FLOAT NOT NULL,
                    latency_ms FLOAT NOT NULL,
                    tokens_used INT,
                    error TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );

                CREATE INDEX IF NOT EXISTS idx_results_run_id ON results(run_id);
            """)
            self.conn.commit()

    def save_run(self, run: BenchmarkRun) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO runs (id, timestamp, mode, strategy)
                VALUES (%s, %s, %s, %s)
                """,
                (run.id, run.timestamp, run.mode.value, run.strategy.value)
            )
            self.conn.commit()

    def save_result(self, result: Result) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO results (run_id, task_id, strategy, actual_answer,
                                    expected_answer, score, latency_ms, tokens_used, error)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (result.run_id, result.task_id, result.strategy.value,
                 result.actual_answer, result.expected_answer, result.score,
                 result.latency_ms, result.tokens_used, result.error)
            )
            self.conn.commit()

    # ... implement other methods
```

---

## Extending the CLI

### Adding Custom Commands

```python
# In src/oolong_pairs/cli.py

@cli.command()
@click.argument("run_id")
@click.option("--threshold", type=float, default=0.5, help="Score threshold")
@click.pass_context
def failures(ctx: click.Context, run_id: str, threshold: float) -> None:
    """Show failed tasks (score below threshold) for a run."""
    storage: Storage = ctx.obj["storage"]

    results = storage.get_results_below_threshold(run_id, threshold)

    if not results:
        console.print(f"[green]No tasks below {threshold} threshold[/green]")
        return

    table = Table(title=f"Failed Tasks (score < {threshold})")
    table.add_column("Task ID", style="cyan")
    table.add_column("Score", style="red")
    table.add_column("Expected", style="green")
    table.add_column("Actual", style="yellow")

    for r in results:
        table.add_row(
            r.task_id[:20],
            f"{r.score:.4f}",
            r.expected_answer[:30],
            r.actual_answer[:30],
        )

    console.print(table)


@cli.command()
@click.argument("run_ids", nargs=-1)
@click.pass_context
def aggregate(ctx: click.Context, run_ids: tuple[str]) -> None:
    """Aggregate statistics across multiple runs."""
    storage: Storage = ctx.obj["storage"]

    all_scores = []
    for run_id in run_ids:
        summary = storage.get_run_summary(run_id)
        if summary:
            all_scores.append(summary.avg_score)

    if not all_scores:
        console.print("[red]No valid runs found[/red]")
        return

    import statistics
    console.print(f"Runs analyzed: {len(all_scores)}")
    console.print(f"Mean score: {statistics.mean(all_scores):.4f}")
    console.print(f"Std dev: {statistics.stdev(all_scores):.4f}" if len(all_scores) > 1 else "")
    console.print(f"Min: {min(all_scores):.4f}")
    console.print(f"Max: {max(all_scores):.4f}")
```

### Custom Output Formats

```python
@cli.command()
@click.argument("run_id")
@click.option("--format", "fmt", type=click.Choice(["markdown", "html", "latex"]), default="markdown")
@click.pass_context
def report(ctx: click.Context, run_id: str, fmt: str) -> None:
    """Generate a formatted report for a benchmark run."""
    storage: Storage = ctx.obj["storage"]
    summary = storage.get_run_summary(run_id)

    if not summary:
        console.print(f"[red]Run not found: {run_id}[/red]")
        return

    if fmt == "markdown":
        output = f"""# Benchmark Report: {run_id}

## Summary
- **Strategy:** {summary.strategy.value}
- **Mode:** {summary.mode.value}
- **Tasks Completed:** {summary.tasks_completed}
- **Average Score:** {summary.avg_score:.4f}

## Score Distribution
- Min: {summary.min_score:.4f}
- Max: {summary.max_score:.4f}

## Performance
- Total Latency: {summary.total_latency_ms:.0f}ms
- Avg Latency: {summary.avg_latency_ms:.0f}ms
"""
    elif fmt == "html":
        output = f"""<html>
<head><title>Benchmark Report: {run_id}</title></head>
<body>
<h1>Benchmark Report: {run_id}</h1>
<table>
<tr><th>Metric</th><th>Value</th></tr>
<tr><td>Strategy</td><td>{summary.strategy.value}</td></tr>
<tr><td>Average Score</td><td>{summary.avg_score:.4f}</td></tr>
</table>
</body>
</html>"""
    # ... handle latex

    console.print(output)
```

---

## Configuration Files

Create a configuration file for reusable settings:

```yaml
# oolong-pairs.yaml
strategies:
  truncation:
    max_context_chars: 180000
  rlm_rs:
    chunker: semantic
    chunk_size: 150000
    subcall_model: claude-haiku-3-5-20241022

defaults:
  strategy: rlm_rs
  mode: sdk
  min_context: 100000
  dataset: trec_coarse

scoring:
  numeric_base: 0.75
  comparison_variants:
    more: ["more", "greater", "higher", "larger"]
    less: ["less", "fewer", "smaller", "lower"]
    same: ["same", "equal", "tied"]
```

Load configuration:

```python
import yaml
from pathlib import Path

def load_config(config_path: Path = Path("oolong-pairs.yaml")) -> dict:
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f)
    return {}
```

---

## Next Steps

- [API-REFERENCE.md](./API-REFERENCE.md) - Detailed module documentation
- [CONTRIBUTING.md](./CONTRIBUTING.md) - How to contribute improvements
- [HOOKS-GUIDE.md](./HOOKS-GUIDE.md) - More on hooks integration
