
# Chat CLI

A comprehensive command-line interface for chatting with various AI language models. This application allows you to interact with different LLM providers through an intuitive terminal-based interface.

## Features

- Interactive terminal UI with Textual library
- Support for multiple AI models:
  - OpenAI models (GPT-3.5, GPT-4)
  - OpenAI reasoning models (o1, o1-mini, o3, o3-mini, o4-mini)
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

### Testing Reasoning Models

To test the OpenAI reasoning models implementation, you can use the included test script:
```
./test_reasoning.py
```

This script will test both completion and streaming with the available reasoning models.

### About OpenAI Reasoning Models

OpenAI's reasoning models (o1, o3, o4-mini, etc.) are LLMs trained with reinforcement learning to perform reasoning. These models:

- Think before they answer, producing a long internal chain of thought
- Excel in complex problem solving, coding, scientific reasoning, and multi-step planning
- Use "reasoning tokens" to work through problems step by step before providing a response
- Support different reasoning effort levels (low, medium, high)

The implementation in this CLI supports both standard completions and streaming with these models.

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
