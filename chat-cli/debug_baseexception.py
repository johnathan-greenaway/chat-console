#!/usr/bin/env python3
"""
Debug script to find the BaseException error
"""
import sys
import asyncio
import traceback
sys.path.insert(0, '.')

async def test_response_generation():
    """Test generating a response to trigger the BaseException error"""
    try:
        from app.console_interface import ConsoleUI
        from app.config import CONFIG
        from app.utils import get_model_client
        
        # Create a console UI instance
        ui = ConsoleUI()
        
        # Try to get a model client
        model_id = "gemma3:4b"  # Using a model that might exist
        
        print(f"Testing with model: {model_id}")
        
        # Get the client
        client = await get_model_client(model_id)
        print(f"Got client: {type(client)}")
        
        # Try to generate a response
        messages = [{"role": "user", "content": "Hello"}]
        
        print("Attempting to generate response...")
        response = await client.generate_completion(messages, model_id)
        print(f"Response: {response}")
        
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_response_generation())