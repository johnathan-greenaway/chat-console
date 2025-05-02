#!/usr/bin/env python3
"""
Test script for OpenAI reasoning models in chat-cli
"""

import asyncio
import os
from dotenv import load_dotenv
from app.api.openai import OpenAIClient
from app.config import CONFIG

# Load environment variables
load_dotenv()

async def test_reasoning_model():
    """Test a reasoning model using the OpenAI client"""
    print("Testing OpenAI reasoning model...")
    
    # Create OpenAI client
    client = await OpenAIClient.create()
    
    # Define test messages
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Write a bash script that takes a matrix represented as a string with format '[1,2],[3,4],[5,6]' and prints the transpose in the same format."}
    ]
    
    # Test models
    reasoning_models = ["o4-mini", "o3-mini", "o1-mini"]
    
    for model in reasoning_models:
        if model in CONFIG["available_models"]:
            print(f"\n\nTesting model: {model}")
            print("-" * 40)
            
            try:
                # Generate completion
                print(f"Generating completion with {model}...")
                response = await client.generate_completion(
                    messages=messages,
                    model=model
                )
                
                print("\nResponse:")
                print("-" * 40)
                print(response)
                print("-" * 40)
                
            except Exception as e:
                print(f"Error with {model}: {str(e)}")
        else:
            print(f"\nSkipping {model} - not in available models")
    
    print("\nTest completed!")

async def test_streaming():
    """Test streaming with a reasoning model"""
    print("\nTesting streaming with reasoning model...")
    
    # Create OpenAI client
    client = await OpenAIClient.create()
    
    # Define test messages
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Explain the concept of recursion in programming in 3 sentences."}
    ]
    
    # Use o4-mini for streaming test
    model = "o4-mini"
    
    if model in CONFIG["available_models"]:
        print(f"\nStreaming with model: {model}")
        print("-" * 40)
        
        try:
            # Generate streaming response
            print("Response:")
            full_response = ""
            
            async for chunk in client.generate_stream(
                messages=messages,
                model=model
            ):
                print(chunk, end="", flush=True)
                full_response += chunk
            
            print("\n" + "-" * 40)
            
        except Exception as e:
            print(f"Error with streaming {model}: {str(e)}")
    else:
        print(f"\nSkipping {model} - not in available models")

async def main():
    """Main function"""
    # Test completion
    await test_reasoning_model()
    
    # Test streaming
    await test_streaming()

if __name__ == "__main__":
    asyncio.run(main())
