# Chat CLI Makefile

.PHONY: install dev clean demo test

# Install the package in development mode
install:
	pip install -e .

# Install development dependencies
dev:
	pip install pytest black isort flake8

# Run the application
run:
	python main.py

# Run the demo
demo:
	python demo.py

# Clean up Python cache files
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name "*.egg" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".coverage" -exec rm -rf {} +
	find . -type d -name "htmlcov" -exec rm -rf {} +
	find . -type d -name "dist" -exec rm -rf {} +
	find . -type d -name "build" -exec rm -rf {} +

# Format code
format:
	isort .
	black .

# Run linter
lint:
	flake8

# Run tests
test:
	pytest

# Help
help:
	@echo "Chat CLI development commands:"
	@echo "make install  - Install the package in development mode"
	@echo "make dev      - Install development dependencies"
	@echo "make run      - Run the application"
	@echo "make demo     - Run the demo version with sample data"
	@echo "make clean    - Clean up Python cache files"
	@echo "make format   - Format code with isort and black"
	@echo "make lint     - Run the linter (flake8)"
	@echo "make test     - Run tests"
