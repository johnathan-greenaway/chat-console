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
    async def cancel_stream(self) -> None:
        """Cancel any active streaming request"""
        pass
    
    @abstractmethod
    def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available models from this provider"""
        pass
    
    @staticmethod
    def get_client_type_for_model(model_name: str) -> type:
        """Get the client class for a model without instantiating it"""
        from ..config import CONFIG, AVAILABLE_PROVIDERS, CUSTOM_PROVIDERS
        from .anthropic import AnthropicClient
        from .openai import OpenAIClient
        from .ollama import OllamaClient
        from .custom_openai import CustomOpenAIClient
        import logging
        
        logger = logging.getLogger(__name__)
        
        # Safety check for None or empty string
        if not model_name:
            logger.warning("Empty model name passed to get_client_type_for_model")
            return None
            
        # Get model info and provider
        model_info = CONFIG["available_models"].get(model_name)
        model_name_lower = model_name.lower()
        
        # Debug log the model name
        logger.info(f"Getting client type for model: {model_name}")
        
        # If model is in config, use its provider
        if model_info:
            provider = model_info["provider"]
            logger.info(f"Found model in config with provider: {provider}")
        # For custom models, try to infer provider
        else:
            # Check if this model was selected from a specific provider in the UI
            # This would be stored in a temporary attribute on the app instance
            try:
                from ..classic_main import SimpleChatApp
                import inspect
                frame = inspect.currentframe()
                while frame:
                    if 'self' in frame.f_locals and isinstance(frame.f_locals['self'], SimpleChatApp):
                        app_instance = frame.f_locals['self']
                        if hasattr(app_instance, 'selected_provider'):
                            provider = app_instance.selected_provider
                            logger.info(f"Using provider from UI selection: {provider}")
                            return OllamaClient if provider == "ollama" else (
                                   OpenAIClient if provider == "openai" else 
                                   AnthropicClient if provider == "anthropic" else None)
                    frame = frame.f_back
            except Exception as e:
                logger.error(f"Error checking for UI provider selection: {str(e)}")
            
            # If we couldn't get the provider from the UI, infer it from the model name
            # Check for common OpenAI model patterns or prefixes
            if (model_name_lower.startswith(("gpt-", "text-", "davinci", "o1", "o3", "o4")) or 
                "gpt" in model_name_lower or 
                model_name_lower in ["04-mini", "04", "04-turbo", "04-vision", "o1", "o3", "o4-mini"]):
                provider = "openai"
                logger.info(f"Identified {model_name} as an OpenAI model")
            # Then check for Anthropic models - these should ALWAYS use Anthropic client
            elif any(name in model_name_lower for name in ["claude", "anthropic"]):
                provider = "anthropic"
                logger.info(f"Identified as Anthropic model: {model_name}")
            # Then try Ollama for known model names or if selected from Ollama UI
            elif (any(name in model_name_lower for name in ["llama", "mistral", "codellama", "gemma"]) or
                  model_name in [m["id"] for m in CONFIG.get("ollama_models", [])]):
                provider = "ollama"
                logger.info(f"Identified as Ollama model: {model_name}")
            else:
                # Default to Ollama for unknown models
                provider = "ollama"
                logger.info(f"Unknown model type, defaulting to Ollama: {model_name}")
        
        # Return appropriate client class
        if provider == "ollama":
            return OllamaClient
        elif provider == "openai":
            return OpenAIClient
        elif provider == "anthropic":
            return AnthropicClient
        elif provider in CUSTOM_PROVIDERS:
            # Check if it's an OpenAI-compatible custom provider
            if CUSTOM_PROVIDERS[provider].get("type") == "openai_compatible":
                return CustomOpenAIClient
        else:
            return None
            
    @staticmethod
    async def get_client_for_model(model_name: str) -> 'BaseModelClient':
        """Factory method to get appropriate client for model"""
        from ..config import CONFIG, AVAILABLE_PROVIDERS, CUSTOM_PROVIDERS
        from .anthropic import AnthropicClient
        from .openai import OpenAIClient
        from .ollama import OllamaClient
        from .custom_openai import CustomOpenAIClient
        import logging
        
        logger = logging.getLogger(__name__)
        
        # Safety check for None or empty string
        if not model_name:
            logger.warning("Empty model name passed to get_client_for_model")
            raise ValueError("Model name cannot be empty")
            
        # Log the model name we're getting a client for
        logger.info(f"Getting client for model: {model_name}")
        
        # Get model info and provider
        model_info = CONFIG["available_models"].get(model_name)
        model_name_lower = model_name.lower()
        
        # If model is in config, use its provider
        if model_info:
            provider = model_info["provider"]
            logger.info(f"Found model in config with provider: {provider}")
            if not AVAILABLE_PROVIDERS[provider]:
                raise Exception(f"Provider '{provider}' is not available. Please check your configuration.")
        # For custom models, try to infer provider
        else:
            # Check if this model was selected from a specific provider in the UI
            provider = None
            try:
                from ..classic_main import SimpleChatApp
                import inspect
                frame = inspect.currentframe()
                while frame:
                    if 'self' in frame.f_locals and isinstance(frame.f_locals['self'], SimpleChatApp):
                        app_instance = frame.f_locals['self']
                        if hasattr(app_instance, 'selected_provider'):
                            provider = app_instance.selected_provider
                            logger.info(f"Using provider from UI selection: {provider}")
                            break
                    frame = frame.f_back
            except Exception as e:
                logger.error(f"Error checking for UI provider selection: {str(e)}")
            
            # If we couldn't get the provider from the UI, infer it from the model name
            if not provider:
                # Check for common OpenAI model patterns or prefixes
                if (model_name_lower.startswith(("gpt-", "text-", "davinci", "o1", "o3", "o4")) or 
                    "gpt" in model_name_lower or 
                    model_name_lower in ["04-mini", "04", "04-turbo", "04-vision", "o1", "o3", "o4-mini"]):
                    if not AVAILABLE_PROVIDERS["openai"]:
                        raise Exception("OpenAI API key not found. Please set OPENAI_API_KEY environment variable.")
                    provider = "openai"
                    logger.info(f"Identified {model_name} as an OpenAI model")
                # Then check for Anthropic models - these should ALWAYS use Anthropic client
                elif any(name in model_name_lower for name in ["claude", "anthropic"]):
                    if not AVAILABLE_PROVIDERS["anthropic"]:
                        raise Exception("Anthropic API key not found. Please set ANTHROPIC_API_KEY environment variable.")
                    provider = "anthropic"
                    logger.info(f"Identified as Anthropic model: {model_name}")
                # Then try Ollama for known model names or if selected from Ollama UI
                elif (any(name in model_name_lower for name in ["llama", "mistral", "codellama", "gemma"]) or
                      model_name in [m["id"] for m in CONFIG.get("ollama_models", [])]):
                    if not AVAILABLE_PROVIDERS["ollama"]:
                        raise Exception("Ollama server is not running. Please start Ollama and try again.")
                    provider = "ollama"
                    logger.info(f"Identified as Ollama model: {model_name}")
                else:
                    # Default to Ollama for unknown models
                    if AVAILABLE_PROVIDERS["ollama"]:
                        provider = "ollama"
                        logger.info(f"Unknown model type, defaulting to Ollama: {model_name}")
                    else:
                        raise Exception(f"Unknown model: {model_name}")
            
            # Verify the selected provider is available
            if provider and not AVAILABLE_PROVIDERS.get(provider, False):
                raise Exception(f"Provider '{provider}' is not available. Please check your configuration.")
        
        # Return appropriate client
        if provider == "ollama":
            return await OllamaClient.create()
        elif provider == "openai":
            return await OpenAIClient.create()
        elif provider == "anthropic":
            return await AnthropicClient.create()
        elif provider in CUSTOM_PROVIDERS:
            # Check if it's an OpenAI-compatible custom provider
            if CUSTOM_PROVIDERS[provider].get("type") == "openai_compatible":
                return await CustomOpenAIClient.create(provider)
        else:
            raise ValueError(f"Unknown provider: {provider}")
    
    @staticmethod
    async def create(provider: str) -> 'BaseModelClient':
        """Create a client for a specific provider ID"""
        from ..config import AVAILABLE_PROVIDERS, CUSTOM_PROVIDERS
        from .anthropic import AnthropicClient
        from .openai import OpenAIClient
        from .ollama import OllamaClient
        from .custom_openai import CustomOpenAIClient
        
        if provider == "ollama":
            return await OllamaClient.create()
        elif provider == "openai":
            return await OpenAIClient.create()
        elif provider == "anthropic":
            return await AnthropicClient.create()
        elif provider in CUSTOM_PROVIDERS:
            # Check if it's an OpenAI-compatible custom provider
            if CUSTOM_PROVIDERS[provider].get("type") == "openai_compatible":
                return await CustomOpenAIClient.create(provider)
        else:
            raise ValueError(f"Unknown provider: {provider}")
