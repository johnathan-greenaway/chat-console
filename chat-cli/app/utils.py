import os
import json
import time
import asyncio
import subprocess
import logging
import anthropic # Add missing import
from typing import Optional, Dict, Any, List, TYPE_CHECKING, Callable, Awaitable
from datetime import datetime
from textual import work # Import work decorator
from .config import CONFIG, save_config

# Import SimpleChatApp for type hinting only if TYPE_CHECKING is True
if TYPE_CHECKING:
    from .main import SimpleChatApp # Keep this for type hinting

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def generate_conversation_title(message: str, model: str, client: Any) -> str:
    """Generate a descriptive title for a conversation based on the first message"""
    try:
        from app.main import debug_log
    except ImportError:
        debug_log = lambda msg: None
    
    debug_log(f"Starting title generation with model: {model}, client type: {type(client).__name__}")
    
    # For safety, always use a default title first
    default_title = f"Conversation ({datetime.now().strftime('%Y-%m-%d %H:%M')})"
    
    # Try-except the entire function to ensure we always return a title
    try:
        # Check if we're using an Ollama client
        from app.api.ollama import OllamaClient
        is_ollama_client = isinstance(client, OllamaClient)
        debug_log(f"Client is Ollama: {is_ollama_client}")
        
        # Pick a reliable title generation model - prefer OpenAI if available
        from app.config import OPENAI_API_KEY, ANTHROPIC_API_KEY
        
        if OPENAI_API_KEY:
            from app.api.openai import OpenAIClient
            title_client = await OpenAIClient.create()
            title_model = "gpt-3.5-turbo"
            debug_log("Using OpenAI for title generation")
        elif ANTHROPIC_API_KEY:
            from app.api.anthropic import AnthropicClient
            title_client = await AnthropicClient.create() 
            title_model = "claude-3-haiku-20240307"
            debug_log("Using Anthropic for title generation")
        else:
            # For Ollama clients, ensure we have a clean instance to avoid conflicts with preloaded models
            if is_ollama_client:
                debug_log("Creating fresh Ollama client instance for title generation")
                title_client = await OllamaClient.create()
                title_model = model
            else:
                # Use the passed client for other providers
                title_client = client
                title_model = model
            debug_log(f"Using {type(title_client).__name__} for title generation with model {title_model}")
        
        # Create a special prompt for title generation
        title_prompt = [
            {
                "role": "system", 
                "content": "Generate a brief, descriptive title (maximum 40 characters) for a conversation that starts with the following message. ONLY output the title text. DO NOT include phrases like 'Sure, here's a title' or any additional formatting, explanation, or quotes."
            },
            {
                "role": "user",
                "content": message
            }
        ]
        
        # Generate title
        debug_log(f"Sending title generation request to {title_model}")
        
        # Check if this is a reasoning model (o-series)
        is_reasoning_model = title_model.startswith(("o1", "o3", "o4")) or title_model in ["o1", "o3", "o4-mini"]
        
        if is_reasoning_model:
            # For reasoning models, don't include temperature
            title = await title_client.generate_completion(
                messages=title_prompt,
                model=title_model,
                max_tokens=60
            )
        else:
            # For non-reasoning models, include temperature
            title = await title_client.generate_completion(
                messages=title_prompt,
                model=title_model,
                temperature=0.7,
                max_tokens=60
            )
        
        # Sanitize the title - remove quotes, extra spaces and unwanted prefixes
        title = title.strip().strip('"\'').strip()
        
        # Remove common LLM prefixes like "Title:", "Sure, here's a title:", etc.
        prefixes_to_remove = [
            "title:", "here's a title:", "here is a title:", 
            "a title for this conversation:", "sure,", "certainly,",
            "the title is:", "suggested title:"
        ]
        
        # Case-insensitive prefix removal
        title_lower = title.lower()
        for prefix in prefixes_to_remove:
            if title_lower.startswith(prefix):
                title = title[len(prefix):].strip()
                title_lower = title.lower()  # Update lowercase version after removal
        
        # Remove any remaining quotes
        title = title.strip('"\'').strip()
        
        # Enforce length limit
        if len(title) > 40:
            title = title[:37] + "..."
            
        debug_log(f"Generated title (after sanitization): {title}")
        return title
        
    except Exception as e:
        # Log the error and return default title
        debug_log(f"Title generation failed: {str(e)}")
        logger.error(f"Title generation failed: {str(e)}")
        return default_title

