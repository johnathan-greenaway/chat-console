import anthropic
import asyncio
import logging
from typing import List, Dict, Any, Optional, Generator, AsyncGenerator
from .base import BaseModelClient
from ..config import ANTHROPIC_API_KEY

# Set up logging
logger = logging.getLogger(__name__)

class AnthropicClient(BaseModelClient):
    def __init__(self):
        self.client = None  # Initialize in create()
        self._active_stream = None  # Track active stream for cancellation

    @classmethod
    async def create(cls) -> 'AnthropicClient':
        """Create a new instance with async initialization."""
        instance = cls()
        instance.client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
        return instance
    
    def _prepare_messages(self, messages: List[Dict[str, str]], style: Optional[str] = None) -> List[Dict[str, str]]:
        """Prepare messages for Anthropic API"""
        processed_messages = []
        
        # Add style instructions if provided
        if style and style != "default":
            style_instructions = self._get_style_instructions(style)
            processed_messages.append({
                "role": "system",
                "content": style_instructions
            })
        
        # Add the rest of the messages
        for message in messages:
            # Ensure message has required fields
            if "role" not in message or "content" not in message:
                continue
                
            # Map 'user' and 'assistant' roles directly
            # Anthropic only supports 'user' and 'assistant' roles
            if message["role"] in ["user", "assistant"]:
                processed_messages.append(message)
            elif message["role"] == "system":
                # For system messages, we need to add them as system messages
                processed_messages.append({
                    "role": "system",
                    "content": message["content"]
                })
            else:
                # For any other role, treat as user message
                processed_messages.append({
                    "role": "user",
                    "content": message["content"]
                })
        
        return processed_messages
    
    def _get_style_instructions(self, style: str) -> str:
        """Get formatting instructions for different styles"""
        styles = {
            "concise": "Please provide concise, to-the-point responses without unnecessary elaboration.",
            "detailed": "Please provide comprehensive responses with thorough explanations and examples.",
            "technical": "Please use precise technical language and focus on accuracy and technical details.",
            "friendly": "Please use a warm, conversational tone and relatable examples.",
        }
        
        return styles.get(style, "")
    
    async def generate_completion(self, messages: List[Dict[str, str]], 
                           model: str, 
                           style: Optional[str] = None, 
                           temperature: float = 0.7, 
                           max_tokens: Optional[int] = None) -> str:
        """Generate a text completion using Anthropic"""
        processed_messages = self._prepare_messages(messages, style)
        
        try:
            response = await self.client.messages.create(
                model=model,
                messages=processed_messages,
                temperature=temperature,
                max_tokens=max_tokens if max_tokens else 4096,
            )
            
            return response.content[0].text
        except Exception as e:
            logger.error(f"Error generating completion: {str(e)}")
            raise Exception(f"Anthropic API error: {str(e)}")
    
    async def generate_stream(self, messages: List[Dict[str, str]], 
                            model: str, 
                            style: Optional[str] = None,
                            temperature: float = 0.7, 
                            max_tokens: Optional[int] = None) -> AsyncGenerator[str, None]:
        """Generate a streaming text completion using Anthropic"""
        try:
            from app.main import debug_log  # Import debug logging if available
            debug_log(f"Anthropic: starting streaming generation with model: {model}")
        except ImportError:
            # If debug_log not available, create a no-op function
            debug_log = lambda msg: None
            
        processed_messages = self._prepare_messages(messages, style)
        
        try:
            debug_log(f"Anthropic: preparing {len(processed_messages)} messages for stream")
            
            # Use more robust error handling with retry for connection issues
            max_retries = 2
            retry_count = 0
            
            while retry_count <= max_retries:
                try:
                    debug_log(f"Anthropic: creating stream with model {model}")
                    
                    # Create the stream
                    stream = await self.client.messages.create(
                        model=model,
                        messages=processed_messages,
                        temperature=temperature,
                        max_tokens=max_tokens if max_tokens else 4096,
                        stream=True
                    )
                    
                    # Store the stream for potential cancellation
                    self._active_stream = stream
                    
                    debug_log("Anthropic: stream created successfully")
                    
                    # Process stream chunks
                    chunk_count = 0
                    debug_log("Anthropic: starting to process chunks")
                    
                    async for chunk in stream:
                        # Check if stream has been cancelled
                        if self._active_stream is None:
                            debug_log("Anthropic: stream was cancelled, stopping generation")
                            break
                            
                        chunk_count += 1
                        try:
                            if hasattr(chunk, 'delta') and hasattr(chunk.delta, 'text'):
                                content = chunk.delta.text
                                if content is not None:
                                    debug_log(f"Anthropic: yielding chunk {chunk_count} of length: {len(content)}")
                                    yield content
                                else:
                                    debug_log(f"Anthropic: skipping None content chunk {chunk_count}")
                            else:
                                debug_log(f"Anthropic: skipping chunk {chunk_count} with missing content")
                        except Exception as chunk_error:
                            debug_log(f"Anthropic: error processing chunk {chunk_count}: {str(chunk_error)}")
                            # Skip problematic chunks but continue processing
                            continue
                    
                    debug_log(f"Anthropic: stream completed successfully with {chunk_count} chunks")
                    
                    # Clear the active stream reference when done
                    self._active_stream = None
                    
                    # If we reach this point, we've successfully processed the stream
                    break
                    
                except Exception as e:
                    debug_log(f"Anthropic: error in attempt {retry_count+1}/{max_retries+1}: {str(e)}")
                    retry_count += 1
                    if retry_count <= max_retries:
                        debug_log(f"Anthropic: retrying after error (attempt {retry_count+1})")
                        # Simple exponential backoff
                        await asyncio.sleep(1 * retry_count)
                    else:
                        debug_log("Anthropic: max retries reached, raising exception")
                        raise Exception(f"Anthropic streaming error after {max_retries+1} attempts: {str(e)}")
                        
        except Exception as e:
            debug_log(f"Anthropic: error in generate_stream: {str(e)}")
            # Yield a simple error message as a last resort to ensure UI updates
            yield f"Error: {str(e)}"
            raise Exception(f"Anthropic streaming error: {str(e)}")
    
    async def cancel_stream(self) -> None:
        """Cancel any active streaming request"""
        logger.info("Cancelling active Anthropic stream")
        try:
            from app.main import debug_log
            debug_log("Anthropic: cancelling active stream")
        except ImportError:
            pass
            
        # Simply set the active stream to None
        # This will cause the generate_stream method to stop processing chunks
        self._active_stream = None
        logger.info("Anthropic stream cancelled successfully")
    
    async def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available Anthropic models"""
        # Anthropic doesn't have a models endpoint, so we return a static list
        models = [
            {
                "id": "claude-3-opus-20240229",
                "name": "Claude 3 Opus",
                "description": "Most powerful model for highly complex tasks",
                "context_window": 200000,
                "provider": "anthropic"
            },
            {
                "id": "claude-3-sonnet-20240229",
                "name": "Claude 3 Sonnet",
                "description": "Balanced model for most tasks",
                "context_window": 200000,
                "provider": "anthropic"
            },
            {
                "id": "claude-3-haiku-20240307",
                "name": "Claude 3 Haiku",
                "description": "Fastest and most compact model",
                "context_window": 200000,
                "provider": "anthropic"
            },
            {
                "id": "claude-3-5-sonnet-20240620",
                "name": "Claude 3.5 Sonnet",
                "description": "Latest model with improved capabilities",
                "context_window": 200000,
                "provider": "anthropic"
            },
            {
                "id": "claude-3-7-sonnet-20250219",
                "name": "Claude 3.7 Sonnet",
                "description": "Newest model with advanced reasoning",
                "context_window": 200000,
                "provider": "anthropic"
            }
        ]
        
        return models
