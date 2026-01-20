"""Dataset loading for OOLONG benchmark."""

from typing import Iterator

from datasets import load_dataset

from .models import AnswerType, Task


def map_answer_type(answer_type_str: str) -> AnswerType:
    """Map dataset answer_type string to AnswerType enum."""
    mapping = {
        "NUMERIC": AnswerType.NUMERIC,
        "NUMERIC_ONE_CLASS": AnswerType.NUMERIC,
        "LABEL": AnswerType.LABEL,
        "COMPARISON": AnswerType.COMPARISON,
        "DATE": AnswerType.DATE,
    }
    return mapping.get(answer_type_str.upper(), AnswerType.LABEL)


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
    # Load dataset from HuggingFace
    ds = load_dataset("oolongbench/oolong-synth", split=split)

    tasks = []
    for idx, row in enumerate(ds):
        # Filter by dataset column
        if dataset_filter and row.get("dataset") != dataset_filter:
            continue

        # Get context (prefer without labels for cleaner eval)
        context = row.get("context_window_text", "")

        # Filter by context length
        if len(context) < min_context_length:
            continue

        # Create task
        task = Task(
            id=f"{row.get('id', idx)}",
            dataset=row.get("dataset", "unknown"),
            context=context,
            question=row.get("question", ""),
            expected_answer=str(row.get("answer", "")).strip("[]"),
            answer_type=map_answer_type(row.get("answer_type", "LABEL")),
            context_length=len(context),
            task_type=row.get("task", ""),
            metadata={
                "task_group": row.get("task_group", ""),
                "num_labels": row.get("num_labels", 0),
                "context_window_id": row.get("context_window_id", 0),
                "input_subset": row.get("input_subset", ""),
            },
        )
        tasks.append(task)

        if limit and len(tasks) >= limit:
            break

    return tasks


def iter_oolong_tasks(
    dataset_filter: str = "trec_coarse",
    split: str = "validation",
    min_context_length: int = 100_000,
) -> Iterator[Task]:
    """Iterate OOLONG tasks without loading all into memory.

    Args:
        dataset_filter: Filter by dataset column
        split: Dataset split
        min_context_length: Minimum context length

    Yields:
        Task objects one at a time
    """
    ds = load_dataset("oolongbench/oolong-synth", split=split, streaming=True)

    for idx, row in enumerate(ds):
        if dataset_filter and row.get("dataset") != dataset_filter:
            continue

        context = row.get("context_window_text", "")
        if len(context) < min_context_length:
            continue

        yield Task(
            id=f"{row.get('id', idx)}",
            dataset=row.get("dataset", "unknown"),
            context=context,
            question=row.get("question", ""),
            expected_answer=str(row.get("answer", "")).strip("[]"),
            answer_type=map_answer_type(row.get("answer_type", "LABEL")),
            context_length=len(context),
            task_type=row.get("task", ""),
            metadata={
                "task_group": row.get("task_group", ""),
                "num_labels": row.get("num_labels", 0),
                "context_window_id": row.get("context_window_id", 0),
                "input_subset": row.get("input_subset", ""),
            },
        )


def get_dataset_stats(
    dataset_filter: str = "trec_coarse",
    split: str = "validation",
) -> dict:
    """Get statistics about the filtered dataset.

    Returns:
        Dictionary with task counts, context length distribution, etc.
    """
    ds = load_dataset("oolongbench/oolong-synth", split=split)

    total = 0
    filtered = 0
    context_lengths = []
    task_types: dict[str, int] = {}
    answer_types: dict[str, int] = {}

    for row in ds:
        total += 1
        if dataset_filter and row.get("dataset") != dataset_filter:
            continue
        filtered += 1

        ctx_len = len(row.get("context_window_text", ""))
        context_lengths.append(ctx_len)

        task_type = row.get("task", "unknown")
        task_types[task_type] = task_types.get(task_type, 0) + 1

        ans_type = row.get("answer_type", "unknown")
        answer_types[ans_type] = answer_types.get(ans_type, 0) + 1

    return {
        "total_in_split": total,
        "filtered_count": filtered,
        "dataset_filter": dataset_filter,
        "context_length": {
            "min": min(context_lengths) if context_lengths else 0,
            "max": max(context_lengths) if context_lengths else 0,
            "avg": sum(context_lengths) / len(context_lengths) if context_lengths else 0,
        },
        "task_types": task_types,
        "answer_types": answer_types,
    }
