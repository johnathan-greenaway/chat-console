from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Generator, AsyncGenerator

class BaseModelClient(ABC):
    """Base class for AI model clients"""
    
    @abstractmethod
    async def generate_completion(self, messages: List[Dict[str, str]], 
                                model: str, 
                                style: Optional[str] = None, 
                                temperature: float = 0.7, 
                                max_tokens: Optional[int] = None) -> str:
        """Generate a text completion"""
        pass
    
    @abstractmethod
    async def generate_stream(self, messages: List[Dict[str, str]], 
                            model: str, 
                            style: Optional[str] = None,
                            temperature: float = 0.7, 
                            max_tokens: Optional[int] = None) -> AsyncGenerator[str, None]:
        """Generate a streaming text completion"""
        yield ""  # Placeholder implementation
    
    @abstractmethod
    def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available models from this provider"""
        pass
    
    @staticmethod
    def get_client_for_model(model_name: str) -> 'BaseModelClient':
        """Factory method to get appropriate client for model"""
        from ..config import CONFIG, AVAILABLE_PROVIDERS
        from .anthropic import AnthropicClient
        from .openai import OpenAIClient
        from .ollama import OllamaClient
        
        # Get model info and provider
        model_info = CONFIG["available_models"].get(model_name)
        model_name_lower = model_name.lower()
        
        # Helper function to check if model exists in Ollama
        def check_ollama_model(client, model):
            try:
                models = client.get_available_models()
                return any(m["id"] == model for m in models)
            except:
                return False
        
        # If model is in config, use its provider
        if model_info:
            provider = model_info["provider"]
            if not AVAILABLE_PROVIDERS[provider]:
                raise Exception(f"Provider '{provider}' is not available. Please check your configuration.")
        # For custom models, try to infer provider
        else:
            # First try Ollama for known model names
            if any(name in model_name_lower for name in ["llama", "mistral", "codellama", "gemma"]):
                if not AVAILABLE_PROVIDERS["ollama"]:
                    raise Exception("Ollama server is not running. Please start Ollama and try again.")
                provider = "ollama"
            # Then try other providers if they're available
            elif any(name in model_name_lower for name in ["gpt", "text-", "davinci"]):
                if not AVAILABLE_PROVIDERS["openai"]:
                    raise Exception("OpenAI API key not found. Please set OPENAI_API_KEY environment variable.")
                provider = "openai"
            elif any(name in model_name_lower for name in ["claude", "anthropic"]):
                if not AVAILABLE_PROVIDERS["anthropic"]:
                    raise Exception("Anthropic API key not found. Please set ANTHROPIC_API_KEY environment variable.")
                provider = "anthropic"
            else:
                # Try Ollama as a last resort if it's available
                if AVAILABLE_PROVIDERS["ollama"]:
                    client = OllamaClient()
                    if check_ollama_model(client, model_name):
                        return client
                raise Exception(f"Unknown model: {model_name}")
        
        # Return appropriate client
        if provider == "ollama":
            client = OllamaClient()
            if not check_ollama_model(client, model_name):
                raise Exception(f"Model '{model_name}' not found. Please pull it first with 'ollama pull {model_name}'")
            return client
        elif provider == "openai":
            return OpenAIClient()
        elif provider == "anthropic":
            return AnthropicClient()
        else:
            raise ValueError(f"Unknown provider: {provider}")
