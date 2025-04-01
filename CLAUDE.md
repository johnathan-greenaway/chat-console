# Chat-Console Development Guide

## Commands
- Install: `make install` (pip install -e .)
- Dev dependencies: `make dev` (installs pytest, black, isort, flake8)
- Format code: `make format` (runs isort and black)
- Lint: `make lint` (runs flake8)
- Test: `make test` (runs pytest)
- Single test: `pytest path/to/test.py::test_function`
- Run app: `make run`
- Run demo: `make demo`
- Clean: `make clean`

## Code Style
- Black for formatting (default settings)
- isort for imports (stdlib → third-party → local)
- Type annotations for all functions and parameters
- Use snake_case for functions/variables, PascalCase for classes
- Dataclasses for model representations
- Exception handling: Use specific exceptions, log with severity levels
- Comments: Docstrings for all functions, modules, and classes
- Imports: Prefer explicit imports over wildcards (`from x import y` not `from x import *`)