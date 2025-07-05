#!/usr/bin/env python3
"""
Test the full UI flow to reproduce the error
"""
import sys
import asyncio
import traceback
sys.path.insert(0, '.')

async def test_full_ui_flow():
    """Test the complete UI flow including model resolution"""
    try:
        print("Testing full UI flow...")
        
        # Import console UI
        from app.console_interface import ConsoleUI
        
        # Create UI instance
        print("Creating ConsoleUI instance...")
        ui = ConsoleUI()
        
        print(f"Selected model: {ui.selected_model}")
        print(f"Selected style: {ui.selected_style}")
        
        # Try to generate a response using the UI's method
        print("Testing UI generate_response method...")
        await ui.generate_response("Hello, how are you?")
        
        print("SUCCESS: Full UI flow completed without error")
        
    except Exception as e:
        print(f"ERROR FOUND: {type(e).__name__}: {e}")
        print("\nFull traceback:")
        traceback.print_exc()
        
        # Check if this is the BaseException error
        error_str = str(e)
        if "catching classes that do not inherit from BaseException" in error_str:
            print(f"\n🎯 FOUND THE ERROR: {error_str}")

if __name__ == "__main__":
    asyncio.run(test_full_ui_flow())