# Contributing to OOLONG-Pairs

Thank you for your interest in contributing to OOLONG-Pairs! This guide walks you through the contribution process step by step.

## Table of Contents

- [Development Environment Setup](#development-environment-setup)
- [Code Style and Standards](#code-style-and-standards)
- [Making Changes](#making-changes)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Adding New Features](#adding-new-features)
- [Documentation](#documentation)
- [Issue Reporting](#issue-reporting)

## Development Environment Setup

### Prerequisites

Before contributing, ensure you have:

- Python 3.11 or higher
- uv (recommended) or pip
- Git
- Claude CLI (for integration testing)
- (Optional) rlm-rs for RLM-RS strategy testing

### Step 1: Fork and Clone

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/oolong-pairs.git
cd oolong-pairs
```

### Step 2: Set Up Development Environment

#### Using uv (Recommended)

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv sync

# Install development dependencies
uv sync --dev
```

#### Using pip

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in editable mode with dev dependencies
pip install -e ".[dev]"
```

### Step 3: Verify Installation

```bash
# Run the CLI
oolong-pairs --help

# Run tests
pytest tests/
```

### Step 4: Set Up Pre-commit Hooks (Optional but Recommended)

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install
```

## Code Style and Standards

### Python Style

OOLONG-Pairs follows these standards:

1. **Type hints**: All public functions must have type hints
2. **Docstrings**: All modules, classes, and public functions need docstrings
3. **Line length**: Maximum 88 characters (Black default)
4. **Imports**: Use absolute imports, sorted with isort

### Example Function

```python
def calculate_score(
    actual: str,
    expected: str,
    answer_type: AnswerType,
    base: float = 0.75,
) -> float:
    """Calculate the accuracy score for a benchmark answer.

    Uses exponential decay for numeric answers (0.75^|error|) and
    exact matching for label/categorical answers.

    Args:
        actual: The answer produced by the model.
        expected: The expected correct answer.
        answer_type: The type of answer (NUMERIC, LABEL, etc.).
        base: Base for exponential decay scoring.

    Returns:
        Score between 0.0 and 1.0.

    Raises:
        ValueError: If answer_type is not recognized.

    Example:
        >>> calculate_score("42", "42", AnswerType.NUMERIC)
        1.0
        >>> calculate_score("40", "42", AnswerType.NUMERIC)
        0.5625
    """
    # Implementation...
```

### Code Formatting

Use these tools before committing:

```bash
# Format code with Black
black src/ tests/

# Sort imports with isort
isort src/ tests/

# Type check with mypy
mypy src/

# Lint with ruff
ruff check src/ tests/
```

### Configuration Files

The project uses these configuration files:

- `pyproject.toml`: Project metadata and tool configuration
- `.pre-commit-config.yaml`: Pre-commit hook configuration (if added)
- `ruff.toml`: Ruff linter configuration (if added)

## Making Changes

### Step 1: Create a Branch

Always work on a feature branch, never directly on `main`:

```bash
# Ensure you're on main and it's up to date
git checkout main
git pull upstream main  # If you have upstream configured

# Create and switch to a new branch
git checkout -b feature/your-feature-name
```

Branch naming conventions:

| Type | Format | Example |
|------|--------|---------|
| Feature | `feature/description` | `feature/add-rouge-scoring` |
| Bug fix | `fix/description` | `fix/numeric-parsing` |
| Documentation | `docs/description` | `docs/hooks-guide-update` |
| Refactor | `refactor/description` | `refactor/storage-layer` |

### Step 2: Make Your Changes

1. Write your code following the style guidelines
2. Add or update tests as needed
3. Update documentation if behavior changes
4. Commit frequently with clear messages

### Step 3: Commit Messages

Follow conventional commit format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Code style (formatting, semicolons, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

Examples:

```bash
# Feature
git commit -m "feat(scoring): add ROUGE-L scoring for text answers"

# Bug fix
git commit -m "fix(dataset): handle missing context field gracefully"

# Documentation
git commit -m "docs(hooks): add troubleshooting section"
```

## Testing

### Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=src/oolong_pairs --cov-report=html

# Run specific test file
pytest tests/test_scoring.py

# Run specific test
pytest tests/test_scoring.py::test_exact_match

# Run with verbose output
pytest tests/ -v
```

### Writing Tests

Tests live in the `tests/` directory with filenames matching `test_*.py`.

#### Test Structure

```python
"""Tests for the scoring module."""

import pytest
from oolong_pairs.models import AnswerType
from oolong_pairs.scoring import calculate_score, extract_numeric


class TestCalculateScore:
    """Tests for calculate_score function."""

    def test_exact_numeric_match(self):
        """Exact numeric match should return 1.0."""
        score = calculate_score("42", "42", AnswerType.NUMERIC)
        assert score == 1.0

    def test_numeric_with_tolerance(self):
        """Numeric within tolerance should score correctly."""
        # Off by 2: 0.75^2 = 0.5625
        score = calculate_score("40", "42", AnswerType.NUMERIC)
        assert abs(score - 0.5625) < 0.001

    @pytest.mark.parametrize("actual,expected,expected_score", [
        ("PERSON", "PERSON", 1.0),
        ("person", "PERSON", 1.0),  # Case insensitive
        ("LOCATION", "PERSON", 0.0),
    ])
    def test_label_scoring(self, actual, expected, expected_score):
        """Label scoring uses exact match (case insensitive)."""
        score = calculate_score(actual, expected, AnswerType.LABEL)
        assert score == expected_score


class TestExtractNumeric:
    """Tests for extract_numeric function."""

    def test_simple_integer(self):
        """Simple integer extraction."""
        assert extract_numeric("42") == 42.0

    def test_with_surrounding_text(self):
        """Extract number from text."""
        assert extract_numeric("The answer is 42.") == 42.0

    def test_negative_number(self):
        """Handle negative numbers."""
        assert extract_numeric("-15") == -15.0

    def test_no_number_returns_none(self):
        """Return None when no number found."""
        assert extract_numeric("no numbers here") is None
```

#### Test Categories

1. **Unit tests**: Test individual functions in isolation
2. **Integration tests**: Test component interactions
3. **End-to-end tests**: Test full benchmark runs (slower)

Mark slow tests:

```python
@pytest.mark.slow
def test_full_benchmark_run():
    """Run a complete benchmark (slow, requires Claude)."""
    # This test is skipped by default, run with: pytest -m slow
    pass
```

### Test Coverage Requirements

- New code should have at least 80% test coverage
- All public functions must have at least one test
- Edge cases should be tested

Check coverage:

```bash
pytest tests/ --cov=src/oolong_pairs --cov-report=term-missing
```

## Submitting Changes

### Step 1: Push Your Branch

```bash
git push origin feature/your-feature-name
```

### Step 2: Create a Pull Request

1. Go to the repository on GitHub
2. Click "Compare & pull request"
3. Fill in the PR template:

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Refactoring

## Testing
Describe how you tested these changes

## Checklist
- [ ] Code follows project style guidelines
- [ ] Tests pass locally
- [ ] New tests added for new functionality
- [ ] Documentation updated
```

### Step 3: Address Review Feedback

1. Make requested changes in new commits
2. Push updates to the same branch
3. Respond to comments

### Step 4: Merge

Once approved, a maintainer will merge your PR.

## Adding New Features

### Adding a New Strategy

See [CUSTOMIZATION.md](./CUSTOMIZATION.md) for detailed instructions. Summary:

1. Create strategy function in `src/oolong_pairs/strategies.py`
2. Add to `STRATEGY_REGISTRY`
3. Update `Strategy` enum in `models.py`
4. Add tests in `tests/test_strategies.py`
5. Update documentation

### Adding a New Answer Type

1. Add to `AnswerType` enum in `models.py`:
   ```python
   class AnswerType(Enum):
       NUMERIC = "NUMERIC"
       LABEL = "LABEL"
       YOUR_NEW_TYPE = "YOUR_NEW_TYPE"
   ```

2. Add scoring logic in `scoring.py`
3. Add tests
4. Update documentation

### Adding a New CLI Command

1. Add command in `src/oolong_pairs/cli.py`:
   ```python
   @cli.command()
   @click.argument("name")
   @click.option("--flag", "-f", is_flag=True, help="Description")
   def your_command(name: str, flag: bool):
       """Command description shown in help."""
       # Implementation
   ```

2. Add tests
3. Update CLI reference in documentation

## Documentation

### Documentation Structure

```
docs/
├── QUICKSTART.md       # Getting started guide
├── HOOKS-GUIDE.md      # Hooks integration
├── CUSTOMIZATION.md    # Extension guide
├── API-REFERENCE.md    # API documentation
└── CONTRIBUTING.md     # This file
```

### Writing Documentation

1. Use clear, concise language
2. Include code examples for all features
3. Keep examples runnable
4. Use consistent formatting

### Documentation Standards

- Use ATX-style headers (`#`, `##`, `###`)
- Code blocks must specify language
- Tables for comparisons
- Links between related documents

### Building Documentation Locally

Documentation is plain Markdown. To preview:

```bash
# Using grip (GitHub-flavored markdown)
pip install grip
grip docs/QUICKSTART.md

# Or using a Markdown preview extension in your editor
```

## Issue Reporting

### Reporting Bugs

Create a GitHub issue with:

1. **Title**: Clear, concise description
2. **Environment**: Python version, OS, Claude CLI version
3. **Steps to reproduce**: Minimal steps to trigger the bug
4. **Expected behavior**: What should happen
5. **Actual behavior**: What actually happens
6. **Error messages**: Full stack traces if applicable

Template:

```markdown
## Bug Description
Brief description of the bug

## Environment
- Python version: 3.11.x
- OS: macOS 14.x / Ubuntu 22.04 / Windows 11
- Claude CLI version: x.x.x
- OOLONG-Pairs version: x.x.x

## Steps to Reproduce
1. Run `oolong-pairs run --strategy truncation --limit 1`
2. Wait for completion
3. Observe error

## Expected Behavior
The benchmark should complete successfully

## Actual Behavior
Error occurs with message: [error message]

## Stack Trace
```
[paste full stack trace here]
```

## Additional Context
Any other relevant information
```

### Requesting Features

Create a GitHub issue with:

1. **Title**: Feature description
2. **Use case**: Why this feature is needed
3. **Proposed solution**: How it might work
4. **Alternatives considered**: Other approaches

## Questions?

- Open a GitHub Discussion for general questions
- Check existing issues before creating new ones
- Join the community chat (if available)

Thank you for contributing to OOLONG-Pairs!
