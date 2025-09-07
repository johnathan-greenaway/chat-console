from openai import AsyncOpenAI
import asyncio
from typing import List, Dict, Any, Optional, Generator, AsyncGenerator
from .base import BaseModelClient
from ..config import CUSTOM_PROVIDERS
import logging

# Set up logging
logger = logging.getLogger(__name__)

class CustomOpenAIClient(BaseModelClient):
    def __init__(self, provider_name: str):
        self.provider_name = provider_name
        self.client = None  # Initialize in create()
        self._active_stream = None  # Track active stream for cancellation

    @classmethod
    async def create(cls, provider_name: str) -> 'CustomOpenAIClient':
        """Create a new instance with async initialization."""
        instance = cls(provider_name)
        
        # Get provider config
        provider_config = CUSTOM_PROVIDERS.get(provider_name)
        if not provider_config:
            raise ValueError(f"Unknown provider: {provider_name}")
            
        # Initialize OpenAI client with custom base URL
        instance.client = AsyncOpenAI(
            api_key=provider_config["api_key"],
            base_url=provider_config["base_url"]
        )
        return instance
    
    def _prepare_messages(self, messages: List[Dict[str, str]], style: Optional[str] = None) -> List[Dict[str, str]]:
        """Prepare messages for OpenAI API"""
        processed_messages = messages.copy()
        
        # Add style instructions if provided
        if style and style != "default":
            style_instructions = self._get_style_instructions(style)
            processed_messages.insert(0, {
                "role": "system",
                "content": style_instructions
            })
        
        return processed_messages
    
    def _get_style_instructions(self, style: str) -> str:
        """Get formatting instructions for different styles"""
        styles = {
            "concise": "You are a concise assistant. Provide brief, to-the-point responses without unnecessary elaboration.",
            "detailed": "You are a detailed assistant. Provide comprehensive responses with thorough explanations and examples.",
            "technical": "You are a technical assistant. Use precise technical language and focus on accuracy and technical details.",
            "friendly": "You are a friendly assistant. Use a warm, conversational tone and relatable examples.",
        }
        
        return styles.get(style, "")
    
    async def list_models(self) -> List[Dict[str, Any]]:
        """Fetch available models from custom API"""
        try:
            models_response = await self.client.models.list()
            
            # Known decommissioned models to filter out
            decommissioned_models = {
                'gemma-7b-it',  # Decommissioned by Groq - causes 400 errors
            }
            
            # Return all models from the custom provider, excluding decommissioned ones
            models = []
            for model in models_response.data:
                if model.id not in decommissioned_models:
                    models.append({
                        'id': model.id,
                        'name': self._generate_display_name(model.id),
                        'created': getattr(model, 'created', 0),
                        'owned_by': getattr(model, 'owned_by', self.provider_name)
                    })
            
            # Add OpenAI-compatible models that work via mapping but aren't in /models
            if self.provider_name == "openai-compatible":
                openai_compatible_models = [
                    {
                        'id': 'gpt-4o',
                        'name': 'GPT-4o (OpenAI Compatible)',
                        'created': 0,
                        'owned_by': 'openai-compatible'
                    },
                    {
                        'id': 'gpt-4',
                        'name': 'GPT-4 (OpenAI Compatible)', 
                        'created': 0,
                        'owned_by': 'openai-compatible'
                    },
                    {
                        'id': 'gpt-3.5-turbo',
                        'name': 'GPT-3.5 Turbo (OpenAI Compatible)',
                        'created': 0,
                        'owned_by': 'openai-compatible'
                    }
                ]
                models.extend(openai_compatible_models)
            
            # Sort by name
            models.sort(key=lambda x: x['name'])
            
            return models
            
        except Exception as e:
            logger.error(f"Failed to fetch {self.provider_name} models: {e}")
            # Return fallback list based on provider
            return self._get_fallback_models()
    
    def _generate_display_name(self, model_id: str) -> str:
        """Generate a user-friendly display name from model ID"""
        # Custom mappings for known models
        display_names = {
            'qwen/qwen3-32b': 'Qwen 3 32B (Reasoning & Code)',
            'qwen2.5-coder-32b-instruct': 'Qwen 2.5 Coder 32B',
            'qwen-2.5-coder-14b-instruct': 'Qwen 2.5 Coder 14B',
            'qwen-2.5-coder-7b-instruct': 'Qwen 2.5 Coder 7B',
            'llama-3.3-70b-versatile': 'Llama 3.3 70B Versatile',
            'llama-3.2-90b-vision-preview': 'Llama 3.2 90B Vision',
            'llama3-groq-70b-8192-tool-use-preview': 'Llama 3 70B Tool Use',
            'llama-3.1-8b-instant': 'Llama 3.1 8B Instant',
            'mixtral-8x7b-32768': 'Mixtral 8x7B',
            'deepseek-r1-lite-preview': 'DeepSeek R1 Lite (Reasoning)',
        }
        
        if model_id in display_names:
            return display_names[model_id]
        
        # Generate display name from ID
        name = model_id.replace('-', ' ').replace('_', ' ').title()
        
        # Add special tags for certain model types
        if any(p in model_id.lower() for p in ['coder', 'code']):
            if 'Code' not in name:
                name += ' (Code)'
        elif any(p in model_id.lower() for p in ['vision']):
            if 'Vision' not in name:
                name += ' (Vision)'
        elif any(p in model_id.lower() for p in ['reasoning', 'r1']):
            if 'Reasoning' not in name:
                name += ' (Reasoning)'
        elif any(p in model_id.lower() for p in ['tool-use', 'tool_use']):
            if 'Tool' not in name:
                name += ' (Tool Use)'
                
        return name
    
    def _get_fallback_models(self) -> List[Dict[str, Any]]:
        """Return fallback models when API fetch fails"""
        # For OpenAI-compatible providers, use the default model set
        if self.provider_name == "openai-compatible":
            fallback_models = [
                'qwen/qwen3-32b',
                'qwen2.5-coder-32b-instruct',
                'qwen-2.5-coder-14b-instruct',
                'qwen-2.5-coder-7b-instruct',
                'llama-3.3-70b-versatile',
                'llama-3.2-90b-vision-preview',
                'llama3-groq-70b-8192-tool-use-preview',
                'llama-3.1-8b-instant',
                'mixtral-8x7b-32768',
                'deepseek-r1-lite-preview'
            ]
        else:
            fallback_models = []
            
        return [
            {
                'id': model_id,
                'name': self._generate_display_name(model_id),
                'created': 0,
                'owned_by': self.provider_name
            } for model_id in fallback_models
        ]
    
    async def generate_completion(self, messages: List[Dict[str, str]], 
                           model: str, 
                           style: Optional[str] = None, 
                           temperature: float = 0.7, 
                           max_tokens: Optional[int] = None) -> str:
        """Generate a text completion using custom OpenAI-compatible API"""
        processed_messages = self._prepare_messages(messages, style)
        
        # Check if this is a reasoning model
        is_reasoning_model = any(pattern in model.lower() for pattern in 
                                ["qwen3", "deepseek-r1", "reasoning"])
        
        # Use the Chat Completions API (most custom providers use this)
        params = {
            "model": model,
            "messages": processed_messages,
            "temperature": temperature,
        }
        
        # Only add max_tokens if it's not None
        if max_tokens is not None:
            params["max_tokens"] = max_tokens
        
        # Add reasoning parameters for reasoning models if supported
        if is_reasoning_model and self.provider_name == "openai-compatible":
            params["reasoning_effort"] = "medium"
        
        response = await self.client.chat.completions.create(**params)
        return response.choices[0].message.content
    
    async def generate_stream(self, messages: List[Dict[str, str]], 
                            model: str, 
                            style: Optional[str] = None,
                            temperature: float = 0.7, 
                            max_tokens: Optional[int] = None) -> AsyncGenerator[str, None]:
        """Generate a streaming text completion using custom OpenAI-compatible API"""
        try:
            from app.main import debug_log  # Import debug logging if available
            debug_log(f"{self.provider_name}: starting streaming generation with model: {model}")
        except ImportError:
            # If debug_log not available, create a no-op function
            debug_log = lambda msg: None
            
        processed_messages = self._prepare_messages(messages, style)
        
        try:
            debug_log(f"{self.provider_name}: preparing {len(processed_messages)} messages for stream")
            
            # Safely prepare messages
            try:
                api_messages = []
                for m in processed_messages:
                    if isinstance(m, dict) and "role" in m and "content" in m:
                        # Sanitize content to remove control characters
                        content = m["content"]
                        if isinstance(content, str):
                            # Remove control characters except for tab, newline, and carriage return
                            import re
                            content = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', content)
                        api_messages.append({"role": m["role"], "content": content})
                    else:
                        debug_log(f"{self.provider_name}: skipping invalid message: {m}")
                
                debug_log(f"{self.provider_name}: prepared {len(api_messages)} valid messages")
                
            except Exception as msg_error:
                debug_log(f"{self.provider_name}: error preparing messages: {str(msg_error)}")
                # Fallback to a simpler message format if processing fails
                api_messages = [{"role": "user", "content": "Please respond to my request."}]
            
            debug_log(f"{self.provider_name}: requesting stream")
            
            # Use more robust error handling with retry for connection issues
            max_retries = 3
            retry_count = 0
            
            while retry_count <= max_retries:
                try:
                    # Create parameters dict
                    params = {
                        "model": model,
                        "messages": api_messages,
                        "temperature": temperature,
                        "stream": True,
                    }
                    
                    # Only add max_tokens if it's not None
                    if max_tokens is not None:
                        params["max_tokens"] = max_tokens
                    
                    # Add reasoning parameters for reasoning models if supported
                    is_reasoning_model = any(pattern in model.lower() for pattern in 
                                            ["qwen3", "deepseek-r1", "reasoning"])
                    if is_reasoning_model and self.provider_name == "openai-compatible":
                        params["reasoning_effort"] = "medium"
                    
                    debug_log(f"{self.provider_name}: creating stream with params: {params}")
                    stream = await self.client.chat.completions.create(**params)
                    
                    # Store the stream for potential cancellation
                    self._active_stream = stream
                    
                    debug_log(f"{self.provider_name}: stream created successfully")
                    
                    # Process stream chunks
                    chunk_count = 0
                    debug_log(f"{self.provider_name}: starting to process chunks")
                    
                    async for chunk in stream:
                        # Check if stream has been cancelled
                        if self._active_stream is None:
                            debug_log(f"{self.provider_name}: stream was cancelled, stopping generation")
                            break
                            
                        chunk_count += 1
                        try:
                            # Handle standard OpenAI-compatible response format
                            if chunk.choices and hasattr(chunk.choices[0], 'delta') and hasattr(chunk.choices[0].delta, 'content'):
                                content = chunk.choices[0].delta.content
                                if content is not None:
                                    # Ensure we're returning a string
                                    text = str(content)
                                    debug_log(f"{self.provider_name}: yielding chunk {chunk_count} of length: {len(text)}")
                                    yield text
                                else:
                                    debug_log(f"{self.provider_name}: skipping None content chunk {chunk_count}")
                            else:
                                debug_log(f"{self.provider_name}: skipping chunk {chunk_count} with missing content")
                        except Exception as chunk_error:
                            debug_log(f"{self.provider_name}: error processing chunk {chunk_count}: {str(chunk_error)}")
                            # Skip problematic chunks but continue processing
                            continue
                    
                    debug_log(f"{self.provider_name}: stream completed successfully with {chunk_count} chunks")
                    
                    # Clear the active stream reference when done
                    self._active_stream = None
                    
                    # If we reach this point, we've successfully processed the stream
                    break
                    
                except Exception as e:
                    error_str = str(e)
                    debug_log(f"{self.provider_name}: error in attempt {retry_count+1}/{max_retries+1}: {error_str}")
                    
                    # Check for decommissioned model errors - don't retry these
                    if "decommissioned" in error_str.lower() or "no longer supported" in error_str.lower():
                        debug_log(f"{self.provider_name}: model decommissioned error, not retrying")
                        raise Exception(f"Model '{model}' has been decommissioned and is no longer available. Please select a different model.")
                    
                    retry_count += 1
                    if retry_count <= max_retries:
                        debug_log(f"{self.provider_name}: retrying after error (attempt {retry_count+1})")
                        # Simple exponential backoff
                        await asyncio.sleep(1 * retry_count)
                    else:
                        debug_log(f"{self.provider_name}: max retries reached, raising exception")
                        raise Exception(f"{self.provider_name} streaming error after {max_retries+1} attempts: {error_str}")
                        
        except Exception as e:
            debug_log(f"{self.provider_name}: error in generate_stream: {str(e)}")
            # Yield a simple error message as a last resort to ensure UI updates
            yield f"Error: {str(e)}"
            raise Exception(f"{self.provider_name} streaming error: {str(e)}")
    
    async def cancel_stream(self) -> None:
        """Cancel any active streaming request"""
        logger.info(f"Cancelling active {self.provider_name} stream")
        try:
            from app.main import debug_log
            debug_log(f"{self.provider_name}: cancelling active stream")
        except ImportError:
            pass
            
        # Simply set the active stream to None
        # This will cause the generate_stream method to stop processing chunks
        self._active_stream = None
        logger.info(f"{self.provider_name} stream cancelled successfully")
    
    async def get_available_models(self) -> List[Dict[str, Any]]:
        """Fetch list of available models from the custom provider"""
        return await self.list_models()