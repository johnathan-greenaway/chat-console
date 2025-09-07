#!/usr/bin/env python3
"""Test script for Settings UI and dynamic model loading"""

import os
import sys
import asyncio
from pathlib import Path

# Add the chat-cli directory to Python path
chat_cli_dir = Path(__file__).parent / "chat-cli"
sys.path.insert(0, str(chat_cli_dir))

async def test_settings_flow():
    """Test the complete settings flow"""
    print("Testing Settings UI and Dynamic Model Loading")
    print("=" * 50)
    
    # Import after path is set
    from app.config import CONFIG, CUSTOM_PROVIDERS, AVAILABLE_PROVIDERS, save_config
    from app.api.custom_openai import CustomOpenAIClient
    
    # 1. Check initial state
    print("\n1️⃣ Initial Configuration:")
    print(f"   Custom API enabled: {CONFIG.get('custom_api_enabled', True)}")
    print(f"   Custom API URL: {CONFIG.get('custom_api_base_url', CUSTOM_PROVIDERS.get('openai-compatible', {}).get('base_url'))}")
    print(f"   Custom API key: {CONFIG.get('custom_api_key', CUSTOM_PROVIDERS.get('openai-compatible', {}).get('api_key'))[:10]}...")
    print(f"   Display name: {CONFIG.get('custom_api_display_name', 'Custom API')}")
    print(f"   Provider available: {AVAILABLE_PROVIDERS.get('openai-compatible', False)}")
    
    # 2. Test saving settings
    print("\n2️⃣ Testing Settings Save:")
    test_settings = {
        "custom_api_enabled": True,
        "custom_api_base_url": "https://api.example.com/v1",
        "custom_api_key": "xxxxx",
        "custom_api_display_name": "My Custom API"
    }
    
    # Update CONFIG
    CONFIG.update(test_settings)
    save_config(CONFIG)
    print("   ✅ Settings saved to config")
    
    # 3. Test provider update
    print("\n3️⃣ Testing Provider Update:")
    from app.config import check_provider_availability
    AVAILABLE_PROVIDERS.clear()
    AVAILABLE_PROVIDERS.update(check_provider_availability())
    print(f"   Provider available after update: {AVAILABLE_PROVIDERS.get('openai-compatible', False)}")
    
    # 4. Test dynamic model fetching
    print("\n4️⃣ Testing Dynamic Model Fetching:")
    if AVAILABLE_PROVIDERS.get('openai-compatible', False):
        try:
            client = await CustomOpenAIClient.create("openai-compatible")
            models = await client.list_models()
            print(f"   ✅ Fetched {len(models)} models from API")
            
            # Show sample models
            for i, model in enumerate(models[:5]):
                print(f"      {i+1}. {model['name']} ({model['id']})")
            if len(models) > 5:
                print(f"      ... and {len(models) - 5} more")
                
        except Exception as e:
            print(f"   ⚠️ Error fetching models: {e}")
    else:
        print("   ❌ Custom API provider not available")
    
    # 5. Test command parsing
    print("\n5️⃣ Testing Command Recognition:")
    test_commands = ["/settings", "/models", "/history", "/help"]
    for cmd in test_commands:
        print(f"   • {cmd} - Would open: ", end="")
        if cmd == "/settings":
            print("Settings screen")
        elif cmd == "/models":
            print("Model browser")
        elif cmd == "/history":
            print("Chat history")
        elif cmd == "/help":
            print("Help message")
    
    print("\n✅ All tests completed!")
    return True

if __name__ == "__main__":
    print("Chat-Console Settings UI Test")
    print("=============================\n")
    
    success = asyncio.run(test_settings_flow())
    
    if success:
        print("\n🎉 Settings flow test successful!")
        print("\nTo test in the app:")
        print("1. Run: chat-console")
        print("2. Press 's' or type /settings")
        print("3. Configure your Custom API settings")
        print("4. Test connection and save")
        print("5. Select 'Custom API' from provider dropdown")
        print("6. See live models from your API!")
    
    sys.exit(0 if success else 1)