# Helper function for OpenAI streaming
async def _generate_openai_stream(
    app: 'SimpleChatApp',
    messages: List[Dict],
    model: str,
    style: str,
    client: Any,
    callback: Callable[[str], Awaitable[None]],
    update_lock: asyncio.Lock
) -> Optional[str]:
    """Generate streaming response using OpenAI provider."""
    try:
        from app.main import debug_log
    except ImportError:
        debug_log = lambda msg: None
    
    debug_log(f"Using OpenAI-specific streaming for model: {model}")
    
    # Initialize variables for response tracking
    full_response = ""
    buffer = []
    last_update = time.time()
    update_interval = 0.03  # Responsive updates for OpenAI
    
    try:
        # Initialize stream generator
        debug_log("Initializing OpenAI stream generator")
        stream_generator = client.generate_stream(messages, model, style)
        
        # Process stream chunks
        debug_log("Beginning to process OpenAI stream chunks")
        async for chunk in stream_generator:
            # Check for task cancellation
            if asyncio.current_task().cancelled():
                debug_log("Task cancellation detected during OpenAI chunk processing")
                if hasattr(client, 'cancel_stream'):
                    await client.cancel_stream()
                raise asyncio.CancelledError()
                
            # Process chunk content
            if chunk:
                if not isinstance(chunk, str):
                    try:
                        chunk = str(chunk)
                    except Exception:
                        continue
                        
                buffer.append(chunk)
                current_time = time.time()
                
                # Update UI with new content
                if (current_time - last_update >= update_interval or
                    len(''.join(buffer)) > 5 or
                    len(full_response) < 50):
                    
                    new_content = ''.join(buffer)
                    full_response += new_content
                    
                    try:
                        async with update_lock:
                            await callback(full_response)
                            if hasattr(app, 'refresh'):
                                app.refresh(layout=True)
                    except Exception as callback_err:
                        logger.error(f"Error in OpenAI UI callback: {str(callback_err)}")
                        
                    buffer = []
                    last_update = current_time
                    await asyncio.sleep(0.02)
                    
        # Process any remaining buffer content
        if buffer:
            new_content = ''.join(buffer)
            full_response += new_content
            
            try:
                async with update_lock:
                    await callback(full_response)
                    if hasattr(app, 'refresh'):
                        app.refresh(layout=True)
                        await asyncio.sleep(0.02)
                        try:
                            messages_container = app.query_one("#messages-container")
                            if messages_container:
                                messages_container.scroll_end(animate=False)
                        except Exception:
                            pass
            except Exception as callback_err:
                logger.error(f"Error in final OpenAI UI callback: {str(callback_err)}")
                
        # Final refresh to ensure everything is displayed correctly
        try:
            await asyncio.sleep(0.05)
            async with update_lock:
                await callback(full_response)
                if hasattr(app, 'refresh'):
                    app.refresh(layout=True)
        except Exception:
            pass
            
        return full_response
        
    except asyncio.CancelledError:
        logger.info(f"OpenAI streaming cancelled. Partial response length: {len(full_response)}")
        if hasattr(client, 'cancel_stream'):
            await client.cancel_stream()
        return full_response
        
    except Exception as e:
        logger.error(f"Error during OpenAI streaming: {str(e)}")
        if hasattr(client, 'cancel_stream'):
            await client.cancel_stream()
        raise

