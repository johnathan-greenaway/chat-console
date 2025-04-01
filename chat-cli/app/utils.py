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
                 async for chunk in client.generate_stream(title_prompt, model, style=""): # Assuming style might not apply or needs default
                     title_chunks.append(chunk)
                 title = "".join(title_chunks)
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
    generation_task = None
    
    try:
        # Store reference to the active stream generation task
        stream_gen = client.generate_stream(messages, model, style)
        
        # Check for cancellation
        async def check_cancellation():
            while app.is_generating:
                await asyncio.sleep(0.1)  # Check every 100ms
            # If we exit the loop, generation was cancelled
            logger.info("Cancellation check detected is_generating = False")
            
            # Cancel the actual network request in the client
            if hasattr(client, 'cancel_stream'):
                logger.info("Calling client.cancel_stream()")
                await client.cancel_stream()
            
            # Cancel our generation task if it exists
            if generation_task and not generation_task.done():
                logger.info("Cancelling generation task")
                generation_task.cancel()
        
        # Start the cancellation checker in the background
        cancellation_task = asyncio.create_task(check_cancellation())
        
        try:
            async for chunk in stream_gen:
                # Check if generation was cancelled by the app (e.g., via escape key)
                if not app.is_generating:
                    logger.info("Generation cancelled by app flag.")
                    break  # Exit the loop immediately

                if chunk:  # Only process non-empty chunks
                    buffer.append(chunk)
                    current_time = time.time()
                    
                    # Update UI if enough time has passed or buffer is large
                    if current_time - last_update >= update_interval or len(''.join(buffer)) > 100:
                        new_content = ''.join(buffer)
                        full_response += new_content
                        # Check again before calling callback, in case it was cancelled during chunk processing
                        if not app.is_generating:
                            logger.info("Generation cancelled before UI update.")
                            break
                        await callback(full_response)
                        buffer = []
                        last_update = current_time
                        
                        # Small delay to let UI catch up
                        await asyncio.sleep(0.05)
            
            # Send any remaining content if generation wasn't cancelled
            if buffer and app.is_generating:
                new_content = ''.join(buffer)
                full_response += new_content
                await callback(full_response)
            
            if app.is_generating:
                logger.info("Streaming response completed normally.")
            else:
                logger.info("Streaming response loop exited due to cancellation.")
                
            return full_response
            
        except asyncio.CancelledError:
            logger.info("Stream generation was cancelled")
            raise
        finally:
            # Clean up cancellation task
            if not cancellation_task.done():
                cancellation_task.cancel()
                try:
                    await cancellation_task
                except asyncio.CancelledError:
                    pass
                
    except Exception as e:
        logger.error(f"Error in streaming response: {str(e)}")
        # Ensure the app knows generation stopped on error
        app.is_generating = False
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
