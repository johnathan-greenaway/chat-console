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
    def get_client_type_for_model(model_name: str) -> type:
        """Get the client class for a model without instantiating it"""
        from ..config import CONFIG, AVAILABLE_PROVIDERS
        from .anthropic import AnthropicClient
        from .openai import OpenAIClient
        from .ollama import OllamaClient
        import logging
        
        logger = logging.getLogger(__name__)
        
        # Get model info and provider
        model_info = CONFIG["available_models"].get(model_name)
        model_name_lower = model_name.lower()
        
        # If model is in config, use its provider
        if model_info:
            provider = model_info["provider"]
        # For custom models, try to infer provider
        else:
            # First try Ollama for known model names or if selected from Ollama UI
            if (any(name in model_name_lower for name in ["llama", "mistral", "codellama", "gemma"]) or
                model_name in [m["id"] for m in CONFIG.get("ollama_models", [])]):
                provider = "ollama"
            # Then try other providers
            elif any(name in model_name_lower for name in ["gpt", "text-", "davinci"]):
                provider = "openai"
            elif any(name in model_name_lower for name in ["claude", "anthropic"]):
                provider = "anthropic"
            else:
                # Default to Ollama for unknown models
                provider = "ollama"
        
        # Return appropriate client class
        if provider == "ollama":
            return OllamaClient
        elif provider == "openai":
            return OpenAIClient
        elif provider == "anthropic":
            return AnthropicClient
        else:
            return None
            
    @staticmethod
    async def get_client_for_model(model_name: str) -> 'BaseModelClient':
        """Factory method to get appropriate client for model"""
        from ..config import CONFIG, AVAILABLE_PROVIDERS
        from .anthropic import AnthropicClient
        from .openai import OpenAIClient
        from .ollama import OllamaClient
        import logging
        
        logger = logging.getLogger(__name__)
        
        # Get model info and provider
        model_info = CONFIG["available_models"].get(model_name)
        model_name_lower = model_name.lower()
        
        # If model is in config, use its provider
        if model_info:
            provider = model_info["provider"]
            if not AVAILABLE_PROVIDERS[provider]:
                raise Exception(f"Provider '{provider}' is not available. Please check your configuration.")
        # For custom models, try to infer provider
        else:
            # First try Ollama for known model names or if selected from Ollama UI
            if (any(name in model_name_lower for name in ["llama", "mistral", "codellama", "gemma"]) or
                model_name in [m["id"] for m in CONFIG.get("ollama_models", [])]):
                if not AVAILABLE_PROVIDERS["ollama"]:
                    raise Exception("Ollama server is not running. Please start Ollama and try again.")
                provider = "ollama"
                logger.info(f"Using Ollama for model: {model_name}")
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
                # Default to Ollama for unknown models
                if AVAILABLE_PROVIDERS["ollama"]:
                    provider = "ollama"
                    logger.info(f"Defaulting to Ollama for unknown model: {model_name}")
                else:
                    raise Exception(f"Unknown model: {model_name}")
        
        # Return appropriate client
        if provider == "ollama":
            return await OllamaClient.create()
        elif provider == "openai":
            return OpenAIClient()
        elif provider == "anthropic":
            return AnthropicClient()
        else:
            raise ValueError(f"Unknown provider: {provider}")