# Helper function for Anthropic streaming
async def _generate_anthropic_stream(
    app: 'SimpleChatApp',
    messages: List[Dict],
    model: str,
    style: str,
    client: Any,
    callback: Callable[[str], Awaitable[None]],
    update_lock: asyncio.Lock
) -> Optional[str]:
    """Generate streaming response using Anthropic provider."""
    try:
        from app.main import debug_log
    except ImportError:
        debug_log = lambda msg: None
    
    debug_log(f"Using Anthropic-specific streaming for model: {model}")
    
    # Initialize variables for response tracking
    full_response = ""
    buffer = []
    last_update = time.time()
    update_interval = 0.03  # Responsive updates for Anthropic
    
    try:
        # Initialize stream generator
        debug_log("Initializing Anthropic stream generator")
        stream_generator = client.generate_stream(messages, model, style)
        
        # Process stream chunks
        debug_log("Beginning to process Anthropic stream chunks")
        async for chunk in stream_generator:
            # Check for task cancellation
            if asyncio.current_task().cancelled():
                debug_log("Task cancellation detected during Anthropic chunk processing")
                if hasattr(client, 'cancel_stream'):
                    await client.cancel_stream()
                raise asyncio.CancelledError()
                
            # Process chunk content
            if chunk:
                if not isinstance(chunk, str):
                    try:
                        chunk = str(chunk)
                    except Exception:
                        continue
                        
                buffer.append(chunk)
                current_time = time.time()
                
                # Update UI with new content
                if (current_time - last_update >= update_interval or
                    len(''.join(buffer)) > 5 or
                    len(full_response) < 50):
                    
                    new_content = ''.join(buffer)
                    full_response += new_content
                    
                    try:
                        async with update_lock:
                            await callback(full_response)
                            if hasattr(app, 'refresh'):
                                app.refresh(layout=True)
                    except Exception as callback_err:
                        logger.error(f"Error in Anthropic UI callback: {str(callback_err)}")
                        
                    buffer = []
                    last_update = current_time
                    await asyncio.sleep(0.02)
                    
        # Process any remaining buffer content
        if buffer:
            new_content = ''.join(buffer)
            full_response += new_content
            
            try:
                async with update_lock:
                    await callback(full_response)
                    if hasattr(app, 'refresh'):
                        app.refresh(layout=True)
                        await asyncio.sleep(0.02)
                        try:
                            messages_container = app.query_one("#messages-container")
                            if messages_container:
                                messages_container.scroll_end(animate=False)
                        except Exception:
                            pass
            except Exception as callback_err:
                logger.error(f"Error in final Anthropic UI callback: {str(callback_err)}")
                
        # Final refresh to ensure everything is displayed correctly
        try:
            await asyncio.sleep(0.05)
            async with update_lock:
                await callback(full_response)
                if hasattr(app, 'refresh'):
                    app.refresh(layout=True)
        except Exception:
            pass
            
        return full_response
        
    except asyncio.CancelledError:
        logger.info(f"Anthropic streaming cancelled. Partial response length: {len(full_response)}")
        if hasattr(client, 'cancel_stream'):
            await client.cancel_stream()
        return full_response
        
    except Exception as e:
        logger.error(f"Error during Anthropic streaming: {str(e)}")
        if hasattr(client, 'cancel_stream'):
            await client.cancel_stream()
        raise

