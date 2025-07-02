import aiohttp
import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Generator, AsyncGenerator
from .base import BaseModelClient

# Set up logging
logger = logging.getLogger(__name__)

# Custom exception for Ollama API errors
class OllamaApiError(Exception):
    """Exception raised for errors in the Ollama API."""
    def __init__(self, message: str, status_code: Optional[int] = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

class OllamaClient(BaseModelClient):
    def __init__(self):
        from ..config import OLLAMA_BASE_URL
        self.base_url = OLLAMA_BASE_URL.rstrip('/')
        logger.info(f"Initializing Ollama client with base URL: {self.base_url}")
        
        # Track active stream session
        self._active_stream_session = None
        
        # Track model loading state
        self._model_loading = False
        
        # Track preloaded models and their last use timestamp
        self._preloaded_models = {}
        
        # Default timeout values (in seconds)
        self.DEFAULT_TIMEOUT = 30
        self.MODEL_LOAD_TIMEOUT = 120
        self.MODEL_PULL_TIMEOUT = 3600  # 1 hour for large models
        
        # Path to the cached models file
        self.models_cache_path = Path(__file__).parent.parent / "data" / "ollama-models.json"
        
    def get_timeout_for_model(self, model_id: str, operation: str = "generate") -> int:
        """
        Calculate an appropriate timeout based on model size
        
        Parameters:
        - model_id: The model identifier
        - operation: The operation type ('generate', 'load', 'pull')
        
        Returns:
        - Timeout in seconds
        """
        # Default timeouts by operation
        default_timeouts = {
            "generate": self.DEFAULT_TIMEOUT,      # 30s
            "load": self.MODEL_LOAD_TIMEOUT,       # 2min 
            "pull": self.MODEL_PULL_TIMEOUT,       # 1h
            "list": 5,                             # 5s
            "test": 2                              # 2s
        }
        
        # Parameter size multipliers
        size_multipliers = {
            # For models < 3B
            "1b": 0.5,
            "2b": 0.7,
            "3b": 1.0,
            # For models 3B-10B
            "5b": 1.2,
            "6b": 1.3,
            "7b": 1.5,
            "8b": 1.7,
            "9b": 1.8,
            # For models 10B-20B
            "13b": 2.0,
            "14b": 2.0,
            # For models 20B-50B
            "27b": 3.0,
            "34b": 3.5,
            "40b": 4.0,
            # For models 50B+
            "70b": 5.0,
            "80b": 6.0,
            "100b": 7.0,
            "400b": 10.0,
            "405b": 10.0,
        }
        
        # Get the base timeout for the operation
        base_timeout = default_timeouts.get(operation, self.DEFAULT_TIMEOUT)
        
        # Try to determine the model size from the model ID
        model_size = "7b"  # Default assumption is 7B parameters
        model_lower = model_id.lower()
        
        # Check for size indicators in the model name
        for size in size_multipliers.keys():
            if size in model_lower:
                model_size = size
                break
                
        # If it's a known large model without size in name
        if "llama3.1" in model_lower and not any(size in model_lower for size in size_multipliers.keys()):
            model_size = "8b"  # Default for llama3.1 without size specified
            
        # For first generation after model selection, if preloaded, use shorter timeout
        if operation == "generate" and model_id in self._preloaded_models:
            # For preloaded models, use a shorter timeout
            return max(int(base_timeout * 0.7), 20)  # Min 20 seconds
        
        # Calculate final timeout with multiplier
        multiplier = size_multipliers.get(model_size, 1.0)
        timeout = int(base_timeout * multiplier)
        
        # For pull operation, ensure we have a reasonable maximum
        if operation == "pull":
            return min(timeout, 7200)  # Max 2 hours
            
        logger.info(f"Calculated timeout for {model_id} ({operation}): {timeout}s (base: {base_timeout}s, multiplier: {multiplier})")
        return timeout

    @classmethod
    async def create(cls) -> 'OllamaClient':
        """Factory method to create and initialize an OllamaClient instance"""
        from ..utils import ensure_ollama_running
        client = cls()
        
        # Try to start Ollama if not running
        if not await ensure_ollama_running():
            raise Exception(f"Failed to start Ollama server. Please ensure Ollama is installed and try again.")
            
        return client
        
    def _prepare_messages(self, messages: List[Dict[str, str]], style: Optional[str] = None) -> str:
        """Convert chat messages to Ollama format"""
        try:
            from app.main import debug_log  # Import debug logging
            debug_log(f"_prepare_messages called with {len(messages)} messages and style: {style}")
        except ImportError:
            # If debug_log not available, create a no-op function
            debug_log = lambda msg: None
        
        # Start with any style instructions
        formatted_messages = []
        if style and style != "default":
            style_instructions = self._get_style_instructions(style)
            debug_log(f"Adding style instructions: {style_instructions[:50]}...")
            formatted_messages.append(style_instructions)
            
        # Special case for title generation - check if this is a title generation message
        is_title_generation = False
        for msg in messages:
            if msg.get("role") == "system" and "generate a brief, descriptive title" in msg.get("content", "").lower():
                is_title_generation = True
                debug_log("Detected title generation prompt")
                break
        
        # For title generation, use a direct approach
        if is_title_generation:
            debug_log("Using specialized formatting for title generation")
            # Find the user message containing the input for title generation
            user_msg = next((msg for msg in messages if msg.get("role") == "user"), None)
            if user_msg and "content" in user_msg:
                # Create a direct prompt
                prompt = "You must generate a short, descriptive title (maximum 40 characters) for this conversation. ONLY output the title with no additional text, no quotes, and no explanation. Do not start with phrases like 'Here's a title' or 'Title:'. RESPOND ONLY WITH THE TITLE TEXT for the following message:\n\n" + user_msg["content"]
                debug_log(f"Created title generation prompt: {prompt[:100]}...")
                return prompt
            else:
                debug_log("Could not find user message for title generation, using standard formatting")
        
        # Standard processing for normal chat messages
        # Add message content, preserving conversation flow
        for i, msg in enumerate(messages):
            try:
                debug_log(f"Processing message {i}: role={msg.get('role', 'unknown')}, content length={len(msg.get('content', ''))}")
                
                # Safely extract content with fallback
                if "content" in msg and msg["content"] is not None:
                    content = msg["content"]
                    formatted_messages.append(content)
                else:
                    debug_log(f"Message {i} has no valid content key, using fallback")
                    # Try to get content from alternative sources
                    if isinstance(msg, dict):
                        # Try to convert the whole message to string as last resort
                        content = str(msg)
                        debug_log(f"Using fallback content: {content[:50]}...")
                        formatted_messages.append(content)
                    else:
                        debug_log(f"Message {i} is not a dict, skipping")
                
            except KeyError as e:
                debug_log(f"KeyError processing message {i}: {e}, message: {msg}")
                # Handle missing key more gracefully
                content = msg.get('content', '')
                if content:
                    formatted_messages.append(content)
                else:
                    debug_log(f"Warning: Message {i} has no content, skipping")
            except Exception as e:
                debug_log(f"Error processing message {i}: {e}")
                # Continue processing other messages
                continue
        
        # Defensive check to ensure we have something to return
        if not formatted_messages:
            debug_log("Warning: No formatted messages were created, using fallback")
            formatted_messages = ["Please provide some input for the model to respond to."]
        
        # Join with double newlines for better readability
        result = "\n\n".join(formatted_messages)
        debug_log(f"Final formatted prompt length: {len(result)}")
        return result
    
    def _get_style_instructions(self, style: str) -> str:
        """Get formatting instructions for different styles"""
        styles = {
            "concise": "Be extremely concise and to the point. Use short sentences and avoid unnecessary details.",
            "detailed": "Be comprehensive and thorough. Provide detailed explanations and examples.",
            "technical": "Use precise technical language and terminology. Focus on accuracy and technical details.",
            "friendly": "Be warm and conversational. Use casual language and a friendly tone.",
        }
        
        return styles.get(style, "")
    
    async def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available Ollama models"""
        logger.info("Fetching available Ollama models...")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/api/tags",
                    timeout=5,
                    headers={"Accept": "application/json"}
                ) as response:
                    response.raise_for_status()
                    data = await response.json()
                    logger.debug(f"Ollama API response: {data}")
                    
                    if not isinstance(data, dict):
                        logger.error("Invalid response format: expected object")
                        raise Exception("Invalid response format: expected object")
                    if "models" not in data:
                        logger.error("Invalid response format: missing 'models' key")
                        raise Exception("Invalid response format: missing 'models' key")
                    if not isinstance(data["models"], list):
                        logger.error("Invalid response format: 'models' is not an array")
                        raise Exception("Invalid response format: 'models' is not an array")
                    
                    models = []
                    for model in data["models"]:
                        if not isinstance(model, dict) or "name" not in model:
                            continue  # Skip invalid models
                        models.append({
                            "id": model["name"],
                            "name": model["name"].title(),
                            "tags": model.get("tags", [])
                        })
                    
                    logger.info(f"Found {len(models)} Ollama models")
                    return models
                    
        except aiohttp.ClientConnectorError:
            error_msg = f"Could not connect to Ollama server at {self.base_url}. Please ensure Ollama is running and the URL is correct."
            logger.error(error_msg)
            raise Exception(error_msg)
        except aiohttp.ClientTimeout:
            error_msg = f"Connection to Ollama server at {self.base_url} timed out after 5 seconds. The server might be busy or unresponsive."
            logger.error(error_msg)
            raise Exception(error_msg)
        except aiohttp.ClientError as e:
            error_msg = f"Ollama API error: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error getting models: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
            
    async def generate_completion(self, messages: List[Dict[str, str]],
                                model: str,
                                style: Optional[str] = None,
                                temperature: float = 0.7,
                                max_tokens: Optional[int] = None) -> str:
        """Generate a text completion using Ollama"""
        logger.info(f"Generating completion with model: {model}")
        prompt = self._prepare_messages(messages, style)
        retries = 2
        last_error = None
        
        while retries >= 0:
            try:
                async with aiohttp.ClientSession() as session:
                    logger.debug(f"Sending request to {self.base_url}/api/generate")
                    gen_timeout = self.get_timeout_for_model(model, "generate")
                    async with session.post(
                        f"{self.base_url}/api/generate",
                        json={
                            "model": model,
                            "prompt": prompt,
                            "temperature": temperature,
                            "stream": False
                        },
                        timeout=gen_timeout
                    ) as response:
                        response.raise_for_status()
                        data = await response.json()
                        if "response" not in data:
                            raise Exception("Invalid response format from Ollama server")
                            
                        # Update the model usage timestamp to keep it hot
                        self.update_model_usage(model)
                        
                        return data["response"]
                        
            except aiohttp.ClientConnectorError:
                last_error = "Could not connect to Ollama server. Make sure Ollama is running and accessible at " + self.base_url
            except aiohttp.ClientResponseError as e:
                last_error = f"Ollama API error: {e.status} - {e.message}"
            except aiohttp.ClientTimeout:
                last_error = "Request to Ollama server timed out"
            except json.JSONDecodeError:
                last_error = "Invalid JSON response from Ollama server"
            except Exception as e:
                last_error = f"Error generating completion: {str(e)}"
            
            logger.error(f"Attempt failed: {last_error}")
            retries -= 1
            if retries >= 0:
                logger.info(f"Retrying... {retries} attempts remaining")
                await asyncio.sleep(1)
                
        raise Exception(last_error)
    
    async def generate_stream(self, messages: List[Dict[str, str]],
                            model: str,
                            style: Optional[str] = None,
                            temperature: float = 0.7,
                            max_tokens: Optional[int] = None) -> AsyncGenerator[str, None]:
        """Generate a streaming text completion using Ollama"""
        logger.info(f"Starting streaming generation with model: {model}")
        try:
            from app.main import debug_log  # Import debug logging if available
            debug_log(f"Starting streaming generation with model: {model}")
        except ImportError:
            # If debug_log not available, create a no-op function
            debug_log = lambda msg: None
            
        debug_log(f"generate_stream called with model: {model}, {len(messages)} messages")
        
        # At the beginning of the method, check messages format
        if not messages:
            debug_log("Error: messages is empty")
            raise ValueError("Messages list is empty")
        
        for i, msg in enumerate(messages):
            try:
                if not isinstance(msg, dict):
                    debug_log(f"Error: message {i} is not a dict: {type(msg)}")
                    raise ValueError(f"Message {i} is not a dictionary")
                if 'role' not in msg:
                    debug_log(f"Error: message {i} missing 'role' key, using default")
                    msg['role'] = 'user'
                if 'content' not in msg:
                    debug_log(f"Error: message {i} missing 'content' key, using default")
                    msg['content'] = ''
            except Exception as e:
                debug_log(f"Error validating message {i}: {str(e)}")
        
        # Now prepare the messages with our robust _prepare_messages method
        try:
            debug_log("Calling _prepare_messages to format prompt")
            prompt = self._prepare_messages(messages, style)
            debug_log(f"Prompt prepared, length: {len(prompt)}")
        except Exception as prep_error:
            debug_log(f"Error preparing messages: {str(prep_error)}")
            # Create a simple fallback prompt
            if len(messages) > 0 and isinstance(messages[-1], dict) and 'content' in messages[-1]:
                prompt = messages[-1]['content']
                debug_log(f"Using last message content as fallback prompt: {prompt[:100]}...")
            else:
                prompt = "Please respond to the user's query."
                debug_log("Using generic fallback prompt")
                
        retries = 2
        last_error = None
        self._active_stream_session = None  # Track the active session
        
        # First check if the model exists in our available models
        try:
            available_models = await self.get_available_models()
            model_exists = False
            available_model_names = []
            
            for m in available_models:
                model_id = m.get("id", "")
                available_model_names.append(model_id)
                if model_id == model:
                    model_exists = True
                    break
                    
            if not model_exists:
                error_msg = f"Model '{model}' not found in available models. Available models include: {', '.join(available_model_names[:5])}"
                if len(available_model_names) > 5:
                    error_msg += f" and {len(available_model_names) - 5} more."
                logger.error(error_msg)
                # Instead of raising a custom error, yield the message and return
                yield error_msg
                return
        except Exception as e:
            debug_log(f"Error checking model availability: {str(e)}")
            # Continue anyway, the main request will handle errors
        
        while retries >= 0:
            try:
                # First try a quick test request to check if model is loaded
                async with aiohttp.ClientSession() as session:
                    try:
                        logger.info("Testing model availability...")
                        debug_log("Testing model availability...")
                        # Build test payload with careful error handling
                        try:
                            test_payload = {
                                "model": str(model) if model is not None else "gemma:2b",
                                "prompt": "test",
                                "temperature": float(temperature) if temperature is not None else 0.7,
                                "stream": False
                            }
                            debug_log(f"Prepared test payload: {test_payload}")
                        except Exception as payload_error:
                            debug_log(f"Error preparing test payload: {str(payload_error)}, using defaults")
                            test_payload = {
                                "model": "gemma:2b",  # Safe default
                                "prompt": "test",
                                "temperature": 0.7,
                                "stream": False
                            }
                            
                        test_timeout = self.get_timeout_for_model(model, "test")
                        async with session.post(
                            f"{self.base_url}/api/generate",
                            json=test_payload,
                            timeout=test_timeout
                        ) as response:
                            if response.status != 200:
                                logger.warning(f"Model test request failed with status {response.status}")
                                debug_log(f"Model test request failed with status {response.status}")
                                
                                # Check if this is a 404 Not Found error
                                if response.status == 404:
                                    error_text = await response.text()
                                    debug_log(f"404 error details: {error_text}")
                                    error_msg = f"Error: Model '{model}' not found on the Ollama server. Please check if the model name is correct or try pulling it first."
                                    logger.error(error_msg)
                                    # Instead of raising, yield the error message for user display
                                    yield error_msg
                                    return  # End the generation
                                    
                                raise aiohttp.ClientError("Model not ready")
                    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                        logger.info(f"Model cold start detected: {str(e)}")
                        debug_log(f"Model cold start detected: {str(e)}")
                        # Set model loading flag
                        self._model_loading = True
                        logger.info("Setting model_loading state to True")
                        debug_log("Setting model_loading state to True")
                        
                        # Model might need loading, try pulling it
                        # Prepare pull payload safely
                        try:
                            pull_payload = {"name": str(model) if model is not None else "gemma:2b"}
                            debug_log(f"Prepared pull payload: {pull_payload}")
                        except Exception as pull_err:
                            debug_log(f"Error preparing pull payload: {str(pull_err)}, using default")
                            pull_payload = {"name": "gemma:2b"}  # Safe default
                            
                        pull_timeout = self.get_timeout_for_model(model, "pull")
                        async with session.post(
                            f"{self.base_url}/api/pull",
                            json=pull_payload,
                            timeout=pull_timeout
                        ) as pull_response:
                            if pull_response.status != 200:
                                logger.error("Failed to pull model")
                                debug_log("Failed to pull model")
                                self._model_loading = False  # Reset flag on failure
                                
                                # Check if this is a 404 Not Found error
                                if response.status == 404:
                                    error_text = await response.text()
                                    debug_log(f"404 error details: {error_text}")
                                    # This is likely a model not found in registry
                                    error_msg = f"Error: Model '{model}' not found in the Ollama registry. Please check if the model name is correct or try a different model."
                                    logger.error(error_msg)
                                    # Instead of raising a custom error, yield the message and return
                                    yield error_msg
                                    return
                                    
                                raise Exception("Failed to pull model")
                            logger.info("Model pulled successfully")
                            debug_log("Model pulled successfully")
                            self._model_loading = False  # Reset flag after successful pull
                
                # Now proceed with actual generation
                session = aiohttp.ClientSession()
                self._active_stream_session = session  # Store reference to active session
                
                try:
                    logger.debug(f"Sending streaming request to {self.base_url}/api/generate")
                    debug_log(f"Sending streaming request to {self.base_url}/api/generate with model: {model}")
                    debug_log(f"Request payload: model={model}, prompt_length={len(prompt) if prompt else 0}, temperature={temperature}")
                    
                    # Build request payload with careful error handling
                    try:
                        request_payload = {
                            "model": str(model) if model is not None else "gemma:2b",  # Default if model is None
                            "prompt": str(prompt) if prompt is not None else "Please respond to the user's query.",
                            "temperature": float(temperature) if temperature is not None else 0.7,
                            "stream": True
                        }
                        debug_log(f"Prepared request payload successfully")
                    except Exception as payload_error:
                        debug_log(f"Error preparing payload: {str(payload_error)}, using defaults")
                        request_payload = {
                            "model": "gemma:2b",  # Safe default
                            "prompt": "Please respond to the user's query.",
                            "temperature": 0.7,
                            "stream": True
                        }
                    
                    debug_log(f"Sending request to Ollama API")
                    gen_timeout = self.get_timeout_for_model(model, "generate")
                    response = await session.post(
                        f"{self.base_url}/api/generate",
                        json=request_payload,
                        timeout=gen_timeout
                    )
                    response.raise_for_status()
                    debug_log(f"Response status: {response.status}")
                    
                    # Use a simpler async iteration pattern that's less error-prone
                    debug_log("Starting to process response stream")
                    
                    # Update the model usage timestamp to keep it hot
                    self.update_model_usage(model)
                    
                    # Set a flag to track if we've yielded any real content (not loading messages)
                    has_yielded_content = False
                    has_yielded_real_content = False
                    
                    async for line in response.content:
                        # Check cancellation periodically
                        if self._active_stream_session is None:
                            debug_log("Stream session closed, stopping stream processing")
                            break
                            
                        try:
                            # Process the chunk
                            if line:
                                chunk_str = line.decode().strip()
                                # Check if it looks like JSON before trying to parse
                                if chunk_str.startswith('{') and chunk_str.endswith('}'):
                                    try:
                                        data = json.loads(chunk_str)
                                        if isinstance(data, dict):
                                            # Check for error in the chunk
                                            if "error" in data:
                                                error_msg = data.get("error", "")
                                                debug_log(f"Ollama API error in chunk: {error_msg}")
                                                
                                                # Handle model loading state
                                                if "loading model" in error_msg.lower():
                                                    # Yield a user-friendly message and keep trying
                                                    yield "The model is still loading. Please wait a moment..."
                                                    has_yielded_content = True  # We did yield something
                                                    # Add delay before continuing
                                                    await asyncio.sleep(2)
                                                    continue
                                            
                                            # Process normal response
                                            if "response" in data:
                                                response_text = data["response"]
                                                if response_text:  # Only yield non-empty responses
                                                    has_yielded_content = True
                                                    has_yielded_real_content = True  # This is actual model content
                                                    chunk_length = len(response_text)
                                                    # Only log occasionally to reduce console spam
                                                    if chunk_length % 20 == 0:
                                                        debug_log(f"Yielding chunk of length: {chunk_length}")
                                                    yield response_text
                                            else:
                                                debug_log(f"JSON chunk missing 'response' key: {chunk_str[:100]}")
                                        else:
                                            debug_log(f"JSON chunk is not a dict: {chunk_str[:100]}")
                                    except json.JSONDecodeError:
                                        debug_log(f"JSON decode error for chunk: {chunk_str[:100]}")
                                else:
                                    # Log unexpected non-JSON lines but don't process them
                                    if chunk_str and len(chunk_str) > 5:  # Avoid logging empty or tiny lines
                                        debug_log(f"Received unexpected non-JSON line: {chunk_str[:100]}")
                        except Exception as chunk_err:
                            debug_log(f"Error processing chunk: {str(chunk_err)}")
                            # Continue instead of breaking to try processing more chunks
                            continue
                    
                    # If we didn't yield any real content (only loading messages), yield a default message
                    if not has_yielded_real_content:
                        debug_log("No real content was yielded from stream, providing fallback response")
                        yield "I'm sorry, but I couldn't generate a response. Please try again or try a different model."
                    
                    logger.info("Streaming completed successfully")
                    debug_log("Streaming completed successfully")
                    return
                finally:
                    self._active_stream_session = None  # Clear reference when done
                    await session.close()  # Ensure session is closed
                    debug_log("Stream session closed")
                        
            except aiohttp.ClientConnectorError:
                last_error = "Could not connect to Ollama server. Make sure Ollama is running and accessible at " + self.base_url
                debug_log(f"ClientConnectorError: {last_error}")
            except aiohttp.ClientResponseError as e:
                last_error = f"Ollama API error: {e.status} - {e.message}"
                debug_log(f"ClientResponseError: {last_error}")
            except aiohttp.ClientTimeout:
                last_error = "Request to Ollama server timed out"
                debug_log(f"ClientTimeout: {last_error}")
            except asyncio.CancelledError:
                logger.info("Streaming cancelled by client")
                debug_log("CancelledError: Streaming cancelled by client")
                raise  # Propagate cancellation
            except Exception as e:
                last_error = f"Error streaming completion: {str(e)}"
                debug_log(f"General exception: {last_error}")
            
            logger.error(f"Streaming attempt failed: {last_error}")
            debug_log(f"Streaming attempt failed: {last_error}")
            retries -= 1
            if retries >= 0:
                logger.info(f"Retrying stream... {retries} attempts remaining")
                debug_log(f"Retrying stream... {retries} attempts remaining")
                await asyncio.sleep(1)
                
        debug_log(f"All retries failed. Last error: {last_error}")
        raise Exception(last_error)
        
    async def cancel_stream(self) -> None:
        """Cancel any active streaming request"""
        if self._active_stream_session:
            logger.info("Cancelling active stream session")
            await self._active_stream_session.close()
            self._active_stream_session = None
            self._model_loading = False
            logger.info("Stream session closed successfully")
            
    def is_loading_model(self) -> bool:
        """Check if Ollama is currently loading a model"""
        return self._model_loading
    
    async def preload_model(self, model_id: str) -> bool:
        """
        Preload a model to keep it hot/ready for use
        Returns True if successful, False otherwise
        """
        from datetime import datetime
        import asyncio
        
        logger.info(f"Preloading model: {model_id}")
        
        # First, check if the model is already preloaded
        if model_id in self._preloaded_models:
            # Update timestamp if already preloaded
            self._preloaded_models[model_id] = datetime.now()
            logger.info(f"Model {model_id} already preloaded, updated timestamp")
            return True
        
        try:
            # We'll use a minimal prompt to load the model
            warm_up_prompt = "hello"
            
            # Set model loading state
            old_loading_state = self._model_loading
            self._model_loading = True
            
            async with aiohttp.ClientSession() as session:
                # First try pulling the model if needed
                try:
                    logger.info(f"Ensuring model {model_id} is pulled")
                    pull_payload = {"name": model_id}
                    pull_timeout = self.get_timeout_for_model(model_id, "pull")
                    async with session.post(
                        f"{self.base_url}/api/pull",
                        json=pull_payload,
                        timeout=pull_timeout
                    ) as pull_response:
                        # We don't need to process the full pull, just initiate it
                        if pull_response.status != 200:
                            logger.warning(f"Pull request for model {model_id} failed with status {pull_response.status}")
                except Exception as e:
                    logger.warning(f"Error during model pull check: {str(e)}")
                
                # Now send a small generation request to load the model into memory
                logger.info(f"Sending warm-up request for model {model_id}")
                gen_timeout = self.get_timeout_for_model(model_id, "load")
                async with session.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": model_id,
                        "prompt": warm_up_prompt,
                        "temperature": 0.7,
                        "stream": False
                    },
                    timeout=gen_timeout
                ) as response:
                    if response.status != 200:
                        logger.error(f"Failed to preload model {model_id}, status: {response.status}")
                        self._model_loading = old_loading_state
                        return False
                    
                    # Read the response to ensure the model is fully loaded
                    await response.json()
                    
                    # Update preloaded models with timestamp
                    self._preloaded_models[model_id] = datetime.now()
                    logger.info(f"Successfully preloaded model {model_id}")
                    return True
        except Exception as e:
            logger.error(f"Error preloading model {model_id}: {str(e)}")
            return False
        finally:
            # Reset model loading state
            self._model_loading = old_loading_state
    
    def get_preloaded_models(self) -> Dict[str, datetime]:
        """Return the dict of preloaded models and their last use times"""
        return self._preloaded_models
    
    def update_model_usage(self, model_id: str) -> None:
        """Update the timestamp for a model that is being used"""
        if model_id and model_id in self._preloaded_models:
            from datetime import datetime
            self._preloaded_models[model_id] = datetime.now()
            logger.info(f"Updated usage timestamp for model {model_id}")
    
    async def release_inactive_models(self, max_inactive_minutes: int = 30) -> List[str]:
        """
        Release models that have been inactive for more than the specified time
        Returns a list of model IDs that were released
        """
        from datetime import datetime, timedelta
        
        if not self._preloaded_models:
            return []
            
        now = datetime.now()
        inactive_threshold = timedelta(minutes=max_inactive_minutes)
        models_to_release = []
        
        # Find models that have been inactive for too long
        for model_id, last_used in list(self._preloaded_models.items()):
            if now - last_used > inactive_threshold:
                models_to_release.append(model_id)
                
        # Release the models
        released_models = []
        for model_id in models_to_release:
            try:
                logger.info(f"Releasing inactive model: {model_id} (inactive for {(now - self._preloaded_models[model_id]).total_seconds() / 60:.1f} minutes)")
                # We don't have an explicit "unload" API in Ollama, but we can remove it from our tracking
                del self._preloaded_models[model_id]
                released_models.append(model_id)
            except Exception as e:
                logger.error(f"Error releasing model {model_id}: {str(e)}")
                
        return released_models
            
    async def get_model_details(self, model_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific Ollama model"""
        logger.info(f"Getting details for model: {model_id}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/show",
                    json={"name": model_id},
                    timeout=5
                ) as response:
                    response.raise_for_status()
                    data = await response.json()
                    logger.debug(f"Ollama model details response: {data}")
                    return data
        except Exception as e:
            logger.error(f"Error getting model details: {str(e)}")
            # Return a dict with error info instead of raising an exception
            return {
                "error": str(e),
                "modelfile": None,
                "parameters": None,
                "size": 0,
                "created_at": None,
                "modified_at": None
            }
    
    async def _fetch_and_cache_models(self) -> List[Dict[str, Any]]:
        """Fetch models from Ollama website and cache them for 24 hours"""
        logger.info("Performing a full fetch of Ollama models to update cache")
        
        try:
            # First load models from base file
            base_models = []
            try:
                # Read the base models file
                base_file_path = Path(__file__).parent.parent / "data" / "ollama-models-base.json"
                if base_file_path.exists():
                    with open(base_file_path, 'r') as f:
                        base_data = json.load(f)
                        if "models" in base_data:
                            base_models = base_data["models"]
                            logger.info(f"Loaded {len(base_models)} models from base file")
                            
                            # Process models from the base file to ensure consistent format
                            for model in base_models:
                                # Convert any missing fields to expected format
                                if "parameter_size" not in model and "variants" in model and model["variants"]:
                                    # Use the first variant as the default parameter size if not specified
                                    for variant in model["variants"]:
                                        if any(char.isdigit() for char in variant):
                                            # This looks like a size variant (e.g., "7b", "70b")
                                            if variant.lower().endswith('b'):
                                                model["parameter_size"] = variant.upper()
                                            else:
                                                model["parameter_size"] = f"{variant}B"
                                            break
                            
            except Exception as e:
                logger.warning(f"Error loading base models file: {str(e)}")
            
            # Web scraping for more models
            scraped_models = []
            try:
                async with aiohttp.ClientSession() as session:
                    # Get model data from the Ollama website search page (without query to get all models)
                    search_url = "https://ollama.com/search"
                    
                    logger.info(f"Fetching all models from Ollama web: {search_url}")
                    async with session.get(
                        search_url,
                        timeout=20,  # Longer timeout for comprehensive scrape
                        headers={"User-Agent": "Mozilla/5.0 (compatible; chat-console/1.0)"}
                    ) as response:
                        if response.status == 200:
                            html = await response.text()
                            
                            # Extract model data from JSON embedded in the page
                            try:
                                import re
                                
                                # Look for model data in JSON format
                                model_match = re.search(r'window\.__NEXT_DATA__\s*=\s*({.+?});', html, re.DOTALL)
                                if model_match:
                                    json_data = json.loads(model_match.group(1))
                                    
                                    # Navigate to where models are stored in the JSON
                                    if (json_data and 'props' in json_data and 
                                        'pageProps' in json_data['props'] and 
                                        'models' in json_data['props']['pageProps']):
                                        
                                        web_models = json_data['props']['pageProps']['models']
                                        logger.info(f"Found {len(web_models)} models on Ollama website")
                                        
                                        # Process models
                                        for model in web_models:
                                            try:
                                                # Skip models without necessary data
                                                if not model.get('name'):
                                                    continue
                                                    
                                                # Create structured model data
                                                processed_model = {
                                                    "name": model.get('name', ''),
                                                    "description": model.get('description', f"{model.get('name')} model"),
                                                    "model_family": model.get('modelFamily', 'Unknown'),
                                                }
                                                
                                                # Add variants if available
                                                if model.get('variants'):
                                                    processed_model["variants"] = model.get('variants', [])
                                                
                                                # Extract parameter size from model details
                                                if model.get('parameterSize'):
                                                    processed_model["parameter_size"] = f"{model.get('parameterSize')}B"
                                                else:
                                                    # Try to extract from name
                                                    name = model.get('name', '').lower()
                                                    param_size = None
                                                    
                                                    # Check for specific patterns
                                                    if "70b" in name:
                                                        param_size = "70B"
                                                    elif "405b" in name or "400b" in name:
                                                        param_size = "405B"
                                                    elif "34b" in name or "35b" in name:
                                                        param_size = "34B"
                                                    elif "27b" in name or "28b" in name:
                                                        param_size = "27B"
                                                    elif "13b" in name or "14b" in name:
                                                        param_size = "13B"
                                                    elif "8b" in name:
                                                        param_size = "8B"
                                                    elif "7b" in name:
                                                        param_size = "7B"
                                                    elif "6b" in name:
                                                        param_size = "6B"
                                                    elif "3b" in name:
                                                        param_size = "3B"
                                                    elif "2b" in name:
                                                        param_size = "2B"
                                                    elif "1b" in name:
                                                        param_size = "1B"
                                                    elif "mini" in name:
                                                        param_size = "3B"
                                                    elif "small" in name:
                                                        param_size = "7B"
                                                    elif "medium" in name:
                                                        param_size = "13B"
                                                    elif "large" in name:
                                                        param_size = "34B"
                                                    
                                                    # Special handling for models with ":latest" or no size indicator
                                                    if not param_size and ("latest" in name or not any(size in name for size in ["1b", "2b", "3b", "6b", "7b", "8b", "13b", "14b", "27b", "28b", "34b", "35b", "70b", "405b", "400b", "mini", "small", "medium", "large"])):
                                                        # Strip the ":latest" part to get base model
                                                        base_name = name.split(":")[0]
                                                        
                                                        # Check if we have default parameter sizes for known models
                                                        model_defaults = {
                                                            "llama3": "8B",
                                                            "llama2": "7B",
                                                            "mistral": "7B",
                                                            "gemma": "7B",
                                                            "gemma2": "9B",
                                                            "phi": "3B",
                                                            "phi2": "3B",
                                                            "phi3": "3B",
                                                            "phi4": "7B",
                                                            "orca-mini": "7B",
                                                            "llava": "7B",
                                                            "codellama": "7B",
                                                            "neural-chat": "7B",
                                                            "wizard-math": "7B",
                                                            "yi": "6B",
                                                            "deepseek": "7B",
                                                            "deepseek-coder": "7B",
                                                            "qwen": "7B",
                                                            "falcon": "7B",
                                                            "stable-code": "3B"
                                                        }
                                                        
                                                        # Try to find a match in default sizes
                                                        for model_name, default_size in model_defaults.items():
                                                            if model_name in base_name:
                                                                param_size = default_size
                                                                break
                                                        
                                                        # If we still don't have a param size, check model metadata
                                                        if not param_size and model.get('defaultParameterSize'):
                                                            param_size = f"{model.get('defaultParameterSize')}B"
                                                            
                                                        # Check model variants for clues
                                                        if not param_size and model.get('variants'):
                                                            # The default variant is often the first one
                                                            try:
                                                                variants = model.get('variants', [])
                                                                if variants and len(variants) > 0:
                                                                    # Try to get parameter size from the first variant
                                                                    first_variant = variants[0]
                                                                    if first_variant and 'parameterSize' in first_variant:
                                                                        param_size = f"{first_variant['parameterSize']}B"
                                                                    # Just use the first variant if it looks like a size
                                                                    elif isinstance(first_variant, str) and any(char.isdigit() for char in first_variant):
                                                                        if first_variant.lower().endswith('b'):
                                                                            param_size = first_variant.upper()
                                                                        else:
                                                                            param_size = f"{first_variant}B"
                                                            except Exception as e:
                                                                logger.warning(f"Error getting parameter size from variants: {str(e)}")
                                                    
                                                    processed_model["parameter_size"] = param_size or "Unknown"
                                                
                                                # Set disk size based on parameter size
                                                param_value = processed_model.get("parameter_size", "").lower()
                                                if "70b" in param_value:
                                                    processed_model["size"] = 40000000000  # ~40GB
                                                elif "405b" in param_value or "400b" in param_value:
                                                    processed_model["size"] = 200000000000  # ~200GB
                                                elif "34b" in param_value or "35b" in param_value:
                                                    processed_model["size"] = 20000000000  # ~20GB
                                                elif "27b" in param_value or "28b" in param_value:
                                                    processed_model["size"] = 15000000000  # ~15GB
                                                elif "13b" in param_value or "14b" in param_value:
                                                    processed_model["size"] = 8000000000  # ~8GB
                                                elif "8b" in param_value:
                                                    processed_model["size"] = 4800000000  # ~4.8GB
                                                elif "7b" in param_value:
                                                    processed_model["size"] = 4500000000  # ~4.5GB
                                                elif "6b" in param_value:
                                                    processed_model["size"] = 3500000000  # ~3.5GB
                                                elif "3b" in param_value:
                                                    processed_model["size"] = 2000000000  # ~2GB
                                                elif "2b" in param_value:
                                                    processed_model["size"] = 1500000000  # ~1.5GB
                                                elif "1b" in param_value:
                                                    processed_model["size"] = 800000000  # ~800MB
                                                else:
                                                    processed_model["size"] = 4500000000  # Default to ~4.5GB
                                                
                                                scraped_models.append(processed_model)
                                            except Exception as e:
                                                logger.warning(f"Error processing web model {model.get('name', 'unknown')}: {str(e)}")
                            except Exception as e:
                                logger.warning(f"Error extracting model data from Ollama website: {str(e)}")
            except Exception as web_e:
                logger.warning(f"Error fetching from Ollama website: {str(web_e)}")
            
            # Add curated models from the registry
            curated_models = await self.get_registry_models("")
            
            # Combine all models - prefer base models, then scraped models, then curated
            all_models = []
            existing_names = set()
            
            # First add all base models (highest priority)
            for model in base_models:
                if model.get("name"):
                    all_models.append(model)
                    existing_names.add(model["name"])
            
            # Then add scraped models if not already added
            for model in scraped_models:
                if model.get("name") and model["name"] not in existing_names:
                    all_models.append(model)
                    existing_names.add(model["name"])
            
            # Finally add curated models if not already added
            for model in curated_models:
                if model.get("name") and model["name"] not in existing_names:
                    all_models.append(model)
                    existing_names.add(model["name"])
            
            # Cache the combined models
            cache_data = {
                "last_updated": datetime.now().isoformat(),
                "models": all_models
            }
            
            try:
                with open(self.models_cache_path, 'w') as f:
                    json.dump(cache_data, f, indent=2)
                logger.info(f"Cached {len(all_models)} models to {self.models_cache_path}")
            except Exception as cache_error:
                logger.error(f"Error caching models: {str(cache_error)}")
            
            return all_models
                
        except Exception as e:
            logger.error(f"Error during model fetch and cache: {str(e)}")
            # Return an empty list in case of catastrophic failure
            return []
            
    async def list_available_models_from_registry(self, query: str = "") -> List[Dict[str, Any]]:
        """List available models from Ollama registry with cache support"""
        logger.info(f"Fetching available models from Ollama registry, query: '{query}'")
        
        # Check if we need to update the cache
        need_cache_update = True
        models_from_cache = []
        
        try:
            # Try to read from cache first
            if self.models_cache_path.exists():
                try:
                    with open(self.models_cache_path, 'r') as f:
                        cache_data = json.load(f)
                    
                    # Check if cache is still valid (less than 24 hours old)
                    if cache_data.get("last_updated"):
                        last_updated = datetime.fromisoformat(cache_data["last_updated"])
                        # Cache valid if less than 24 hours old
                        if datetime.now() - last_updated < timedelta(hours=24):
                            need_cache_update = False
                            models_from_cache = cache_data.get("models", [])
                            logger.info(f"Using cached models from {last_updated.isoformat()} ({len(models_from_cache)} models)")
                        else:
                            logger.info(f"Cache from {last_updated.isoformat()} is older than 24 hours, refreshing")
                except Exception as e:
                    logger.warning(f"Error reading cache: {str(e)}, will refresh")
            else:
                logger.info("No cache found, creating a new one")
        except Exception as e:
            logger.warning(f"Error checking cache: {str(e)}")
        
        # Always read the base file first
        base_models = []
        try:
            # Read the base models file
            base_file_path = Path(__file__).parent.parent / "data" / "ollama-models-base.json"
            if base_file_path.exists():
                with open(base_file_path, 'r') as f:
                    base_data = json.load(f)
                    if "models" in base_data:
                        base_models = base_data["models"]
                        logger.info(f"Loaded {len(base_models)} models from base file")
                        
                # Process base models to ensure they have proper format
                for model in base_models:
                    # Make sure they have model_family
                    if "model_family" not in model and "name" in model:
                        name = model["name"].lower()
                        if "llama" in name:
                            model["model_family"] = "Llama"
                        elif "mistral" in name:
                            model["model_family"] = "Mistral"
                        elif "phi" in name:
                            model["model_family"] = "Phi"
                        elif "gemma" in name:
                            model["model_family"] = "Gemma"
                        elif "qwen" in name:
                            model["model_family"] = "Qwen"
                        else:
                            # Try to extract family from name (before any colon)
                            base_name = name.split(":")[0]
                            model["model_family"] = base_name.capitalize()
                
                # If no cache yet but base file exists, use base models and trigger update
                if not models_from_cache and base_models:
                    models_from_cache = base_models
                    logger.info(f"Using {len(base_models)} models from base file while cache updates")
                    
                    # Start cache update in background
                    asyncio.create_task(self._fetch_and_cache_models())
                    need_cache_update = False
        except Exception as e:
            logger.warning(f"Error loading base models file: {str(e)}")
        
        # If we need to update the cache, do it now
        if need_cache_update:
            # Run the cache update in the background if we have cached data
            if models_from_cache:
                # We can use cached data for now but update in background
                asyncio.create_task(self._fetch_and_cache_models())
            else:
                # We need to wait for the cache update
                models_from_cache = await self._fetch_and_cache_models()
        
        # Always make sure base models are included
        if base_models:
            # Create a set of existing model names
            existing_names = set(model.get("name", "") for model in models_from_cache)
            
            # Add base models if not already in cache
            for model in base_models:
                if model.get("name") and model["name"] not in existing_names:
                    models_from_cache.append(model)
                    existing_names.add(model["name"])
            
            logger.info(f"Combined total: {len(models_from_cache)} models")
            
        # Log the number of models available
        logger.info(f"Total available models: {len(models_from_cache)}")
        
        # No filtering here - the UI will handle filtering
        return models_from_cache
            
    async def get_registry_models(self, query: str = "") -> List[Dict[str, Any]]:
        """Get a curated list of popular Ollama models"""
        logger.info("Returning a curated list of popular Ollama models (query: {})".format(query or "none"))
        
        # Provide a curated list of popular models as fallback
        models = [
            # Llama 3 models
            {
                "name": "llama3",
                "description": "Meta's Llama 3 8B model",
                "model_family": "Llama",
                "size": 4500000000,
                "parameter_size": "8B"
            },
            {
                "name": "llama3:8b",
                "description": "Meta's Llama 3 8B parameter model",
                "model_family": "Llama",
                "size": 4500000000,
                "parameter_size": "8B"
            },
            {
                "name": "llama3:70b",
                "description": "Meta's Llama 3 70B parameter model",
                "model_family": "Llama",
                "size": 40000000000,
                "parameter_size": "70B"
            },
            # Llama 3.1 models
            {
                "name": "llama3.1:8b",
                "description": "Meta's Llama 3.1 8B parameter model",
                "model_family": "Llama",
                "size": 4500000000
            },
            {
                "name": "llama3.1:70b",
                "description": "Meta's Llama 3.1 70B parameter model",
                "model_family": "Llama",
                "size": 40000000000
            },
            {
                "name": "llama3.1:405b",
                "description": "Meta's Llama 3.1 405B parameter model",
                "model_family": "Llama",
                "size": 200000000000
            },
            # Gemma models
            {
                "name": "gemma:2b",
                "description": "Google's Gemma 2B parameter model",
                "model_family": "Gemma",
                "size": 1500000000
            },
            {
                "name": "gemma:7b",
                "description": "Google's Gemma 7B parameter model",
                "model_family": "Gemma",
                "size": 4000000000
            },
            {
                "name": "gemma2:9b",
                "description": "Google's Gemma 2 9B parameter model",
                "model_family": "Gemma",
                "size": 5000000000
            },
            {
                "name": "gemma2:27b",
                "description": "Google's Gemma 2 27B parameter model",
                "model_family": "Gemma",
                "size": 15000000000
            },
            # Mistral models
            {
                "name": "mistral",
                "description": "Mistral 7B model - balanced performance",
                "model_family": "Mistral",
                "size": 4200000000
            },
            {
                "name": "mistral:7b",
                "description": "Mistral 7B model - balanced performance",
                "model_family": "Mistral",
                "size": 4200000000
            },
            {
                "name": "mistral:8x7b",
                "description": "Mistral 8x7B mixture of experts model",
                "model_family": "Mistral",
                "size": 15000000000
            },
            # Phi models
            {
                "name": "phi3:mini",
                "description": "Microsoft's Phi-3 Mini model",
                "model_family": "Phi",
                "size": 3500000000
            },
            {
                "name": "phi3:small",
                "description": "Microsoft's Phi-3 Small model",
                "model_family": "Phi",
                "size": 7000000000
            },
            {
                "name": "phi3:medium",
                "description": "Microsoft's Phi-3 Medium model",
                "model_family": "Phi",
                "size": 14000000000
            },
            {
                "name": "phi2",
                "description": "Microsoft's Phi-2 model, small but capable",
                "model_family": "Phi",
                "size": 2800000000
            },
            # Orca models
            {
                "name": "orca-mini",
                "description": "Small, fast model optimized for chat",
                "model_family": "Orca",
                "size": 2000000000
            },
            {
                "name": "orca-mini:3b",
                "description": "Small 3B parameter model optimized for chat",
                "model_family": "Orca",
                "size": 2000000000
            },
            {
                "name": "orca-mini:7b",
                "description": "Medium 7B parameter model optimized for chat",
                "model_family": "Orca",
                "size": 4000000000
            },
            # Llava models (multimodal)
            {
                "name": "llava",
                "description": "Multimodal model with vision capabilities",
                "model_family": "LLaVA",
                "size": 4700000000
            },
            {
                "name": "llava:13b",
                "description": "Multimodal model with vision capabilities (13B)",
                "model_family": "LLaVA",
                "size": 8000000000
            },
            {
                "name": "llava:34b",
                "description": "Multimodal model with vision capabilities (34B)",
                "model_family": "LLaVA",
                "size": 20000000000
            },
            # CodeLlama models
            {
                "name": "codellama",
                "description": "Llama model fine-tuned for code generation",
                "model_family": "CodeLlama",
                "size": 4200000000
            },
            {
                "name": "codellama:7b",
                "description": "7B parameter Llama model for code generation",
                "model_family": "CodeLlama",
                "size": 4200000000
            },
            {
                "name": "codellama:13b",
                "description": "13B parameter Llama model for code generation",
                "model_family": "CodeLlama",
                "size": 8000000000
            },
            {
                "name": "codellama:34b",
                "description": "34B parameter Llama model for code generation",
                "model_family": "CodeLlama",
                "size": 20000000000
            },
            # Other models
            {
                "name": "neural-chat",
                "description": "Intel's Neural Chat model",
                "model_family": "Neural Chat",
                "size": 4200000000
            },
            {
                "name": "wizard-math",
                "description": "Specialized for math problem solving",
                "model_family": "Wizard",
                "size": 4200000000
            },
            {
                "name": "yi",
                "description": "01AI's Yi model, high performance",
                "model_family": "Yi",
                "size": 4500000000
            },
            {
                "name": "yi:6b",
                "description": "01AI's Yi 6B parameter model",
                "model_family": "Yi",
                "size": 3500000000
            },
            {
                "name": "yi:9b",
                "description": "01AI's Yi 9B parameter model",
                "model_family": "Yi",
                "size": 5000000000
            },
            {
                "name": "yi:34b",
                "description": "01AI's Yi 34B parameter model, excellent performance",
                "model_family": "Yi",
                "size": 20000000000
            },
            {
                "name": "stable-code",
                "description": "Stability AI's code generation model",
                "model_family": "StableCode",
                "size": 4200000000
            },
            {
                "name": "llama2",
                "description": "Meta's Llama 2 model",
                "model_family": "Llama",
                "size": 4200000000
            },
            {
                "name": "llama2:7b",
                "description": "Meta's Llama 2 7B parameter model",
                "model_family": "Llama",
                "size": 4200000000
            },
            {
                "name": "llama2:13b",
                "description": "Meta's Llama 2 13B parameter model",
                "model_family": "Llama",
                "size": 8000000000
            },
            {
                "name": "llama2:70b",
                "description": "Meta's Llama 2 70B parameter model",
                "model_family": "Llama", 
                "size": 40000000000
            },
            {
                "name": "deepseek-coder",
                "description": "DeepSeek's code generation model",
                "model_family": "DeepSeek",
                "size": 4200000000
            },
            {
                "name": "falcon:40b",
                "description": "TII's Falcon 40B, very capable model",
                "model_family": "Falcon",
                "size": 25000000000
            },
            {
                "name": "qwen:14b",
                "description": "Alibaba's Qwen 14B model",
                "model_family": "Qwen",
                "size": 9000000000
            }
        ]
        
        # Filter by query if provided
        query = query.lower() if query else ""
        if query:
            filtered_models = []
            for model in models:
                if (query in model["name"].lower() or 
                    query in model["description"].lower() or
                    query in model["model_family"].lower()):
                    filtered_models.append(model)
            return filtered_models
        
        return models
            
    async def pull_model(self, model_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Pull a model from Ollama registry with progress updates"""
        logger.info(f"Pulling model: {model_id}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/pull",
                    json={"name": model_id},
                    timeout=3600  # 1 hour timeout for large models
                ) as response:
                    response.raise_for_status()
                    async for line in response.content:
                        if line:
                            chunk = line.decode().strip()
                            try:
                                data = json.loads(chunk)
                                yield data
                            except json.JSONDecodeError:
                                continue
        except Exception as e:
            logger.error(f"Error pulling model: {str(e)}")
            raise Exception(f"Failed to pull model: {str(e)}")
            
    async def delete_model(self, model_id: str) -> None:
        """Delete a model from Ollama"""
        logger.info(f"Deleting model: {model_id}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.delete(
                    f"{self.base_url}/api/delete",
                    json={"name": model_id},
                    timeout=30
                ) as response:
                    response.raise_for_status()
                    logger.info(f"Model {model_id} deleted successfully")
        except Exception as e:
            logger.error(f"Error deleting model: {str(e)}")
            raise Exception(f"Failed to delete model: {str(e)}")
