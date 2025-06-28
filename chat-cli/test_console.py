#!/usr/bin/env python3
"""
Test script for the pure console version
"""

import sys
import os
import asyncio

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

def test_console_imports():
    """Test that console version imports work"""
    print("Testing console imports...")
    
    try:
        from console_chat import ConsoleUI
        print("✓ ConsoleUI imported successfully")
        
        from app.console_utils import console_streaming_response, apply_style_prefix
        print("✓ Console utilities imported successfully")
        
        from app.models import Message, Conversation
        print("✓ Models imported successfully")
        
        from app.database import ChatDatabase
        print("✓ Database imported successfully")
        
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False

def test_console_ui_creation():
    """Test creating ConsoleUI instance"""
    print("\nTesting ConsoleUI creation...")
    
    try:
        from console_chat import ConsoleUI
        
        ui = ConsoleUI()
        print("✓ ConsoleUI instance created")
        
        # Test basic properties
        assert hasattr(ui, 'width')
        assert hasattr(ui, 'height')
        assert hasattr(ui, 'db')
        assert hasattr(ui, 'selected_model')
        print("✓ ConsoleUI has required attributes")
        
        # Test border drawing
        border_chars = ui.get_border_chars()
        assert 'horizontal' in border_chars
        assert 'vertical' in border_chars
        print("✓ Border characters available")
        
        border_line = ui.draw_border_line(50)
        assert len(border_line) == 50
        print("✓ Border drawing works")
        
        return True
    except Exception as e:
        print(f"❌ ConsoleUI creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_message_formatting():
    """Test message formatting"""
    print("\nTesting message formatting...")
    
    try:
        from console_chat import ConsoleUI
        from app.models import Message
        
        ui = ConsoleUI()
        message = Message(role="user", content="Hello, this is a test message!")
        
        formatted = ui.format_message(message)
        assert isinstance(formatted, list)
        assert len(formatted) > 0
        print("✓ Message formatting works")
        
        return True
    except Exception as e:
        print(f"❌ Message formatting failed: {e}")
        return False

def test_console_utils():
    """Test console utilities"""
    print("\nTesting console utilities...")
    
    try:
        from app.console_utils import apply_style_prefix, word_wrap, truncate_text
        
        # Test style prefix
        messages = [{"role": "user", "content": "Hello"}]
        styled = apply_style_prefix(messages, "concise")
        assert "concise" in styled[0]["content"].lower()
        print("✓ Style prefix application works")
        
        # Test word wrap
        wrapped = word_wrap("This is a long message that should be wrapped", 10)
        assert len(wrapped) > 1
        print("✓ Word wrapping works")
        
        # Test text truncation
        truncated = truncate_text("This is a very long message", 10)
        assert len(truncated) == 10
        print("✓ Text truncation works")
        
        return True
    except Exception as e:
        print(f"❌ Console utilities test failed: {e}")
        return False

async def test_basic_console_flow():
    """Test basic console flow without user interaction"""
    print("\nTesting basic console flow...")
    
    try:
        from console_chat import ConsoleUI
        
        ui = ConsoleUI()
        
        # Test conversation creation
        await ui.create_new_conversation()
        assert ui.current_conversation is not None
        print("✓ Conversation creation works")
        
        # Test adding a message
        await ui.add_message("user", "Hello test")
        assert len(ui.messages) == 1
        assert ui.messages[0].content == "Hello test"
        print("✓ Message addition works")
        
        return True
    except Exception as e:
        print(f"❌ Basic console flow test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def print_usage_examples():
    """Print usage examples"""
    print("\n" + "=" * 60)
    print("PURE CONSOLE VERSION USAGE")
    print("=" * 60)
    print()
    print("Direct execution:")
    print("  python3 console_chat.py")
    print("  python3 console_chat.py 'Hello, how are you?'")
    print()
    print("With model selection:")
    print("  python3 console_chat.py --model gpt-3.5-turbo")
    print("  python3 console_chat.py --style concise")
    print()
    print("Via main app with console flag:")
    print("  python3 -m app.main --console")
    print("  python3 -m app.main --console 'Hello world'")
    print()
    print("After installation:")
    print("  chat-console-pure")
    print("  c-c-pure")
    print()
    print("Key Features:")
    print("✓ No Textual dependencies - pure terminal")
    print("✓ Real-time ASCII art interface")
    print("✓ Streaming response display")
    print("✓ All existing backend functionality")
    print("✓ Keyboard shortcuts: q (quit), n (new), h (history), s (settings)")
    print("✓ Ctrl+C cancellation support")
    print()
    print("Console Interface Preview:")
    print("┌ Chat Console v0.4.3 ──────────── Model: Claude 3.7 Sonnet ┐")
    print("│ New Conversation                                            │")
    print("├─────────────────────────────────────────────────────────────┤")
    print("│                                                             │")
    print("│  12:34  Hello, can you help me with something?             │")
    print("│                                                             │")
    print("│  12:35  Of course! I'd be happy to help.                   │")
    print("│                                                             │")
    print("├─────────────────────────────────────────────────────────────┤")
    print("│ Type your message:                                          │")
    print("│ > _                                                         │")
    print("├─────────────────────────────────────────────────────────────┤")
    print("│ [q] Quit  [n] New  [h] History  [s] Settings  [ctrl+c] Cancel │")
    print("└─────────────────────────────────────────────────────────────┘")

async def main():
    """Run all tests"""
    print("🖥️  Testing Pure Console Chat CLI (No Textual)")
    print("=" * 60)
    
    all_passed = True
    
    # Run tests
    tests = [
        test_console_imports,
        test_console_ui_creation,
        test_message_formatting,
        test_console_utils,
    ]
    
    for test_func in tests:
        if not test_func():
            all_passed = False
    
    # Run async test
    try:
        await test_basic_console_flow()
    except Exception as e:
        print(f"❌ Async test failed: {e}")
        all_passed = False
    
    if all_passed:
        print("\n🎉 All console tests passed!")
        print_usage_examples()
    else:
        print("\n❌ Some tests failed!")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))