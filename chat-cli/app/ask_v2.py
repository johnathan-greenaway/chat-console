#!/usr/bin/env python3
"""
ASK v2 - Enhanced AI assistance with terminal output and screenshot support
Captures terminal scrollback, screenshots, and sends to vision-capable AI models
"""

import argparse
import asyncio
import os
import sys
import subprocess
import json
from pathlib import Path
from typing import Optional, Dict, List

from .config import CONFIG, update_last_used_model
from .api.base import BaseModelClient
from .utils import resolve_model_id
from .ask_enhanced import (
    get_enhanced_terminal_context, 
    get_screenshot,
    encode_image,
    EnhancedTerminalCapture
)


# Vision-capable models mapping
VISION_CAPABLE_MODELS = {
    'gpt-4-vision-preview': {'provider': 'openai', 'vision': True},
    'gpt-4-turbo': {'provider': 'openai', 'vision': True},
    'gpt-4o': {'provider': 'openai', 'vision': True},
    'gpt-4o-mini': {'provider': 'openai', 'vision': True},
    'claude-3-opus': {'provider': 'anthropic', 'vision': True},
    'claude-3-sonnet': {'provider': 'anthropic', 'vision': True},
    'claude-3-haiku': {'provider': 'anthropic', 'vision': True},
    'claude-3-5-sonnet': {'provider': 'anthropic', 'vision': True},
    'llava': {'provider': 'ollama', 'vision': True},
    'bakllava': {'provider': 'ollama', 'vision': True},
    'llava-llama3': {'provider': 'ollama', 'vision': True},
}


def is_vision_capable(model_id: str) -> bool:
    """Check if a model supports vision/images"""
    # Check direct mapping
    if model_id in VISION_CAPABLE_MODELS:
        return True
    
    # Check if it's an Ollama model with vision indicators
    if ':' in model_id:  # Ollama model format
        base_model = model_id.split(':')[0]
        if base_model in VISION_CAPABLE_MODELS:
            return True
        # Check for vision-related keywords
        vision_keywords = ['vision', 'llava', 'bakllava', 'clip']
        if any(keyword in model_id.lower() for keyword in vision_keywords):
            return True
    
    return False


