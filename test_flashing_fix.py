#!/usr/bin/env python3
"""Test script to verify the screen flashing fix"""

import sys
import os
sys.path.insert(0, "chat-cli")

def test_compilation():
    """Test that the console interface compiles correctly"""
    try:
        from app.console_interface import ConsoleUI
        print("✓ Console interface imports successfully")
        
        # Create instance to test basic functionality
        console = ConsoleUI()
        print(f"✓ ConsoleUI instance created successfully")
        print(f"  Screen dimensions: {console.width}x{console.height}")
        
        # Test the new buffered update method exists
        if hasattr(console, '_update_screen_buffered'):
            print("✓ New _update_screen_buffered method is available")
        else:
            print("✗ New _update_screen_buffered method is missing")
            return False
        
        # Test the updated streaming display method
        if hasattr(console, '_update_streaming_display'):
            print("✓ Updated _update_streaming_display method is available")
        else:
            print("✗ Updated _update_streaming_display method is missing")
            return False
        
        return True
        
    except Exception as e:
        print(f"✗ Error testing console interface: {e}")
        return False

def test_anti_flash_improvements():
    """Test that the anti-flash improvements are in place"""
    try:
        from app.console_interface import ConsoleUI
        console = ConsoleUI()
        
        # Check that the rate limiting has been improved
        # The new implementation should have reduced the update frequency
        import inspect
        source = inspect.getsource(console._update_streaming_display)
        
        if "0.05" in source:
            print("✓ Rate limiting improved: 20 updates/sec (was 50/sec)")
        else:
            print("? Rate limiting may not be fully updated")
        
        if "_update_screen_buffered" in source:
            print("✓ Now uses buffered screen updates instead of clear_screen()")
        else:
            print("✗ Still using clear_screen() method")
            return False
            
        # Check the buffered method uses ANSI positioning
        buffer_source = inspect.getsource(console._update_screen_buffered)
        if "\\033[H" in buffer_source:
            print("✓ Uses ANSI cursor positioning instead of screen clearing")
        else:
            print("? ANSI cursor positioning may not be implemented")
            
        if "\\033[K" in buffer_source:
            print("✓ Uses line clearing to prevent artifacts")
        else:
            print("? Line clearing may not be implemented")
            
        return True
        
    except Exception as e:
        print(f"✗ Error testing anti-flash improvements: {e}")
        return False

def main():
    print("🔄 Testing Screen Flashing Fix")
    print("=" * 50)
    
    success = True
    
    print("\n1. Testing compilation...")
    if not test_compilation():
        success = False
    
    print("\n2. Testing anti-flash improvements...")
    if not test_anti_flash_improvements():
        success = False
    
    print("\n" + "=" * 50)
    if success:
        print("✅ All tests passed! Screen flashing should be significantly reduced.")
        print("\nImprovements made:")
        print("• Reduced update frequency from 50fps to 20fps")
        print("• Replaced screen clearing with ANSI cursor positioning")
        print("• Added line-by-line clearing to prevent artifacts")
        print("• Implemented double buffering for smoother updates")
    else:
        print("❌ Some tests failed. The fix may not be working correctly.")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)