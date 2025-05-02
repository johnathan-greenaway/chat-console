from openai import AsyncOpenAI
import asyncio
from typing import List, Dict, Any, Optional, Generator, AsyncGenerator
from .base import BaseModelClient
from ..config import OPENAI_API_KEY
import logging

# Set up logging
logger = logging.getLogger(__name__)

class OpenAIClient(BaseModelClient):
    def __init__(self):
        self.client = None  # Initialize in create()
        self._active_stream = None  # Track active stream for cancellation

    @classmethod
    async def create(cls) -> 'OpenAIClient':
        """Create a new instance with async initialization."""
        instance = cls()
        instance.client = AsyncOpenAI(api_key=OPENAI_API_KEY)
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
    
    async def generate_completion(self, messages: List[Dict[str, str]], 
                           model: str, 
                           style: Optional[str] = None, 
                           temperature: float = 0.7, 
                           max_tokens: Optional[int] = None) -> str:
        """Generate a text completion using OpenAI"""
        processed_messages = self._prepare_messages(messages, style)
        
        # Check if this is a reasoning model (o-series)
        is_reasoning_model = model.startswith(("o1", "o3", "o4")) or model in ["o1", "o3", "o4-mini"]
        
        # Use the Responses API for reasoning models
        if is_reasoning_model:
            # Create parameters dict for the Responses API
            params = {
                "model": model,
                "input": processed_messages,
                "reasoning": {"effort": "medium"},  # Default to medium effort
            }
            
            # Only add max_tokens if it's not None
            if max_tokens is not None:
                params["max_output_tokens"] = max_tokens
            
            response = await self.client.responses.create(**params)
            return response.output_text
        else:
            # Use the Chat Completions API for non-reasoning models
            params = {
                "model": model,
                "messages": processed_messages,
                "temperature": temperature,
            }
            
            # Only add max_tokens if it's not None
            if max_tokens is not None:
                params["max_tokens"] = max_tokens
            
            response = await self.client.chat.completions.create(**params)
            return response.choices[0].message.content
    
    async def generate_stream(self, messages: List[Dict[str, str]], 
                            model: str, 
                            style: Optional[str] = None,
                            temperature: float = 0.7, 
                            max_tokens: Optional[int] = None) -> AsyncGenerator[str, None]:
        """Generate a streaming text completion using OpenAI"""
        try:
            from app.main import debug_log  # Import debug logging if available
            debug_log(f"OpenAI: starting streaming generation with model: {model}")
        except ImportError:
            # If debug_log not available, create a no-op function
            debug_log = lambda msg: None
            
        processed_messages = self._prepare_messages(messages, style)
        
        # Check if this is a reasoning model (o-series)
        is_reasoning_model = model.startswith(("o1", "o3", "o4")) or model in ["o1", "o3", "o4-mini"]
        
        try:
            debug_log(f"OpenAI: preparing {len(processed_messages)} messages for stream")
            
            # Safely prepare messages
            try:
                api_messages = []
                for m in processed_messages:
                    if isinstance(m, dict) and "role" in m and "content" in m:
                        api_messages.append({"role": m["role"], "content": m["content"]})
                    else:
                        debug_log(f"OpenAI: skipping invalid message: {m}")
                
                debug_log(f"OpenAI: prepared {len(api_messages)} valid messages")
                
                # Check for empty or very short prompts and enhance them slightly
                # This helps with the "hi" case where OpenAI might not generate a meaningful response
                if api_messages and len(api_messages) > 0:
                    last_message = api_messages[-1]
                    if last_message["role"] == "user" and len(last_message["content"].strip()) <= 3:
                        debug_log(f"OpenAI: Enhancing very short user prompt: '{last_message['content']}'")
                        last_message["content"] = f"{last_message['content']} - Please respond conversationally."
                        debug_log(f"OpenAI: Enhanced to: '{last_message['content']}'")
                
            except Exception as msg_error:
                debug_log(f"OpenAI: error preparing messages: {str(msg_error)}")
                # Fallback to a simpler message format if processing fails
                api_messages = [{"role": "user", "content": "Please respond to my request."}]
            
            debug_log("OpenAI: requesting stream")
            
            # Use more robust error handling with retry for connection issues
            max_retries = 2
            retry_count = 0
            
            while retry_count <= max_retries:
                try:
                    # Create parameters dict based on model type
                    if is_reasoning_model:
                        # Use the Responses API for reasoning models
                        params = {
                            "model": model,
                            "input": api_messages,
                            "reasoning": {"effort": "medium"},  # Default to medium effort
                            "stream": True,
                        }
                        
                        # Only add max_tokens if it's not None
                        if max_tokens is not None:
                            params["max_output_tokens"] = max_tokens
                        
                        debug_log(f"OpenAI: creating reasoning model stream with params: {params}")
                        stream = await self.client.responses.create(**params)
                    else:
                        # Use the Chat Completions API for non-reasoning models
                        params = {
                            "model": model,
                            "messages": api_messages,
                            "temperature": temperature,
                            "stream": True,
                        }
                        
                        # Only add max_tokens if it's not None
                        if max_tokens is not None:
                            params["max_tokens"] = max_tokens
                        
                        debug_log(f"OpenAI: creating chat completion stream with params: {params}")
                        stream = await self.client.chat.completions.create(**params)
                    
                    # Store the stream for potential cancellation
                    self._active_stream = stream
                    
                    debug_log("OpenAI: stream created successfully")
                    
                    # Yield a small padding token at the beginning for very short prompts
                    # This ensures the UI sees immediate content updates
                    if any(m["role"] == "user" and len(m["content"].strip()) <= 3 for m in api_messages):
                        debug_log("OpenAI: Adding initial padding token for short message")
                        yield ""  # Empty string to trigger UI update cycle
                    
                    # Process stream chunks
                    chunk_count = 0
                    debug_log("OpenAI: starting to process chunks")
                    
                    async for chunk in stream:
                        # Check if stream has been cancelled
                        if self._active_stream is None:
                            debug_log("OpenAI: stream was cancelled, stopping generation")
                            break
                            
                        chunk_count += 1
                        try:
                            # Handle different response formats based on model type
                            if is_reasoning_model:
                                # For reasoning models using the Responses API
                                if hasattr(chunk, 'output_text') and chunk.output_text is not None:
                                    text = str(chunk.output_text)
                                    debug_log(f"OpenAI reasoning: yielding chunk {chunk_count} of length: {len(text)}")
                                    yield text
                                else:
                                    debug_log(f"OpenAI reasoning: skipping chunk {chunk_count} with missing content")
                            else:
                                # For regular models using the Chat Completions API
                                if chunk.choices and hasattr(chunk.choices[0], 'delta') and hasattr(chunk.choices[0].delta, 'content'):
                                    content = chunk.choices[0].delta.content
                                    if content is not None:
                                        # Ensure we're returning a string
                                        text = str(content)
                                        debug_log(f"OpenAI: yielding chunk {chunk_count} of length: {len(text)}")
                                        yield text
                                    else:
                                        debug_log(f"OpenAI: skipping None content chunk {chunk_count}")
                                else:
                                    debug_log(f"OpenAI: skipping chunk {chunk_count} with missing content")
                        except Exception as chunk_error:
                            debug_log(f"OpenAI: error processing chunk {chunk_count}: {str(chunk_error)}")
                            # Skip problematic chunks but continue processing
                            continue
                    
                    debug_log(f"OpenAI: stream completed successfully with {chunk_count} chunks")
                    
                    # Clear the active stream reference when done
                    self._active_stream = None
                    
                    # If we reach this point, we've successfully processed the stream
                    break
                    
                except Exception as e:
                    debug_log(f"OpenAI: error in attempt {retry_count+1}/{max_retries+1}: {str(e)}")
                    retry_count += 1
                    if retry_count <= max_retries:
                        debug_log(f"OpenAI: retrying after error (attempt {retry_count+1})")
                        # Simple exponential backoff
                        await asyncio.sleep(1 * retry_count)
                    else:
                        debug_log("OpenAI: max retries reached, raising exception")
                        raise Exception(f"OpenAI streaming error after {max_retries+1} attempts: {str(e)}")
                        
        except Exception as e:
            debug_log(f"OpenAI: error in generate_stream: {str(e)}")
            # Yield a simple error message as a last resort to ensure UI updates
            yield f"Error: {str(e)}"
            raise Exception(f"OpenAI streaming error: {str(e)}")
    
    async def cancel_stream(self) -> None:
        """Cancel any active streaming request"""
        logger.info("Cancelling active OpenAI stream")
        try:
            from app.main import debug_log
            debug_log("OpenAI: cancelling active stream")
        except ImportError:
            pass
            
        # Simply set the active stream to None
        # This will cause the generate_stream method to stop processing chunks
        self._active_stream = None
        logger.info("OpenAI stream cancelled successfully")
    
    async def get_available_models(self) -> List[Dict[str, Any]]:
        """Fetch list of available OpenAI models from the /models endpoint"""
        try:
            models_response = await self.client.models.list()
            # Each model has an 'id' and possibly other metadata
            models = []
            for model in models_response.data:
                # Use 'id' as both id and name for now; can enhance with more info if needed
                models.append({"id": model.id, "name": model.id})
            
            # Add reasoning models which might not be in the models list
            reasoning_models = [
                {"id": "o1", "name": "o1 (Reasoning)"},
                {"id": "o1-mini", "name": "o1-mini (Reasoning)"},
                {"id": "o3", "name": "o3 (Reasoning)"},
                {"id": "o3-mini", "name": "o3-mini (Reasoning)"},
                {"id": "o4-mini", "name": "o4-mini (Reasoning)"}
            ]
            
            # Add reasoning models if they're not already in the list
            existing_ids = {model["id"] for model in models}
            for reasoning_model in reasoning_models:
                if reasoning_model["id"] not in existing_ids:
                    models.append(reasoning_model)
                    
            return models
        except Exception as e:
            # Fallback to a static list if API call fails
            return [
                {"id": "gpt-3.5-turbo", "name": "gpt-3.5-turbo"},
                {"id": "gpt-4", "name": "gpt-4"},
                {"id": "gpt-4-turbo", "name": "gpt-4-turbo"},
                {"id": "o1", "name": "o1 (Reasoning)"},
                {"id": "o1-mini", "name": "o1-mini (Reasoning)"},
                {"id": "o3", "name": "o3 (Reasoning)"},
                {"id": "o3-mini", "name": "o3-mini (Reasoning)"},
                {"id": "o4-mini", "name": "o4-mini (Reasoning)"}
            ]