def get_terminal_scrollback():
    """Original terminal scrollback capture for backwards compatibility"""
    # Try enhanced capture first
    text_content, _ = get_enhanced_terminal_context()
    if text_content:
        return text_content
    
    # Fallback to original tmux-only method
    if os.environ.get('TMUX'):
        try:
            result = subprocess.run(['tmux', 'capture-pane', '-p'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout
        except:
            pass
    
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


async def ask_ai_with_image(context_text: str, image_path: Optional[str], question: Optional[str]):
    """Send context and/or image to AI and get response"""
    
    # Determine which model to use
    model_id = CONFIG.get("last_used_model")
    if not model_id or model_id not in CONFIG["available_models"]:
        model_id = CONFIG["default_model"]
    
    model_id = resolve_model_id(model_id)
    
    # Check if we need a vision-capable model
    if image_path and not is_vision_capable(model_id):
        print(f"⚠️  Current model {model_id} doesn't support images.")
        print("Switching to a vision-capable model...")
        
        # Find first available vision model
        for vid_model, info in VISION_CAPABLE_MODELS.items():
            if vid_model in CONFIG["available_models"]:
                model_id = vid_model
                print(f"✅ Using {CONFIG['available_models'][model_id]['display_name']}")
                break
        else:
            print("❌ No vision-capable model available. Processing text only.")
            image_path = None
    
    # Update last used model
    update_last_used_model(model_id)
    
    # Prepare the messages
    messages = []
    
    if image_path:
        # For vision models, we need to structure the message with image
        content = []
        
        # Add text prompt
        if question:
            prompt_text = f"I need help with this. {question}"
        else:
            prompt_text = "Please analyze this screenshot and provide helpful guidance."
        
        if context_text:
            prompt_text += f"\n\nAdditional context:\n```\n{context_text}\n```"
        
        content.append({"type": "text", "text": prompt_text})
        
        # Add image
        if CONFIG["available_models"][model_id]["provider"] == "openai":
            # OpenAI format
            image_data = encode_image(image_path)
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{image_data}"
                }
            })
        elif CONFIG["available_models"][model_id]["provider"] == "anthropic":
            # Anthropic format
            image_data = encode_image(image_path)
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": image_data
                }
            })
        else:
            # For other providers (like Ollama), we might need different handling
            # For now, just mention the image
            prompt_text += f"\n\n[Image provided: {image_path}]"
            content = [{"type": "text", "text": prompt_text}]
        
        messages.append({"role": "user", "content": content})
    else:
        # Text-only message
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
```"""
        
        messages.append({"role": "user", "content": prompt})
    
    # Get AI client and send request
    try:
        client = await BaseModelClient.get_client_for_model(model_id)
        
        print(f"🤖 Asking {CONFIG['available_models'][model_id]['display_name']}...")
        if image_path:
            print(f"📸 Including screenshot: {os.path.basename(image_path)}")
        print("─" * 60)
        
        # Stream the response
        response_text = ""
        async for chunk in client.generate_stream(messages, model_id):
            if chunk:
                print(chunk, end='', flush=True)
                response_text += chunk
        
        print("\n" + "─" * 60)
        
        # Cleanup temporary image if it exists
        if image_path and image_path.startswith('/tmp/'):
            try:
                os.remove(image_path)
            except:
                pass
        
        return response_text
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def main():
    """Main ASK v2 command entry point"""
    parser = argparse.ArgumentParser(
        description="Ask AI about your terminal output or screenshots",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ask                           # Analyze recent terminal activity
  ask "Why did this fail?"      # Ask specific question about terminal output
  ask --screenshot              # Take a screenshot and analyze it
  ask --image /path/to/img.png  # Analyze specific image
  ask --history                 # Include recent command history
  ask --model gpt-4o           # Use specific vision-capable model
  ask --paste                   # Manually paste content
  ask --interactive            # Interactive capture mode
        """
    )
    
    parser.add_argument(
        'question', 
        nargs='?', 
        help='Specific question about the terminal output or screenshot'
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
    
    parser.add_argument(
        '--screenshot', '-s',
        action='store_true',
        help='Take a screenshot to include with the question'
    )
    
    parser.add_argument(
        '--image', '-i',
        help='Path to an image file to analyze'
    )
    
    parser.add_argument(
        '--interactive',
        action='store_true',
        help='Interactive capture mode with menu options'
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
                vision_indicator = " 👁️" if is_vision_capable(model_id) else ""
                print(f"  - {model_id}: {info['display_name']}{vision_indicator}")
            sys.exit(1)
    
    # Initialize context
    context_parts = []
    image_path = None
    
    # Handle interactive mode
    if args.interactive:
        text_content, image_path = EnhancedTerminalCapture.interactive_capture()
        if text_content:
            context_parts.append(text_content)
    else:
        # Handle image/screenshot options
        if args.image:
            if os.path.exists(args.image):
                image_path = args.image
            else:
                print(f"❌ Image file not found: {args.image}")
                sys.exit(1)
        elif args.screenshot:
            print("📷 Taking screenshot...")
            image_path = get_screenshot()
            if not image_path:
                print("❌ Failed to capture screenshot")
                print("Make sure you have one of these tools installed:")
                print("  - gnome-screenshot, spectacle, scrot, or flameshot (Linux)")
                print("  - screencapture (macOS)")
                print("  - PowerShell (Windows via WSL)")
                sys.exit(1)
            print(f"✅ Screenshot captured")
        
        # Handle text capture
        if args.paste:
            print("📋 Paste your content below (Ctrl+D when done):")
            try:
                pasted_content = sys.stdin.read()
                if pasted_content.strip():
                    context_parts.append("Pasted content:")
                    context_parts.append(pasted_content)
            except KeyboardInterrupt:
                print("\n❌ Cancelled")
                sys.exit(1)
        else:
            # Try to capture terminal scrollback
            scrollback = get_terminal_scrollback()
            if scrollback:
                context_parts.append("Terminal output:")
                context_parts.append(scrollback)
    
    # Include command history if requested
    if args.history:
        recent_commands = get_recent_commands()
        if recent_commands:
            context_parts.append("\nRecent commands:")
            for cmd in recent_commands:
                context_parts.append(f"$ {cmd.strip()}")
    
    # Check if we have any content
    context_text = "\n".join(context_parts) if context_parts else ""
    
    if not context_text and not image_path:
        print("🤔 No content captured.")
        print("\nOptions:")
        print("  - Use --screenshot to capture your screen")
        print("  - Use --paste to manually paste text")
        print("  - Use --interactive for guided capture")
        print("  - Run inside tmux for automatic terminal capture")
        
        if not args.question:
            try:
                question = input("\n❓ What do you need help with? ")
                if not question.strip():
                    print("❌ No question provided")
                    sys.exit(1)
                args.question = question
                context_text = f"User question: {question}"
            except KeyboardInterrupt:
                print("\n❌ Cancelled")
                sys.exit(1)
    
    # Send to AI
    try:
        asyncio.run(ask_ai_with_image(context_text, image_path, args.question))
    except KeyboardInterrupt:
        print("\n❌ Cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()