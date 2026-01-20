# Claude Code Hooks Integration Guide

This guide explains how to use OOLONG-Pairs in hooks mode, which integrates directly with Claude Code sessions to test the rlm-rs plugin in real interactive scenarios.

## Overview

Hooks mode differs from SDK mode in a critical way:

| Aspect | SDK Mode | Hooks Mode |
|--------|----------|------------|
| Invocation | Calls `claude --print` directly | Uses Claude Code hooks |
| Plugin testing | Calls rlm-rs CLI directly | Claude executes plugin commands |
| Realism | Tests algorithm only | Tests full plugin integration |
| Setup | Simple | Requires hook configuration |

**Use hooks mode when you want to test how the rlm-rs plugin performs in actual Claude Code sessions.**

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         HOOKS MODE FLOW                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐                     ┌──────────────────────────┐  │
│  │ Orchestrator │                     │   Claude Code Session    │  │
│  │              │                     │                          │  │
│  │ 1. Write     │                     │  ┌────────────────────┐  │  │
│  │    task      │─────────────────────▶│  │ SessionStart Hook │  │  │
│  │    state     │                     │  │                    │  │  │
│  │              │                     │  │ - Read task state  │  │  │
│  │ 2. Launch    │                     │  │ - Inject prompt    │  │  │
│  │    session   │═════════════════════▶│  └────────────────────┘  │  │
│  │              │                     │            │              │  │
│  │              │                     │            ▼              │  │
│  │              │                     │  ┌────────────────────┐  │  │
│  │              │                     │  │ Claude processes   │  │  │
│  │              │                     │  │                    │  │  │
│  │              │                     │  │ For RLM-RS:        │  │  │
│  │              │                     │  │ - /rlm-load        │  │  │
│  │              │                     │  │ - /rlm-query       │  │  │
│  │              │                     │  │   └─ subcalls      │  │  │
│  │              │                     │  │   └─ synthesize    │  │  │
│  │              │                     │  │                    │  │  │
│  │              │                     │  │ Outputs "ANSWER:"  │  │  │
│  │              │                     │  └────────────────────┘  │  │
│  │              │                     │            │              │  │
│  │              │                     │            ▼              │  │
│  │              │                     │  ┌────────────────────┐  │  │
│  │              │                     │  │ Stop Hook          │  │  │
│  │              │                     │  │                    │  │  │
│  │ 4. Read      │◀────────────────────│  │ - Extract answer   │  │  │
│  │    result    │                     │  │ - Score answer     │  │  │
│  │              │                     │  │ - Save to SQLite   │  │  │
│  │              │                     │  └────────────────────┘  │  │
│  │ 5. Next      │                     │                          │  │
│  │    task      │                     │                          │  │
│  └──────────────┘                     └──────────────────────────┘  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Step 1: Understand the Hook Files

OOLONG-Pairs includes three hook files in the `hooks/` directory:

### hooks/hooks.json

Defines when hooks run:

```json
{
  "SessionStart": [
    {
      "matcher": ".*",
      "hooks": [
        {
          "type": "command",
          "command": "python ${CLAUDE_PLUGIN_ROOT}/hooks/session_start.py",
          "timeout": 2000
        }
      ]
    }
  ],
  "Stop": [
    {
      "matcher": ".*",
      "hooks": [
        {
          "type": "command",
          "command": "python ${CLAUDE_PLUGIN_ROOT}/hooks/stop.py"
        }
      ]
    }
  ]
}
```

### hooks/session_start.py

Executes at session start:

1. Checks for queued task in `$OOLONG_STATE_DIR/current_task.json`
2. If task exists with status "pending":
   - Marks status as "in_progress"
   - Writes context to temp file
   - Outputs injection prompt based on strategy

For **truncation** strategy:
```xml
<benchmark-task id="...">
You are being evaluated on a long-context reasoning benchmark.

<context>
[truncated context here]
</context>

<question>
[question here]
</question>

Analyze the context above and answer the question.
Output ONLY the final answer on a single line prefixed with "ANSWER: "
</benchmark-task>
```

