# BIMAP — Contributing Guide

[← Back to README](../readme.md)

Thank you for your interest in BIMAP! This guide covers how to report bugs, suggest features, and submit pull requests.

---

## Table of Contents

1. [Code of Conduct](#1-code-of-conduct)
2. [Reporting Bugs](#2-reporting-bugs)
3. [Suggesting Features](#3-suggesting-features)
4. [Setting Up for Development](#4-setting-up-for-development)
5. [Code Style](#5-code-style)
6. [Pull Request Workflow](#6-pull-request-workflow)
7. [Commit Message Convention](#7-commit-message-convention)
8. [Running Tests](#8-running-tests)

---

## 1. Code of Conduct

Be respectful and constructive. This is an experimental research project — feedback and criticism are welcome, but please keep discussions focused on the work.

---

## 2. Reporting Bugs

Open a [GitHub Issue](https://github.com/ogrgijon/BIMAP-V2/issues) and include:

- **Steps to reproduce** — be specific
- **Expected behaviour** — what should happen
- **Actual behaviour** — what does happen
- **BIMAP version** — shown in Help → About
- **OS and Python version**
- **Traceback / error log** — paste from Help → About (triple-click to reveal debug log)

---

## 3. Suggesting Features

Open a GitHub Issue with the label `enhancement`. Describe:

- The **use case** — who needs this and why
- **Proposed behaviour** — how it should work
- Any **prior art** — similar tools or references

---

## 4. Setting Up for Development

```bash
git clone https://github.com/ogrgijon/BIMAP-V2.git
cd BIMAP-V2
python -m venv .venv
.venv\Scripts\activate       # Windows
source .venv/bin/activate    # macOS / Linux
pip install -e .
pip install -r requirements-dev.txt
```

See [docs/INSTALL.md](INSTALL.md) for the full setup guide.

---

## 5. Code Style

| Rule | Standard |
|------|---------|
| Style | PEP 8 |
| Type hints | Required on all public functions and methods |
| Domain models | Pydantic `BaseModel` — do not use plain dataclasses for domain objects |
| UI signals | Connect with lambdas or dedicated slots — avoid inline anonymous logic > 2 lines |
| String literals | Use `t("…")` from `bimap.i18n` for any user-visible string |
| Imports | Standard library → third-party → local; no wildcard imports |
| Line length | 100 characters max |

Run the linter before committing:

```bash
ruff check src/ tests/
```

---

## 6. Pull Request Workflow

1. **Fork** the repository and create a branch:
   ```bash
   git checkout -b fix/my-bug-description
   ```

2. **Make your changes** — keep commits focused and atomic.

3. **Write or update tests** for any changed behaviour.

4. **Run the full test suite**:
   ```bash
   python -m pytest tests/ -q
   ```
   All tests must pass.

5. **Open a Pull Request** against `main`:
   - Describe **what** changed and **why**
   - Reference any related issue with `Closes #123`
   - Keep the PR diff small — large PRs are harder to review

6. A maintainer will review and may request changes.

---

## 7. Commit Message Convention

```
<type>: <short summary>

[optional body — why, not what]

[optional footer: Closes #issue]
```

Types:

| Type | When to use |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `refactor` | Code restructuring without behaviour change |
| `test` | Adding or updating tests |
| `docs` | Documentation only |
| `chore` | Build scripts, CI, dependencies |
| `perf` | Performance improvement |

Examples:
```
feat: add rotation support to polygon zones
fix: prevent spinbox from resetting while user is typing
docs: add CONTRIBUTING guide
```

---

## 8. Running Tests

```bash
# Full suite
python -m pytest tests/ -q

# Single module
python -m pytest tests/test_engine/test_commands.py -v

# With coverage
python -m pytest tests/ --cov=src/bimap --cov-report=term-missing
```

When adding new functionality, place tests in the matching `tests/` subdirectory:

| Module | Test location |
|--------|--------------|
| `src/bimap/models/` | `tests/test_models/` |
| `src/bimap/engine/` | `tests/test_engine/` |
| `src/bimap/ui/` | `tests/test_ui/` |
