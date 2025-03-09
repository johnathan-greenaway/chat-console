import openai
from typing import List, Dict, Any, Optional, Generator
from .base import BaseModelClient
from ..config import OPENAI_API_KEY

class OpenAIClient(BaseModelClient):
    def __init__(self):
        self.client = openai.OpenAI(api_key=OPENAI_API_KEY)
    
    def _prepare_messages(self, messages: List[Dict[str, str]], style: Optional[str] = None) -> List[Dict[str, str]]:
        """Prepare messages for OpenAI API"""
        processed_messages = messages.copy()
        
        # Add style instructions if provided
        if style and style != "default":
            style_instructions = self._get_style_instructions(style)
            processed_messages.insert(0, {
                "role": "system",
                "content": style_instructions
            })
        
        return processed_messages
    
    def _get_style_instructions(self, style: str) -> str:
        """Get formatting instructions for different styles"""
        styles = {
            "concise": "You are a concise assistant. Provide brief, to-the-point responses without unnecessary elaboration.",
            "detailed": "You are a detailed assistant. Provide comprehensive responses with thorough explanations and examples.",
            "technical": "You are a technical assistant. Use precise technical language and focus on accuracy and technical details.",
            "friendly": "You are a friendly assistant. Use a warm, conversational tone and relatable examples.",
        }
        
        return styles.get(style, "")
    
    def generate_completion(self, messages: List[Dict[str, str]], 
                           model: str, 
                           style: Optional[str] = None, 
                           temperature: float = 0.7, 
                           max_tokens: Optional[int] = None) -> str:
        """Generate a text completion using OpenAI"""
        processed_messages = self._prepare_messages(messages, style)
        
        response = self.client.chat.completions.create(
            model=model,
            messages=processed_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        
        return response.choices[0].message.content
    
    def generate_stream(self, messages: List[Dict[str, str]], 
                       model: str, 
                       style: Optional[str] = None,
                       temperature: float = 0.7, 
                       max_tokens: Optional[int] = None) -> Generator[str, None, None]:
        """Generate a streaming text completion using OpenAI"""
        processed_messages = self._prepare_messages(messages, style)
        
        stream = self.client.chat.completions.create(
            model=model,
            messages=processed_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    
    def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available OpenAI models"""
        return [
            {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo"},
            {"id": "gpt-4", "name": "GPT-4"},
            {"id": "gpt-4-turbo", "name": "GPT-4 Turbo"}
        ]