For **rlm_rs** strategy:
```xml
<benchmark-task id="...">
You are being evaluated on a long-context reasoning benchmark using the RLM pattern.

The context document is located at: /tmp/oolong-pairs/context_<id>.txt

Use the rlm-rs plugin to process this large document:
1. Load the file: `/rlm-load file=/tmp/oolong-pairs/context_<id>.txt`
2. Query it: `/rlm-query query="<question>"`

The plugin will chunk the document, run subcalls on relevant chunks, and synthesize an answer.

After getting the synthesized answer, output ONLY the final answer on a single line prefixed with "ANSWER: "
</benchmark-task>
```

### hooks/stop.py

Executes at session end:

1. Reads session data from stdin (JSON)
2. Extracts answer (looks for "ANSWER: " prefix)
3. Scores against expected answer
4. Saves result to SQLite database
5. Updates task state to "completed"

## Step 2: Configure Environment

Set required environment variables:

```bash
# Directory for task state files
export OOLONG_STATE_DIR=/tmp/oolong-pairs

# Path to SQLite database
export OOLONG_DB_PATH=/path/to/oolong-pairs/data/benchmark.db

# Create the state directory
mkdir -p $OOLONG_STATE_DIR
```

## Step 3: Register Hooks with Claude Code

### Option A: As a Claude Code Plugin

Create a `plugin.json` in the oolong-pairs directory:

```json
{
  "name": "oolong-pairs",
  "version": "0.1.0",
  "description": "OOLONG benchmark harness for plugin testing"
}
```

Then install the plugin:
```bash
claude plugins install /path/to/oolong-pairs
```

### Option B: Manual Hook Registration

Add to your Claude Code configuration (`~/.config/claude/settings.json`):

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": ".*",
        "hooks": [
          {
            "type": "command",
            "command": "python /path/to/oolong-pairs/hooks/session_start.py",
            "timeout": 2000
          }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": ".*",
        "hooks": [
          {
            "type": "command",
            "command": "python /path/to/oolong-pairs/hooks/stop.py"
          }
        ]
      }
    ]
  }
}
```

## Step 4: Install rlm-rs Plugin (for RLM-RS Strategy)

The rlm-rs plugin must be installed for the RLM-RS strategy to work:

```bash
# Clone rlm-rs-plugin
git clone https://github.com/zircote/rlm-rs-plugin.git

# Install as Claude Code plugin
claude plugins install /path/to/rlm-rs-plugin
```

Verify installation:
```bash
claude "/rlm-status"  # Should show RLM status
```

## Step 5: Run Benchmark in Hooks Mode

### Using the Python Orchestrator

```python
from oolong_pairs.orchestrator import HooksOrchestrator
from oolong_pairs.models import Strategy
from pathlib import Path

# Create orchestrator
orchestrator = HooksOrchestrator(
    strategy=Strategy.RLM_RS,
    db_path=Path("data/benchmark.db"),
    state_dir=Path("/tmp/oolong-pairs"),
    model="claude-sonnet-4-20250514",
)

# Run benchmark
run_id = orchestrator.run_benchmark(
    dataset_filter="trec_coarse",
    split="validation",
    min_context_length=100_000,
    limit=5,  # Start with 5 tasks
)

print(f"Completed benchmark run: {run_id}")
```

### Using the CLI

```bash
# Run in hooks mode
oolong-pairs run --strategy rlm_rs --mode hooks --limit 5
```

**Note:** The CLI hooks mode is experimental. The Python orchestrator provides more control.

## Step 6: Understanding Task State Flow

The task state file (`$OOLONG_STATE_DIR/current_task.json`) tracks task progress:

### State: pending
```json
{
  "task_id": "abc123",
  "run_id": "run456",
  "context": "...",
  "question": "...",
  "expected_answer": "42",
  "answer_type": "NUMERIC",
  "strategy": "rlm_rs",
  "status": "pending",
  "start_time": 1705689600.0
}
```

### State: in_progress
After SessionStart hook runs:
```json
{
  "...": "...",
  "status": "in_progress"
}
```

### State: completed
After Stop hook runs:
```json
{
  "...": "...",
  "status": "completed",
  "actual_answer": "42",
  "score": 1.0
}
```

## Step 7: Debugging Hooks

### Enable Verbose Output

Add debug output to hooks:

```python
# In session_start.py
import sys
print(f"[DEBUG] Task ID: {task_id}", file=sys.stderr)
print(f"[DEBUG] Strategy: {strategy}", file=sys.stderr)
```

### Check State Files

```bash
# Watch state file changes
watch -n 1 cat /tmp/oolong-pairs/current_task.json

