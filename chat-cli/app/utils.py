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
    # --- Choose a specific, reliable model for title generation ---
    # Prefer Haiku if Anthropic is available, otherwise fallback
    title_model_id = None
    if client and isinstance(client, anthropic.AsyncAnthropic): # Check if the passed client is Anthropic
        # Check if Haiku is listed in the client's available models (more robust)
        available_anthropic_models = client.get_available_models()
        haiku_id = "claude-3-haiku-20240307"
        if any(m["id"] == haiku_id for m in available_anthropic_models):
             title_model_id = haiku_id
             logger.info(f"Using Anthropic Haiku for title generation: {title_model_id}")
        else:
             # If Haiku not found, try Sonnet
             sonnet_id = "claude-3-sonnet-20240229"
             if any(m["id"] == sonnet_id for m in available_anthropic_models):
                  title_model_id = sonnet_id
                  logger.info(f"Using Anthropic Sonnet for title generation: {title_model_id}")
             else:
                  logger.warning(f"Neither Haiku nor Sonnet found in Anthropic client's list. Falling back.")

    # Fallback logic if no specific Anthropic model was found or client is not Anthropic
    if not title_model_id:
        # Use the originally passed model (user's selected chat model) as the final fallback
        title_model_id = model
        logger.warning(f"Falling back to originally selected model for title generation: {title_model_id}")
        # Consider adding fallbacks to OpenAI/Ollama here if needed based on config/availability

    logger.info(f"Generating title for conversation using model: {title_model_id}")

    # Create a special prompt for title generation
    title_prompt = [
        {
            "role": "system", 
            "content": "Generate a brief, descriptive title (maximum 40 characters) for a conversation that starts with the following message. The title should be concise and reflect the main topic or query. Return only the title text with no additional explanation or formatting."
        },
        {
            "role": "user",
            "content": message
        }
    ]
    
    tries = 2  # Number of retries
    last_error = None
    
    while tries > 0:
        try:
            # Generate a title using the same model but with a separate request
            # Assuming client has a method like generate_completion or similar
            # Adjust the method call based on the actual client implementation
            if hasattr(client, 'generate_completion'):
                title = await client.generate_completion(
                    messages=title_prompt,
                    model=title_model_id, # Use the chosen title model
                    temperature=0.7,
                    max_tokens=60  # Titles should be short
                )
            elif hasattr(client, 'generate_stream'): # Fallback or alternative method?
                 # If generate_completion isn't available, maybe adapt generate_stream?
                 # This part needs clarification based on the client's capabilities.
                 # For now, let's assume a hypothetical non-streaming call or adapt stream
                 # Simplified adaptation: collect stream chunks
                 title_chunks = []
                 try:
                     # Use the chosen title model here too
                     async for chunk in client.generate_stream(title_prompt, title_model_id, style=""):
                         if chunk is not None:  # Ensure we only process non-None chunks
                             title_chunks.append(chunk)
                     title = "".join(title_chunks)
                     # If we didn't get any content, use a default
                     if not title.strip():
                         title = f"Conversation ({datetime.now().strftime('%Y-%m-%d %H:%M')})"
                 except Exception as stream_error:
                     logger.error(f"Error during title stream processing: {str(stream_error)}")
                     title = f"Conversation ({datetime.now().strftime('%Y-%m-%d %H:%M')})"
            else:
                 raise NotImplementedError("Client does not support a suitable method for title generation.")

            # Sanitize and limit the title
            title = title.strip().strip('"\'').strip()
            if len(title) > 40:  # Set a maximum title length
                title = title[:37] + "..."
                
            logger.info(f"Generated title: {title}")
            return title # Return successful title
            
        except Exception as e:
            last_error = str(e)
            logger.error(f"Error generating title (tries left: {tries - 1}): {last_error}")
            tries -= 1
            if tries > 0: # Only sleep if there are more retries
                await asyncio.sleep(1)  # Small delay before retry
    
    # If all retries fail, log the last error and return a default title
    logger.error(f"Failed to generate title after multiple retries. Last error: {last_error}")
    return f"Conversation ({datetime.now().strftime('%Y-%m-%d %H:%M')})"

