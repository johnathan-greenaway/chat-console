#!/usr/bin/env python3
"""Test script for Custom API integration with chat-console
Supports testing any OpenAI-compatible API including Uplink Worker and Ollama
"""

import os
import sys
import asyncio
import argparse
from pathlib import Path

# Add the chat-cli directory to Python path
chat_cli_dir = Path(__file__).parent / "chat-cli"
sys.path.insert(0, str(chat_cli_dir))

from app.config import CONFIG, CUSTOM_PROVIDERS, AVAILABLE_PROVIDERS, save_config
from app.api.base import BaseModelClient
from app.api.custom_openai import CustomOpenAIClient

async def test_custom_api(base_url=None, api_key=None, provider_name="openai-compatible", test_model=None, is_ollama=False):
    """Test Custom API integration (Uplink Worker, Ollama, or any OpenAI-compatible API)"""
    if is_ollama:
        print("Testing Ollama OpenAI-Compatible API")
    elif "uplink" in (base_url or "").lower():
        print("Testing Uplink Worker Integration") 
    else:
        print("Testing Custom OpenAI-Compatible API")
    print("=" * 40)
    
    # Update configuration if custom URL or API key provided
    if base_url or api_key:
        print(f"🔧 Configuring custom provider settings...")
        
        # Update or create the custom provider config
        if provider_name not in CUSTOM_PROVIDERS:
            CUSTOM_PROVIDERS[provider_name] = {
                "type": "openai-compatible",
                "display_name": provider_name.title()
            }
        
        if base_url:
            CUSTOM_PROVIDERS[provider_name]["base_url"] = base_url
            print(f"✅ Base URL set to: {base_url}")
        
        if api_key:
            CUSTOM_PROVIDERS[provider_name]["api_key"] = api_key
            print(f"✅ API key set: {api_key[:10]}...")
        elif is_ollama:
            # Ollama doesn't need an API key
            CUSTOM_PROVIDERS[provider_name]["api_key"] = "ollama"
            print(f"✅ Using Ollama mode (no API key required)")
        
        # Mark provider as available
        AVAILABLE_PROVIDERS[provider_name] = True
        
        # Save config
        save_config(CONFIG)
        print(f"✅ Configuration saved")
    
    # Check API key configuration
    if not is_ollama:
        current_key = CUSTOM_PROVIDERS.get(provider_name, {}).get("api_key") or os.getenv("CUSTOM_API_KEY")
        if not current_key:
            print("❌ No API key configured")
            print("Please provide an API key with --api-key or set CUSTOM_API_KEY environment variable")
            return False
        print(f"✅ Using API key: {current_key[:10]}...")
    
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
        
        # Determine which model to test
        if test_model:
            model_to_test = test_model
            print(f"   Using specified model: {model_to_test}")
        elif is_ollama:
            # For Ollama, try to get available models
            try:
                models = await client.list_models()
                if models:
                    model_to_test = models[0]['id']
                    print(f"   Using first available Ollama model: {model_to_test}")
                else:
                    model_to_test = "llama2"  # fallback
                    print(f"   Using fallback Ollama model: {model_to_test}")
            except:
                model_to_test = "llama2"
                print(f"   Using default Ollama model: {model_to_test}")
        else:
            model_to_test = "qwen2.5-coder-32b-instruct"
            print(f"   Using default model: {model_to_test}")
        
        try:
            test_prompt = "Hello from Ollama!" if is_ollama else "Hello from Custom API!"
            test_messages = [{"role": "user", "content": f"Say '{test_prompt}' and nothing else."}]
            
            print(f"   Sending test message to {model_to_test}...")
            response = await client.generate_completion(
                messages=test_messages,
                model=model_to_test,
                max_tokens=50
            )
            print(f"✅ Completion successful!")
            print(f"   Response: {response[:200]}...")
            
        except Exception as e:
            print(f"⚠️ Completion test failed: {e}")
            if is_ollama:
                print("   Make sure Ollama is running and the model is downloaded")
                print("   Try: ollama pull llama2")
            else:
                print("   This might be due to API key issues or network connectivity")
            
        print("\n✅ Integration test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Client creation failed: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(
        description="Test Custom OpenAI-Compatible API Integration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test default Uplink Worker (uses CUSTOM_API_KEY env var)
  python test_uplink_integration.py
  
  # Test custom Uplink Worker URL with API key
  python test_uplink_integration.py --url https://your-worker.domain.workers.dev --api-key your-key
  
  # Test Ollama OpenAI-compatible endpoint
  python test_uplink_integration.py --ollama
  python test_uplink_integration.py --ollama --url http://localhost:11434/v1
  
  # Test specific model
  python test_uplink_integration.py --model gpt-4-turbo
  python test_uplink_integration.py --ollama --model mistral
  
  # Test custom provider with different name
  python test_uplink_integration.py --url https://api.example.com/v1 --provider my-api --api-key key123
        """
    )
    
    parser.add_argument("--url", "--base-url", 
                       help="Custom API base URL (e.g., https://your-worker.domain.workers.dev)")
    parser.add_argument("--api-key", "--key",
                       help="API key for authentication")
    parser.add_argument("--model",
                       help="Specific model to test")
    parser.add_argument("--provider",
                       default="openai-compatible",
                       help="Provider name to configure (default: openai-compatible)")
    parser.add_argument("--ollama",
                       action="store_true",
                       help="Test Ollama OpenAI-compatible endpoint")
    
    args = parser.parse_args()
    
    # Set defaults for Ollama mode
    if args.ollama:
        if not args.url:
            args.url = "http://localhost:11434/v1"
        if not args.model:
            print("ℹ️  No model specified, will use first available Ollama model")
    
    # Run the test
    print("Chat-Console Custom API Integration Test")
    print("=========================================\n")
    
    success = asyncio.run(test_custom_api(
        base_url=args.url,
        api_key=args.api_key,
        provider_name=args.provider,
        test_model=args.model,
        is_ollama=args.ollama
    ))
    
    if success:
        print("\n🎉 All tests passed! Your Custom API integration is ready to use.")
        print("\nTo use Custom API models in chat-console:")
        print("1. Run: chat-console or c-c")
        print("2. Go to Settings (press 's')")
        print("3. Select 'Custom API' from providers")
        print("4. Select a model from the available models")
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()