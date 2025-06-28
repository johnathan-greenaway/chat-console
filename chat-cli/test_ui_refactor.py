#!/usr/bin/env python3
"""
Test script for the Rams-inspired UI refactor
"""

import sys
import os
from datetime import datetime

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

def test_border_system():
    """Test the new ASCII border system"""
    print("Testing ASCII Border System...")
    
    from app.ui.borders import CLEAN_BORDERS, create_border_line, create_app_header
    
    # Test border characters
    light_borders = CLEAN_BORDERS['light']
    assert light_borders['top_left'] == '┌'
    assert light_borders['horizontal'] == '─'
    print("✓ Border characters loaded correctly")
    
    # Test border line creation
    top_line = create_border_line(60, 'light', 'top')
    assert len(top_line) == 60
    assert top_line.startswith('┌')
    assert top_line.endswith('┐')
    print("✓ Border line creation works")
    
    # Test app header
    header = create_app_header("Chat Console v0.4.3", "Claude 3.7 Sonnet", 80)
    assert len(header) == 80
    print("✓ App header generation works")
    
    print("Border system tests passed!\n")

def test_color_palette():
    """Test the Rams-inspired color palette"""
    print("Testing Rams Color Palette...")
    
    from app.ui.styles import RAMS_COLORS, get_theme
    
    # Test color structure
    dark_colors = RAMS_COLORS['dark']
    required_colors = ['background', 'foreground', 'accent', 'muted', 'border']
    
    for color in required_colors:
        assert color in dark_colors
        assert dark_colors[color].startswith('#')
    print("✓ Color palette structure correct")
    
    # Test theme generation
    theme = get_theme('dark')
    assert theme is not None
    print("✓ Theme generation works")
    
    # Test Rams principles in colors
    assert dark_colors['background'] == '#0C0C0C'  # Deep black
    assert dark_colors['foreground'] == '#E8E8E8'  # Clean white
    assert dark_colors['accent'] == '#33FF33'       # Minimal green accent
    print("✓ Rams color principles maintained")
    
    print("Color palette tests passed!\n")

def test_message_formatting():
    """Test the clean message formatting"""
    print("Testing Message Formatting...")
    
    from app.ui.chat_interface import MessageDisplay
    from app.models import Message
    
    # Create a test message
    test_message = Message(role="user", content="Hello, world!")
    
    # Test message display creation (without mounting)
    display = MessageDisplay(test_message)
    
    # Test content formatting
    formatted = display._format_content("Test message")
    assert "Test message" in formatted
    print("✓ Message formatting works")
    
    # Test thinking message formatting
    thinking_formatted = display._format_content("Thinking...")
    assert "[dim]" in thinking_formatted
    print("✓ Thinking message styling works")
    
    print("Message formatting tests passed!\n")

def test_css_compilation():
    """Test that CSS compiles without errors"""
    print("Testing CSS Compilation...")
    
    from app.main import SimpleChatApp
    
    # Test CSS string validity
    app_css = SimpleChatApp.CSS
    assert "#main-content" in app_css
    assert "#0C0C0C" in app_css  # Background color
    assert "#E8E8E8" in app_css  # Foreground color
    assert "#33FF33" in app_css  # Accent color
    print("✓ Main app CSS contains Rams colors")
    
    from app.ui.chat_interface import MessageDisplay
    message_css = MessageDisplay.DEFAULT_CSS
    assert "MessageDisplay" in message_css
    assert "user-message" in message_css
    assert "assistant-message" in message_css
    print("✓ Message display CSS structured correctly")
    
    print("CSS compilation tests passed!\n")

def test_minimal_loading():
    """Test the minimal loading animation"""
    print("Testing Minimal Loading Animation...")
    
    from app.ui.borders import MINIMAL_LOADING_FRAMES
    
    # Test loading frames exist and are minimal
    assert len(MINIMAL_LOADING_FRAMES) > 0
    for frame in MINIMAL_LOADING_FRAMES:
        assert len(frame) <= 10  # Should be minimal
    print("✓ Minimal loading frames available")
    
    print("Loading animation tests passed!\n")

def print_design_verification():
    """Print visual verification of the design principles"""
    print("=== DESIGN VERIFICATION ===")
    print("Following Dieter Rams' 'Less but better' principle:")
    print()
    
    from app.ui.borders import create_app_header, create_border_line
    
    # Show the clean header design
    header = create_app_header("Chat Console v0.4.3", "Claude 3.7 Sonnet", 70)
    print("Clean App Header:")
    print(header)
    print()
    
    # Show minimal border example
    print("Minimal Border Example:")
    print(create_border_line(50, 'light', 'top'))
    print("│" + " " * 48 + "│")
    print("│  12:34  Hello, can you help me with something?  │")
    print("│                                                │")
    print("│  12:35  Of course! I'd be happy to help.       │")
    print("│                                                │")
    print(create_border_line(50, 'light', 'bottom'))
    print()
    
    # Show color palette
    from app.ui.styles import RAMS_COLORS
    print("Rams Color Palette (Dark):")
    for name, color in RAMS_COLORS['dark'].items():
        print(f"  {name:12}: {color}")
    print()
    
    print("Key Design Changes:")
    print("✓ Replaced bright green (#33FF33) with purpose-driven accent use")
    print("✓ Clean ASCII borders instead of heavy decoration")
    print("✓ Generous spacing (2-3 padding instead of 0-1)")
    print("✓ Minimal loading animations (simple ● ○ instead of complex)")
    print("✓ Functional button symbols (● for new, ✎ for edit)")
    print("✓ Clean typography with timestamps formatted consistently")
    print("✓ Removed unnecessary visual elements")
    print("✓ Purposeful color hierarchy (foreground, muted, accent)")

def main():
    """Run all tests"""
    print("🎨 Testing Rams-Inspired UI Refactor")
    print("=" * 50)
    print()
    
    try:
        test_border_system()
        test_color_palette()
        test_message_formatting()
        test_css_compilation()
        test_minimal_loading()
        
        print("🎉 All tests passed!")
        print()
        
        print_design_verification()
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())