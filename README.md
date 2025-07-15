Chat CLI
========

Chat CLI is a comprehensive terminal-based interface for interacting with various Large Language Models (LLMs) directly from your command line. This application provides an intuitive TUI (Text User Interface) for conducting AI conversations with multiple model providers.

Features
--------

*   Interactive terminal UI built with the Textual library
*   Support for multiple AI providers:
    *   OpenAI (GPT-3.5, GPT-4)
    *   Anthropic (Claude 3 Opus, Sonnet, Haiku, Claude 3.7 Sonnet)
    *   Ollama (local models like Llama, Mistral, CodeLlama)
*   Conversation history with search functionality
*   Customizable response styles (concise, detailed, technical, friendly)
*   Code syntax highlighting
*   Markdown rendering
*   SQLite database for persistent storage


Installation
------------

### From PyPI

    pip install chat-console

### From Source

    git clone https://github.com/wazacraftrfid/chat-console.git
    cd chat-console
    pip install -e .

Configuration
-------------

Create a `.env` file in your project directory with your API keys:

    # OpenAI API key for GPT models
    OPENAI_API_KEY=your_openai_api_key_here
    
    # Anthropic API key for Claude models
    ANTHROPIC_API_KEY=your_anthropic_api_key_here
    
    # Ollama base URL (optional, defaults to http://localhost:11434)
    OLLAMA_BASE_URL=http://localhost:11434

Usage
-----

Start the application with:

    chat-console

Or use the short alias:

    c-c

You can also start it with an initial prompt:

    chat-console "Explain quantum computing"

### Ask Feature - Quick AI Assistance

The `ask` command provides quick AI assistance with terminal output and errors. It can automatically capture your recent terminal activity and send it to an AI model for analysis and suggestions.

**Basic Usage:**

    ask "Why did this command fail?"
    ask "What does this error mean?"

**Automatic Terminal Capture:**

The ask command will automatically try to capture recent terminal output using various methods:
- **tmux sessions**: Captures pane content if you're using tmux
- **GNU screen**: Captures screen content if you're using screen  
- **Kitty terminal**: Uses kitty's built-in capture API
- **Clipboard detection**: Checks clipboard for terminal-like content

**Manual Input Options:**

    ask --paste "What's wrong here?"           # Manually paste terminal output
    ask --history "Explain recent commands"    # Include command history
    ask --model gpt-4 "Help with this error"  # Use specific model

**Examples:**

    # After getting an error, just run:
    ask "help me fix this"
    
    # For installation issues:
    ask "why did the installation fail?"
    
    # Include recent command history:
    ask --history "what went wrong with my setup?"
    
    # Use a specific model:
    ask --model claude-3-opus "explain this error"

**Tips:**
- Works best in tmux, screen, or kitty terminal for automatic capture
- If auto-capture fails, use `--paste` to manually provide output
- The ask command uses your last-used model from the main chat interface
- For Ollama models, make sure they're downloaded first: `ollama pull model-name`

### Keyboard Shortcuts

*   `q` - Quit the application
*   `n` - Start a new conversation
*   `s` - Open settings panel (when input is not focused)
*   `h` - View chat history
*   `Escape` - Cancel current generation or close settings
*   `Ctrl+C` - Quit the application

Interface
---------

The Chat CLI interface consists of:

*   A conversation display area showing message history
*   A text input area for entering prompts
*   Model and style selectors in the settings panel
*   Chat history browser

Response Styles
---------------

Chat CLI supports different response styles that can be selected from the settings menu:

*   **Default**: Standard assistant responses
*   **Concise**: Brief and to-the-point responses
*   **Detailed**: Comprehensive and thorough explanations
*   **Technical**: Technical language with precise terminology
*   **Friendly**: Warm, conversational tone

Data Storage
------------

All conversations are stored in a SQLite database at `~/.terminalchat/chat_history.db`.

Configuration is stored at `~/.terminalchat/config.json`.

Using with Ollama
-----------------

To use local models with Ollama:

1.  Install Ollama from [https://ollama.ai](https://ollama.ai)
2.  Start the Ollama service: `ollama serve`
3.  Pull models you want to use: `ollama pull mistral`
4.  Launch Chat CLI and select an Ollama model from the settings panel

Development
-----------

### Project Structure

*   `app/` - Main application code
    *   `api/` - API clients for different LLM providers
    *   `ui/` - Textual UI components
    *   `config.py` - Configuration management
    *   `database.py` - SQLite database operations
    *   `models.py` - Data models
    *   `utils.py` - Utility functions
*   `main.py` - Application entry point

### Development Commands

The included Makefile provides helpful commands:

*   `make install` - Install in development mode
*   `make dev` - Install development dependencies
*   `make run` - Run the application
*   `make demo` - Run with sample data
*   `make clean` - Clean Python cache files
*   `make format` - Format code with isort and black
*   `make lint` - Run linter
*   `make test` - Run tests

License
-------

This project is licensed under the MIT License - see the LICENSE file for details.
