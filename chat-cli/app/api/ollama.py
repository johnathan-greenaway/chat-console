import aiohttp
import asyncio
import json
import logging
from typing import List, Dict, Any, Optional, Generator, AsyncGenerator
from .base import BaseModelClient

# Set up logging
logger = logging.getLogger(__name__)

class OllamaClient(BaseModelClient):
    def __init__(self):
        from ..config import OLLAMA_BASE_URL
        from ..utils import ensure_ollama_running
        self.base_url = OLLAMA_BASE_URL.rstrip('/')
        logger.info(f"Initializing Ollama client with base URL: {self.base_url}")
        
        # Try to start Ollama if not running
        if not ensure_ollama_running():
            raise Exception(f"Failed to start Ollama server. Please ensure Ollama is installed and try again.")
        
    def _prepare_messages(self, messages: List[Dict[str, str]], style: Optional[str] = None) -> str:
        """Convert chat messages to Ollama format"""
        # Start with any style instructions
        formatted_messages = []
        if style and style != "default":
            formatted_messages.append(self._get_style_instructions(style))
            
        # Add message content, preserving conversation flow
        for msg in messages:
            formatted_messages.append(msg["content"])
            
        # Join with double newlines for better readability
        return "\n\n".join(formatted_messages)
    
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
                    async with session.post(
                        f"{self.base_url}/api/generate",
                        json={
                            "model": model,
                            "prompt": prompt,
                            "temperature": temperature,
                            "stream": False
                        },
                        timeout=30
                    ) as response:
                        response.raise_for_status()
                        data = await response.json()
                        if "response" not in data:
                            raise Exception("Invalid response format from Ollama server")
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
        prompt = self._prepare_messages(messages, style)
        retries = 2
        last_error = None
        
        while retries >= 0:
            try:
                # First try a quick test request to check if model is loaded
                async with aiohttp.ClientSession() as session:
                    try:
                        logger.info("Testing model availability...")
                        async with session.post(
                            f"{self.base_url}/api/generate",
                            json={
                                "model": model,
                                "prompt": "test",
                                "temperature": temperature,
                                "stream": False
                            },
                            timeout=2
                        ) as response:
                            if response.status != 200:
                                logger.warning(f"Model test request failed with status {response.status}")
                                raise aiohttp.ClientError("Model not ready")
                    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                        logger.info(f"Model cold start detected: {str(e)}")
                        # Model might need loading, try pulling it
                        async with session.post(
                            f"{self.base_url}/api/pull",
                            json={"name": model},
                            timeout=60
                        ) as pull_response:
                            if pull_response.status != 200:
                                logger.error("Failed to pull model")
                                raise Exception("Failed to pull model")
                            logger.info("Model pulled successfully")
                
                # Now proceed with actual generation
                async with aiohttp.ClientSession() as session:
                    logger.debug(f"Sending streaming request to {self.base_url}/api/generate")
                    async with session.post(
                        f"{self.base_url}/api/generate",
                        json={
                            "model": model,
                            "prompt": prompt,
                            "temperature": temperature,
                            "stream": True
                        },
                        timeout=60  # Longer timeout for actual generation
                    ) as response:
                        response.raise_for_status()
                        async for line in response.content:
                            if line:
                                chunk = line.decode().strip()
                                try:
                                    data = json.loads(chunk)
                                    if "response" in data:
                                        yield data["response"]
                                except json.JSONDecodeError:
                                    continue
                        logger.info("Streaming completed successfully")
                        return
                        
            except aiohttp.ClientConnectorError:
                last_error = "Could not connect to Ollama server. Make sure Ollama is running and accessible at " + self.base_url
            except aiohttp.ClientResponseError as e:
                last_error = f"Ollama API error: {e.status} - {e.message}"
            except aiohttp.ClientTimeout:
                last_error = "Request to Ollama server timed out"
            except Exception as e:
                last_error = f"Error streaming completion: {str(e)}"
            
            logger.error(f"Streaming attempt failed: {last_error}")
            retries -= 1
            if retries >= 0:
                logger.info(f"Retrying stream... {retries} attempts remaining")
                await asyncio.sleep(1)
                
        raise Exception(last_error)
