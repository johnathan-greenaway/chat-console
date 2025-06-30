# Pure Console Chat CLI

## 🎯 Overview

This is a **pure terminal console version** of Chat CLI that **does not use Textual** at all. It provides the same powerful backend functionality with a clean, ASCII-based interface that works on any terminal.

## 🚀 Quick Start

```bash
# Install the package
pip install -e .

# Start pure console version
c-c-pure

# Or use the alternative command
chat-console-pure

# Direct execution
python3 app/console_chat.py

# Via main app with console flag
python3 -m app.main --console
```

## ✨ Features

### Backend (Same as Textual Version)
- ✅ **OpenAI, Anthropic, Ollama support**
- ✅ **Streaming responses** with real-time updates
- ✅ **Conversation history** with SQLite storage
- ✅ **Multiple response styles** (concise, detailed, technical, friendly)
- ✅ **Model switching** with all available models
- ✅ **Configuration management**
- ✅ **Async streaming** with proper cancellation

### Console UI (Pure Terminal)
- ✅ **No external dependencies** beyond standard library
- ✅ **ASCII art interface** with clean borders
- ✅ **Real-time character input** processing
- ✅ **Cross-platform support** (Windows/Linux/macOS)
- ✅ **Keyboard shortcuts** for navigation
- ✅ **Responsive layout** that adapts to terminal size
- ✅ **Clean visual hierarchy** following Dieter Rams principles

## 🎨 Interface Preview

```
┌ Chat Console v0.4.3 ──────────── Model: Claude 3.7 Sonnet ┐
│ New Conversation                                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  12:34  Hello, can you help me with something?             │
│                                                             │
│  12:35  Of course! I'd be happy to help. What do you need  │
│         assistance with?                                    │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│ Type your message:                                          │
│ > _                                                         │
├─────────────────────────────────────────────────────────────┤
│ [q] Quit  [n] New  [h] History  [s] Settings  [ctrl+c] Cancel │
└─────────────────────────────────────────────────────────────┘
```

## ⌨️ Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `q` | Quit application |
| `n` | New conversation |
| `h` | View conversation history |
| `s` | Settings menu |
| `Enter` | Send message |
| `Backspace` | Delete character |
| `Ctrl+C` | Cancel generation or quit |

## 🛠️ Technical Implementation

### Core Architecture
- **`app/console_chat.py`** - Main console application class
- **`app/console_main.py`** - Entry point for installed commands
- **`app/console_utils.py`** - Console-specific utilities
- **No Textual imports** - pure terminal handling

### Key Components

#### ConsoleUI Class
```python
class ConsoleUI:
    def __init__(self):
        self.width = min(shutil.get_terminal_size().columns, 120)
        self.height = shutil.get_terminal_size().lines
        # ... terminal handling setup
        
    def draw_screen(self):
        # Real-time ASCII interface rendering
        
    def get_input(self):
        # Character-by-character input processing
        
    async def generate_response(self):
        # Streaming response with console updates
```

#### Terminal Input Handling
- **Cross-platform** character reading (termios on Unix, msvcrt on Windows)
- **Real-time display updates** during typing
- **Non-blocking input** with immediate feedback

#### ASCII Border System
- **Clean Unicode borders** (┌─┐│└─┘├─┤)
- **Responsive layout** that adapts to terminal size
- **Visual hierarchy** with different border styles

## 🔧 Configuration

### Environment Variables
Same as the Textual version:
```bash
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
OLLAMA_BASE_URL=http://localhost:11434  # optional
```

### Model Selection
Access the settings menu with `s` key to:
- Choose from available models
- Switch between providers
- Change response styles

## 🆚 Comparison with Textual Version

| Feature | Textual Version | Console Version |
|---------|----------------|-----------------|
| **Backend** | ✅ Full support | ✅ Full support |
| **UI Framework** | Textual library | Pure terminal |
| **Dependencies** | Rich, Textual | Standard library only |
| **Mouse Support** | ✅ Yes | ❌ Keyboard only |
| **Colors/Themes** | ✅ Rich colors | ✅ ASCII art |
| **Animations** | ✅ Smooth | ✅ Minimal |
| **SSH Compatible** | ⚠️ Limited | ✅ Excellent |
| **Memory Usage** | Higher | Lower |
| **Startup Time** | Slower | Faster |
| **Terminal Compatibility** | Good | Excellent |

## 🎯 Use Cases

### When to Use Console Version
- ✅ **SSH/Remote sessions** - Better compatibility
- ✅ **Minimal environments** - No extra dependencies
- ✅ **Automation/Scripts** - Easy to integrate
- ✅ **Resource constrained** - Lower memory usage
- ✅ **Terminal purists** - Clean ASCII aesthetic
- ✅ **Legacy systems** - Works everywhere

### When to Use Textual Version
- ✅ **Rich UI experience** - Mouse support, colors, animations
- ✅ **Desktop development** - Full terminal features
- ✅ **Complex interactions** - Advanced widgets

## 🧪 Testing

Run the test suite:
```bash
# Test console functionality
python3 test_console.py

# Test command line interface
python3 test_console_command.py

# Demo the UI rendering
python3 demo_console.py
```

## 🐛 Troubleshooting

### Common Issues

1. **Command not found after installation**
   ```bash
   # Make sure ~/.local/bin is in your PATH
   export PATH="$HOME/.local/bin:$PATH"
   ```

2. **Terminal size issues**
   ```bash
   # The console adapts automatically, but you can verify:
   python3 -c "import shutil; print(shutil.get_terminal_size())"
   ```

3. **Character encoding issues**
   ```bash
   # Ensure your terminal supports Unicode
   export LANG=en_US.UTF-8
   ```

4. **API connection issues**
   ```bash
   # Same troubleshooting as Textual version
   # Check your API keys and network connectivity
   ```

## 🚀 Advanced Usage

### Command Line Arguments
```bash
# Start with initial message
c-c-pure "Explain quantum computing"

# Specify model and style
c-c-pure --model gpt-4 --style technical

# Use with specific style
c-c-pure --style concise "Summarize the latest AI news"
```

### Integration Examples
```bash
# Use in scripts
echo "What is 2+2?" | c-c-pure

# Pipe responses
c-c-pure "Write a haiku" > poem.txt

# Use with other tools
c-c-pure "$(cat question.txt)"
```

## 📝 Development Notes

### Key Design Decisions
1. **No Textual imports** - Complete separation from rich UI framework
2. **Minimal dependencies** - Only standard library for UI
3. **Same backend** - Reuses all existing API clients and database
4. **Responsive design** - Adapts to any terminal size
5. **Cross-platform** - Works on Windows, Linux, macOS

### Code Organization
- Console-specific code isolated in separate files
- Shared backend components reused
- Clean separation between UI and business logic
- Proper async handling for streaming responses

This pure console version gives you the full power of Chat CLI without any UI framework dependencies, perfect for servers, automation, and environments where you want maximum compatibility and minimal overhead.