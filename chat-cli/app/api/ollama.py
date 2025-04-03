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
        
        # Track active stream session
        self._active_stream_session = None
        
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
        self._active_stream_session = None  # Track the active session
        
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
                session = aiohttp.ClientSession()
                self._active_stream_session = session  # Store reference to active session
                
                try:
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
                finally:
                    self._active_stream_session = None  # Clear reference when done
                    await session.close()  # Ensure session is closed
                        
            except aiohttp.ClientConnectorError:
                last_error = "Could not connect to Ollama server. Make sure Ollama is running and accessible at " + self.base_url
            except aiohttp.ClientResponseError as e:
                last_error = f"Ollama API error: {e.status} - {e.message}"
            except aiohttp.ClientTimeout:
                last_error = "Request to Ollama server timed out"
            except asyncio.CancelledError:
                logger.info("Streaming cancelled by client")
                raise  # Propagate cancellation
            except Exception as e:
                last_error = f"Error streaming completion: {str(e)}"
            
            logger.error(f"Streaming attempt failed: {last_error}")
            retries -= 1
            if retries >= 0:
                logger.info(f"Retrying stream... {retries} attempts remaining")
                await asyncio.sleep(1)
                
        raise Exception(last_error)
        
    async def cancel_stream(self) -> None:
        """Cancel any active streaming request"""
        if self._active_stream_session:
            logger.info("Cancelling active stream session")
            await self._active_stream_session.close()
            self._active_stream_session = None
            
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
    
    async def list_available_models_from_registry(self, query: str = "") -> List[Dict[str, Any]]:
        """List available models from Ollama registry"""
        logger.info("Fetching available models from Ollama registry")
        try:
            # First try to scrape the Ollama website for better model data
            try:
                async with aiohttp.ClientSession() as session:
                    # Try to get model data from the Ollama website search page
                    search_url = "https://ollama.com/search"
                    if query:
                        search_url += f"?q={query}"
                    
                    logger.info(f"Fetching models from Ollama web: {search_url}")
                    async with session.get(
                        search_url,
                        timeout=10,
                        headers={"User-Agent": "Mozilla/5.0 (compatible; chat-console/1.0)"}
                    ) as response:
                        if response.status == 200:
                            html = await response.text()
                            
                            # Extract model data from JSON embedded in the page
                            # The data is in a script tag with JSON containing model information
                            try:
                                import re
                                import json
                                
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
                                        processed_models = []
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
                                                
                                                processed_models.append(processed_model)
                                            except Exception as e:
                                                logger.warning(f"Error processing web model {model.get('name', 'unknown')}: {str(e)}")
                                                
                                        if processed_models:
                                            logger.info(f"Successfully processed {len(processed_models)} models from Ollama website")
                                            return processed_models
                            except Exception as e:
                                logger.warning(f"Error extracting model data from Ollama website: {str(e)}")
            except Exception as web_e:
                logger.warning(f"Error fetching from Ollama website: {str(web_e)}")
            
            # Next try the library endpoint (newer Ollama versions)
            try:
                async with aiohttp.ClientSession() as session:
                    url = f"{self.base_url}/api/library"
                    if query:
                        url += f"?query={query}"
                    async with session.get(
                        url,
                        timeout=10
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            logger.debug(f"Ollama library response: {data}")
                            if "models" in data:
                                # If this succeeded, we'll use registry models instead of the curated list
                                # Ensure models have all the needed fields
                                registry_models = data.get("models", [])
                                
                                # Create a new list to store processed models
                                processed_models = []
                                
                                for model in registry_models:
                                    if "name" not in model:
                                        continue
                                    
                                    # Process the model
                                    try:
                                        # Add default values for missing fields to avoid UNKNOWN displays
                                        if "model_family" not in model:
                                            try:
                                                # Try to infer family from name
                                                name = str(model["name"]).lower() if isinstance(model["name"], (str, int, float)) else ""
                                                if "llama" in name:
                                                    model["model_family"] = "Llama"
                                                elif "mistral" in name:
                                                    model["model_family"] = "Mistral"
                                                elif "phi" in name:
                                                    model["model_family"] = "Phi"
                                                elif "gemma" in name:
                                                    model["model_family"] = "Gemma"
                                                else:
                                                    model["model_family"] = "General"
                                            except (KeyError, TypeError, ValueError) as e:
                                                logger.warning(f"Error inferring model family: {str(e)}")
                                                model["model_family"] = "General"
                                        
                                        try:
                                            if "description" not in model or not model["description"]:
                                                model_name = str(model["name"]) if isinstance(model["name"], (str, int, float)) else "Unknown"
                                                model["description"] = f"{model_name} model"
                                        except (KeyError, TypeError, ValueError) as e:
                                            logger.warning(f"Error setting model description: {str(e)}")
                                            model["description"] = "Model description unavailable"
                                            
                                        # Ensure size is present and has a reasonable value
                                        if "size" not in model or not model["size"] or model["size"] == 0:
                                            # Set a reasonable default size based on model name
                                            try:
                                                name = str(model["name"]).lower() if isinstance(model["name"], (str, int, float)) else ""
                                                if "70b" in name or "65b" in name:
                                                    model["size"] = 40000000000  # 40GB for 70B models
                                                elif "405b" in name or "400b" in name:
                                                    model["size"] = 200000000000  # 200GB for 405B models
                                                elif "34b" in name or "35b" in name:
                                                    model["size"] = 20000000000  # 20GB for 34B models
                                                elif "27b" in name or "28b" in name:
                                                    model["size"] = 15000000000  # 15GB for 27B models
                                                elif "13b" in name or "14b" in name:
                                                    model["size"] = 8000000000   # 8GB for 13B models
                                                elif "7b" in name or "8b" in name:
                                                    model["size"] = 4500000000   # 4.5GB for 7-8B models
                                                elif "6b" in name:
                                                    model["size"] = 3500000000   # 3.5GB for 6B models
                                                elif "3b" in name:
                                                    model["size"] = 2000000000   # 2GB for 3B models
                                                elif "1b" in name or "2b" in name:
                                                    model["size"] = 1500000000   # 1.5GB for 1-2B models
                                                else:
                                                    model["size"] = 4500000000   # Default to 4.5GB if unknown
                                            except (KeyError, TypeError, ValueError) as e:
                                                logger.warning(f"Error setting model size: {str(e)}")
                                                model["size"] = 4500000000  # Default fallback size
                                        
                                        # Add parameter_size field based on model name
                                        if "parameter_size" not in model:
                                            try:
                                                name = str(model["name"]).lower() if isinstance(model["name"], (str, int, float)) else ""
                                                if "70b" in name:
                                                    model["parameter_size"] = "70B"
                                                elif "405b" in name or "400b" in name:
                                                    model["parameter_size"] = "405B"
                                                elif "34b" in name or "35b" in name:
                                                    model["parameter_size"] = "34B"
                                                elif "27b" in name or "28b" in name:
                                                    model["parameter_size"] = "27B"
                                                elif "13b" in name or "14b" in name:
                                                    model["parameter_size"] = "13B"
                                                elif "8b" in name:
                                                    model["parameter_size"] = "8B"
                                                elif "7b" in name:
                                                    model["parameter_size"] = "7B"
                                                elif "6b" in name:
                                                    model["parameter_size"] = "6B"
                                                elif "3b" in name:
                                                    model["parameter_size"] = "3B"
                                                elif "2b" in name:
                                                    model["parameter_size"] = "2B"
                                                elif "1b" in name:
                                                    model["parameter_size"] = "1B"
                                                elif "mini" in name:
                                                    model["parameter_size"] = "3B"
                                                elif "small" in name:
                                                    model["parameter_size"] = "7B"
                                                elif "medium" in name:
                                                    model["parameter_size"] = "13B"
                                                elif "large" in name:
                                                    model["parameter_size"] = "34B"
                                                else:
                                                    model["parameter_size"] = "Unknown"
                                            except (KeyError, TypeError, ValueError) as e:
                                                logger.warning(f"Error setting parameter size: {str(e)}")
                                                model["parameter_size"] = "Unknown"
                                            
                                        # Add to processed models list
                                        processed_models.append(model)
                                    except Exception as e:
                                        logger.warning(f"Error processing model {model.get('name', 'unknown')}: {str(e)}")
                                    
                                return processed_models
            except Exception as lib_e:
                logger.warning(f"Error using /api/library endpoint: {str(lib_e)}, falling back to /api/tags")
                
            # Fallback to tags endpoint (older Ollama versions)
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/api/tags"
                if query:
                    url += f"?query={query}"
                async with session.get(
                    url,
                    timeout=10
                ) as response:
                    response.raise_for_status()
                    data = await response.json()
                    logger.debug(f"Ollama registry response: {data}")
                    
                    if "models" in data:
                        # This is local models, not registry models
                        # Return empty list since we can't get registry models
                        logger.warning("Tags endpoint returned local models, not registry models")
                        return []
                    
                    # Try to determine if we're dealing with an older version
                    # Just return an empty list in this case
                    return []
        except Exception as e:
            logger.error(f"Error listing registry models: {str(e)}")
            raise Exception(f"Failed to list models from registry: {str(e)}")
            
    async def get_registry_models(self, query: str = "") -> List[Dict[str, Any]]:
        """Get a curated list of popular Ollama models"""
        logger.info("Returning a curated list of popular Ollama models")
        
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
