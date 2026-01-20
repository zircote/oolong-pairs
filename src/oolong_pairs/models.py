"""Data models for OOLONG-Pairs benchmark."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AnswerType(str, Enum):
    """Type of answer expected."""

    NUMERIC = "NUMERIC"
    LABEL = "LABEL"
    COMPARISON = "COMPARISON"
    DATE = "DATE"


class Strategy(str, Enum):
    """Execution strategy for benchmark."""

    RLM_RS = "rlm_rs"
    TRUNCATION = "truncation"


class ExecutionMode(str, Enum):
    """Mode of execution."""

    SDK = "sdk"
    HOOKS = "hooks"


class Task(BaseModel):
    """A single OOLONG benchmark task."""

    id: str
    dataset: str  # e.g., 'trec_coarse'
    context: str  # The long context window text
    question: str
    expected_answer: str
    answer_type: AnswerType
    context_length: int = Field(default=0)
    task_type: str = ""  # e.g., 'MOST_FREQ', 'NUMERIC_ONE_CLASS'
    metadata: dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, _context: Any) -> None:
        """Calculate context length after initialization."""
        if self.context_length == 0:
            self.context_length = len(self.context)


class Result(BaseModel):
    """Result of a single task execution."""

    task_id: str
    run_id: str
    strategy: Strategy
    actual_answer: str
    expected_answer: str
    score: float  # 0.0 to 1.0
    latency_ms: float
    tokens_used: int = 0
    error: str | None = None


class BenchmarkRun(BaseModel):
    """A complete benchmark run."""

    id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    mode: ExecutionMode
    strategy: Strategy
    tasks_total: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    avg_score: float = 0.0
    total_latency_ms: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunSummary(BaseModel):
    """Summary statistics for a benchmark run."""

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
    by_task_type: dict[str, dict[str, float]] = Field(default_factory=dict)
