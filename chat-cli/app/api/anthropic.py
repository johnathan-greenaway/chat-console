import anthropic
import asyncio  # Add missing import
from typing import List, Dict, Any, Optional, Generator, AsyncGenerator
from .base import BaseModelClient
from ..config import ANTHROPIC_API_KEY
from ..utils import resolve_model_id  # Import the resolve_model_id function

class AnthropicClient(BaseModelClient):
    def __init__(self):
        self.client = None  # Initialize in create()

    @classmethod
    async def create(cls) -> 'AnthropicClient':
        """Create a new instance with async initialization."""
        instance = cls()
        instance.client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
        return instance
    
    def _prepare_messages(self, messages: List[Dict[str, str]], style: Optional[str] = None) -> List[Dict[str, str]]:
        """Prepare messages for Claude API"""
        # Anthropic expects role to be 'user' or 'assistant'
        processed_messages = []
        
        for msg in messages:
            role = msg["role"]
            if role == "system":
                # For Claude, we'll convert system messages to user messages with a special prefix
                processed_messages.append({
                    "role": "user",
                    "content": f"<system>\n{msg['content']}\n</system>"
                })
            else:
                processed_messages.append(msg)
        
        # Add style instructions if provided
        if style and style != "default":
            # Find first non-system message to attach style to
            for i, msg in enumerate(processed_messages):
                if msg["role"] == "user":
                    content = msg["content"]
                    if "<userStyle>" not in content:
                        style_instructions = self._get_style_instructions(style)
                        msg["content"] = f"<userStyle>{style_instructions}</userStyle>\n\n{content}"
                    break
        
        return processed_messages
    
    def _get_style_instructions(self, style: str) -> str:
        """Get formatting instructions for different styles"""
        styles = {
            "concise": "Be extremely concise and to the point. Use short sentences and paragraphs. Avoid unnecessary details.",
            "detailed": "Be comprehensive and thorough in your responses. Provide detailed explanations, examples, and cover all relevant aspects of the topic.",
            "technical": "Use precise technical language and terminology. Be formal and focus on accuracy and technical details.",
            "friendly": "Be warm, approachable and conversational. Use casual language, personal examples, and a friendly tone.",
        }
        
        return styles.get(style, "")
    
    async def generate_completion(self, messages: List[Dict[str, str]],
                           model: str,
                           style: Optional[str] = None,
                           temperature: float = 0.7,
                           max_tokens: Optional[int] = None) -> str:
        """Generate a text completion using Claude"""
        try:
            from app.main import debug_log
        except ImportError:
            debug_log = lambda msg: None
            
        # Resolve the model ID right before making the API call
        original_model = model
        resolved_model = resolve_model_id(model)
        debug_log(f"Anthropic: Original model ID '{original_model}' resolved to '{resolved_model}' in generate_completion")
        
        processed_messages = self._prepare_messages(messages, style)
        
        response = await self.client.messages.create(
            model=resolved_model,  # Use the resolved model ID
            messages=processed_messages,
            temperature=temperature,
            max_tokens=max_tokens or 1024,
        )
        
        return response.content[0].text
    
    async def generate_stream(self, messages: List[Dict[str, str]],
                            model: str,
                            style: Optional[str] = None,
                            temperature: float = 0.7,
                            max_tokens: Optional[int] = None) -> AsyncGenerator[str, None]:
        """Generate a streaming text completion using Claude"""
        try:
            from app.main import debug_log  # Import debug logging if available
        except ImportError:
            # If debug_log not available, create a no-op function
            debug_log = lambda msg: None
            
        # Resolve the model ID right before making the API call
        original_model = model
        resolved_model = resolve_model_id(model)
        debug_log(f"Anthropic: Original model ID '{original_model}' resolved to '{resolved_model}'")
        debug_log(f"Anthropic: starting streaming generation with model: {resolved_model}")
            
        processed_messages = self._prepare_messages(messages, style)
        
        try:
            debug_log(f"Anthropic: requesting stream with {len(processed_messages)} messages")
            # Remove await from this line - it returns the context manager, not an awaitable
            stream = self.client.messages.stream(
                model=resolved_model,  # Use the resolved model ID
                messages=processed_messages,
                temperature=temperature,
                max_tokens=max_tokens or 1024,
            )
            
            debug_log("Anthropic: stream created successfully, processing chunks using async with")
            async with stream as stream_context: # Use async with
                async for chunk in stream_context: # Iterate over the context
                    try:
                        if chunk.type == "content_block_delta": # Check for delta type
                            # Ensure we always return a string
                            if chunk.delta.text is None:
                                debug_log("Anthropic: skipping empty text delta chunk")
                                continue
                                
                            text = str(chunk.delta.text) # Get text from delta
                            debug_log(f"Anthropic: yielding chunk of length: {len(text)}")
                            yield text
                        else:
                            debug_log(f"Anthropic: skipping non-content_delta chunk of type: {chunk.type}")
                    except Exception as chunk_error: # Restore the except block for chunk processing
                        debug_log(f"Anthropic: error processing chunk: {str(chunk_error)}")
                        # Skip problematic chunks but continue processing
                        continue # This continue is now correctly inside the loop and except block
                    
        except Exception as e:
            debug_log(f"Anthropic: error in generate_stream: {str(e)}")
            raise Exception(f"Anthropic streaming error: {str(e)}")

    async def _fetch_models_from_api(self) -> List[Dict[str, Any]]:
        """Fetch available models directly from the Anthropic API."""
        try:
            from app.main import debug_log
        except ImportError:
            debug_log = lambda msg: None

        # Always include a reliable fallback list in case API calls fail
        fallback_models = [
            {"id": "claude-3-opus-20240229", "name": "Claude 3 Opus"},
            {"id": "claude-3-sonnet-20240229", "name": "Claude 3 Sonnet"},
            {"id": "claude-3-haiku-20240307", "name": "Claude 3 Haiku"},
            {"id": "claude-3-5-sonnet-20240620", "name": "Claude 3.5 Sonnet"},
            {"id": "claude-3-7-sonnet-20250219", "name": "Claude 3.7 Sonnet"},
        ]

        # If no client is initialized, return fallback immediately
        if not self.client:
            debug_log("Anthropic: No client initialized, using fallback models")
            return fallback_models

        try:
            debug_log("Anthropic: Fetching models from API...")
            
            # Try using the models.list method if available in newer SDK versions
            if hasattr(self.client, 'models') and hasattr(self.client.models, 'list'):
                try:
                    debug_log("Anthropic: Using client.models.list() method")
                    models_response = await self.client.models.list()
                    if hasattr(models_response, 'data') and isinstance(models_response.data, list):
                        formatted_models = [
                            {"id": model.id, "name": getattr(model, "name", model.id)}
                            for model in models_response.data
                        ]
                        debug_log(f"Anthropic: Found {len(formatted_models)} models via SDK")
                        return formatted_models
                except Exception as sdk_err:
                    debug_log(f"Anthropic: Error using models.list(): {str(sdk_err)}")
                    # Continue to next method
            
            # Try direct HTTP request if client exposes the underlying HTTP client
            if hasattr(self.client, '_client') and hasattr(self.client._client, 'get'):
                try:
                    debug_log("Anthropic: Using direct HTTP request to /v1/models")
                    response = await self.client._client.get(
                        "/v1/models",
                        headers={"anthropic-version": "2023-06-01"}
                    )
                    response.raise_for_status()
                    models_data = response.json()
                    
                    if 'data' in models_data and isinstance(models_data['data'], list):
                        formatted_models = [
                            {"id": model.get("id"), "name": model.get("display_name", model.get("id"))}
                            for model in models_data['data']
                            if model.get("id")
                        ]
                        debug_log(f"Anthropic: Found {len(formatted_models)} models via HTTP request")
                        return formatted_models
                    else:
                        debug_log("Anthropic: Unexpected API response format")
                except Exception as http_err:
                    debug_log(f"Anthropic: HTTP request error: {str(http_err)}")
                    # Continue to fallback
            
            # If we reach here, both methods failed
            debug_log("Anthropic: All API methods failed, using fallback models")
            return fallback_models

        except Exception as e:
            debug_log(f"Anthropic: Failed to fetch models from API: {str(e)}")
            debug_log("Anthropic: Using fallback model list")
            return fallback_models

    def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available Claude models by fetching from API."""
        # Reliable fallback list that doesn't depend on async operations
        fallback_models = [
            {"id": "claude-3-opus-20240229", "name": "Claude 3 Opus"},
            {"id": "claude-3-sonnet-20240229", "name": "Claude 3 Sonnet"},
            {"id": "claude-3-haiku-20240307", "name": "Claude 3 Haiku"},
            {"id": "claude-3-5-sonnet-20240620", "name": "Claude 3.5 Sonnet"},
            {"id": "claude-3-7-sonnet-20250219", "name": "Claude 3.7 Sonnet"},
        ]
        
        try:
            # Check if we're already in an event loop
            try:
                loop = asyncio.get_running_loop()
                in_loop = True
            except RuntimeError:
                in_loop = False
                
            if in_loop:
                # We're already in an event loop, create a future
                try:
                    from app.main import debug_log
                except ImportError:
                    debug_log = lambda msg: None
                    
                debug_log("Anthropic: Already in event loop, using fallback models")
                return fallback_models
            else:
                # Not in an event loop, we can use asyncio.run
                models = asyncio.run(self._fetch_models_from_api())
                return models
        except Exception as e:
            try:
                from app.main import debug_log
            except ImportError:
                debug_log = lambda msg: None
                
            debug_log(f"Anthropic: Error in get_available_models: {str(e)}")
            return fallback_models
