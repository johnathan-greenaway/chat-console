#!/usr/bin/env python3
"""Test scrolling functionality with pre-populated messages"""

import asyncio
import sys
sys.path.insert(0, '.')

from app.console_interface import ConsoleUI
from app.models import Message

async def test_scroll():
    """Test the scroll functionality"""
    console = ConsoleUI()
    
    # Create a new conversation
    await console.create_new_conversation()
    
    # Add some test messages
    test_messages = [
        ("user", "Hello, this is message 1"),
        ("assistant", "Response to message 1. This is a longer response to test how the scrolling works with multi-line content."),
        ("user", "This is message 2"),
        ("assistant", "Response to message 2"),
        ("user", "Message 3 - asking a question?"),
        ("assistant", "Here's the answer to message 3. Let me provide a detailed response with multiple lines.\n\nThis helps test scrolling."),
        ("user", "Message 4"),
        ("assistant", "Response 4"),
        ("user", "Message 5 - another test"),
        ("assistant", "Response 5 - getting longer now"),
        ("user", "Message 6"),
        ("assistant", "Response 6"),
        ("user", "Message 7 - almost there"),
        ("assistant", "Response 7 - this should give us enough messages to scroll"),
        ("user", "Message 8 - final test message"),
        ("assistant", "Response 8 - now we should have plenty of messages to test scrolling!")
    ]
    
    # Add all messages
    for role, content in test_messages:
        message = Message(role=role, content=content)
        console.messages.append(message)
    
    print(f"Added {len(console.messages)} test messages")
    print("Now you can test scrolling:")
    print("- Ctrl+B: Toggle scroll mode")
    print("- Ctrl+U: Page up")
    print("- Ctrl+D: Page down") 
    print("- j/k: Line-by-line scrolling (when in scroll mode)")
    print("- Ctrl+G: Go to top")
    print("- Ctrl+E: Go to bottom")
    print("- Esc: Exit scroll mode")
    print("\nTip: Use Ctrl+B first to enter scroll mode, then try j/k for smooth scrolling!")
    print("Press Enter to start...")
    input()
    
    # Run the console
    await console.run()

if __name__ == "__main__":
    asyncio.run(test_scroll())