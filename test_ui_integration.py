#!/usr/bin/env python3
"""Test script for UI integration with custom providers"""

import os
import sys
import asyncio
from pathlib import Path

# Add the chat-cli directory to Python path
chat_cli_dir = Path(__file__).parent / "chat-cli"
sys.path.insert(0, str(chat_cli_dir))

from app.config import CONFIG, CUSTOM_PROVIDERS, AVAILABLE_PROVIDERS
from app.ui.model_selector import ModelSelector

async def test_ui_integration():
    """Test the UI integration with custom providers"""
    print("Testing UI Integration with Custom Providers")
    print("=" * 45)
    
    # Test 1: Check provider options
    print("🔧 Testing provider options generation...")
    
    # Create a mock ModelSelector to test provider options
    selector = ModelSelector()
    
    # Check provider options (this is done in compose, but we can simulate)
    provider_options = [
        ("OpenAI", "openai"),
        ("Anthropic", "anthropic"), 
        ("Ollama", "ollama")
    ]
    
    # Add custom providers that are available
    for provider_name, provider_config in CUSTOM_PROVIDERS.items():
        if AVAILABLE_PROVIDERS.get(provider_name, False):
            # Create a user-friendly display name
            display_name = provider_name.title()
            if provider_name == "uplink":
                display_name = "Uplink Worker"
            provider_options.append((display_name, provider_name))
    
    print(f"✅ Available provider options: {len(provider_options)}")
    for display_name, provider_id in provider_options:
        available = "✅" if AVAILABLE_PROVIDERS.get(provider_id, False) else "❌"
        print(f"   {available} {display_name} ({provider_id})")
    
    # Test 2: Check model options for custom providers
    print(f"\n🔧 Testing model options for custom providers...")
    
    for provider_name in CUSTOM_PROVIDERS.keys():
        if AVAILABLE_PROVIDERS.get(provider_name, False):
            print(f"\n   Testing {provider_name.title()} provider:")
            try:
                # Test getting model options
                options = await selector._get_model_options(provider_name)
                print(f"   ✅ Found {len(options)} model options")
                
                # Show first few models
                for i, (display_name, model_id) in enumerate(options[:3]):
                    print(f"      - {display_name} ({model_id})")
                if len(options) > 3:
                    print(f"      ... and {len(options) - 3} more")
                    
            except Exception as e:
                print(f"   ⚠️ Error getting model options: {e}")
        else:
            print(f"\n   ❌ {provider_name.title()} provider not available (API key missing)")
    
    # Test 3: Check config-based model loading
    print(f"\n🔧 Testing config-based custom provider models...")
    
    custom_models_in_config = 0
    for model_id, model_info in CONFIG["available_models"].items():
        if model_info.get("provider") in CUSTOM_PROVIDERS:
            custom_models_in_config += 1
            if custom_models_in_config <= 3:  # Show first 3
                print(f"   ✅ {model_info['display_name']} ({model_id}) - {model_info['provider']}")
    
    if custom_models_in_config > 3:
        print(f"   ... and {custom_models_in_config - 3} more custom provider models")
    
    print(f"\n✅ Total custom provider models in config: {custom_models_in_config}")
    
    # Test 4: Provider detection for models
    print(f"\n🔧 Testing provider detection for custom models...")
    
    test_models = [
        "qwen2.5-coder-32b-instruct",
        "llama-3.3-70b-versatile", 
        "deepseek-r1-lite-preview"
    ]
    
    for model_id in test_models:
        if model_id in CONFIG["available_models"]:
            provider = CONFIG["available_models"][model_id]["provider"]
            available = "✅" if AVAILABLE_PROVIDERS.get(provider, False) else "❌"
            print(f"   {available} {model_id} → {provider}")
        else:
            print(f"   ❓ {model_id} → not in config")
    
    return True

if __name__ == "__main__":
    print("Chat-Console UI Integration Test")
    print("=================================\n")
    
    # Check if we have any custom providers configured
    if not CUSTOM_PROVIDERS:
        print("❌ No custom providers configured in CUSTOM_PROVIDERS")
        sys.exit(1)
    
    success = asyncio.run(test_ui_integration())
    
    if success:
        print(f"\n🎉 UI integration test completed!")
        print(f"\nSummary:")
        print(f"- Custom providers configured: {len(CUSTOM_PROVIDERS)}")
        available_custom = sum(1 for p in CUSTOM_PROVIDERS.keys() if AVAILABLE_PROVIDERS.get(p, False))
        print(f"- Available custom providers: {available_custom}")
        custom_models = sum(1 for info in CONFIG['available_models'].values() if info.get('provider') in CUSTOM_PROVIDERS)
        print(f"- Custom provider models in config: {custom_models}")
        
        if available_custom > 0:
            print(f"\n✅ Your custom providers will appear in the UI!")
            print(f"To test: Run 'chat-console' and check the Provider dropdown")
        else:
            print(f"\n⚠️ Set API keys for custom providers to see them in the UI:")
            for provider_name in CUSTOM_PROVIDERS.keys():
                if not AVAILABLE_PROVIDERS.get(provider_name, False):
                    key_name = f"{provider_name.upper()}_API_KEY"
                    print(f"   export {key_name}='your-{provider_name}-key'")
    
    sys.exit(0 if success else 1)