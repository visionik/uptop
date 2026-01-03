# Contributing to uptop

Thank you for your interest in contributing to uptop! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Development Setup](#development-setup)
- [Code Style Guidelines](#code-style-guidelines)
- [Pre-Commit Workflow](#pre-commit-workflow)
- [Commit Message Format](#commit-message-format)
- [Testing Requirements](#testing-requirements)
- [Pull Request Process](#pull-request-process)
- [Plugin Development](#plugin-development)

## Development Setup

### Prerequisites

- Python 3.11 or higher
- [Task](https://taskfile.dev/) (task runner)
- Git

### Initial Setup

1. **Fork and clone the repository**

   ```bash
   git clone https://github.com/yourusername/uptop.git
   cd uptop
   ```

2. **Create a virtual environment**

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install development dependencies**

   ```bash
   task install
   ```

   This will install uptop in editable mode with all development dependencies.

4. **Verify installation**

   ```bash
   task check
   ```

   This runs all quality checks (formatting, linting, type checking, tests, and coverage).

## Code Style Guidelines

We maintain high code quality standards using automated tools. All code must pass these checks before being merged.

### Formatting

- **Black**: Code formatter with 100-character line length
- **isort**: Import sorting with black-compatible profile

Run formatters:
```bash
task fmt
```

### Linting

- **Ruff**: Fast, comprehensive Python linter

Run linter:
```bash
task lint
```

### Type Checking

- **mypy**: Static type checker in strict mode
- **Type hints required**: All functions and methods must have type hints (PEP 484)

Run type checker:
```bash
task type
```

### Code Organization

- **File size**: Files SHOULD be < 500 lines, MUST be < 1000 lines
- **Documentation**: PEP 257 docstrings for all public APIs
- **Style compliance**: Follow PEP 8 via automated tools

### Example Code Style

```python
"""Module docstring describing the purpose of this module."""

from typing import Optional

from pydantic import BaseModel


class ExampleData(BaseModel):
    """Data model for example functionality.

    Attributes:
        value: The numeric value.
        label: A descriptive label.
    """

    value: float
    label: str


def process_data(data: ExampleData, threshold: float = 0.0) -> Optional[str]:
    """Process example data and return a result.

    Args:
        data: The data to process.
        threshold: Minimum threshold value (default: 0.0).

    Returns:
        A formatted string if value exceeds threshold, None otherwise.
    """
    if data.value > threshold:
        return f"{data.label}: {data.value}"
    return None
```

## Pre-Commit Workflow

**ALWAYS run `task check` before committing**. This is required and runs:

1. `task fmt` - Format code (black, isort)
2. `task lint` - Lint code (ruff)
3. `task type` - Type check (mypy)
4. `task test` - Run tests
5. `task test:coverage` - Verify coverage ≥75%

```bash
# Make your changes
git add .

# Run all quality checks
task check

# If all checks pass, commit
git commit -m "feat: add new feature"
```

**Note**: If `task check` fails, fix the issues before committing. Do not skip checks.

## Commit Message Format

We use [Conventional Commits](https://www.conventionalcommits.org/) format for all commit messages. This enables automated changelog generation and semantic versioning.

### Format

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only changes
- `style`: Code style changes (formatting, no logic change)
- `refactor`: Code restructuring (no feature/bug change)
- `test`: Adding or updating tests
- `chore`: Maintenance tasks (dependencies, build, etc.)
- `perf`: Performance improvements
- `ci`: CI/CD changes
- `build`: Build system changes

### Scope (optional)

The scope specifies what part of the codebase is affected:

- `core`: Core plugin system
- `tui`: TUI implementation
- `cli`: CLI mode
- `cpu`: CPU pane
- `memory`: Memory pane
- `process`: Process pane
- `network`: Network pane
- `disk`: Disk pane
- `gpu`: GPU pane
- `sensors`: Sensors pane
- `config`: Configuration system
- `docs`: Documentation

### Examples

```bash
# Feature
git commit -m "feat(cpu): add per-core temperature display"

# Bug fix
git commit -m "fix(process): handle permission denied errors gracefully"

# Documentation
git commit -m "docs: update plugin development guide"

# Refactoring
git commit -m "refactor(core): extract plugin loading logic"

# Testing
git commit -m "test(network): add unit tests for bandwidth calculation"

# With body
git commit -m "feat(tui): add theme switching

Add runtime theme switching with keybinding 'T'.
Supports all built-in themes and custom themes.

Closes #123"
```

### Breaking Changes

For breaking changes, add `BREAKING CHANGE:` in the footer:

```bash
git commit -m "feat(api): redesign plugin API

BREAKING CHANGE: PanePlugin.collect_data() now returns Pydantic model instead of dict"
```

## Testing Requirements

All code must have comprehensive tests. We enforce minimum coverage requirements.

### Coverage Requirements

- **Overall coverage**: ≥75%
- **Per-module coverage**: ≥75%
- **Exclusions**: `__main__` and entry points are excluded from coverage

### Running Tests

```bash
# Run all tests
task test

# Run tests with coverage report
task test:coverage

# Run specific test file
pytest tests/test_specific.py

# Run tests matching a pattern
pytest -k "test_cpu"
```

### Test Organization

```
tests/
├── unit/           # Unit tests (individual functions/classes)
├── integration/    # Integration tests (end-to-end workflows)
└── fixtures/       # Shared test fixtures
```

### Writing Tests

Use pytest with these tools:

- **pytest-cov**: Coverage reporting
- **pytest-mock**: Mocking support
- **pytest-asyncio**: Async test support
- **pytest-snapshot**: Snapshot testing for formatters

Example unit test:

```python
"""Tests for CPU data collection."""

import pytest
from unittest.mock import Mock, patch

from uptop.plugins.cpu import CPUPane, CPUData


@pytest.fixture
def mock_psutil():
    """Mock psutil functions."""
    with patch('psutil.cpu_percent') as cpu_pct, \
         patch('psutil.cpu_freq') as cpu_freq, \
         patch('psutil.getloadavg') as load_avg:
        cpu_pct.return_value = [45.2, 32.1]
        cpu_freq.return_value = [Mock(current=2800), Mock(current=2600)]
        load_avg.return_value = (1.2, 1.5, 1.8)
        yield


def test_cpu_collect_data(mock_psutil):
    """Test CPU data collection."""
    pane = CPUPane()
    data = pane.collect_data()

    assert isinstance(data, CPUData)
    assert len(data.cores) == 2
    assert data.cores[0].usage_percent == 45.2
    assert data.load_avg_1min == 1.2
```

### Integration Tests

Test complete workflows:

```python
"""Integration tests for CLI mode."""

import json
from click.testing import CliRunner

from uptop.__main__ import main


def test_json_output_once():
    """Test JSON output in once mode."""
    runner = CliRunner()
    result = runner.invoke(main, ['--json', '--once'])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert 'cpu' in data
    assert 'memory' in data
    assert 'timestamp' in data
```

## Pull Request Process

### Before Submitting

1. **Create a feature branch**

   ```bash
   git checkout -b feat/my-new-feature
   ```

2. **Make your changes** following the code style guidelines

3. **Write tests** for your changes (maintain ≥75% coverage)

4. **Run quality checks**

   ```bash
   task check
   ```

5. **Update documentation** if needed

6. **Commit with conventional commit messages**

### Submitting the PR

1. **Push your branch**

   ```bash
   git push origin feat/my-new-feature
   ```

2. **Create a Pull Request** on GitHub

3. **Fill out the PR template** completely

4. **Wait for CI checks** to pass

5. **Address review feedback** if requested

### PR Checklist

Your PR must:

- [ ] Pass all CI checks (tests, linting, type checking)
- [ ] Maintain or improve code coverage (≥75%)
- [ ] Include tests for new functionality
- [ ] Update documentation for user-facing changes
- [ ] Follow conventional commit format
- [ ] Have a clear description of changes
- [ ] Reference related issues (if applicable)

### Review Process

1. **Automated checks** run on every PR
2. **Code review** by maintainers
3. **Feedback addressed** by contributor
4. **Approval** by at least one maintainer
5. **Squash and merge** to main branch

## Plugin Development

If you're developing a plugin, see the [Plugin Development Guide](https://uptop.readthedocs.io/plugins/overview/) for detailed instructions.

### Plugin Contribution Options

1. **Internal plugin**: Add to `src/uptop/plugins/` (requires PR to main repo)
2. **External plugin**: Create separate package `uptop-plugin-yourname`
3. **Plugin gallery**: Submit to [Plugin Gallery](https://uptop.readthedocs.io/community/plugin-gallery/)

### Plugin Quality Standards

External plugins should follow the same quality standards:

- Type hints and docstrings
- Tests with ≥75% coverage
- Clear README with usage examples
- Conventional commits
- Semantic versioning

## Questions?

- **General questions**: Open a [Discussion](https://github.com/yourusername/uptop/discussions)
- **Bug reports**: Open an [Issue](https://github.com/yourusername/uptop/issues) using the bug report template
- **Feature requests**: Open an [Issue](https://github.com/yourusername/uptop/issues) using the feature request template

Thank you for contributing to uptop!
