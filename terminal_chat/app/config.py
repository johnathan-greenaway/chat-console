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

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Default configuration
DEFAULT_CONFIG = {
    "default_model": "gpt-3.5-turbo",
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
    "auto_save": True
}

def load_config():
    """Load the user configuration or create default if not exists"""
    if not CONFIG_PATH.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG
    
    try:
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)
        # Merge with defaults to ensure all keys exist
        merged_config = DEFAULT_CONFIG.copy()
        merged_config.update(config)
        return merged_config
    except Exception as e:
        print(f"Error loading config: {e}. Using defaults.")
        return DEFAULT_CONFIG

def save_config(config):
    """Save the configuration to disk"""
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)

# Current configuration
CONFIG = load_config()
