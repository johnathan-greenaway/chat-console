#!/usr/bin/env python3
"""
Script to reproduce the BaseException error
"""
import sys
import asyncio
import traceback
sys.path.insert(0, '.')

async def test_response_with_gemma():
    """Test generating a response with gemma3:4b to reproduce the error"""
    try:
        print("Starting response generation test...")
        
        # Import the API client directly
        from app.api.ollama import OllamaClient
        
        # Create client
        print("Creating Ollama client...")
        client = await OllamaClient.create()
        
        # Test with gemma3:4b
        model_id = "gemma3:4b"
        messages = [{"role": "user", "content": "Hello, how are you?"}]
        
        print(f"Testing response generation with model: {model_id}")
        
        # Try to generate a response (non-streaming first)
        response = await client.generate_completion(messages, model_id)
        print(f"SUCCESS (non-streaming): Got response: {response[:100]}...")
        
        # Now test streaming which is more likely to have the error
        print("\nTesting streaming response...")
        full_response = ""
        async for chunk in client.generate_stream(messages, model_id):
            if chunk:
                full_response += chunk
                print(f"CHUNK: {chunk[:50]}...")
                if len(full_response) > 100:  # Stop after getting some content
                    break
        
        print(f"SUCCESS (streaming): Got {len(full_response)} characters")
        
        # Test the console UI streaming function specifically
        print("\nTesting console UI streaming function...")
        from app.console_utils import console_streaming_response
        
        # Create a simple callback
        def update_callback(text):
            print(f"CALLBACK: {text[:50]}...")
        
        # Test the console streaming function
        full_ui_response = ""
        async for chunk in console_streaming_response(messages, model_id, None, client, update_callback):
            if chunk:
                full_ui_response += chunk
                print(f"UI_CHUNK: {chunk[:50]}...")
                if len(full_ui_response) > 100:
                    break
                    
        print(f"SUCCESS (UI streaming): Got {len(full_ui_response)} characters")
        
    except Exception as e:
        print(f"ERROR REPRODUCED: {type(e).__name__}: {e}")
        print("\nFull traceback:")
        traceback.print_exc()
        
        # Print the exact error message format that appears in the UI
        error_str = str(e)
        if "catching classes that do not inherit from BaseException" in error_str:
            print(f"\n✨ ERROR: Error generating response: {error_str}")

if __name__ == "__main__":
    asyncio.run(test_response_with_gemma())