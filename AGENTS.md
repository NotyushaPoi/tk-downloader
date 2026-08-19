# Repository Guidelines

## Project Structure & Module Organization

`main.py` is the primary launcher. Application orchestration lives in `src/application/`, while platform API clients are grouped under `src/interface/`. Keep downloading logic in `src/downloader/`, persistence backends in `src/storage/`, data models in `src/models/`, and reusable helpers in `src/tools/`. Encryption and request-signing implementations belong in `src/encrypt/`. Tests and test support code live in `src/testers/`. Documentation, translations, JavaScript helpers, and images are stored in `docs/`, `locale/`, and `static/` respectively. Runtime downloads and generated data belong in the ignored `Volume/` directory.

## Build, Test, and Development Commands

This project requires Python 3.12 or newer and uses `uv` for reproducible environments.

- `uv sync` installs runtime and development dependencies from `uv.lock`.
- `uv run main.py` starts the interactive downloader locally.
- `uv run pytest` runs the test suite under `src/testers/`.
- `uvx ruff check .` checks configured Pyflakes and pycodestyle rules.
- `uvx ruff format --check .` verifies formatting without modifying files.
- `docker build -t douk-downloader .` builds the container image.

On Apple Silicon, the locked `never-jscore` release lacks a native wheel; use a supported x86_64 environment or container if dependency installation fails.

## Coding Style & Naming Conventions

Use four-space indentation, double-quoted strings, and a maximum line length of 88 characters, as configured in `pyproject.toml`. Ruff targets Python 3.12. Use `snake_case` for modules, functions, variables, and test names; use `PascalCase` for classes; use `UPPER_SNAKE_CASE` for constants. Prefer async context managers for network clients and keep platform-specific behavior in the relevant interface module. Run Ruff checks before submitting changes.

## Testing Guidelines

Pytest is the test framework. Name test files `test_*.py` and test functions `test_*`; use `pytest.mark.parametrize` for compact input/output cases. Add focused unit tests for parsing, formatting, and storage behavior. Network-dependent checks should avoid real credentials and should be isolated from the default suite. No coverage threshold is currently enforced, but changed logic should have regression coverage.

## Commit & Pull Request Guidelines

Recent history follows Conventional Commit-style prefixes such as `feat:`, `fix:`, `perf:`, `refactor:`, `docs:`, and `build(deps):`. Keep the subject concise and describe one logical change. Pull requests should explain the problem and solution, list validation commands, link related issues, and include screenshots for terminal or Web UI changes. Never commit cookies, tokens, proxy credentials, generated downloads, or local configuration files.
