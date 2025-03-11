import aiohttp
import json
from typing import List, Dict, Any, Optional, Generator, AsyncGenerator
from .base import BaseModelClient
from ..config import CONFIG

class OllamaClient(BaseModelClient):
    def __init__(self):
        self.base_url = "http://localhost:11434"
        
    def _prepare_messages(self, messages: List[Dict[str, str]], style: Optional[str] = None) -> str:
        """Convert chat messages to Ollama format"""
        # Convert messages to a single string with role prefixes
        formatted_messages = []
        
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            
            if role == "system":
                formatted_messages.append(f"System: {content}")
            elif role == "user":
                formatted_messages.append(f"Human: {content}")
            elif role == "assistant":
                formatted_messages.append(f"Assistant: {content}")
                
        # Add style instructions if provided
        if style and style != "default":
            style_instructions = self._get_style_instructions(style)
            formatted_messages.insert(0, f"System: {style_instructions}")
            
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
    
    async def generate_completion(self, messages: List[Dict[str, str]], 
                                model: str, 
                                style: Optional[str] = None, 
                                temperature: float = 0.7, 
                                max_tokens: Optional[int] = None) -> str:
        """Generate a text completion using Ollama"""
        prompt = self._prepare_messages(messages, style)
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "temperature": temperature,
                    "stream": False
                }
            ) as response:
                response.raise_for_status()
                data = await response.json()
                return data["response"]
    
    async def generate_stream(self, messages: List[Dict[str, str]], 
                            model: str, 
                            style: Optional[str] = None,
                            temperature: float = 0.7, 
                            max_tokens: Optional[int] = None) -> AsyncGenerator[str, None]:
        """Generate a streaming text completion using Ollama"""
        prompt = self._prepare_messages(messages, style)
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "temperature": temperature,
                    "stream": True
                }
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
    
    async def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available Ollama models"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/api/tags") as response:
                    response.raise_for_status()
                    data = await response.json()
                    models = data["models"]
                    
                    return [
                        {"id": model["name"], "name": model["name"].title()}
                        for model in models
                    ]
        except:
            # Return some default models if Ollama is not running
            return [
                {"id": "llama2", "name": "Llama 2"},
                {"id": "mistral", "name": "Mistral"},
                {"id": "codellama", "name": "Code Llama"},
                {"id": "gemma", "name": "Gemma"}
            ]
