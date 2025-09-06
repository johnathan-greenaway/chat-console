"""
Model Manager - Handles dynamic model fetching and caching
"""
import asyncio
import time
import json
from typing import Dict, List, Optional, Any
from pathlib import Path
import logging

from .config import AVAILABLE_PROVIDERS, get_custom_providers
from .api.openai import OpenAIClient
from .api.anthropic import AnthropicClient
from .api.custom_openai import CustomOpenAIClient

logger = logging.getLogger(__name__)

class ModelManager:
    """Manages dynamic model fetching and caching"""
    
    def __init__(self, cache_duration_minutes: int = 30):
        self.cache_duration = cache_duration_minutes * 60  # Convert to seconds
        self.cache_file = Path.home() / ".terminalchat" / "models_cache.json"
        self.cache_file.parent.mkdir(exist_ok=True)
        self._models_cache = {}
        self._cache_timestamps = {}
        
    def _is_cache_valid(self, provider: str) -> bool:
        """Check if cache for provider is still valid"""
        if provider not in self._cache_timestamps:
            return False
        return time.time() - self._cache_timestamps[provider] < self.cache_duration
    
    def _load_cache_from_disk(self):
        """Load cached models from disk"""
        if not self.cache_file.exists():
            return
            
        try:
            with open(self.cache_file, 'r') as f:
                data = json.load(f)
                self._models_cache = data.get('models', {})
                self._cache_timestamps = data.get('timestamps', {})
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load models cache: {e}")
            
    def _save_cache_to_disk(self):
        """Save cached models to disk"""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump({
                    'models': self._models_cache,
                    'timestamps': self._cache_timestamps
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save models cache: {e}")
    
    async def get_openai_models(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Get OpenAI models with caching"""
        provider = 'openai'
        
        if not force_refresh and self._is_cache_valid(provider):
            return self._models_cache.get(provider, [])
        
        if not AVAILABLE_PROVIDERS.get(provider, False):
            logger.warning(f"OpenAI provider not available, returning fallback models")
            # Still return fallback models even if API key is not configured
            # This allows users to see what models would be available
            client = OpenAIClient()
            return client._get_fallback_models()
        
        try:
            client = await OpenAIClient.create()
            models = await client.list_models()
            
            # Cache the results
            self._models_cache[provider] = models
            self._cache_timestamps[provider] = time.time()
            self._save_cache_to_disk()
            
            logger.info(f"Fetched {len(models)} OpenAI models")
            return models
            
        except Exception as e:
            logger.error(f"Failed to fetch OpenAI models: {e}")
            # Return cached models if available, otherwise empty list
            return self._models_cache.get(provider, [])
    
    async def get_anthropic_models(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Get Anthropic models with caching"""
        provider = 'anthropic'
        
        if not force_refresh and self._is_cache_valid(provider):
            return self._models_cache.get(provider, [])
        
        if not AVAILABLE_PROVIDERS.get(provider, False):
            logger.warning(f"Anthropic provider not available, returning known models")
            # Still return known models even if API key is not configured
            # This allows users to see what models would be available
            client = AnthropicClient()
            return client._get_known_models()
        
        try:
            client = await AnthropicClient.create()
            models = await client.list_models()
            
            # Cache the results
            self._models_cache[provider] = models
            self._cache_timestamps[provider] = time.time()
            self._save_cache_to_disk()
            
            logger.info(f"Fetched {len(models)} Anthropic models")
            return models
            
        except Exception as e:
            logger.error(f"Failed to fetch Anthropic models: {e}")
            # Return cached models if available, otherwise empty list
            return self._models_cache.get(provider, [])
    
    async def get_ollama_models(self) -> List[Dict[str, Any]]:
        """Get Ollama models - these are handled separately by the existing system"""
        # Ollama models are handled by the existing model browser system
        # We'll return an empty list here and let the existing system handle it
        return []
    
    async def get_custom_models(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Get models from custom OpenAI-compatible providers"""
        provider = 'openai-compatible'
        
        # Check if custom providers are configured
        custom_providers = get_custom_providers()
        if not custom_providers or provider not in custom_providers:
            logger.info("No custom providers configured")
            return []
        
        # Check if the custom API is enabled
        provider_config = custom_providers[provider]
        if not provider_config.get('api_key'):
            logger.info("Custom API key not configured")
            return []
        
        # Check cache unless force refresh
        if not force_refresh and self._is_cache_valid(provider):
            logger.info(f"Using cached custom models (valid for {self.cache_duration/60:.0f} minutes)")
            return self._models_cache.get(provider, [])
        
        try:
            logger.info("Fetching models from custom API...")
            client = await CustomOpenAIClient.create(provider)
            models = await client.list_models()
            
            # Cache the results
            self._models_cache[provider] = models
            self._cache_timestamps[provider] = time.time()
            self._save_cache_to_disk()
            
            logger.info(f"Fetched {len(models)} custom models from {provider_config.get('display_name', 'Custom API')}")
            return models
            
        except Exception as e:
            logger.error(f"Failed to fetch custom models: {e}")
            # Return cached models if available, otherwise empty list
            return self._models_cache.get(provider, [])
    
    async def get_all_models(self, force_refresh: bool = False) -> Dict[str, List[Dict[str, Any]]]:
        """Get models from all available providers"""
        self._load_cache_from_disk()
        
        results = {}
        
        # Fetch models concurrently
        # Always try to get models (fallbacks will be returned if provider unavailable)
        tasks = [
            ('openai', self.get_openai_models(force_refresh)),
            ('anthropic', self.get_anthropic_models(force_refresh))
        ]
        
        # Add custom providers if configured
        custom_providers = get_custom_providers()
        if custom_providers and 'openai-compatible' in custom_providers:
            tasks.append(('openai-compatible', self.get_custom_models(force_refresh)))
        
        # Run concurrent fetches with timeout
        if tasks:
            try:
                completed_tasks = await asyncio.wait_for(
                    asyncio.gather(*[task[1] for task in tasks], return_exceptions=True),
                    timeout=10.0  # 10 second timeout
                )
                
                for i, result in enumerate(completed_tasks):
                    provider_name = tasks[i][0]
                    if isinstance(result, Exception):
                        logger.error(f"Error fetching {provider_name} models: {result}")
                        results[provider_name] = []
                    else:
                        results[provider_name] = result
                        
            except asyncio.TimeoutError:
                logger.error("Timeout fetching models from APIs")
                # Use cached data if available
                for provider_name, _ in tasks:
                    results[provider_name] = self._models_cache.get(provider_name, [])
        
        return results
    
    def format_models_for_config(self, all_models: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Dict[str, Any]]:
        """Format fetched models for config system"""
        formatted_models = {}
        
        for provider, models in all_models.items():
            for model in models:
                model_id = model['id']
                formatted_models[model_id] = {
                    'provider': provider,
                    'max_tokens': self._estimate_max_tokens(model_id, provider),
                    'display_name': model['name'],
                    'created': model.get('created', 0),
                    'owned_by': model.get('owned_by', provider)
                }
        
        return formatted_models
    
    def _estimate_max_tokens(self, model_id: str, provider: str) -> int:
        """Estimate max tokens for a model"""
        # Convert to lowercase for case-insensitive matching
        model_id_lower = model_id.lower()
        
        # These are rough estimates based on known model capabilities
        if provider == 'openai':
            # Check most specific patterns first
            if any(x in model_id_lower for x in ['o1', 'o3', 'o4']):
                return 128000  # Reasoning models have high context
            elif 'gpt-4o' in model_id_lower or 'gpt-4-turbo' in model_id_lower:
                return 128000  # GPT-4o and GPT-4 Turbo have 128k context
            elif '32k' in model_id_lower:
                return 32768
            elif '16k' in model_id_lower:
                return 16384  
            elif 'gpt-4' in model_id_lower:
                return 8192  # Base GPT-4
            else:
                return 4096  # Default for GPT-3.5 and others
        elif provider == 'anthropic':
            if 'opus' in model_id_lower:
                return 200000  # Claude 3 Opus has 200k context
            elif 'sonnet' in model_id_lower or 'haiku' in model_id_lower:
                return 200000  # Claude 3.5 models have 200k context
            else:
                return 100000  # Conservative default
        elif provider == 'openai-compatible':
            # Estimates for common custom/Groq models
            if 'llama-3' in model_id_lower and '70b' in model_id_lower:
                return 128000
            elif 'llama' in model_id_lower:
                return 32768
            elif 'mixtral' in model_id_lower:
                return 32768
            elif 'qwen' in model_id_lower:
                return 32768
            elif 'deepseek' in model_id_lower:
                return 64000
            elif 'gemma' in model_id_lower:
                return 8192
            else:
                return 8192  # Conservative default for custom models
        else:
            return 4096  # Default fallback

# Global model manager instance
model_manager = ModelManager()