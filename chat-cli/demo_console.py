#!/usr/bin/env python3
"""
Demo script for the pure console version
Shows the UI without requiring API keys
"""

import sys
import os
import asyncio
from datetime import datetime

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

def demo_console_ui():
    """Demonstrate the console UI rendering"""
    from console_chat import ConsoleUI
    
    print("🖥️  Pure Console Chat CLI Demo")
    print("=" * 60)
    print()
    
    # Create console UI instance
    ui = ConsoleUI()
    
    # Demo the header
    print("Header rendering:")
    header_lines = ui.draw_header()
    for line in header_lines:
        print(line)
    print()
    
    # Demo message formatting
    print("Message formatting:")
    from app.models import Message
    
    user_msg = Message(role="user", content="Hello! Can you help me understand how this console interface works?")
    assistant_msg = Message(role="assistant", content="Of course! This is a pure terminal interface that doesn't use Textual. It uses ASCII art borders and real-time screen updates to create an interactive chat experience.")
    
    user_formatted = ui.format_message(user_msg)
    assistant_formatted = ui.format_message(assistant_msg)
    
    for line in user_formatted:
        print(line)
    for line in assistant_formatted:
        print(line)
    print()
    
    # Demo input area
    print("Input area rendering:")
    input_lines = ui.draw_input_area("Hello world", "Type your message")
    for line in input_lines:
        print(line)
    print()
    
    # Demo footer
    print("Footer rendering:")
    footer_lines = ui.draw_footer()
    for line in footer_lines:
        print(line)
    print()
    
    # Show full screen simulation
    print("Full screen simulation:")
    print("=" * ui.width)
    
    # Simulate adding messages to UI
    ui.messages = [user_msg, assistant_msg]
    ui.current_conversation = type('obj', (object,), {'title': 'Demo Conversation'})()
    
    # Draw complete screen
    header_lines = ui.draw_header()
    message_lines = ui.draw_messages()
    input_lines = ui.draw_input_area("", "Type your message")
    footer_lines = ui.draw_footer()
    
    all_lines = header_lines + message_lines[:10] + input_lines + footer_lines
    
    for line in all_lines:
        print(line)
    
    print("=" * ui.width)

def show_feature_comparison():
    """Show feature comparison between Textual and Console versions"""
    print("\n📊 Feature Comparison")
    print("=" * 60)
    print()
    print("TEXTUAL VERSION vs PURE CONSOLE VERSION")
    print("-" * 60)
    print()
    print("Backend Features (Both Versions):")
    print("✓ OpenAI, Anthropic, Ollama support")
    print("✓ Streaming responses") 
    print("✓ Conversation history")
    print("✓ Multiple response styles")
    print("✓ Model switching")
    print("✓ SQLite database storage")
    print("✓ Configuration management")
    print()
    print("UI Features:")
    print()
    print("TEXTUAL VERSION:")
    print("✓ Rich TUI widgets")
    print("✓ Mouse support")
    print("✓ Advanced layouts")
    print("✓ Built-in scrolling")
    print("✓ Color themes")
    print("✓ Animation effects")
    print("⚠ Requires textual dependency")
    print()
    print("PURE CONSOLE VERSION:")
    print("✓ No external UI dependencies")
    print("✓ Works on any terminal")
    print("✓ ASCII art interface")
    print("✓ Keyboard-only navigation")
    print("✓ Real-time screen updates")
    print("✓ Lightweight and fast")
    print("✓ Better for SSH/remote sessions")
    print("✓ Lower memory footprint")
    print()
    print("Use Cases:")
    print()
    print("TEXTUAL VERSION: When you want the richest UI experience")
    print("CONSOLE VERSION: When you want maximum compatibility and minimal dependencies")

def show_usage_examples():
    """Show usage examples"""
    print("\n💡 Usage Examples")
    print("=" * 60)
    print()
    print("1. Direct execution:")
    print("   python3 console_chat.py")
    print()
    print("2. With initial message:")
    print("   python3 console_chat.py 'Explain quantum computing'")
    print()
    print("3. Via main app with console flag:")
    print("   python3 -m app.main --console")
    print("   python3 -m app.main --console 'Hello world'")
    print()
    print("4. After installation:")
    print("   chat-console-pure")
    print("   c-c-pure")
    print()
    print("5. Keyboard shortcuts in console mode:")
    print("   q          - Quit application")
    print("   n          - New conversation")
    print("   h          - View history")
    print("   s          - Settings menu")
    print("   Ctrl+C     - Cancel generation or quit")
    print("   Enter      - Send message")
    print("   Backspace  - Delete character")
    print()
    print("6. Technical details:")
    print("   • Real-time character input processing")
    print("   • Cross-platform terminal support (Windows/Linux/macOS)")
    print("   • Automatic terminal size detection")
    print("   • Clean ASCII border rendering")
    print("   • Responsive layout adaptation")

def main():
    """Run the demo"""
    try:
        demo_console_ui()
        show_feature_comparison()
        show_usage_examples()
        
        print("\n🚀 Ready to try the console version!")
        print("Run: python3 console_chat.py")
        
    except Exception as e:
        print(f"Demo error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())