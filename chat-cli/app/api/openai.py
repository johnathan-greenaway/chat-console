from openai import AsyncOpenAI
from typing import List, Dict, Any, Optional, Generator, AsyncGenerator
from .base import BaseModelClient
from ..config import OPENAI_API_KEY

class OpenAIClient(BaseModelClient):
    def __init__(self):
        self.client = None  # Initialize in create()

    @classmethod
    async def create(cls) -> 'OpenAIClient':
        """Create a new instance with async initialization."""
        instance = cls()
        instance.client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        return instance
    
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
    
    async def generate_completion(self, messages: List[Dict[str, str]], 
                           model: str, 
                           style: Optional[str] = None, 
                           temperature: float = 0.7, 
                           max_tokens: Optional[int] = None) -> str:
        """Generate a text completion using OpenAI"""
        processed_messages = self._prepare_messages(messages, style)
        
        response = await self.client.chat.completions.create(
            model=model,
            messages=processed_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        
        return response.choices[0].message.content
    
    async def generate_stream(self, messages: List[Dict[str, str]], 
                            model: str, 
                            style: Optional[str] = None,
                            temperature: float = 0.7, 
                            max_tokens: Optional[int] = None) -> AsyncGenerator[str, None]:
        """Generate a streaming text completion using OpenAI"""
        try:
            from app.main import debug_log  # Import debug logging if available
            debug_log(f"OpenAI: starting streaming generation with model: {model}")
        except ImportError:
            # If debug_log not available, create a no-op function
            debug_log = lambda msg: None
            
        processed_messages = self._prepare_messages(messages, style)
        
        try:
            debug_log(f"OpenAI: preparing {len(processed_messages)} messages for stream")
            
            # Safely prepare messages
            try:
                api_messages = []
                for m in processed_messages:
                    if isinstance(m, dict) and "role" in m and "content" in m:
                        api_messages.append({"role": m["role"], "content": m["content"]})
                    else:
                        debug_log(f"OpenAI: skipping invalid message: {m}")
                
                debug_log(f"OpenAI: prepared {len(api_messages)} valid messages")
            except Exception as msg_error:
                debug_log(f"OpenAI: error preparing messages: {str(msg_error)}")
                # Fallback to a simpler message format if processing fails
                api_messages = [{"role": "user", "content": "Please respond to my request."}]
            
            debug_log("OpenAI: requesting stream")
            stream = await self.client.chat.completions.create(
                model=model,
                messages=api_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            
            debug_log("OpenAI: stream created successfully, processing chunks")
            async for chunk in stream:
                try:
                    if chunk.choices and hasattr(chunk.choices[0], 'delta') and hasattr(chunk.choices[0].delta, 'content'):
                        content = chunk.choices[0].delta.content
                        if content is not None:
                            # Ensure we're returning a string
                            text = str(content)
                            debug_log(f"OpenAI: yielding chunk of length: {len(text)}")
                            yield text
                        else:
                            debug_log("OpenAI: skipping None content chunk")
                    else:
                        debug_log("OpenAI: skipping chunk with missing content")
                except Exception as chunk_error:
                    debug_log(f"OpenAI: error processing chunk: {str(chunk_error)}")
                    # Skip problematic chunks but continue processing
                    continue
                    
        except Exception as e:
            debug_log(f"OpenAI: error in generate_stream: {str(e)}")
            raise Exception(f"OpenAI streaming error: {str(e)}")
    
    def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available OpenAI models"""
        return [
            {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo"},
            {"id": "gpt-4", "name": "GPT-4"},
            {"id": "gpt-4-turbo", "name": "GPT-4 Turbo"}
        ]
