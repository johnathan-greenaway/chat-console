import aiohttp
import asyncio
import json
from typing import List, Dict, Any, Optional, Generator, AsyncGenerator
from .base import BaseModelClient

class OllamaClient(BaseModelClient):
    def __init__(self):
        from ..config import OLLAMA_BASE_URL, AVAILABLE_PROVIDERS
        self.base_url = OLLAMA_BASE_URL.rstrip('/')
        if not AVAILABLE_PROVIDERS["ollama"]:
            raise Exception(f"Ollama server is not running or not accessible at {self.base_url}")
        
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
    
    async def _verify_model_exists(self, model: str) -> bool:
        """Verify that the requested model exists in Ollama"""
        try:
            # Handle built-in models that might not be pulled yet
            if model in ["llama2", "mistral", "codellama", "gemma"]:
                return True
                
            # Check currently available models
            models = self.get_available_models()
            if any(m["id"] == model for m in models):
                return True
                
            # Model not found, try to pull it
            import subprocess
            try:
                subprocess.run(["ollama", "pull", model], 
                             check=True, 
                             capture_output=True,
                             timeout=300)  # 5 minute timeout
                return True
            except subprocess.CalledProcessError as e:
                raise Exception(f"Failed to pull model '{model}': {e.stderr.decode()}")
            except subprocess.TimeoutExpired:
                raise Exception(f"Timed out while pulling model '{model}'")
                
        except Exception as e:
            raise Exception(f"Failed to verify/pull model: {str(e)}")
            
        return False
            
    async def generate_completion(self, messages: List[Dict[str, str]],
                                model: str,
                                style: Optional[str] = None,
                                temperature: float = 0.7,
                                max_tokens: Optional[int] = None) -> str:
        """Generate a text completion using Ollama"""
        # Verify model exists
        if not await self._verify_model_exists(model):
            raise Exception(f"Model '{model}' not found. Please pull it first with 'ollama pull {model}'")
            
        prompt = self._prepare_messages(messages, style)
        retries = 2
        last_error = None
        
        while retries >= 0:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.base_url}/api/generate",
                        json={
                            "model": model,
                            "prompt": prompt,
                            "temperature": temperature,
                            "stream": False
                        },
                        timeout=30  # Add timeout
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
            
            retries -= 1
            if retries >= 0:
                await asyncio.sleep(1)  # Wait before retry
                
        raise Exception(last_error)
    
    async def generate_stream(self, messages: List[Dict[str, str]],
                            model: str,
                            style: Optional[str] = None,
                            temperature: float = 0.7,
                            max_tokens: Optional[int] = None) -> AsyncGenerator[str, None]:
        """Generate a streaming text completion using Ollama"""
        # Verify model exists
        if not await self._verify_model_exists(model):
            raise Exception(f"Model '{model}' not found. Please pull it first with 'ollama pull {model}'")
            
        prompt = self._prepare_messages(messages, style)
        retries = 2
        last_error = None
        
        while retries >= 0:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.base_url}/api/generate",
                        json={
                            "model": model,
                            "prompt": prompt,
                            "temperature": temperature,
                            "stream": True
                        },
                        timeout=30
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
                        return  # Successful completion
                        
            except aiohttp.ClientConnectorError:
                last_error = "Could not connect to Ollama server. Make sure Ollama is running and accessible at " + self.base_url
            except aiohttp.ClientResponseError as e:
                last_error = f"Ollama API error: {e.status} - {e.message}"
            except aiohttp.ClientTimeout:
                last_error = "Request to Ollama server timed out"
            except Exception as e:
                last_error = f"Error streaming completion: {str(e)}"
            
            retries -= 1
            if retries >= 0:
                await asyncio.sleep(1)  # Wait before retry
                
        raise Exception(last_error)
    
    def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available Ollama models"""
        import requests
        from requests.exceptions import RequestException, ConnectionError, Timeout
        
        try:
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=5,
                headers={"Accept": "application/json"}
            )
            response.raise_for_status()
            
            try:
                data = response.json()
            except json.JSONDecodeError:
                raise Exception("Invalid JSON response from Ollama server")
            
            if not isinstance(data, dict):
                raise Exception("Invalid response format: expected object")
            if "models" not in data:
                raise Exception("Invalid response format: missing 'models' key")
            if not isinstance(data["models"], list):
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
            
            return models
            
        except ConnectionError:
            raise Exception(
                f"Could not connect to Ollama server at {self.base_url}. "
                "Please ensure Ollama is running and the URL is correct."
            )
        except Timeout:
            raise Exception(
                f"Connection to Ollama server at {self.base_url} timed out after 5 seconds. "
                "The server might be busy or unresponsive."
            )
        except RequestException as e:
            raise Exception(f"Ollama API error: {str(e)}")
        except Exception as e:
            raise Exception(f"Unexpected error getting models: {str(e)}")
