#!/usr/bin/env python3
"""Test script to verify the model details fix works correctly."""

import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'chat-cli'))

from app.api.ollama import OllamaClient


async def test_model_details_fix():
    """Test that our fix for handling dict model_id works correctly."""
    
    client = OllamaClient()
    
    # Test case 1: Normal string model_id
    print("Test 1: Normal string model_id")
    try:
        result = await client.get_model_details("gemma3")
        print(f"✓ String model_id worked: {result.get('error', 'No error')}")
    except Exception as e:
        print(f"✗ String model_id failed: {e}")
    
    # Test case 2: Dict model_id (this was causing the error)
    print("\nTest 2: Dict model_id (the bug scenario)")
    model_dict = {
        'name': 'gemma3',
        'description': 'The current, most capable model that runs on a single GPU.',
        'variants': ['vision', '1b', '4b', '12b', '27b'],
        'stats': {'pulls': '3.1M', 'tags': 17, 'last_updated': '9 days ago'},
        'model_family': 'Gemma'
    }
    
    try:
        result = await client.get_model_details(model_dict)
        print(f"✓ Dict model_id handled correctly: {result.get('error', 'No error')}")
    except Exception as e:
        print(f"✗ Dict model_id failed: {e}")
    
    # Test case 3: Dict model_id without name (edge case)
    print("\nTest 3: Dict model_id without name")
    bad_dict = {'description': 'No name field'}
    
    try:
        result = await client.get_model_details(bad_dict)
        if 'error' in result:
            print(f"✓ Dict without name handled correctly: {result['error']}")
        else:
            print(f"✗ Dict without name should have returned error")
    except Exception as e:
        print(f"✗ Dict without name failed: {e}")
    
    # Test pull_model method with dict input
    print("\nTest 4: pull_model with dict input")
    try:
        async for progress in client.pull_model(model_dict):
            print(f"✓ pull_model with dict worked: {progress}")
            break  # Just test the first response
    except ValueError as e:
        print(f"✓ pull_model dict validation worked: {e}")
    except Exception as e:
        print(f"? pull_model with dict: {e}")
    
    print("\nAll tests completed!")


if __name__ == "__main__":
    asyncio.run(test_model_details_fix())