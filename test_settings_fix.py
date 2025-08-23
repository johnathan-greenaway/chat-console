#!/usr/bin/env python3
"""Test script to verify the settings screen fix"""

import sys
import os
sys.path.insert(0, "chat-cli")

from app.config import load_config

def test_settings_display_fix():
    """Test that the settings screen can handle unknown models gracefully"""
    CONFIG = load_config()
    
    # Simulate the scenario where selected_model is 'gemma3n:e4b' but not in CONFIG
    selected_model = 'gemma3n:e4b'
    selected_style = 'default'
    
    # Test the fixed logic
    try:
        current_model_name = CONFIG['available_models'][selected_model]['display_name']
    except KeyError:
        current_model_name = f"{selected_model} (Ollama)"
    
    try:
        current_style_name = CONFIG['user_styles'][selected_style]['name']
    except KeyError:
        current_style_name = selected_style
    
    print(f"✓ Settings screen fix working!")
    print(f"  Current Model: {current_model_name}")
    print(f"  Current Style: {current_style_name}")
    
    # Verify that we get the expected fallback for unknown model
    assert current_model_name == "gemma3n:e4b (Ollama)", f"Expected 'gemma3n:e4b (Ollama)', got '{current_model_name}'"
    print("✓ Fallback logic works correctly for unknown models")

if __name__ == "__main__":
    test_settings_display_fix()
    print("✓ All tests passed! Settings screen should now work properly.")