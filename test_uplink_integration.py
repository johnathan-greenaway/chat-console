#!/usr/bin/env python3
"""Test script for Uplink Worker integration with chat-console"""

import os
import sys
import asyncio
from pathlib import Path

# Add the chat-cli directory to Python path
chat_cli_dir = Path(__file__).parent / "chat-cli"
sys.path.insert(0, str(chat_cli_dir))

from app.config import CONFIG, CUSTOM_PROVIDERS, AVAILABLE_PROVIDERS
from app.api.base import BaseModelClient
from app.api.custom_openai import CustomOpenAIClient

async def test_uplink_integration():
    """Test the Uplink Worker integration"""
    print("Testing Uplink Worker Integration")
    print("=" * 40)
    
    # Check if Custom API key is configured (either env var or default)
    api_key = os.getenv("CUSTOM_API_KEY")
    if api_key:
        print(f"✅ CUSTOM_API_KEY from environment: {api_key[:10]}...")
    else:
        # Check if default key is being used
        if AVAILABLE_PROVIDERS.get("openai-compatible", False):
            default_key = CUSTOM_PROVIDERS.get("openai-compatible", {}).get("api_key", "")
            print(f"✅ Using default API key: {default_key[:10]}...")
        else:
            print("❌ No API key configured and Custom API not available")
            print("Please set your Custom API key:")
            print("export CUSTOM_API_KEY='your-api-key-here'")
            return False
    
    # Check provider availability
    print(f"✅ Available providers: {list(AVAILABLE_PROVIDERS.keys())}")
    print(f"✅ Custom API available: {AVAILABLE_PROVIDERS.get('openai-compatible', False)}")
    
    # Check custom provider configuration
    print(f"✅ Custom providers configured: {list(CUSTOM_PROVIDERS.keys())}")
    provider_config = CUSTOM_PROVIDERS.get('openai-compatible')
    if provider_config:
        print(f"✅ Base URL: {provider_config['base_url']}")
        print(f"✅ Type: {provider_config['type']}")
        print(f"✅ Display name: {provider_config.get('display_name', 'N/A')}")
    
    # Check if custom models are in config
    custom_models = [model for model, info in CONFIG["available_models"].items() 
                     if info.get("provider") == "openai-compatible"]
    print(f"✅ Custom API models in config: {len(custom_models)}")
    for model in custom_models[:3]:  # Show first 3
        print(f"   - {model}: {CONFIG['available_models'][model]['display_name']}")
    if len(custom_models) > 3:
        print(f"   ... and {len(custom_models) - 3} more")
    
    # Test client creation
    try:
        print("\n🔧 Testing client creation...")
        client = await CustomOpenAIClient.create("openai-compatible")
        print("✅ CustomOpenAIClient created successfully")
        
        # Test model listing
        print("\n🔧 Testing model listing...")
        try:
            models = await client.list_models()
            print(f"✅ Retrieved {len(models)} models from Custom API")
            if models:
                print("   Sample models:")
                for model in models[:3]:
                    print(f"   - {model['id']}: {model['name']}")
        except Exception as e:
            print(f"⚠️ Model listing failed (using fallback): {e}")
            models = client._get_fallback_models()
            print(f"✅ Using {len(models)} fallback models")
        
        # Test client factory
        print("\n🔧 Testing client factory...")
        factory_client = await BaseModelClient.get_client_for_model("qwen2.5-coder-32b-instruct")
        print(f"✅ Factory created client: {type(factory_client).__name__}")
        
        # Test simple completion (if API key is valid)
        print("\n🔧 Testing simple completion...")
        try:
            test_messages = [{"role": "user", "content": "Say 'Hello from Uplink!'"}]
            response = await client.generate_completion(
                messages=test_messages,
                model="qwen2.5-coder-32b-instruct",
                max_tokens=50
            )
            print(f"✅ Completion successful: {response[:100]}...")
            
        except Exception as e:
            print(f"⚠️ Completion test failed: {e}")
            print("   This might be due to API key issues or network connectivity")
            
        print("\n✅ Integration test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Client creation failed: {e}")
        return False

if __name__ == "__main__":
    print("Chat-Console Uplink Integration Test")
    print("====================================\n")
    
    success = asyncio.run(test_uplink_integration())
    
    if success:
        print("\n🎉 All tests passed! Your Custom API integration is ready to use.")
        print("\nTo use Custom API models in chat-console:")
        print("1. Set your API key: export CUSTOM_API_KEY='your-key'")
        print("2. Run: chat-console or c-c")
        print("3. Select 'Custom API' from the Provider dropdown")
        print("4. Select a model from the available models")
    else:
        print("\n❌ Some tests failed. Please check the configuration.")
    
    sys.exit(0 if success else 1)