# Make this the worker function directly
@work(exit_on_error=True)
async def generate_streaming_response(
    app: 'SimpleChatApp',
    messages: List[Dict],
    model: str,
    style: str,
    client: Any,
    callback: Callable[[str], Awaitable[None]] # More specific type hint for callback
) -> Optional[str]: # Return Optional[str] as cancellation might return None implicitly or error
    """Generate a streaming response from the model (as a Textual worker)"""
    # Import debug_log function from main
    # Note: This import might be slightly less reliable inside a worker, but let's try
    try:
        from app.main import debug_log
    except ImportError:
        debug_log = lambda msg: None # Fallback

    # Worker function needs to handle its own state and cleanup partially
    # The main app will also need cleanup logic in generate_response

    logger.info(f"Starting streaming response with model: {model}")
    debug_log(f"Starting streaming response with model: '{model}', client type: {type(client).__name__}")
    
    # Very defensive check of messages format
    if not messages:
        debug_log("Error: messages list is empty")
        raise ValueError("Messages list cannot be empty")
    
    for i, msg in enumerate(messages):
        try:
            debug_log(f"Message {i}: role={msg.get('role', 'missing')}, content_len={len(msg.get('content', ''))}")
            # Ensure essential fields exist
            if 'role' not in msg:
                debug_log(f"Adding missing 'role' to message {i}")
                msg['role'] = 'user'  # Default to user
            if 'content' not in msg:
                debug_log(f"Adding missing 'content' to message {i}")
                msg['content'] = ''  # Default to empty string
        except Exception as e:
            debug_log(f"Error checking message {i}: {str(e)}")
            # Try to repair the message
            messages[i] = {
                'role': 'user',
                'content': str(msg) if msg else ''
            }
            debug_log(f"Repaired message {i}")
    
    debug_log(f"Messages validation complete: {len(messages)} total messages")
    
    # Import time module within the worker function scope
    import time
    
    full_response = ""
    buffer = []
    last_update = time.time()
    update_interval = 0.1  # Update UI every 100ms
    
    try:
        # Check that we have a valid client and model before proceeding
        if client is None:
            debug_log("Error: client is None, cannot proceed with streaming")
            raise ValueError("Model client is None, cannot proceed with streaming")
            
        # Check if the client has the required generate_stream method
        if not hasattr(client, 'generate_stream'):
            debug_log(f"Error: client {type(client).__name__} does not have generate_stream method")
            raise ValueError(f"Client {type(client).__name__} does not support streaming")
            
        # Set initial model loading state if using Ollama
        # Always show the model loading indicator for Ollama until we confirm otherwise
        is_ollama = 'ollama' in str(type(client)).lower()
        debug_log(f"Is Ollama client: {is_ollama}")
        
        if is_ollama and hasattr(app, 'query_one'):
            try:
                # Show model loading indicator by default for Ollama
                debug_log("Showing initial model loading indicator for Ollama")
                logger.info("Showing initial model loading indicator for Ollama")
                loading = app.query_one("#loading-indicator")
                loading.add_class("model-loading")
                loading.update("⚙️ Loading Ollama model...")
            except Exception as e:
                debug_log(f"Error setting initial Ollama loading state: {str(e)}")
                logger.error(f"Error setting initial Ollama loading state: {str(e)}")
        
        # Now proceed with streaming
        debug_log(f"Starting stream generation with messages length: {len(messages)}")
        logger.info(f"Starting stream generation for model: {model}")
        
        # Defensive approach - wrap the stream generation in a try-except
        try:
            debug_log("Calling client.generate_stream()")
            stream_generator = client.generate_stream(messages, model, style)
            debug_log("Successfully obtained stream generator")
        except Exception as stream_init_error:
            debug_log(f"Error initializing stream generator: {str(stream_init_error)}")
            logger.error(f"Error initializing stream generator: {str(stream_init_error)}")
            raise  # Re-raise to be handled in the main catch block
        
        # After getting the generator, check if we're NOT in model loading state
        if hasattr(client, 'is_loading_model') and not client.is_loading_model() and hasattr(app, 'query_one'):
            try:
                debug_log("Model is ready for generation, updating UI")
                logger.info("Model is ready for generation, updating UI")
                loading = app.query_one("#loading-indicator")
                loading.remove_class("model-loading")
                loading.update("▪▪▪ Generating response...")
            except Exception as e:
                debug_log(f"Error updating UI after stream init: {str(e)}")
                logger.error(f"Error updating UI after stream init: {str(e)}")
        
        # Process the stream with careful error handling
        debug_log("Beginning to process stream chunks")
        try:
            async for chunk in stream_generator:
                # Check for cancellation frequently
                if asyncio.current_task().cancelled():
                    debug_log("Task cancellation detected during chunk processing")
                    logger.info("Task cancellation detected during chunk processing")
                    # Close the client stream if possible
                    if hasattr(client, 'cancel_stream'):
                        debug_log("Calling client.cancel_stream() due to task cancellation")
                        await client.cancel_stream()
                    raise asyncio.CancelledError()
                    
                # Check if model loading state changed, but more safely
                if hasattr(client, 'is_loading_model'):
                    try:
                        # Get the model loading state
                        model_loading = client.is_loading_model()
                        debug_log(f"Model loading state: {model_loading}")
                        
                        # Safely update the UI elements if they exist
                        if hasattr(app, 'query_one'):
                            try:
                                loading = app.query_one("#loading-indicator")
                                
                                # Check for class existence first
                                if model_loading and hasattr(loading, 'has_class') and not loading.has_class("model-loading"):
                                    # Model loading started
                                    debug_log("Model loading started during streaming")
                                    logger.info("Model loading started during streaming")
                                    loading.add_class("model-loading")
                                    loading.update("⚙️ Loading Ollama model...")
                                elif not model_loading and hasattr(loading, 'has_class') and loading.has_class("model-loading"):
                                    # Model loading finished
                                    debug_log("Model loading finished during streaming")
                                    logger.info("Model loading finished during streaming")
                                    loading.remove_class("model-loading")
                                    loading.update("▪▪▪ Generating response...")
                            except Exception as ui_e:
                                debug_log(f"Error updating UI elements: {str(ui_e)}")
                                logger.error(f"Error updating UI elements: {str(ui_e)}")
                    except Exception as e:
                        debug_log(f"Error checking model loading state: {str(e)}")
                        logger.error(f"Error checking model loading state: {str(e)}")
                
                # Process the chunk - with careful type handling
                if chunk:  # Only process non-empty chunks
                    # Ensure chunk is a string - critical fix for providers returning other types
                    if not isinstance(chunk, str):
                        debug_log(f"WARNING: Received non-string chunk of type: {type(chunk).__name__}")
                        try:
                            # Try to convert to string if possible
                            chunk = str(chunk)
                            debug_log(f"Successfully converted chunk to string, length: {len(chunk)}")
                        except Exception as e:
                            debug_log(f"Error converting chunk to string: {str(e)}")
                            # Skip this chunk since it can't be converted
                            continue
                    
                    debug_log(f"Received chunk of length: {len(chunk)}")
                    buffer.append(chunk)
                    current_time = time.time()
                    
                    # Update UI if enough time has passed or buffer is large
                    if current_time - last_update >= update_interval or len(''.join(buffer)) > 100:
                        new_content = ''.join(buffer)
                        full_response += new_content
                        # Send content to UI
                        debug_log(f"Updating UI with content length: {len(full_response)}")
                        await callback(full_response)
                        buffer = []
                        last_update = current_time
                        
                        # Small delay to let UI catch up
                        await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            debug_log("CancelledError in stream processing")
            raise
        except Exception as chunk_error:
            debug_log(f"Error processing stream chunks: {str(chunk_error)}")
            logger.error(f"Error processing stream chunks: {str(chunk_error)}")
            raise

        # Send any remaining content if the loop finished normally
        if buffer:
            new_content = ''.join(buffer)
            full_response += new_content
            debug_log(f"Sending final content, total length: {len(full_response)}")
            await callback(full_response)

        debug_log(f"Streaming response completed successfully. Response length: {len(full_response)}")
        logger.info(f"Streaming response completed successfully. Response length: {len(full_response)}")
        return full_response
        
    except asyncio.CancelledError:
        # This is expected when the user cancels via Escape
        debug_log(f"Streaming response task cancelled. Partial response length: {len(full_response)}")
        logger.info(f"Streaming response task cancelled. Partial response length: {len(full_response)}")
        # Ensure the client stream is closed
        if hasattr(client, 'cancel_stream'):
            debug_log("Calling client.cancel_stream() after cancellation")
            try:
                await client.cancel_stream()
                debug_log("Successfully cancelled client stream")
            except Exception as cancel_err:
                debug_log(f"Error cancelling client stream: {str(cancel_err)}")
        # Return whatever was collected so far
        return full_response
        
    except Exception as e:
        debug_log(f"Error during streaming response: {str(e)}")
        logger.error(f"Error during streaming response: {str(e)}")
        # Close the client stream if possible
        if hasattr(client, 'cancel_stream'):
            debug_log("Attempting to cancel client stream after error")
            try:
                await client.cancel_stream()
                debug_log("Successfully cancelled client stream after error")
            except Exception as cancel_err:
                debug_log(f"Error cancelling client stream after error: {str(cancel_err)}")
        # Re-raise the exception for the worker runner to handle
        # The @work decorator might catch this depending on exit_on_error
        raise
    finally:
        # Basic cleanup within the worker itself (optional, main cleanup in app)
        debug_log("generate_streaming_response worker finished or errored.")
        # Return the full response if successful, otherwise error is raised or cancellation occurred
        # Note: If cancelled, CancelledError is raised, and @work might handle it.
        # If successful, return the response.
        # If error, exception is raised.
        # Let's explicitly return the response on success.
        # If cancelled or error, this return might not be reached.
        if 'full_response' in locals():
             return full_response
        return None # Indicate completion without full response (e.g., error before loop)

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
    """
    if not model_id_or_name:
        logger.warning("resolve_model_id called with empty input, returning empty string.")
        return ""

    input_lower = model_id_or_name.lower().strip()
    logger.info(f"Attempting to resolve model identifier: '{input_lower}'")

    available_models = CONFIG.get("available_models", {})
    if not available_models:
         logger.warning("No available_models found in CONFIG to resolve against.")
         return model_id_or_name # Return original if no models to check

    # 1. Check if the input is already a valid full ID (must contain a date suffix)
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

    # 2. Iterate through available models for other matches
    for full_id, model_info in available_models.items():
        full_id_lower = full_id.lower()
        display_name = model_info.get("display_name", "")
        display_name_lower = display_name.lower()

        logger.debug(f"Comparing '{input_lower}' against '{full_id_lower}' (Display: '{display_name}')")

        # 2a. Exact match on display name (case-insensitive)
        if display_name_lower == input_lower:
            logger.info(f"Resolved '{model_id_or_name}' to '{full_id}' via exact display name match.")
            return full_id # Exact display name match is high confidence

        # 2b. Check if input is a known short alias (handle common cases explicitly)
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

        # 2c. Check if input is a prefix of the full ID (more general, lower confidence)
        if full_id_lower.startswith(input_lower):
            logger.debug(f"Potential prefix match: '{input_lower}' vs '{full_id_lower}'")
            # Don't return immediately, might find a better match (e.g., display name or alias)
            if best_match is None: # Only take prefix if no other match found yet
                 best_match = full_id
                 match_type = "Prefix"
                 logger.debug(f"Setting best_match to '{full_id}' based on prefix.")

        # 2d. Check derived short name from display name (less reliable, keep as lower priority)
        # Normalize display name: lower, replace space and dot with hyphen
        derived_short_name = display_name_lower.replace(" ", "-").replace(".", "-")
        if derived_short_name == input_lower:
             logger.debug(f"Potential derived short name match: '{input_lower}' vs derived '{derived_short_name}' from '{display_name}'")
             # Prioritize this over a simple prefix match if found
             if best_match is None or match_type == "Prefix":
                  best_match = full_id
                  match_type = "Derived Short Name"
                  logger.debug(f"Updating best_match to '{full_id}' based on derived name.")

    # 3. Return best match found or original input
    if best_match:
        logger.info(f"Returning best match found for '{model_id_or_name}': '{best_match}' (Type: {match_type})")
        return best_match
    else:
        logger.warning(f"Could not resolve model ID or name '{model_id_or_name}' to any known full ID. Returning original.")
        return model_id_or_name
