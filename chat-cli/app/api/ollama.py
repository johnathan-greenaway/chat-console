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
            raise Exception(f"Failed to get model details: {str(e)}")
    
    async def list_available_models_from_registry(self, query: str = "") -> List[Dict[str, Any]]:
        """List available models from Ollama registry"""
        logger.info("Fetching available models from Ollama registry")
        try:
            # First try the library endpoint (newer Ollama versions)
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
                                return data.get("models", [])
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
            {
                "name": "llama3",
                "description": "Meta's Llama 3 8B model",
                "model_family": "Llama",
                "size": 4500000000
            },
            {
                "name": "llama3:8b",
                "description": "Meta's Llama 3 8B parameter model",
                "model_family": "Llama",
                "size": 4500000000
            },
            {
                "name": "llama3:70b",
                "description": "Meta's Llama 3 70B parameter model",
                "model_family": "Llama",
                "size": 40000000000
            },
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
            {
                "name": "llava",
                "description": "Multimodal model with vision capabilities",
                "model_family": "LLaVA",
                "size": 4700000000
            },
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
                "name": "phi2",
                "description": "Microsoft's Phi-2 model, small but capable",
                "model_family": "Phi",
                "size": 2800000000
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
