import os
from dotenv import load_dotenv
from pathlib import Path
import json

# Load environment variables
load_dotenv()

# Base paths
APP_DIR = Path.home() / ".terminalchat"
APP_DIR.mkdir(exist_ok=True)
DB_PATH = APP_DIR / "chat_history.db"
CONFIG_PATH = APP_DIR / "config.json"

# API Keys and Provider Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Custom provider configurations - load from config or environment
def get_custom_providers():
    """Get custom provider configuration from config or environment"""
    # Try to load from saved config first
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, 'r') as f:
                saved_config = json.load(f)
                if saved_config.get("custom_api_enabled", True):
                    return {
                        "openai-compatible": {
                            "base_url": saved_config.get("custom_api_base_url", 
                                                        os.getenv("CUSTOM_API_BASE_URL", "https://api.example.com/v1")),
                            "api_key": saved_config.get("custom_api_key", 
                                                       os.getenv("CUSTOM_API_KEY", "")),
                            "type": "openai_compatible",
                            "display_name": saved_config.get("custom_api_display_name", "Custom API")
                        }
                    }
        except:
            pass
    
    # Fallback to environment variables
    return {
        "openai-compatible": {
            "base_url": os.getenv("CUSTOM_API_BASE_URL", "https://api.example.com/v1"),
            "api_key": os.getenv("CUSTOM_API_KEY", ""),
            "type": "openai_compatible",
            "display_name": "Custom API"
        }
    }

CUSTOM_PROVIDERS = get_custom_providers()

def check_provider_availability():
    """Check which providers are available"""
    providers = {
        "openai": bool(OPENAI_API_KEY),
        "anthropic": bool(ANTHROPIC_API_KEY),
        "ollama": False
    }
    
    # Check custom providers
    for provider_name, config in CUSTOM_PROVIDERS.items():
        if config.get("api_key"):
            providers[provider_name] = True
        else:
            providers[provider_name] = False
    
    # Check if Ollama is running at configured URL
    import requests
    try:
        response = requests.get(OLLAMA_BASE_URL + "/api/tags", timeout=2)
        providers["ollama"] = response.status_code == 200
    except (requests.RequestException, ValueError, OSError):
        # If can't connect to configured URL, don't mark as unavailable yet
        # The ensure_ollama_running function will handle starting it if needed
        providers["ollama"] = True  # Assume available, will verify later
        
    return providers

# Get available providers
AVAILABLE_PROVIDERS = check_provider_availability()