# Helper function for Ollama streaming
async def _generate_ollama_stream(
    app: 'SimpleChatApp',
    messages: List[Dict],
    model: str,
    style: str,
    client: Any,
    callback: Callable[[str], Awaitable[None]],
    update_lock: asyncio.Lock
) -> Optional[str]:
    """Generate streaming response using Ollama provider."""
    try:
        from app.main import debug_log
    except ImportError:
        debug_log = lambda msg: None
    
    debug_log(f"Using Ollama-specific streaming for model: {model}")
    
    # Initialize variables for response tracking
    full_response = ""
    buffer = []
    last_update = time.time()
    update_interval = 0.03  # Responsive updates for Ollama
    
    try:
        # Show loading indicator for Ollama (which may need to load models)
        if hasattr(app, 'query_one'):
            try:
                debug_log("Showing initial model loading indicator for Ollama")
                loading = app.query_one("#loading-indicator")
                loading.add_class("model-loading")
                loading.update("⚙️ Loading Ollama model...")
            except Exception as e:
                debug_log(f"Error setting initial Ollama loading state: {str(e)}")
        
        # Initialize stream generator
        debug_log("Initializing Ollama stream generator")
        stream_generator = client.generate_stream(messages, model, style)
        
        # Update UI if model is ready
        if hasattr(client, 'is_loading_model') and not client.is_loading_model() and hasattr(app, 'query_one'):
            try:
                debug_log("Ollama model is ready for generation, updating UI")
                loading = app.query_one("#loading-indicator")
                loading.remove_class("model-loading")
                loading.update("▪▪▪ Generating response...")
            except Exception as e:
                debug_log(f"Error updating UI after Ollama stream init: {str(e)}")
        
        # Process stream chunks
        debug_log("Beginning to process Ollama stream chunks")
        async for chunk in stream_generator:
            # Check for task cancellation
            if asyncio.current_task().cancelled():
                debug_log("Task cancellation detected during Ollama chunk processing")
                if hasattr(client, 'cancel_stream'):
                    await client.cancel_stream()
                raise asyncio.CancelledError()
                
            # Handle Ollama model loading state changes
            if hasattr(client, 'is_loading_model'):
                try:
                    model_loading = client.is_loading_model()
                    if hasattr(app, 'query_one'):
                        try:
                            loading = app.query_one("#loading-indicator")
                            if model_loading and hasattr(loading, 'has_class') and not loading.has_class("model-loading"):
                                debug_log("Ollama model loading started during streaming")
                                loading.add_class("model-loading")
                                loading.update("⚙️ Loading Ollama model...")
                            elif not model_loading and hasattr(loading, 'has_class') and loading.has_class("model-loading"):
                                debug_log("Ollama model loading finished during streaming")
                                loading.remove_class("model-loading")
                                loading.update("▪▪▪ Generating response...")
                        except Exception:
                            pass
                except Exception:
                    pass
                
            # Process chunk content
            if chunk:
                if not isinstance(chunk, str):
                    try:
                        chunk = str(chunk)
                    except Exception:
                        continue
                        
                buffer.append(chunk)
                current_time = time.time()
                
                # Update UI with new content
                if (current_time - last_update >= update_interval or
                    len(''.join(buffer)) > 5 or
                    len(full_response) < 50):
                    
                    new_content = ''.join(buffer)
                    full_response += new_content
                    
                    try:
                        async with update_lock:
                            await callback(full_response)
                            if hasattr(app, 'refresh'):
                                app.refresh(layout=True)
                    except Exception as callback_err:
                        logger.error(f"Error in Ollama UI callback: {str(callback_err)}")
                        
                    buffer = []
                    last_update = current_time
                    await asyncio.sleep(0.02)
                    
        # Process any remaining buffer content
        if buffer:
            new_content = ''.join(buffer)
            full_response += new_content
            
            try:
                async with update_lock:
                    await callback(full_response)
                    if hasattr(app, 'refresh'):
                        app.refresh(layout=True)
                        await asyncio.sleep(0.02)
                        try:
                            messages_container = app.query_one("#messages-container")
                            if messages_container:
                                messages_container.scroll_end(animate=False)
                        except Exception:
                            pass
            except Exception as callback_err:
                logger.error(f"Error in final Ollama UI callback: {str(callback_err)}")
                
        # Final refresh to ensure everything is displayed correctly
        try:
            await asyncio.sleep(0.05)
            async with update_lock:
                await callback(full_response)
                if hasattr(app, 'refresh'):
                    app.refresh(layout=True)
        except Exception:
            pass
            
        return full_response
        
    except asyncio.CancelledError:
        logger.info(f"Ollama streaming cancelled. Partial response length: {len(full_response)}")
        if hasattr(client, 'cancel_stream'):
            await client.cancel_stream()
        return full_response
        
    except Exception as e:
        logger.error(f"Error during Ollama streaming: {str(e)}")
        if hasattr(client, 'cancel_stream'):
            await client.cancel_stream()
        raise

