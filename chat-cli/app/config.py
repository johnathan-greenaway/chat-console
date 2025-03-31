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

def check_provider_availability():
    """Check which providers are available"""
    providers = {
        "openai": bool(OPENAI_API_KEY),
        "anthropic": bool(ANTHROPIC_API_KEY),
        "ollama": False
    }
    
    # Check if Ollama is running
    import requests
    try:
        response = requests.get(OLLAMA_BASE_URL + "/api/tags", timeout=2)
        providers["ollama"] = response.status_code == 200
    except:
        pass
        
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
        "claude-3-opus": {
            "provider": "anthropic",
            "max_tokens": 4096,
            "display_name": "Claude 3 Opus"
        },
        "claude-3-sonnet": {
            "provider": "anthropic",
            "max_tokens": 4096,
            "display_name": "Claude 3 Sonnet"
        },
        "claude-3-haiku": {
            "provider": "anthropic",
            "max_tokens": 4096,
            "display_name": "Claude 3 Haiku"
        },
        "claude-3.7-sonnet": {
            "provider": "anthropic",
            "max_tokens": 4096,
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
    "max_history_items": 100,
    "highlight_code": True,
    "auto_save": True,
    "generate_dynamic_titles": True
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

# Current configuration
CONFIG = load_config()