# Default configuration
DEFAULT_CONFIG = {
    "default_model": "mistral" if AVAILABLE_PROVIDERS["ollama"] else "gpt-3.5-turbo",
    "available_models": {
        "gpt-3.5-turbo": {
            "provider": "openai",
            "max_tokens": 4096,
            "display_name": "GPT-3.5 Turbo"
        },
        "gpt-4": {
            "provider": "openai",
            "max_tokens": 8192,
            "display_name": "GPT-4"
        },
        "o1": {
            "provider": "openai",
            "max_tokens": 128000,
            "display_name": "o1 (Reasoning)"
        },
        "o1-mini": {
            "provider": "openai",
            "max_tokens": 128000,
            "display_name": "o1-mini (Reasoning)"
        },
        "o3": {
            "provider": "openai",
            "max_tokens": 128000,
            "display_name": "o3 (Reasoning)"
        },
        "o3-mini": {
            "provider": "openai",
            "max_tokens": 128000,
            "display_name": "o3-mini (Reasoning)"
        },
        "o4-mini": {
            "provider": "openai",
            "max_tokens": 128000,
            "display_name": "o4-mini (Reasoning)"
        },
        # OpenAI-Compatible API models
        "qwen/qwen3-32b": {
            "provider": "openai-compatible",
            "max_tokens": 131072,
            "display_name": "Qwen 3 32B (Reasoning & Code)"
        },
        "qwen2.5-coder-32b-instruct": {
            "provider": "openai-compatible",
            "max_tokens": 32768,
            "display_name": "Qwen 2.5 Coder 32B"
        },
        "qwen-2.5-coder-14b-instruct": {
            "provider": "openai-compatible",
            "max_tokens": 32768,
            "display_name": "Qwen 2.5 Coder 14B"
        },
        "qwen-2.5-coder-7b-instruct": {
            "provider": "openai-compatible",
            "max_tokens": 32768,
            "display_name": "Qwen 2.5 Coder 7B"
        },
        "llama-3.3-70b-versatile": {
            "provider": "openai-compatible",
            "max_tokens": 131072,
            "display_name": "Llama 3.3 70B Versatile"
        },
        "llama-3.2-90b-vision-preview": {
            "provider": "openai-compatible",
            "max_tokens": 131072,
            "display_name": "Llama 3.2 90B Vision"
        },
        "llama3-groq-70b-8192-tool-use-preview": {
            "provider": "openai-compatible",
            "max_tokens": 8192,
            "display_name": "Llama 3 70B Tool Use"
        },
        "llama-3.1-8b-instant": {
            "provider": "openai-compatible",
            "max_tokens": 131072,
            "display_name": "Llama 3.1 8B Instant"
        },
        "mixtral-8x7b-32768": {
            "provider": "openai-compatible",
            "max_tokens": 32768,
            "display_name": "Mixtral 8x7B"
        },
        "deepseek-r1-lite-preview": {
            "provider": "openai-compatible",
            "max_tokens": 65536,
            "display_name": "DeepSeek R1 Lite (Reasoning)"
        },
        # Use the corrected keys from anthropic.py
        "claude-3-opus-20240229": {
            "provider": "anthropic",
            "max_tokens": 4096, # Note: Max tokens might differ per model version
            "display_name": "Claude 3 Opus"
        },
        "claude-3-sonnet-20240229": {
            "provider": "anthropic",
            "max_tokens": 4096, # Note: Max tokens might differ per model version
            "display_name": "Claude 3 Sonnet"
        },
        "claude-3-haiku-20240307": {
            "provider": "anthropic",
            "max_tokens": 4096,
            "display_name": "Claude 3 Haiku"
        },
        "claude-3-5-sonnet-20240620": {
            "provider": "anthropic",
            "max_tokens": 4096, # Note: Max tokens might differ per model version
            "display_name": "Claude 3.5 Sonnet" # Corrected display name
        },
        "claude-3-7-sonnet-20250219": {
            "provider": "anthropic",
            "max_tokens": 4096, # Note: Max tokens might differ per model version
            "display_name": "Claude 3.7 Sonnet"
        },
        "llama2": {
            "provider": "ollama",
            "max_tokens": 4096,
            "display_name": "Llama 2"
        },
        "mistral": {
            "provider": "ollama",
            "max_tokens": 4096,
            "display_name": "Mistral"
        },
        "codellama": {
            "provider": "ollama",
            "max_tokens": 4096,
            "display_name": "Code Llama"
        },
        "gemma": {
            "provider": "ollama",
            "max_tokens": 4096,
            "display_name": "Gemma"
        }
    },
    "theme": "dark",
    "user_styles": {
        "default": {
            "name": "Default",
            "description": "Standard assistant responses"
        },
        "concise": {
            "name": "Concise",
            "description": "Brief and to the point responses"
        },
        "detailed": {
            "name": "Detailed",
            "description": "Comprehensive and thorough responses"
        },
        "technical": {
            "name": "Technical",
            "description": "Technical and precise language"
        },
        "friendly": {
            "name": "Friendly",
            "description": "Warm and conversational tone"
        }
    },
    "default_style": "default",
    "last_used_model": None,  # Track the last model used by the user
    "max_history_items": 100,
    "highlight_code": True,
    "auto_save": True,
    "generate_dynamic_titles": True,
    "ollama_model_preload": True,
    "ollama_inactive_timeout_minutes": 30
}

