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
        
        model_info = CONFIG["available_models"].get(model_name)
        if not model_info:
            raise ValueError(f"Unknown model: {model_name}")
            
        provider = model_info["provider"]
        
        if provider == "anthropic":
            return AnthropicClient()
        elif provider == "openai":
            return OpenAIClient()
        else:
            raise ValueError(f"Unknown provider: {provider}")
