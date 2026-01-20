# API Reference

Complete reference documentation for all OOLONG-Pairs modules, classes, and functions.

## Table of Contents

- [oolong_pairs.models](#oolong_pairsmodels)
- [oolong_pairs.scoring](#oolong_pairsscoring)
- [oolong_pairs.dataset](#oolong_pairsdataset)
- [oolong_pairs.storage](#oolong_pairsstorage)
- [oolong_pairs.strategies](#oolong_pairsstrategies)
- [oolong_pairs.orchestrator](#oolong_pairsorchestrator)
- [oolong_pairs.cli](#oolong_pairscli)

---

## oolong_pairs.models

Data models using Pydantic for type validation.

### Enums

#### `AnswerType`

```python
class AnswerType(str, Enum):
    NUMERIC = "NUMERIC"      # Numeric answers scored with 0.75^|error|
    LABEL = "LABEL"          # Label answers scored with exact match
    COMPARISON = "COMPARISON"  # Comparison answers (more/less/same)
    DATE = "DATE"            # Date answers scored with exact match
```

**Usage:**
```python
from oolong_pairs.models import AnswerType

task_type = AnswerType.NUMERIC
print(task_type.value)  # "NUMERIC"
```

#### `Strategy`

```python
class Strategy(str, Enum):
    RLM_RS = "rlm_rs"        # RLM-RS chunking strategy
    TRUNCATION = "truncation"  # Simple truncation strategy
```

**Usage:**
```python
from oolong_pairs.models import Strategy

strategy = Strategy.RLM_RS
print(strategy.value)  # "rlm_rs"
```

#### `ExecutionMode`

```python
class ExecutionMode(str, Enum):
    SDK = "sdk"      # Direct Claude CLI invocation
    HOOKS = "hooks"  # Claude Code hooks integration
```

### Models

#### `Task`

Represents a single OOLONG benchmark task.

```python
class Task(BaseModel):
    id: str                          # Unique task identifier
    dataset: str                     # Dataset source (e.g., 'trec_coarse')
    context: str                     # The long context text
    question: str                    # Question to answer
    expected_answer: str             # Gold standard answer
    answer_type: AnswerType          # Type of answer expected
    context_length: int = 0          # Auto-calculated from context
    task_type: str = ""              # Task category (e.g., 'MOST_FREQ')
    metadata: dict[str, Any] = {}    # Additional metadata
```

**Example:**
```python
from oolong_pairs.models import Task, AnswerType

task = Task(
    id="task_001",
    dataset="trec_coarse",
    context="Long document text...",
    question="How many times does X appear?",
    expected_answer="42",
    answer_type=AnswerType.NUMERIC,
)

print(task.context_length)  # Auto-calculated
```

#### `Result`

Result of executing a single task.

```python
class Result(BaseModel):
    task_id: str                     # Reference to Task.id
    run_id: str                      # Reference to BenchmarkRun.id
    strategy: Strategy               # Strategy used
    actual_answer: str               # Answer from Claude
    expected_answer: str             # Gold standard answer
    score: float                     # Score between 0.0 and 1.0
    latency_ms: float                # Execution time in milliseconds
    tokens_used: int = 0             # Output tokens used
    error: str | None = None         # Error message if failed
```

**Example:**
```python
from oolong_pairs.models import Result, Strategy

result = Result(
    task_id="task_001",
    run_id="abc123",
    strategy=Strategy.TRUNCATION,
    actual_answer="42",
    expected_answer="42",
    score=1.0,
    latency_ms=5432.1,
    tokens_used=150,
)
```

#### `BenchmarkRun`

Represents a complete benchmark run.

```python
class BenchmarkRun(BaseModel):
    id: str                              # Unique run identifier
    timestamp: datetime                  # When the run started
    mode: ExecutionMode                  # SDK or HOOKS
    strategy: Strategy                   # Strategy used
    tasks_total: int = 0                 # Total tasks in run
    tasks_completed: int = 0             # Successfully completed
    tasks_failed: int = 0                # Failed with errors
    avg_score: float = 0.0               # Average score
    total_latency_ms: float = 0.0        # Total execution time
    metadata: dict[str, Any] = {}        # Additional metadata
```

#### `RunSummary`

Summary statistics for a benchmark run.

```python
class RunSummary(BaseModel):
    run_id: str
    strategy: Strategy
    mode: ExecutionMode
    tasks_completed: int
    tasks_failed: int
    avg_score: float
    min_score: float
    max_score: float
    total_latency_ms: float
    avg_latency_ms: float
    by_task_type: dict[str, dict[str, float]] = {}
```

---

## oolong_pairs.scoring

Scoring logic implementing OOLONG benchmark methodology.

### Functions

#### `score_answer()`

Main scoring function that dispatches to type-specific scorers.

```python
def score_answer(
    expected: str,
    actual: str,
    answer_type: AnswerType | None = None
) -> float:
    """Score an answer against expected.

    Args:
        expected: The expected/gold answer
        actual: The actual/predicted answer
        answer_type: Type of answer (auto-detected if not provided)

    Returns:
        Score between 0.0 and 1.0
    """
```

**Examples:**
```python
from oolong_pairs.scoring import score_answer
from oolong_pairs.models import AnswerType

# Numeric scoring: 0.75^|error|
score_answer("10", "10", AnswerType.NUMERIC)  # 1.0
score_answer("10", "11", AnswerType.NUMERIC)  # 0.75
score_answer("10", "12", AnswerType.NUMERIC)  # 0.5625

# Label scoring: exact match
score_answer("cat", "Cat", AnswerType.LABEL)  # 1.0
score_answer("cat", "dog", AnswerType.LABEL)  # 0.0

# Comparison scoring: semantic match
score_answer("more", "more common", AnswerType.COMPARISON)  # 1.0
score_answer("less", "fewer", AnswerType.COMPARISON)  # 1.0

# Auto-detection
score_answer("42", "42")  # Detects NUMERIC, returns 1.0
```

#### `numeric_score()`

Scores numeric answers using the OOLONG formula.

```python
def numeric_score(expected: float, actual: float) -> float:
    """Score numeric answer using 0.75^|error| formula.

    Args:
        expected: Expected numeric value
        actual: Actual numeric value

    Returns:
        Score = 0.75^|expected - actual|
    """
```

**Formula:** `score = 0.75^|error|`

| Error | Score |
|-------|-------|
| 0 | 1.0000 |
| 1 | 0.7500 |
| 2 | 0.5625 |
| 3 | 0.4219 |
| 5 | 0.2373 |
| 10 | 0.0563 |

#### `label_score()`

Scores label answers with exact match (case-insensitive).

```python
def label_score(expected: str, actual: str) -> float:
    """Score label answer using exact match (case-insensitive).

    Returns:
        1.0 if match, 0.0 otherwise
    """
```

#### `comparison_score()`

Scores comparison answers with semantic matching.

```python
def comparison_score(expected: str, actual: str) -> float:
    """Score comparison answers (more/less/same).

    Recognizes variants:
    - more: more, more common, greater, higher, larger
    - less: less, less common, smaller, lower, fewer
    - same: same, equal, same frequency, tied
    """
```

#### `normalize_answer()`

Normalizes answer strings for comparison.

```python
def normalize_answer(answer: str) -> str:
    """Normalize answer for comparison.

    - Strips whitespace
    - Converts to lowercase
    - Removes markdown formatting (* _ `)
    - Removes quotes
    """
```

#### `detect_answer_type()`

Auto-detects answer type from expected answer.

```python
def detect_answer_type(expected: str) -> AnswerType:
    """Detect answer type from expected answer.

    Detection rules:
    1. If contains comparison words → COMPARISON
    2. If parseable as number → NUMERIC
    3. Otherwise → LABEL
    """
```

#### `map_answer_type_str()`

Maps string to AnswerType enum.

```python
def map_answer_type_str(answer_type_str: str) -> AnswerType:
    """Map string to AnswerType enum.

    Handles: NUMERIC, NUMERIC_ONE_CLASS, LABEL, COMPARISON, DATE
    Unknown types default to LABEL.
    """
```

---

## oolong_pairs.dataset

Functions for loading OOLONG benchmark data from HuggingFace.

### Functions

#### `load_oolong_tasks()`

Load tasks from HuggingFace dataset.

```python
def load_oolong_tasks(
    dataset_filter: str = "trec_coarse",
    split: str = "validation",
    min_context_length: int = 100_000,
    limit: int | None = None,
) -> list[Task]:
    """Load OOLONG tasks from HuggingFace.

    Args:
        dataset_filter: Filter by dataset column (e.g., 'trec_coarse')
        split: Dataset split ('validation' or 'test')
        min_context_length: Minimum context length in characters
        limit: Maximum number of tasks to load

    Returns:
        List of Task objects
    """
```

**Example:**
```python
from oolong_pairs.dataset import load_oolong_tasks

# Load 10 tasks from trec_coarse with 100k+ char contexts
tasks = load_oolong_tasks(
    dataset_filter="trec_coarse",
    min_context_length=100_000,
    limit=10,
)

for task in tasks:
    print(f"{task.id}: {task.question[:50]}...")
```

#### `iter_oolong_tasks()`

Memory-efficient iterator over tasks.

```python
def iter_oolong_tasks(
    dataset_filter: str = "trec_coarse",
    split: str = "validation",
    min_context_length: int = 100_000,
) -> Iterator[Task]:
    """Iterate OOLONG tasks without loading all into memory.

    Uses HuggingFace streaming mode for memory efficiency.
    """
```

**Example:**
```python
from oolong_pairs.dataset import iter_oolong_tasks

for task in iter_oolong_tasks(min_context_length=100_000):
    process_task(task)  # Process one at a time
```

#### `get_dataset_stats()`

Get statistics about the filtered dataset.

```python
def get_dataset_stats(
    dataset_filter: str = "trec_coarse",
    split: str = "validation",
) -> dict:
    """Get statistics about the filtered dataset.

    Returns:
        {
            "total_in_split": int,
            "filtered_count": int,
            "dataset_filter": str,
            "context_length": {"min": int, "max": int, "avg": float},
            "task_types": {str: int},
            "answer_types": {str: int},
        }
    """
```

---

## oolong_pairs.storage

SQLite storage for benchmark results.

### Class: `Storage`

```python
class Storage:
    """SQLite storage for benchmark data."""

    def __init__(self, db_path: Path | str = "data/benchmark.db"):
        """Initialize storage with database path.

        Creates parent directories and schema if needed.
        """
```

### Methods

#### `save_run()`

```python
def save_run(self, run: BenchmarkRun) -> None:
    """Insert or update a benchmark run."""
```

#### `save_result()`

```python
def save_result(self, result: Result) -> None:
    """Insert a task result."""
```

#### `get_run()`

```python
def get_run(self, run_id: str) -> BenchmarkRun | None:
    """Get a benchmark run by ID."""
```

#### `get_results()`

```python
def get_results(self, run_id: str) -> list[Result]:
    """Get all results for a run."""
```

#### `get_run_summary()`

```python
def get_run_summary(self, run_id: str) -> RunSummary | None:
    """Get summary statistics for a run."""
```

#### `list_runs()`

```python
def list_runs(self, limit: int = 20) -> list[BenchmarkRun]:
    """List recent benchmark runs, most recent first."""
```

#### `export_results()`

```python
def export_results(
    self,
    run_id: str,
    output_path: Path,
    format: str = "json"  # json, jsonl, csv
) -> None:
    """Export results to file."""
```

#### `update_run_stats()`

```python
def update_run_stats(self, run_id: str) -> None:
    """Update run statistics from results.

    Recalculates: tasks_total, tasks_completed, tasks_failed,
                  avg_score, total_latency_ms
    """
```

### Database Schema

```sql
CREATE TABLE runs (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    mode TEXT NOT NULL,
    strategy TEXT NOT NULL,
    tasks_total INTEGER DEFAULT 0,
    tasks_completed INTEGER DEFAULT 0,
    tasks_failed INTEGER DEFAULT 0,
    avg_score REAL DEFAULT 0.0,
    total_latency_ms REAL DEFAULT 0.0,
    metadata TEXT DEFAULT '{}'
);

CREATE TABLE results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    strategy TEXT NOT NULL,
    actual_answer TEXT,
    expected_answer TEXT,
    score REAL NOT NULL,
    latency_ms REAL NOT NULL,
    tokens_used INTEGER DEFAULT 0,
    error TEXT,
    FOREIGN KEY (run_id) REFERENCES runs(id)
);
```

---

## oolong_pairs.strategies

Execution strategies for benchmark tasks.

### Abstract Base Class: `BaseStrategy`

```python
class BaseStrategy(ABC):
    """Base class for execution strategies."""

    strategy: Strategy  # Class attribute identifying the strategy

    @abstractmethod
    def execute(self, task: Task, run_id: str) -> Result:
        """Execute a task and return result."""
        pass
```

### Class: `TruncationStrategy`

Truncates context to fit within context window.

```python
class TruncationStrategy(BaseStrategy):
    strategy = Strategy.TRUNCATION

    def __init__(
        self,
        mode: ExecutionMode = ExecutionMode.SDK,
        max_context_chars: int = 180_000,
        model: str = "claude-sonnet-4-20250514",
    ):
        """Initialize truncation strategy.

        Args:
            mode: SDK or HOOKS execution mode
            max_context_chars: Maximum context characters (default 180k)
            model: Claude model to use
        """
```

**Truncation logic:** Keeps first 60% and last 40% of content.

### Class: `RLMRSStrategy`

Uses RLM-RS plugin for semantic chunking.

```python
class RLMRSStrategy(BaseStrategy):
    strategy = Strategy.RLM_RS

    def __init__(
        self,
        mode: ExecutionMode = ExecutionMode.SDK,
        chunker: str = "semantic",
        chunk_size: int = 150_000,
        model: str = "claude-sonnet-4-20250514",
        subcall_model: str = "claude-haiku-3-5-20241022",
    ):
        """Initialize RLM-RS strategy.

        Args:
            mode: SDK or HOOKS execution mode
            chunker: Chunking algorithm ('semantic', 'fixed', 'sentence')
            chunk_size: Target chunk size in characters
            model: Main model for synthesis
            subcall_model: Model for chunk processing
        """
```

**RLM-RS flow:**
1. Initialize rlm-rs database
2. Load context with chunking
3. Process each chunk with subcall model
4. Synthesize findings with main model

### Factory Function: `get_strategy()`

```python
def get_strategy(
    strategy: Strategy,
    mode: ExecutionMode = ExecutionMode.SDK,
    **kwargs,
) -> BaseStrategy:
    """Factory function to get a strategy instance.

    Args:
        strategy: Strategy enum value
        mode: Execution mode
        **kwargs: Strategy-specific parameters

    Returns:
        Configured strategy instance
    """
```

**Example:**
```python
from oolong_pairs.strategies import get_strategy
from oolong_pairs.models import Strategy, ExecutionMode

strategy = get_strategy(
    Strategy.TRUNCATION,
    mode=ExecutionMode.SDK,
    max_context_chars=200_000,
)

result = strategy.execute(task, run_id="abc123")
```

---

## oolong_pairs.orchestrator

Orchestrates benchmark execution in hooks mode.

### Class: `HooksOrchestrator`

```python
class HooksOrchestrator:
    """Orchestrate benchmark execution using Claude Code hooks."""

    def __init__(
        self,
        strategy: Strategy,
        db_path: Path,
        state_dir: Path | None = None,
        model: str = "claude-sonnet-4-20250514",
    ):
        """Initialize orchestrator.

        Args:
            strategy: Strategy to use (affects hook prompts)
            db_path: Path to SQLite database
            state_dir: Directory for task state files
            model: Claude model to use
        """
```

### Methods

#### `run_benchmark()`

```python
def run_benchmark(
    self,
    dataset_filter: str = "trec_coarse",
    split: str = "validation",
    min_context_length: int = 100_000,
    limit: int | None = None,
) -> str:
    """Run the benchmark and return the run ID.

    Creates a new run, loads tasks, and executes each via hooks.
    """
```

**Example:**
```python
from oolong_pairs.orchestrator import HooksOrchestrator
from oolong_pairs.models import Strategy
from pathlib import Path

orchestrator = HooksOrchestrator(
    strategy=Strategy.RLM_RS,
    db_path=Path("data/benchmark.db"),
    state_dir=Path("/tmp/oolong-pairs"),
)

run_id = orchestrator.run_benchmark(limit=10)
print(f"Completed: {run_id}")
```

---

## oolong_pairs.cli

Command-line interface using Click.

### Commands

#### `run`

```bash
oolong-pairs run --strategy <strategy> [OPTIONS]
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--strategy` | Choice | Required | `truncation` or `rlm_rs` |
| `--mode` | Choice | `sdk` | `sdk` or `hooks` |
| `--limit` | Integer | None | Max tasks to run |
| `--min-context` | Integer | 100000 | Min context length |
| `--dataset` | String | `trec_coarse` | Dataset filter |

#### `show`

```bash
oolong-pairs show <run_id>
```

Display detailed results for a benchmark run.

#### `compare`

```bash
oolong-pairs compare <run_id1> <run_id2>
```

Compare two benchmark runs side-by-side.

#### `list-runs`

```bash
oolong-pairs list-runs [--limit 20]
```

List recent benchmark runs.

#### `export`

```bash
oolong-pairs export <run_id> <output_path> [--format json|jsonl|csv]
```

Export results to file.

#### `stats`

```bash
oolong-pairs stats [--dataset trec_coarse] [--split validation]
```

Show dataset statistics.

### Global Options

```bash
oolong-pairs --db <path> <command>
```

| Option | Default | Description |
|--------|---------|-------------|
| `--db` | `data/benchmark.db` | Database path |

---

## Error Handling

### Common Exceptions

```python
# Strategy errors
ValueError("Unknown strategy: xyz")

# Storage errors
sqlite3.Error  # Database errors

# CLI errors
click.ClickException  # CLI-specific errors

# Execution errors
RuntimeError("Claude CLI failed: ...")
subprocess.TimeoutExpired  # Task timeout
```

### Best Practices

```python
from oolong_pairs.strategies import get_strategy, BaseStrategy
from oolong_pairs.models import Result

def safe_execute(strategy: BaseStrategy, task, run_id: str) -> Result:
    """Execute task with error handling."""
    try:
        return strategy.execute(task, run_id)
    except subprocess.TimeoutExpired:
        return Result(
            task_id=task.id,
            run_id=run_id,
            strategy=strategy.strategy,
            actual_answer="",
            expected_answer=task.expected_answer,
            score=0.0,
            latency_ms=300000,  # Timeout value
            error="Task timed out",
        )
    except Exception as e:
        return Result(
            task_id=task.id,
            run_id=run_id,
            strategy=strategy.strategy,
            actual_answer="",
            expected_answer=task.expected_answer,
            score=0.0,
            latency_ms=0,
            error=str(e),
        )
```
