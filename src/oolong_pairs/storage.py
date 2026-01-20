"""SQLite storage for benchmark results."""

import json
import sqlite3
from pathlib import Path
from .models import BenchmarkRun, ExecutionMode, Result, RunSummary, Strategy

DEFAULT_DB_PATH = Path("data/benchmark.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
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

CREATE TABLE IF NOT EXISTS results (
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

CREATE INDEX IF NOT EXISTS idx_results_run_id ON results(run_id);
CREATE INDEX IF NOT EXISTS idx_results_task_id ON results(task_id);
"""


class Storage:
    """SQLite storage for benchmark data."""

    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(SCHEMA)

    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def save_run(self, run: BenchmarkRun) -> None:
        """Insert or update a benchmark run."""
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO runs
                (id, timestamp, mode, strategy, tasks_total, tasks_completed,
                 tasks_failed, avg_score, total_latency_ms, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.id,
                    run.timestamp.isoformat(),
                    run.mode.value,
                    run.strategy.value,
                    run.tasks_total,
                    run.tasks_completed,
                    run.tasks_failed,
                    run.avg_score,
                    run.total_latency_ms,
                    json.dumps(run.metadata),
                ),
            )

    def save_result(self, result: Result) -> None:
        """Insert a task result."""
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO results
                (run_id, task_id, strategy, actual_answer, expected_answer,
                 score, latency_ms, tokens_used, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.run_id,
                    result.task_id,
                    result.strategy.value,
                    result.actual_answer,
                    result.expected_answer,
                    result.score,
                    result.latency_ms,
                    result.tokens_used,
                    result.error,
                ),
            )

    def get_run(self, run_id: str) -> BenchmarkRun | None:
        """Get a benchmark run by ID."""
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
            if not row:
                return None
            return BenchmarkRun(
                id=row["id"],
                timestamp=row["timestamp"],
                mode=ExecutionMode(row["mode"]),
                strategy=Strategy(row["strategy"]),
                tasks_total=row["tasks_total"],
                tasks_completed=row["tasks_completed"],
                tasks_failed=row["tasks_failed"],
                avg_score=row["avg_score"],
                total_latency_ms=row["total_latency_ms"],
                metadata=json.loads(row["metadata"]),
            )

    def get_results(self, run_id: str) -> list[Result]:
        """Get all results for a run."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM results WHERE run_id = ? ORDER BY id", (run_id,)
            ).fetchall()
            return [
                Result(
                    task_id=row["task_id"],
                    run_id=row["run_id"],
                    strategy=Strategy(row["strategy"]),
                    actual_answer=row["actual_answer"] or "",
                    expected_answer=row["expected_answer"] or "",
                    score=row["score"],
                    latency_ms=row["latency_ms"],
                    tokens_used=row["tokens_used"],
                    error=row["error"],
                )
                for row in rows
            ]

    def get_run_summary(self, run_id: str) -> RunSummary | None:
        """Get summary statistics for a run."""
        run = self.get_run(run_id)
        if not run:
            return None

        results = self.get_results(run_id)
        if not results:
            return RunSummary(
                run_id=run_id,
                strategy=run.strategy,
                mode=run.mode,
                tasks_completed=0,
                tasks_failed=0,
                avg_score=0.0,
                min_score=0.0,
                max_score=0.0,
                total_latency_ms=0.0,
                avg_latency_ms=0.0,
            )

        scores = [r.score for r in results if r.error is None]
        failed = [r for r in results if r.error is not None]

        return RunSummary(
            run_id=run_id,
            strategy=run.strategy,
            mode=run.mode,
            tasks_completed=len(scores),
            tasks_failed=len(failed),
            avg_score=sum(scores) / len(scores) if scores else 0.0,
            min_score=min(scores) if scores else 0.0,
            max_score=max(scores) if scores else 0.0,
            total_latency_ms=sum(r.latency_ms for r in results),
            avg_latency_ms=sum(r.latency_ms for r in results) / len(results),
        )

    def list_runs(self, limit: int = 20) -> list[BenchmarkRun]:
        """List recent benchmark runs."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM runs ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
            return [
                BenchmarkRun(
                    id=row["id"],
                    timestamp=row["timestamp"],
                    mode=ExecutionMode(row["mode"]),
                    strategy=Strategy(row["strategy"]),
                    tasks_total=row["tasks_total"],
                    tasks_completed=row["tasks_completed"],
                    tasks_failed=row["tasks_failed"],
                    avg_score=row["avg_score"],
                    total_latency_ms=row["total_latency_ms"],
                    metadata=json.loads(row["metadata"]),
                )
                for row in rows
            ]

    def export_results(self, run_id: str, output_path: Path, format: str = "json") -> None:
        """Export results to file."""
        results = self.get_results(run_id)
        data = [r.model_dump() for r in results]

        output_path.parent.mkdir(parents=True, exist_ok=True)

        if format == "json":
            with open(output_path, "w") as f:
                json.dump(data, f, indent=2, default=str)
        elif format == "jsonl":
            with open(output_path, "w") as f:
                for item in data:
                    f.write(json.dumps(item, default=str) + "\n")
        elif format == "csv":
            import csv

            if data:
                with open(output_path, "w", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=data[0].keys())
                    writer.writeheader()
                    writer.writerows(data)

    def update_run_stats(self, run_id: str) -> None:
        """Update run statistics from results."""
        with self._get_conn() as conn:
            stats = conn.execute(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN error IS NULL THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) as failed,
                    AVG(CASE WHEN error IS NULL THEN score ELSE NULL END) as avg_score,
                    SUM(latency_ms) as total_latency
                FROM results WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()

            conn.execute(
                """
                UPDATE runs SET
                    tasks_total = ?,
                    tasks_completed = ?,
                    tasks_failed = ?,
                    avg_score = ?,
                    total_latency_ms = ?
                WHERE id = ?
                """,
                (
                    stats["total"] or 0,
                    stats["completed"] or 0,
                    stats["failed"] or 0,
                    stats["avg_score"] or 0.0,
                    stats["total_latency"] or 0.0,
                    run_id,
                ),
            )
