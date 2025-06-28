#!/usr/bin/env python3
"""
Test the console command line entry points
"""

import subprocess
import sys
import os

def test_console_help():
    """Test console help command"""
    print("Testing console help command...")
    
    try:
        # Test the direct python approach first
        result = subprocess.run([
            sys.executable, "-c", 
            "from app.console_main import main; print('Console import works')"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("✓ Console main module can be imported")
        else:
            print(f"❌ Console main import failed: {result.stderr}")
            return False
            
        # Test console_chat import
        result = subprocess.run([
            sys.executable, "-c",
            "from app.console_chat import ConsoleUI; ui = ConsoleUI(); print('ConsoleUI created successfully')"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("✓ ConsoleUI can be created")
        else:
            print(f"❌ ConsoleUI creation failed: {result.stderr}")
            return False
            
        # Test the actual command with help
        try:
            result = subprocess.run([
                "c-c-pure", "--help"
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                print("✓ c-c-pure --help works")
                print("Help output preview:")
                print(result.stdout[:200] + "..." if len(result.stdout) > 200 else result.stdout)
            else:
                print(f"❌ c-c-pure --help failed: {result.stderr}")
                return False
                
        except FileNotFoundError:
            print("❌ c-c-pure command not found in PATH")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        return False

def test_console_version_check():
    """Test that we can at least start the console app"""
    print("\nTesting console version startup...")
    
    try:
        # Create a simple test that starts the console app but exits immediately
        test_script = '''
import asyncio
from app.console_chat import ConsoleUI

async def test_startup():
    console = ConsoleUI()
    print("Console UI initialized successfully")
    print(f"Terminal size: {console.width}x{console.height}")
    print(f"Selected model: {console.selected_model}")
    await console.create_new_conversation()
    print("Conversation created successfully")
    
asyncio.run(test_startup())
'''
        
        result = subprocess.run([
            sys.executable, "-c", test_script
        ], capture_output=True, text=True, timeout=15)
        
        if result.returncode == 0:
            print("✓ Console startup test passed")
            print("Output:", result.stdout)
            return True
        else:
            print(f"❌ Console startup test failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Console startup test failed with exception: {e}")
        return False

def show_usage_info():
    """Show usage information"""
    print("\n" + "="*60)
    print("PURE CONSOLE VERSION READY!")
    print("="*60)
    print()
    print("Available commands:")
    print("  c-c-pure                    # Start pure console chat")
    print("  c-c-pure --help             # Show help")
    print("  chat-console-pure           # Alternative command")
    print()
    print("  python3 app/console_chat.py # Direct execution")
    print("  python3 -m app.main --console  # Via main app")
    print()
    print("Features:")
    print("  ✓ No Textual dependencies")
    print("  ✓ Pure terminal interface")
    print("  ✓ ASCII art borders")
    print("  ✓ Real-time streaming")
    print("  ✓ All backend functionality")
    print()
    print("To try it:")
    print("  c-c-pure")
    print()
    print("Note: The console version requires an interactive terminal.")
    print("Use 'q' to quit, 'n' for new chat, 'h' for history, 's' for settings.")

def main():
    """Run all tests"""
    print("🧪 Testing Pure Console Command Line Interface")
    print("=" * 60)
    
    all_passed = True
    
    if not test_console_help():
        all_passed = False
        
    if not test_console_version_check():
        all_passed = False
    
    if all_passed:
        print("\n🎉 All console command tests passed!")
        show_usage_info()
    else:
        print("\n❌ Some console command tests failed!")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())