# Generic fallback streaming implementation
async def _generate_generic_stream(
    app: 'SimpleChatApp',
    messages: List[Dict],
    model: str,
    style: str,
    client: Any,
    callback: Callable[[str], Awaitable[None]],
    update_lock: asyncio.Lock
) -> Optional[str]:
    """Generic fallback implementation for streaming responses."""
    try:
        from app.main import debug_log
    except ImportError:
        debug_log = lambda msg: None
    
    debug_log(f"Using generic streaming for model: {model}, client type: {type(client).__name__}")
    
    # Initialize variables for response tracking
    full_response = ""
    buffer = []
    last_update = time.time()
    update_interval = 0.03  # Responsive updates
    
    try:
        # Initialize stream generator
        debug_log("Initializing generic stream generator")
        stream_generator = client.generate_stream(messages, model, style)
        
        # Process stream chunks
        debug_log("Beginning to process generic stream chunks")
        async for chunk in stream_generator:
            # Check for task cancellation
            if asyncio.current_task().cancelled():
                debug_log("Task cancellation detected during generic chunk processing")
                if hasattr(client, 'cancel_stream'):
                    await client.cancel_stream()
                raise asyncio.CancelledError()
                
            # Process chunk content
            if chunk:
                if not isinstance(chunk, str):
                    try:
                        chunk = str(chunk)
                    except Exception:
                        continue
                        
                buffer.append(chunk)
                current_time = time.time()
                
                # Update UI with new content
                if (current_time - last_update >= update_interval or
                    len(''.join(buffer)) > 5 or
                    len(full_response) < 50):
                    
                    new_content = ''.join(buffer)
                    full_response += new_content
                    
                    try:
                        async with update_lock:
                            await callback(full_response)
                            if hasattr(app, 'refresh'):
                                app.refresh(layout=True)
                    except Exception as callback_err:
                        logger.error(f"Error in generic UI callback: {str(callback_err)}")
                        
                    buffer = []
                    last_update = current_time
                    await asyncio.sleep(0.02)
                    
        # Process any remaining buffer content
        if buffer:
            new_content = ''.join(buffer)
            full_response += new_content
            
            try:
                async with update_lock:
                    await callback(full_response)
                    if hasattr(app, 'refresh'):
                        app.refresh(layout=True)
                        await asyncio.sleep(0.02)
                        try:
                            messages_container = app.query_one("#messages-container")
                            if messages_container:
                                messages_container.scroll_end(animate=False)
                        except Exception:
                            pass
            except Exception as callback_err:
                logger.error(f"Error in final generic UI callback: {str(callback_err)}")
                
        # Final refresh to ensure everything is displayed correctly
        try:
            await asyncio.sleep(0.05)
            async with update_lock:
                await callback(full_response)
                if hasattr(app, 'refresh'):
                    app.refresh(layout=True)
        except Exception:
            pass
            
        return full_response
        
    except asyncio.CancelledError:
        logger.info(f"Generic streaming cancelled. Partial response length: {len(full_response)}")
        if hasattr(client, 'cancel_stream'):
            await client.cancel_stream()
        return full_response
        
    except Exception as e:
        logger.error(f"Error during generic streaming: {str(e)}")
        if hasattr(client, 'cancel_stream'):
            await client.cancel_stream()
        raise

# Worker function for streaming response generation
async def generate_streaming_response(
    app: 'SimpleChatApp',
    messages: List[Dict],
    model: str,
    style: str,
    client: Any,
    callback: Callable[[str], Awaitable[None]]
) -> Optional[str]:
    """
    Generate a streaming response from the model (as a Textual worker).
    Refactored to be a coroutine, not an async generator.
    """
    try:
        from app.main import debug_log
    except ImportError:
        debug_log = lambda msg: None

    logger.info(f"Starting streaming response with model: {model}")
    debug_log(f"Starting streaming response with model: '{model}', client type: {type(client).__name__}")

    # Validate messages
    if not messages:
        debug_log("Error: messages list is empty")
        raise ValueError("Messages list cannot be empty")

    # Ensure all messages have required fields
    for i, msg in enumerate(messages):
        try:
            debug_log(f"Message {i}: role={msg.get('role', 'missing')}, content_len={len(msg.get('content', ''))}")
            if 'role' not in msg:
                debug_log(f"Adding missing 'role' to message {i}")
                msg['role'] = 'user'
            if 'content' not in msg:
                debug_log(f"Adding missing 'content' to message {i}")
                msg['content'] = ''
        except Exception as e:
            debug_log(f"Error checking message {i}: {str(e)}")
            messages[i] = {
                'role': 'user',
                'content': str(msg) if msg else ''
            }
            debug_log(f"Repaired message {i}")
            
    # Create a lock for synchronizing UI updates
    update_lock = asyncio.Lock()
    
    # Validate client
    if client is None:
        debug_log("Error: client is None, cannot proceed with streaming")
        raise ValueError("Model client is None, cannot proceed with streaming")

    if not hasattr(client, 'generate_stream'):
        debug_log(f"Error: client {type(client).__name__} does not have generate_stream method")
        raise ValueError(f"Client {type(client).__name__} does not support streaming")

    # Explicitly check provider type first
    is_ollama = 'ollama' in str(type(client)).lower()
    is_openai = 'openai' in str(type(client)).lower()
    is_anthropic = 'anthropic' in str(type(client)).lower()
    
    debug_log(f"Client types - Ollama: {is_ollama}, OpenAI: {is_openai}, Anthropic: {is_anthropic}")
    
    # Use separate implementations for each provider
    try:
        if is_openai:
            debug_log("Using OpenAI-specific streaming implementation")
            return await _generate_openai_stream(app, messages, model, style, client, callback, update_lock)
        elif is_anthropic:
            debug_log("Using Anthropic-specific streaming implementation")
            return await _generate_anthropic_stream(app, messages, model, style, client, callback, update_lock)
        elif is_ollama:
            debug_log("Using Ollama-specific streaming implementation")
            return await _generate_ollama_stream(app, messages, model, style, client, callback, update_lock)
        else:
            # Generic fallback
            debug_log("Using generic streaming implementation")
            return await _generate_generic_stream(app, messages, model, style, client, callback, update_lock)
    except asyncio.CancelledError:
        debug_log("Task cancellation detected in main streaming function")
        if hasattr(client, 'cancel_stream'):
            await client.cancel_stream()
        raise
    except Exception as e:
        debug_log(f"Error in streaming implementation: {str(e)}")
        logger.error(f"Error in streaming implementation: {str(e)}")
        raise

