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

        try:
            debug_log("Anthropic: Fetching models from API...")
            # The Anthropic Python SDK might not have a direct high-level method for listing models yet.
            # We might need to use the underlying HTTP client or make a direct request.
            # Let's assume for now the SDK client *does* have a way, like self.client.models.list()
            # If this fails, we'd need to implement a direct HTTP GET request.
            # response = await self.client.models.list() # Hypothetical SDK method

            # --- Alternative: Direct HTTP Request using httpx (if client exposes it) ---
            # Check if the client has an internal http_client we can use
            if hasattr(self.client, '_client') and hasattr(self.client._client, 'get'):
                 response = await self.client._client.get(
                     "/v1/models",
                     headers={"anthropic-version": "2023-06-01"} # Add required version header
                 )
                 response.raise_for_status() # Raise HTTP errors
                 models_data = response.json()
                 debug_log(f"Anthropic: API response received: {models_data}")
                 if 'data' in models_data and isinstance(models_data['data'], list):
                      # Format the response as expected: list of {"id": ..., "name": ...}
                      formatted_models = [
                          {"id": model.get("id"), "name": model.get("display_name", model.get("id"))}
                          for model in models_data['data']
                          if model.get("id") # Ensure model has an ID
                      ]
                      # Log each model ID clearly for debugging
                      debug_log(f"Anthropic: Available models from API:")
                      for model in formatted_models:
                          debug_log(f"  - ID: {model.get('id')}, Name: {model.get('name')}")
                      return formatted_models
                 else:
                      debug_log("Anthropic: Unexpected API response format for models.")
                      return []
            else:
                 debug_log("Anthropic: Client does not expose HTTP client for model listing. Returning empty list.")
                 return [] # Cannot fetch dynamically

        except Exception as e:
            debug_log(f"Anthropic: Failed to fetch models from API: {str(e)}")
            # Fallback to a minimal hardcoded list in case of API error
            # Include Claude 3.7 Sonnet with the correct full ID
            fallback_models = [
                {"id": "claude-3-opus-20240229", "name": "Claude 3 Opus"},
                {"id": "claude-3-sonnet-20240229", "name": "Claude 3 Sonnet"},
                {"id": "claude-3-haiku-20240307", "name": "Claude 3 Haiku"},
                {"id": "claude-3-5-sonnet-20240620", "name": "Claude 3.5 Sonnet"},
                {"id": "claude-3-7-sonnet-20250219", "name": "Claude 3.7 Sonnet"},  # Add Claude 3.7 Sonnet
            ]
            debug_log("Anthropic: Using fallback model list:")
            for model in fallback_models:
                debug_log(f"  - ID: {model['id']}, Name: {model['name']}")
            return fallback_models

    # Keep this synchronous for now, but make it call the async fetcher
    # Note: This is slightly awkward. Ideally, config loading would be async.
    # For now, we'll run the async fetcher within the sync method using asyncio.run()
    # This is NOT ideal for performance but avoids larger refactoring of config loading.
    def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available Claude models by fetching from API."""
        try:
            # Run the async fetcher method synchronously
            models = asyncio.run(self._fetch_models_from_api())
            return models
        except RuntimeError as e:
             # Handle cases where asyncio.run can't be called (e.g., already in an event loop)
             # This might happen during app runtime if called again. Fallback needed.
             try:
                 from app.main import debug_log
             except ImportError:
                 debug_log = lambda msg: None
             debug_log(f"Anthropic: Cannot run async model fetch synchronously ({e}). Falling back to hardcoded list.")
             # Use the same fallback list as in _fetch_models_from_api
             fallback_models = [
                 {"id": "claude-3-opus-20240229", "name": "Claude 3 Opus"},
                 {"id": "claude-3-sonnet-20240229", "name": "Claude 3 Sonnet"},
                 {"id": "claude-3-haiku-20240307", "name": "Claude 3 Haiku"},
                 {"id": "claude-3-5-sonnet-20240620", "name": "Claude 3.5 Sonnet"},
                 {"id": "claude-3-7-sonnet-20250219", "name": "Claude 3.7 Sonnet"},  # Add Claude 3.7 Sonnet
             ]
             debug_log("Anthropic: Using fallback model list in get_available_models:")
             for model in fallback_models:
                 debug_log(f"  - ID: {model['id']}, Name: {model['name']}")
             return fallback_models
