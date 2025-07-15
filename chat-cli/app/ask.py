#!/usr/bin/env python3
"""
ASK - Quick AI assistance with terminal output
Captures terminal scrollback and sends it to your preferred AI model
"""

import argparse
import asyncio
import os
import sys
import subprocess
from pathlib import Path

from .config import CONFIG, update_last_used_model
from .api.base import BaseModelClient
from .utils import resolve_model_id


def get_terminal_scrollback():
    """Capture terminal scrollback buffer using various methods"""
    
    # Method 1: Try to get from tmux if running in tmux
    if os.environ.get('TMUX'):
        try:
            result = subprocess.run(['tmux', 'capture-pane', '-p'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout
        except:
            pass
    
    # Method 2: Try to get from screen if running in screen
    if os.environ.get('STY'):
        try:
            # Try screen hardcopy command
            subprocess.run(['screen', '-X', 'hardcopy', '/tmp/screen_capture.txt'], timeout=5)
            if os.path.exists('/tmp/screen_capture.txt'):
                with open('/tmp/screen_capture.txt', 'r') as f:
                    content = f.read()
                os.remove('/tmp/screen_capture.txt')
                return content
        except:
            pass
    
    # Method 3: Try kitty terminal if available
    if os.environ.get('KITTY_WINDOW_ID'):
        try:
            result = subprocess.run(['kitty', '@', 'get-text', '--ansi'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout
        except:
            pass
    
    # Method 4: Try to get from clipboard (might contain terminal output)
    clipboard_tools = [
        ['xclip', '-selection', 'clipboard', '-o'],
        ['xsel', '--clipboard', '--output'],
        ['pbpaste'],  # macOS
        ['powershell.exe', '-command', 'Get-Clipboard']  # Windows via WSL
    ]
    
    for tool_cmd in clipboard_tools:
        try:
            if subprocess.run(['which', tool_cmd[0]], capture_output=True).returncode == 0:
                result = subprocess.run(tool_cmd, capture_output=True, text=True, timeout=2)
                if result.returncode == 0 and result.stdout.strip():
                    # Only return if it looks like terminal output (has prompts, commands, etc.)
                    if any(indicator in result.stdout for indicator in ['$', '>', '❯', '❯', 'Error', 'error', 'failed', 'installed', 'Successfully']):
                        return result.stdout
        except:
            continue
    
    # Method 5: Fallback - ask user to paste or describe
    return None


def get_recent_commands():
    """Get recent shell commands from history"""
    history_lines = []
    
    # Try bash history
    bash_history = Path.home() / '.bash_history'
    if bash_history.exists():
        try:
            with open(bash_history, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                history_lines.extend(lines[-10:])  # Last 10 commands
        except:
            pass
    
    # Try zsh history  
    zsh_history = Path.home() / '.zsh_history'
    if zsh_history.exists():
        try:
            with open(zsh_history, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                # Zsh history has timestamp format, extract commands
                for line in lines[-10:]:
                    if ';' in line:
                        cmd = line.split(';', 1)[1].strip()
                        history_lines.append(cmd)
        except:
            pass
    
    return history_lines


async def ask_ai(context_text, question=None):
    """Send context to AI and get response"""
    
    # Determine which model to use
    model_id = CONFIG.get("last_used_model")
    if not model_id or model_id not in CONFIG["available_models"]:
        model_id = CONFIG["default_model"]
    
    model_id = resolve_model_id(model_id)
    
    # Check if model is available in config
    if model_id not in CONFIG["available_models"]:
        print(f"⚠️  Model '{model_id}' not found in available models.")
        print("This might be an Ollama model that needs to be downloaded.")
        print("\nTip: Try running 'ollama pull {model_id}' first, or use a different model.")
        print("\nAvailable models:")
        for available_id, info in CONFIG["available_models"].items():
            print(f"  - {available_id}: {info['display_name']}")
        return None
    
    # Update last used model
    update_last_used_model(model_id)
    
    # Prepare the prompt
    if question:
        prompt = f"""I need help with this terminal output. Here's my question: {question}

Terminal context:
```
{context_text}
```

Please analyze this and provide helpful guidance."""
    else:
        prompt = f"""I need help with this terminal output. Please analyze what happened and provide helpful guidance or suggestions.

Terminal context:
```
{context_text}
```

Please analyze this and provide helpful guidance."""
    
    # Get AI client
    try:
        client = await BaseModelClient.get_client_for_model(model_id)
        
        # Prepare messages
        messages = [{"role": "user", "content": prompt}]
        
        model_display_name = CONFIG["available_models"][model_id]["display_name"]
        print(f"🤖 Asking {model_display_name}...")
        print("─" * 60)
        
        # Stream the response
        response_text = ""
        async for chunk in client.generate_stream(messages, model_id):
            if chunk:
                print(chunk, end='', flush=True)
                response_text += chunk
        
        print("\n" + "─" * 60)
        return response_text
        
    except Exception as e:
        error_msg = str(e)
        if "Connection refused" in error_msg or "Failed to connect" in error_msg:
            print(f"❌ Connection Error: Cannot connect to the model server.")
            print("For Ollama models, make sure Ollama is running: 'ollama serve'")
        elif "not found" in error_msg.lower():
            print(f"❌ Model Error: Model '{model_id}' not found.")
            print("For Ollama models, try: 'ollama pull {model_id}'")
        else:
            print(f"❌ Error: {error_msg}")
        return None


def main():
    """Main ASK command entry point"""
    parser = argparse.ArgumentParser(
        description="Ask AI about your terminal output",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ask                           # Analyze recent terminal activity
  ask "Why did this fail?"      # Ask specific question about terminal output
  ask --history                 # Include recent command history
  ask --model gpt-4            # Use specific model
        """
    )
    
    parser.add_argument(
        'question', 
        nargs='?', 
        help='Specific question about the terminal output'
    )
    
    parser.add_argument(
        '--history', 
        action='store_true',
        help='Include recent command history in context'
    )
    
    parser.add_argument(
        '--model', 
        help='Specify which model to use'
    )
    
    parser.add_argument(
        '--paste',
        action='store_true', 
        help='Paste terminal output manually instead of auto-capture'
    )
    
    args = parser.parse_args()
    
    # Override model if specified
    if args.model:
        if args.model in CONFIG["available_models"]:
            update_last_used_model(args.model)
        else:
            print(f"❌ Model '{args.model}' not found in configuration")
            print("Available models:")
            for model_id, info in CONFIG["available_models"].items():
                print(f"  - {model_id}: {info['display_name']}")
            sys.exit(1)
    
    # Get terminal context
    context_parts = []
    
    if args.paste:
        print("📋 Paste your terminal output below (Ctrl+D when done):")
        try:
            pasted_content = sys.stdin.read()
            if pasted_content.strip():
                context_parts.append("Pasted terminal output:")
                context_parts.append(pasted_content)
        except KeyboardInterrupt:
            print("\n❌ Cancelled")
            sys.exit(1)
    else:
        # Try to capture terminal scrollback
        scrollback = get_terminal_scrollback()
        if scrollback:
            context_parts.append("Recent terminal output:")
            context_parts.append(scrollback)
    
    # Include command history if requested
    if args.history:
        recent_commands = get_recent_commands()
        if recent_commands:
            context_parts.append("\nRecent commands:")
            for cmd in recent_commands:
                context_parts.append(f"$ {cmd.strip()}")
    
    # If no context captured, ask user to describe or paste
    if not context_parts:
        print("🤔 Couldn't automatically capture terminal output.")
        print("Please describe what you need help with, or use --paste to manually provide output.")
        
        if not args.question:
            try:
                question = input("❓ What do you need help with? ")
                if not question.strip():
                    print("❌ No question provided")
                    sys.exit(1)
                args.question = question
            except KeyboardInterrupt:
                print("\n❌ Cancelled")
                sys.exit(1)
        
        context_parts.append("User needs help with: " + args.question)
    
    # Combine context
    context_text = "\n".join(context_parts)
    
    if len(context_text.strip()) < 10:
        print("❌ No meaningful context to analyze")
        sys.exit(1)
    
    # Send to AI
    try:
        asyncio.run(ask_ai(context_text, args.question))
    except KeyboardInterrupt:
        print("\n❌ Cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()