async def ensure_ollama_running() -> bool:
    """
    Check if Ollama is running and try to start it if not.
    Returns True if Ollama is running after check/start attempt.
    """
    import requests
    try:
        logger.info("Checking if Ollama is running...")
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        if response.status_code == 200:
            logger.info("Ollama is running")
            return True
        else:
            logger.warning(f"Ollama returned status code: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        logger.info("Ollama not running, attempting to start...")
        try:
            # Try to start Ollama
            process = subprocess.Popen(
                ["ollama", "serve"], 
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait a moment for it to start
            await asyncio.sleep(2)  # Use asyncio.sleep instead of time.sleep
            
            # Check if process is still running
            if process.poll() is None:
                logger.info("Ollama server started successfully")
                # Check if we can connect
                try:
                    response = requests.get("http://localhost:11434/api/tags", timeout=2)
                    if response.status_code == 200:
                        logger.info("Successfully connected to Ollama")
                        return True
                    else:
                        logger.error(f"Ollama returned status code: {response.status_code}")
                except Exception as e:
                    logger.error(f"Failed to connect to Ollama after starting: {str(e)}")
            else:
                stdout, stderr = process.communicate()
                logger.error(f"Ollama failed to start. stdout: {stdout}, stderr: {stderr}")
        except FileNotFoundError:
            logger.error("Ollama command not found. Please ensure Ollama is installed.")
        except Exception as e:
            logger.error(f"Error starting Ollama: {str(e)}")
    except Exception as e:
        logger.error(f"Error checking Ollama status: {str(e)}")
    
    return False

def save_settings_to_config(model: str, style: str) -> None:
    """Save settings to global config file"""
    logger.info(f"Saving settings to config - model: {model}, style: {style}")
    CONFIG["default_model"] = model
    CONFIG["default_style"] = style
    save_config(CONFIG)

def resolve_model_id(model_id_or_name: str) -> str:
    """
    Resolves a potentially short model ID or display name to the full model ID
    stored in the configuration. Tries multiple matching strategies.
    
    This function is critical for ensuring models are correctly identified by provider.
    """
    if not model_id_or_name:
        logger.warning("resolve_model_id called with empty input, returning empty string.")
        return ""

    input_lower = model_id_or_name.lower().strip()
    logger.info(f"Attempting to resolve model identifier: '{input_lower}'")
    
    # Add special case handling for common OpenAI models
    openai_model_aliases = {
        "04-mini": "gpt-4-mini",  # Fix "04-mini" typo to "gpt-4-mini"
        "04": "gpt-4",
        "04-vision": "gpt-4-vision",
        "04-turbo": "gpt-4-turbo",
        "035": "gpt-3.5-turbo",
        "35-turbo": "gpt-3.5-turbo",
        "35": "gpt-3.5-turbo",
        "4.1-mini": "gpt-4.1-mini",  # Add support for gpt-4.1-mini
        "4.1": "gpt-4.1",  # Add support for gpt-4.1
        # Add support for reasoning models
        "o1": "o1",
        "o1-mini": "o1-mini",
        "o3": "o3",
        "o3-mini": "o3-mini",
        "o4-mini": "o4-mini"
    }
    
    if input_lower in openai_model_aliases:
        resolved = openai_model_aliases[input_lower]
        logger.info(f"Resolved '{input_lower}' to '{resolved}' via OpenAI model alias")
        return resolved
    
    # Special case handling for common typos and model name variations
    typo_corrections = {
        # Keep reasoning models as-is, don't convert 'o' to '0'
        # "o4-mini": "04-mini",
        # "o1": "01",
        # "o1-mini": "01-mini",
        # "o1-preview": "01-preview",
        # "o4": "04",
        # "o4-preview": "04-preview",
        # "o4-vision": "04-vision"
    }
    
    # Don't convert reasoning model IDs that start with 'o'
    # Check for more complex typo patterns with dates
    if input_lower.startswith("o1-") and "-202" in input_lower and not any(input_lower == model_id for model_id in ["o1", "o1-mini", "o3", "o3-mini", "o4-mini"]):
        corrected = "01" + input_lower[2:]
        logger.info(f"Converting '{input_lower}' to '{corrected}' (letter 'o' to zero '0')")
        input_lower = corrected
        model_id_or_name = corrected
    
    # Only apply typo corrections if not a reasoning model
    if input_lower in typo_corrections and not any(input_lower == model_id for model_id in ["o1", "o1-mini", "o3", "o3-mini", "o4-mini"]):
        corrected = typo_corrections[input_lower]
        logger.info(f"Converting '{input_lower}' to '{corrected}' (letter 'o' to zero '0')")
        input_lower = corrected
        model_id_or_name = corrected
    
    # First, check if this is an OpenAI model - if so, return as-is to ensure correct provider
    if any(name in input_lower for name in ["gpt", "text-", "davinci"]):
        logger.info(f"Input '{input_lower}' appears to be an OpenAI model, returning as-is")
        return model_id_or_name
        
    # Next, check if this is an Anthropic model - if so, return as-is to ensure correct provider
    if any(name in input_lower for name in ["claude", "anthropic"]):
        logger.info(f"Input '{input_lower}' appears to be an Anthropic model, returning as-is")
        return model_id_or_name

    available_models = CONFIG.get("available_models", {})
    if not available_models:
         logger.warning("No available_models found in CONFIG to resolve against.")
         return model_id_or_name # Return original if no models to check

    # Determine provider if possible
    provider = None
    if input_lower in available_models:
        provider = available_models[input_lower].get("provider")
        logger.info(f"Found model in available_models with provider: {provider}")
    else:
        # Try to find by display name
        for model_info in available_models.values():
            if model_info.get("display_name", "").lower() == input_lower:
                provider = model_info.get("provider")
                logger.info(f"Found model by display name with provider: {provider}")
                break

    # Special case for Ollama models with version format (model:version)
    if (provider == "ollama" or any(name in input_lower for name in ["llama", "mistral", "codellama", "gemma"])) and ":" in input_lower and not input_lower.startswith("claude-"):
        logger.info(f"Input '{input_lower}' appears to be an Ollama model with version, returning as-is")
        return model_id_or_name

    # Only apply dot-to-colon for Ollama models
    if (provider == "ollama" or any(name in input_lower for name in ["llama", "mistral", "codellama", "gemma"])) and "." in input_lower and not input_lower.startswith("claude-"):
        logger.info(f"Input '{input_lower}' appears to be an Ollama model with dot notation")
        if ":" not in input_lower:
            parts = input_lower.split(".")
            if len(parts) == 2:
                base_model, version = parts
                ollama_format = f"{base_model}:{version}"
                logger.info(f"Converting '{input_lower}' to Ollama format: '{ollama_format}'")
                return ollama_format
        return model_id_or_name

    # 2. Check if the input is already a valid full ID (must contain a date suffix)
    # Full Claude IDs should have format like "claude-3-opus-20240229" with a date suffix
    for full_id in available_models:
        if full_id.lower() == input_lower:
            # Only consider it a full ID if it contains a date suffix (like -20240229)
            if "-202" in full_id:  # Check for date suffix
                logger.info(f"Input '{model_id_or_name}' is already a full ID with date suffix: '{full_id}'.")
                return full_id # Return the canonical full_id
            else:
                logger.warning(f"Input '{model_id_or_name}' matches a model ID but lacks date suffix.")
                # Continue searching for a better match with date suffix

    logger.debug(f"Input '{input_lower}' is not a direct full ID match. Checking other criteria...")
    logger.debug(f"Available models for matching: {list(available_models.keys())}")

    best_match = None
    match_type = "None"

    # 3. Iterate through available models for other matches
    for full_id, model_info in available_models.items():
        full_id_lower = full_id.lower()
        display_name = model_info.get("display_name", "")
        display_name_lower = display_name.lower()

        logger.debug(f"Comparing '{input_lower}' against '{full_id_lower}' (Display: '{display_name}')")

        # 3a. Exact match on display name (case-insensitive)
        if display_name_lower == input_lower:
            logger.info(f"Resolved '{model_id_or_name}' to '{full_id}' via exact display name match.")
            return full_id # Exact display name match is high confidence

        # 3b. Check if input is a known short alias (handle common cases explicitly)
        # Special case for Claude 3.7 Sonnet which seems to be causing issues
        if input_lower == "claude-3.7-sonnet":
            # Hardcoded resolution for this specific model
            claude_37_id = "claude-3-7-sonnet-20250219"
            logger.warning(f"Special case: Directly mapping '{input_lower}' to '{claude_37_id}'")
            # Check if this ID exists in available models
            for model_id in available_models:
                if model_id.lower() == claude_37_id.lower():
                    logger.info(f"Found exact match for hardcoded ID: {model_id}")
                    return model_id
            # If not found in available models, return the hardcoded ID anyway
            logger.warning(f"Hardcoded ID '{claude_37_id}' not found in available models, returning it anyway")
            return claude_37_id
            
        # Map common short names to their expected full ID prefixes
        short_aliases = {
            "claude-3-opus": "claude-3-opus-",
            "claude-3-sonnet": "claude-3-sonnet-",
            "claude-3-haiku": "claude-3-haiku-",
            "claude-3.5-sonnet": "claude-3-5-sonnet-", # Note the dot vs hyphen
            "claude-3.7-sonnet": "claude-3-7-sonnet-"  # Added this specific case
        }
        if input_lower in short_aliases and full_id_lower.startswith(short_aliases[input_lower]):
             logger.info(f"Resolved '{model_id_or_name}' to '{full_id}' via known short alias match.")
             # This is also high confidence
             return full_id

        # 3c. Check if input is a prefix of the full ID (more general, lower confidence)
        if full_id_lower.startswith(input_lower):
            logger.debug(f"Potential prefix match: '{input_lower}' vs '{full_id_lower}'")
            # Don't return immediately, might find a better match (e.g., display name or alias)
            if best_match is None: # Only take prefix if no other match found yet
                 best_match = full_id
                 match_type = "Prefix"
                 logger.debug(f"Setting best_match to '{full_id}' based on prefix.")

        # 3d. Check derived short name from display name (less reliable, keep as lower priority)
        # Normalize display name: lower, replace space and dot with hyphen
        derived_short_name = display_name_lower.replace(" ", "-").replace(".", "-")
        if derived_short_name == input_lower:
             logger.debug(f"Potential derived short name match: '{input_lower}' vs derived '{derived_short_name}' from '{display_name}'")
             # Prioritize this over a simple prefix match if found
             if best_match is None or match_type == "Prefix":
                  best_match = full_id
                  match_type = "Derived Short Name"
                  logger.debug(f"Updating best_match to '{full_id}' based on derived name.")

    # 4. Return best match found or original input
    if best_match:
        logger.info(f"Returning best match found for '{model_id_or_name}': '{best_match}' (Type: {match_type})")
        return best_match
    else:
        logger.warning(f"Could not resolve model ID or name '{model_id_or_name}' to any known full ID. Returning original.")
        return model_id_or_name
