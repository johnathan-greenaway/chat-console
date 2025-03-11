from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Generator

class BaseModelClient(ABC):
    """Base class for AI model clients"""
    
    @abstractmethod
    def generate_completion(self, messages: List[Dict[str, str]], 
                           model: str, 
                           style: Optional[str] = None, 
                           temperature: float = 0.7, 
                           max_tokens: Optional[int] = None) -> str:
        """Generate a text completion"""
        pass
    
    @abstractmethod
    def generate_stream(self, messages: List[Dict[str, str]], 
                       model: str, 
                       style: Optional[str] = None,
                       temperature: float = 0.7, 
                       max_tokens: Optional[int] = None) -> Generator[str, None, None]:
        """Generate a streaming text completion"""
        pass
    
    @abstractmethod
    def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available models from this provider"""
        pass
    
    @staticmethod
    def get_client_for_model(model_name: str) -> 'BaseModelClient':
        """Factory method to get appropriate client for model"""
        from ..config import CONFIG
        from .anthropic import AnthropicClient
        from .openai import OpenAIClient
        
        # For known models, use their configured provider
        model_info = CONFIG["available_models"].get(model_name)
        if model_info:
            provider = model_info["provider"]
        else:
            # For custom models, infer provider from name prefix
            model_name_lower = model_name.lower()
            if any(name in model_name_lower for name in ["gpt", "text-", "davinci"]):
                provider = "openai"
            elif any(name in model_name_lower for name in ["claude", "anthropic"]):
                provider = "anthropic"
            elif any(name in model_name_lower for name in ["llama", "mistral", "codellama", "gemma"]):
                provider = "ollama"
            else:
                # Try to get from Ollama API first
                from .ollama import OllamaClient
                try:
                    client = OllamaClient()
                    models = client.get_available_models()
                    if any(model["id"] == model_name for model in models):
                        provider = "ollama"
                    else:
                        # Default to OpenAI if not found
                        provider = "openai"
                except:
                    # Default to OpenAI if Ollama not available
                    provider = "openai"
        
        if provider == "anthropic":
            return AnthropicClient()
        elif provider == "openai":
            return OpenAIClient()
        elif provider == "ollama":
            from .ollama import OllamaClient
            return OllamaClient()
        else:
            raise ValueError(f"Unknown provider: {provider}")