def validate_config(config):
    """Validate and fix configuration issues"""
    # Only validate non-Ollama providers since Ollama can be started on demand
    default_model = config.get("default_model")
    if default_model in config["available_models"]:
        provider = config["available_models"][default_model]["provider"]
        if provider != "ollama" and not AVAILABLE_PROVIDERS[provider]:
            # Find first available model, preferring Ollama
            for model, info in config["available_models"].items():
                if info["provider"] == "ollama" or AVAILABLE_PROVIDERS[info["provider"]]:
                    config["default_model"] = model
                    break
    return config

def load_config():
    """Load the user configuration or create default if not exists"""
    if not CONFIG_PATH.exists():
        validated_config = validate_config(DEFAULT_CONFIG.copy())
        save_config(validated_config)
        return validated_config
    
    try:
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)
        # Merge with defaults to ensure all keys exist
        merged_config = DEFAULT_CONFIG.copy()
        
        # Special handling for available_models to merge rather than replace
        if "available_models" in config:
            # Start with default models
            merged_models = DEFAULT_CONFIG["available_models"].copy()
            
            # Migrate old provider names to new ones
            saved_models = config["available_models"].copy()
            for model_id, model_info in saved_models.items():
                if model_info.get("provider") == "uplink":
                    # Migrate uplink to openai-compatible
                    model_info["provider"] = "openai-compatible"
                    saved_models[model_id] = model_info
            
            # Update with any saved models (preserves user additions/modifications)
            merged_models.update(saved_models)
            config["available_models"] = merged_models
        
        merged_config.update(config)
        # Validate and fix any issues
        validated_config = validate_config(merged_config)
        if validated_config != merged_config:
            save_config(validated_config)
        return validated_config
    except Exception as e:
        print(f"Error loading config: {e}. Using defaults.")
        return validate_config(DEFAULT_CONFIG.copy())

def save_config(config):
    """Save the configuration to disk"""
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)

def update_last_used_model(model_id):
    """Update the last used model in config"""
    global CONFIG
    CONFIG["last_used_model"] = model_id
    save_config(CONFIG)

# Current configuration
CONFIG = load_config()

# --- Dynamically update Anthropic models after initial load ---
def update_anthropic_models(config):
    """Update the config with Anthropic models."""
    if AVAILABLE_PROVIDERS["anthropic"]:
        try:
            # Instead of calling an async method, use a hardcoded fallback list
            # that matches what's in the AnthropicClient class
            fallback_models = [
                {"id": "claude-3-opus-20240229", "name": "Claude 3 Opus"},
                {"id": "claude-3-sonnet-20240229", "name": "Claude 3 Sonnet"},
                {"id": "claude-3-haiku-20240307", "name": "Claude 3 Haiku"},
                {"id": "claude-3-5-sonnet-20240620", "name": "Claude 3.5 Sonnet"},
                {"id": "claude-3-7-sonnet-20250219", "name": "Claude 3.7 Sonnet"},
            ]
            
            # Remove old models first
            models_to_remove = [
                model_id for model_id, info in config["available_models"].items()
                if info.get("provider") == "anthropic"
            ]
            for model_id in models_to_remove:
                del config["available_models"][model_id]
                
            # Add the fallback models
            for model in fallback_models:
                config["available_models"][model["id"]] = {
                    "provider": "anthropic",
                    "max_tokens": 4096,
                    "display_name": model["name"]
                }
            print(f"Updated Anthropic models in config with fallback list")
            
        except Exception as e:
            print(f"Error updating Anthropic models in config: {e}")
            # Keep existing config if update fails

    return config

# Update the global CONFIG after loading it
CONFIG = update_anthropic_models(CONFIG)
# Optionally save the updated config back immediately (or rely on later saves)
# save_config(CONFIG) # Uncomment if you want to persist the fetched models immediately
