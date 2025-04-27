#!/usr/bin/env python3
"""
Diagnostic script for chat-cli to debug streaming response issues.
"""
import os
import sys
import asyncio
import logging
from app.main import SimpleChatApp
from app.api.base import BaseModelClient
from app.api.openai import OpenAIClient
from app.api.anthropic import AnthropicClient
from app.api.ollama import OllamaClient
from app.utils import generate_streaming_response

# Set up logging to console
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("diagnostic")

# Debug log function
def debug_log(msg):
    logger.debug(msg)
    print(f"DEBUG: {msg}")

async def test_streaming_response():
    """Test streaming response with a simple prompt."""
    print("Starting diagnostic test for streaming response...")
    
    # Test with OpenAI first (most reliable)
    try:
        print("\n=== Testing OpenAI Streaming ===")
        client = await OpenAIClient.create()
        
        # Simple callback to print chunks
        async def callback(content):
            print(f"CALLBACK: Received content length: {len(content)}")
            print(f"CALLBACK CONTENT: '{content[:50]}...'")
        
        # Test messages
        messages = [
            {"role": "user", "content": "Hello, can you respond with a short greeting?"}
        ]
        
        # Create a mock app object with query_one method
        class MockApp:
            def query_one(self, selector):
                class MockElement:
                    def add_class(self, cls):
                        print(f"MockApp: add_class({cls})")
                    def remove_class(self, cls):
                        print(f"MockApp: remove_class({cls})")
                    def update(self, content):
                        print(f"MockApp: update({content})")
                return MockElement()
            
            def refresh(self, layout=False):
                print(f"MockApp: refresh(layout={layout})")
        
        mock_app = MockApp()
        
        # Test streaming
        print("Starting OpenAI streaming test...")
        response = await generate_streaming_response(
            mock_app,
            messages,
            "gpt-3.5-turbo",
            "default",
            client,
            callback
        )
        
        print(f"\nFinal response: '{response}'")
        print("OpenAI streaming test completed")
        
    except Exception as e:
        print(f"Error testing OpenAI streaming: {str(e)}")
    
    # Test with Anthropic if available
    try:
        print("\n=== Testing Anthropic Streaming ===")
        client = await AnthropicClient.create()
        
        # Test streaming
        print("Starting Anthropic streaming test...")
        response = await generate_streaming_response(
            mock_app,
            messages,
            "claude-3-haiku-20240307",
            "default",
            client,
            callback
        )
        
        print(f"\nFinal response: '{response}'")
        print("Anthropic streaming test completed")
        
    except Exception as e:
        print(f"Error testing Anthropic streaming: {str(e)}")
    
    # Test with Ollama if available
    try:
        print("\n=== Testing Ollama Streaming ===")
        client = await OllamaClient.create()
        
        # Test streaming
        print("Starting Ollama streaming test...")
        response = await generate_streaming_response(
            mock_app,
            messages,
            "gemma:2b",  # Use a small model for quick testing
            "default",
            client,
            callback
        )
        
        print(f"\nFinal response: '{response}'")
        print("Ollama streaming test completed")
        
    except Exception as e:
        print(f"Error testing Ollama streaming: {str(e)}")

def main():
    """Run the diagnostic tests."""
    print("Starting chat-cli diagnostic tests...")
    
    # Run streaming response test
    asyncio.run(test_streaming_response())
    
    print("\nDiagnostic tests completed.")

if __name__ == "__main__":
    main()
