import os
import json
import time
import asyncio
import subprocess
import logging
from typing import Optional, Dict, Any, List, TYPE_CHECKING
from datetime import datetime
from .config import CONFIG, save_config

# Import SimpleChatApp for type hinting only if TYPE_CHECKING is True
if TYPE_CHECKING:
    from .main import SimpleChatApp

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def generate_conversation_title(message: str, model: str, client: Any) -> str:
    """Generate a descriptive title for a conversation based on the first message"""
    logger.info(f"Generating title for conversation using model: {model}")
    
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
                    model=model,
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
                     async for chunk in client.generate_stream(title_prompt, model, style=""): # Assuming style might not apply or needs default
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

# Modified signature to accept app instance
async def generate_streaming_response(app: 'SimpleChatApp', messages: List[Dict], model: str, style: str, client: Any, callback: Any) -> str:
    """Generate a streaming response from the model"""
    logger.info(f"Starting streaming response with model: {model}")
    full_response = ""
    buffer = []
    last_update = time.time()
    update_interval = 0.1  # Update UI every 100ms
    
    try:
        # Set initial model loading state if using Ollama
        # Always show the model loading indicator for Ollama until we confirm otherwise
        is_ollama = 'ollama' in str(type(client)).lower()
        
        if is_ollama and hasattr(app, 'query_one'):
            try:
                # Show model loading indicator by default for Ollama
                logger.info("Showing initial model loading indicator for Ollama")
                loading = app.query_one("#loading-indicator")
                loading.add_class("model-loading")
                loading.update("⚙️ Loading Ollama model...")
            except Exception as e:
                logger.error(f"Error setting initial Ollama loading state: {str(e)}")
        
        # Now proceed with streaming
        logger.info(f"Starting stream generation for model: {model}")
        stream_generator = client.generate_stream(messages, model, style)
        
        # After getting the generator, check if we're NOT in model loading state
        if hasattr(client, 'is_loading_model') and not client.is_loading_model() and hasattr(app, 'query_one'):
            try:
                logger.info("Model is ready for generation, updating UI")
                loading = app.query_one("#loading-indicator")
                loading.remove_class("model-loading")
                loading.update("[▪▪▪ Generating response...]")
            except Exception as e:
                logger.error(f"Error updating UI after stream init: {str(e)}")
        
        # Use asyncio.shield to ensure we can properly interrupt the stream processing
        async for chunk in stream_generator:
            # Check for cancellation frequently
            if asyncio.current_task().cancelled():
                logger.info("Task cancellation detected during chunk processing")
                # Close the client stream if possible
                if hasattr(client, 'cancel_stream'):
                    await client.cancel_stream()
                raise asyncio.CancelledError()
                
            # Check if model loading state changed, but more safely
            if hasattr(client, 'is_loading_model'):
                try:
                    # Get the model loading state
                    model_loading = client.is_loading_model()
                    
                    # Safely update the UI elements if they exist
                    if hasattr(app, 'query_one'):
                        try:
                            loading = app.query_one("#loading-indicator")
                            
                            # Check for class existence first
                            if model_loading and hasattr(loading, 'has_class') and not loading.has_class("model-loading"):
                                # Model loading started
                                logger.info("Model loading started during streaming")
                                loading.add_class("model-loading")
                                loading.update("⚙️ Loading Ollama model...")
                            elif not model_loading and hasattr(loading, 'has_class') and loading.has_class("model-loading"):
                                # Model loading finished
                                logger.info("Model loading finished during streaming")
                                loading.remove_class("model-loading")
                                loading.update("▪▪▪ Generating response...")
                        except Exception as ui_e:
                            logger.error(f"Error updating UI elements: {str(ui_e)}")
                except Exception as e:
                    logger.error(f"Error checking model loading state: {str(e)}")
                
            if chunk:  # Only process non-empty chunks
                buffer.append(chunk)
                current_time = time.time()
                
                # Update UI if enough time has passed or buffer is large
                if current_time - last_update >= update_interval or len(''.join(buffer)) > 100:
                    new_content = ''.join(buffer)
                    full_response += new_content
                    # Send content to UI
                    await callback(full_response)
                    buffer = []
                    last_update = current_time
                    
                    # Small delay to let UI catch up
                    await asyncio.sleep(0.05)

        # Send any remaining content if the loop finished normally
        if buffer:
            new_content = ''.join(buffer)
            full_response += new_content
            await callback(full_response)

        logger.info(f"Streaming response completed successfully. Response length: {len(full_response)}")
        return full_response
        
    except asyncio.CancelledError:
        # This is expected when the user cancels via Escape
        logger.info(f"Streaming response task cancelled. Partial response length: {len(full_response)}")
        # Ensure the client stream is closed
        if hasattr(client, 'cancel_stream'):
            await client.cancel_stream()
        # Return whatever was collected so far
        return full_response
        
    except Exception as e:
        logger.error(f"Error during streaming response: {str(e)}")
        # Close the client stream if possible
        if hasattr(client, 'cancel_stream'):
            await client.cancel_stream()
        # Re-raise the exception for the caller to handle
        raise

def ensure_ollama_running() -> bool:
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
            import time
            time.sleep(2)
            
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
