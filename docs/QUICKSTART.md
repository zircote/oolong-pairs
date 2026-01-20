# Quick Start Guide

This guide walks you through setting up and running your first OOLONG-Pairs benchmark in under 5 minutes.

## Prerequisites Checklist

Before starting, ensure you have:

- [ ] Python 3.11 or higher installed
- [ ] Claude CLI installed and authenticated (`claude --version`)
- [ ] (Optional) rlm-rs installed for RLM-RS strategy (`cargo install rlm-rs`)

## Step 1: Install OOLONG-Pairs

### Option A: Using uv (Recommended)

```bash
# Clone the repository
git clone https://github.com/zircote/oolong-pairs.git
cd oolong-pairs

# Install with uv
uv sync
```

### Option B: Using pip

```bash
# Clone the repository
git clone https://github.com/zircote/oolong-pairs.git
cd oolong-pairs

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in editable mode
pip install -e .
```

## Step 2: Verify Installation

```bash
# Check the CLI is available
oolong-pairs --help
```

Expected output:
```
Usage: oolong-pairs [OPTIONS] COMMAND [ARGS]...

  OOLONG-Pairs benchmark harness for Claude Code plugin testing.

Options:
  --db TEXT  Database path
  --help     Show this message and exit.

Commands:
  compare    Compare two benchmark runs.
  export     Export run results to file.
  list-runs  List recent benchmark runs.
  run        Run benchmark with specified strategy.
  show       Show results for a benchmark run.
  stats      Show dataset statistics.
```

## Step 3: Check Dataset Availability

```bash
# View dataset statistics (downloads dataset on first run)
oolong-pairs stats --dataset trec_coarse
```

This will:
1. Download the OOLONG dataset from HuggingFace (first run only)
2. Display statistics about available tasks

## Step 4: Run Your First Benchmark

### Truncation Strategy (Baseline)

```bash
# Run 5 tasks using truncation strategy
oolong-pairs run --strategy truncation --limit 5
```

Step-by-step breakdown:
1. The harness loads 5 tasks from the OOLONG dataset
2. For each task, it truncates the context to 180k characters
3. Sends the truncated context + question to Claude
4. Captures the answer and scores it
5. Displays a summary table

### RLM-RS Strategy (Requires rlm-rs)

```bash
# First, verify rlm-rs is installed
rlm-rs --version

# Run 5 tasks using RLM-RS strategy
oolong-pairs run --strategy rlm_rs --limit 5
```

Step-by-step breakdown:
1. The harness loads 5 tasks from the OOLONG dataset
2. For each task:
   - Chunks the document using rlm-rs
   - Processes each chunk with Claude Haiku
   - Synthesizes findings with Claude Sonnet
3. Scores the final answer
4. Displays a summary table

## Step 5: View Results

### Show Results for a Run

```bash
# The run command displays results, but you can also view them later
oolong-pairs show <run_id>
```

Example output:
```
┏━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┓
┃ Metric           ┃ Value       ┃
┡━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━┩
│ Strategy         │ truncation  │
│ Mode             │ sdk         │
│ Tasks Completed  │ 5           │
│ Tasks Failed     │ 0           │
│ Average Score    │ 0.7500      │
│ Min Score        │ 0.5625      │
│ Max Score        │ 1.0000      │
│ Total Latency    │ 45230ms     │
│ Avg Latency      │ 9046ms      │
└──────────────────┴─────────────┘
```

### List All Runs

```bash
oolong-pairs list-runs
```

## Step 6: Compare Strategies

After running benchmarks with both strategies:

```bash
# Compare two runs
oolong-pairs compare <truncation_run_id> <rlm_rs_run_id>
```

This shows a side-by-side comparison of scores and latencies.

## Step 7: Export Results

```bash
# Export to JSON
oolong-pairs export <run_id> results.json --format json

# Export to CSV for spreadsheet analysis
oolong-pairs export <run_id> results.csv --format csv

# Export to JSONL for streaming processing
oolong-pairs export <run_id> results.jsonl --format jsonl
```

## Common Options Reference

| Option | Description | Default |
|--------|-------------|---------|
| `--strategy` | Execution strategy (`truncation` or `rlm_rs`) | Required |
| `--limit` | Maximum tasks to run | All tasks |
| `--min-context` | Minimum context length in characters | 100,000 |
| `--dataset` | Dataset filter | `trec_coarse` |
| `--mode` | Execution mode (`sdk` or `hooks`) | `sdk` |
| `--db` | Database path for storing results | `data/benchmark.db` |

## Next Steps

- **Run a larger benchmark**: Remove the `--limit` flag to run all tasks
- **Customize strategies**: See [CUSTOMIZATION.md](./CUSTOMIZATION.md)
- **Use hooks mode**: See [HOOKS-GUIDE.md](./HOOKS-GUIDE.md) for Claude Code integration
- **Understand scoring**: See [README.md](../README.md#scoring) for scoring methodology

## Troubleshooting

### "Command not found: oolong-pairs"

Ensure your virtual environment is activated:
```bash
source .venv/bin/activate  # or: uv run oolong-pairs
```

### "Claude CLI failed"

Verify Claude CLI is authenticated:
```bash
claude --version
claude "Hello"  # Should get a response
```

### "rlm-rs: command not found"

Install rlm-rs for the RLM-RS strategy:
```bash
cargo install rlm-rs
```

### Slow first run

The first run downloads the OOLONG dataset (~500MB). Subsequent runs use the cached dataset.
