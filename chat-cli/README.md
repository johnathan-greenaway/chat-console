# Chat CLI

A comprehensive command-line interface for chatting with various AI language models. This application allows you to interact with different LLM providers through an intuitive terminal-based interface.

## Features

- Interactive terminal UI with Textual library
- Support for multiple AI models:
  - OpenAI models (GPT-3.5, GPT-4)
  - Anthropic models (Claude 3 Opus, Sonnet, Haiku)
- Conversation history with search functionality
- Customizable response styles (concise, detailed, technical, friendly)
- Code syntax highlighting
- Markdown rendering

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/chat-cli.git
   cd chat-cli
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Set up your API keys:
   
   Create a `.env` file in the project root directory with your API keys:
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   ANTHROPIC_API_KEY=your_anthropic_api_key_here
   ```

## Usage

Run the application:
```
chat-cli
```

### Keyboard Shortcuts

- `q` - Quit the application
- `n` - Start a new conversation
- `s` - Toggle sidebar
- `f` - Focus search box
- `Escape` - Cancel current generation
- `Ctrl+C` - Quit the application

### Configuration

The application creates a configuration file at `~/.chatcli/config.json` on first run. You can edit this file to:

- Change the default model
- Modify available models
- Add or edit response styles
- Change the theme
- Adjust other settings

## Data Storage

Conversation history is stored in a SQLite database at `~/.chatcli/chat_history.db`.

## Development

The application is structured as follows:

- `main.py` - Main application entry point
- `app/` - Application modules
  - `api/` - LLM provider API client implementations
  - `ui/` - User interface components
  - `config.py` - Configuration management
  - `database.py` - Database operations
  - `models.py` - Data models
  - `utils.py` - Utility functions

## License

MIT
