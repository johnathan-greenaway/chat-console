# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Chat CLI is a Python-based terminal application that provides an interactive interface for chatting with various AI language models. The application is built using the Textual library for the TUI and supports multiple LLM providers including OpenAI, Anthropic, and Ollama.

## Development Commands

### Core Commands
- `make install` - Install the package in development mode
- `make dev` - Install development dependencies (pytest, black, isort, flake8)
- `make run` - Run the application directly with `python main.py`
- `make demo` - Run the demo version with sample data
- `make clean` - Clean up Python cache files and build artifacts
- `make format` - Format code using isort and black
- `make lint` - Run the linter (flake8)
- `make test` - Run tests with pytest

### Application Entry Points

#### Primary Interface (Console)
- `c-c` - **Main command** - Pure console interface (no Textual dependencies)
- `chat-console` - Main CLI command (pure console version)
- `python -m app.main` - Direct execution of console interface

#### Legacy Interface (Textual UI)
- `c-c-c` - **Legacy Textual UI** - Rich terminal interface using Textual library  
- `chat-console-classic` - Legacy Textual version entry point
- `python -m app.classic_main` - Direct execution of legacy Textual UI

#### Alternative Entry Points
- `chat-console-pure` - Pure console version (no Textual dependencies)
- `c-c-pure` - Short alias for pure console version
- `python main.py` - Direct execution from chat-cli directory
- `python console_chat.py` - Direct execution of pure console version
- `python -m app.main --console` - Run console version via main app

### Testing
- `python test_reasoning.py` - Test OpenAI reasoning models specifically
- `python test_chat.py` - General chat functionality tests
- `python test_console.py` - Test pure console version functionality
- `python demo_console.py` - Demo the console UI rendering
- `pytest` - Run full test suite

## Architecture

### Core Structure
- **Primary Entry Point**: `chat-cli/app/main.py` - Main console interface application (no Textual dependencies)
- **Legacy Entry Point**: `chat-cli/app/classic_main.py` - Legacy Textual UI version with SimpleChatApp class
- **Console Interface**: `chat-cli/app/console_interface.py` - Core console UI implementation
- **Configuration**: `chat-cli/app/config.py` - Handles API keys, model definitions, and user settings
- **Database**: `chat-cli/app/database.py` - SQLite operations for conversation history
- **Models**: `chat-cli/app/models.py` - Data models for conversations and messages
- **Console Utils**: `chat-cli/app/console_utils.py` - Pure console utilities without Textual dependencies

### API Clients (`chat-cli/app/api/`)
- `base.py` - Abstract base class for all model clients with provider detection and factory methods
- `openai.py` - OpenAI API client supporting GPT models and reasoning models (o1, o3, o4-mini)
- `anthropic.py` - Anthropic API client for Claude models
- `ollama.py` - Ollama client for local models with model management features
- `custom_openai.py` - Custom OpenAI-compatible API client for drop-in replacements

### UI Components (`chat-cli/app/ui/`)
- `chat_interface.py` - Main chat display and input components (Textual)
- `model_selector.py` - Model and style selection widgets (Textual)
- `chat_list.py` - Conversation history browser (Textual)
- `model_browser.py` - Ollama model browser and management (Textual)
- `styles.py` - CSS styles for the TUI (Textual)
- `borders.py` - ASCII border system for both UI versions

### Key Features

#### Model Support
- **OpenAI**: Standard models (GPT-3.5, GPT-4) and reasoning models (o1, o1-mini, o3, o3-mini, o4-mini)
- **Anthropic**: Claude 3 family (Opus, Sonnet, Haiku, 3.5 Sonnet, 3.7 Sonnet)
- **Ollama**: Local models with automatic model detection and management

#### Ollama Integration
- Automatic model preloading for faster response times
- Background model cleanup after inactivity (configurable timeout)
- Model browser for discovering and managing local models
- Automatic Ollama service detection and startup

#### Dynamic Features
- Automatic conversation title generation using smaller/faster models
- Streaming response support with cancellation
- Conversation history with search
- Customizable response styles (default, concise, detailed, technical, friendly)

## Configuration

### Environment Variables
- `OPENAI_API_KEY` - Required for OpenAI models
- `ANTHROPIC_API_KEY` - Required for Anthropic models  
- `OLLAMA_BASE_URL` - Ollama server URL (defaults to http://localhost:11434)

### Configuration File
The app creates `~/.terminalchat/config.json` with:
- Model definitions and provider mappings
- Default model and style selections
- Feature flags (dynamic titles, model preloading, etc.)
- Ollama-specific settings (inactive timeout, preloading)

### Data Storage
- Database: `~/.terminalchat/chat_history.db` (SQLite)
- Logs: `~/.cache/chat-cli/debug.log` and `~/.cache/chat-cli/textual.log`

## Model ID Resolution

The application uses a model ID resolution system in `utils.py` that maps user-friendly names to API-specific identifiers. When working with models, always use the resolved ID for API calls but display the user-friendly name in the UI.

## Error Handling

The application includes comprehensive error handling with:
- Automatic fallback to available models when selected model is unavailable
- Provider availability checking with informative warnings
- Graceful degradation when API keys are missing
- Connection error handling for Ollama services

## Dual UI Architecture

### Primary Console Interface (`app/main.py` → `console_interface.py`)
- **Current main interface** - Pure terminal interface with no external UI dependencies
- ASCII art borders, real-time screen updates, slash command support
- Works on any terminal, optimized for SSH/remote sessions and production use
- Entry points: `c-c`, `chat-console`, `python -m app.main`
- Features: `/settings` menu, dynamic model fetching, custom API configuration

### Legacy Textual UI Version (`app/classic_main.py`)
- **Legacy interface** - Rich terminal user interface using Textual library
- Advanced widgets, mouse support, animations
- Best for desktop development environments but being phased out
- Entry points: `c-c-c`, `chat-console-classic`, `python -m app.classic_main`

## Key Patterns

### Async/Await Usage
- All model API calls are asynchronous
- UI updates use appropriate patterns for each version (Textual vs console)
- Background tasks for model management and title generation

### Streaming Implementation
- Real-time response streaming with proper cancellation support
- Different update mechanisms: Textual workers vs console screen redraws
- Proper cancellation support for both UI versions

### Provider Detection
- Automatic provider detection based on model names
- Runtime provider availability checking
- Fallback logic for unavailable providers

### Console UI Features
- Cross-platform terminal input handling (Windows/Linux/macOS)
- Real-time character processing with immediate feedback
- ASCII border rendering with clean visual hierarchy
- Keyboard shortcuts: q (quit), n (new), h (history), s (settings)
- Ctrl+C cancellation support during generation