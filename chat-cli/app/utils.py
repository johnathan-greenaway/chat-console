import os
import json
import time
import asyncio
import subprocess
import logging
from typing import Optional, Dict, Any, List
from .config import CONFIG, save_config

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def generate_streaming_response(messages: List[Dict], model: str, style: str, client: Any, callback: Any) -> str:
    """Generate a streaming response from the model"""
    logger.info(f"Starting streaming response with model: {model}")
    full_response = ""
    buffer = []
    last_update = time.time()
    update_interval = 0.1  # Update UI every 100ms
    
    try:
        async for chunk in client.generate_stream(messages, model, style):
            if chunk:  # Only process non-empty chunks
                buffer.append(chunk)
                current_time = time.time()
                
                # Update UI if enough time has passed or buffer is large
                if current_time - last_update >= update_interval or len(''.join(buffer)) > 100:
                    new_content = ''.join(buffer)
                    full_response += new_content
                    await callback(full_response)
                    buffer = []
                    last_update = current_time
                    
                    # Small delay to let UI catch up
                    await asyncio.sleep(0.05)
        
        # Send any remaining content
        if buffer:
            new_content = ''.join(buffer)
            full_response += new_content
            await callback(full_response)
        
        logger.info("Streaming response completed")
        return full_response
    except Exception as e:
        logger.error(f"Error in streaming response: {str(e)}")
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