# View context file
cat /tmp/oolong-pairs/context_*.txt | head -100
```

### View Hook Execution

Claude Code logs hook execution. Check:
- SessionStart hook output (injected into session)
- Stop hook stderr (any errors)

## Step 8: Analyzing Results

After running in hooks mode, use the same analysis commands:

```bash
# Show results
oolong-pairs show <run_id>

# Compare hooks vs SDK results
oolong-pairs compare <sdk_run_id> <hooks_run_id>

# Export for analysis
oolong-pairs export <run_id> hooks_results.json
```

## Hooks Mode vs SDK Mode Comparison

| Feature | SDK Mode | Hooks Mode |
|---------|----------|------------|
| **What's tested** | rlm-rs CLI algorithm | Full rlm-rs plugin |
| **Claude invocation** | `claude --print` | Interactive session |
| **Plugin commands** | Not used | `/rlm-load`, `/rlm-query` |
| **Subagent spawning** | Direct subprocess | Claude Task tool |
| **Realism** | Lower | Higher |
| **Speed** | Faster | Slower |
| **Setup complexity** | Simple | Requires hook setup |

## Troubleshooting

### Hook not executing

1. Verify environment variables are set:
   ```bash
   echo $OOLONG_STATE_DIR
   echo $OOLONG_DB_PATH
   ```

2. Check hook file permissions:
   ```bash
   chmod +x hooks/session_start.py
   chmod +x hooks/stop.py
   ```

3. Test hook manually:
   ```bash
   # Create test state
   echo '{"status":"pending","task_id":"test","strategy":"truncation","context":"Hello","question":"What?"}' > /tmp/oolong-pairs/current_task.json

   # Run hook
   python hooks/session_start.py
   ```

### No answer captured

1. Ensure Claude outputs "ANSWER: " prefix
2. Check stop hook can read stdin:
   ```bash
   echo '{"final_summary":"ANSWER: 42"}' | python hooks/stop.py
   ```

### Plugin commands not found

1. Verify rlm-rs-plugin is installed:
   ```bash
   claude "/help"  # Should show rlm-* commands
   ```

2. Check plugin path in Claude Code configuration

## Advanced: Custom Orchestration

For complex scenarios, you can write custom orchestration:

```python
import json
import subprocess
import time
from pathlib import Path

def run_single_task(task_data: dict, state_dir: Path) -> dict:
    """Run a single benchmark task with custom handling."""
    state_file = state_dir / "current_task.json"

    # Write task state
    task_data["status"] = "pending"
    task_data["start_time"] = time.time()
    state_file.write_text(json.dumps(task_data))

    # Launch Claude session
    # The hooks will inject the prompt and capture the answer
    result = subprocess.run(
        ["claude", "--print", "-p", "Begin benchmark task."],
        capture_output=True,
        text=True,
        timeout=600,
    )

    # Read completed state
    completed_state = json.loads(state_file.read_text())

    return {
        "task_id": task_data["task_id"],
        "score": completed_state.get("score", 0.0),
        "actual_answer": completed_state.get("actual_answer", ""),
    }
```

## Next Steps

- [CUSTOMIZATION.md](./CUSTOMIZATION.md) - Add custom strategies
- [API-REFERENCE.md](./API-REFERENCE.md) - Module documentation
- [CONTRIBUTING.md](./CONTRIBUTING.md) - Contribute improvements
