import anthropic
from typing import List, Dict, Any, Optional, Generator, AsyncGenerator
from .base import BaseModelClient
from ..config import ANTHROPIC_API_KEY

class AnthropicClient(BaseModelClient):
    def __init__(self):
        self.client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    
    def _prepare_messages(self, messages: List[Dict[str, str]], style: Optional[str] = None) -> List[Dict[str, str]]:
        """Prepare messages for Claude API"""
        # Anthropic expects role to be 'user' or 'assistant'
        processed_messages = []
        
        for msg in messages:
            role = msg["role"]
            if role == "system":
                # For Claude, we'll convert system messages to user messages with a special prefix
                processed_messages.append({
                    "role": "user",
                    "content": f"<system>\n{msg['content']}\n</system>"
                })
            else:
                processed_messages.append(msg)
        
        # Add style instructions if provided
        if style and style != "default":
            # Find first non-system message to attach style to
            for i, msg in enumerate(processed_messages):
                if msg["role"] == "user":
                    content = msg["content"]
                    if "<userStyle>" not in content:
                        style_instructions = self._get_style_instructions(style)
                        msg["content"] = f"<userStyle>{style_instructions}</userStyle>\n\n{content}"
                    break
        
        return processed_messages
    
    def _get_style_instructions(self, style: str) -> str:
        """Get formatting instructions for different styles"""
        styles = {
            "concise": "Be extremely concise and to the point. Use short sentences and paragraphs. Avoid unnecessary details.",
            "detailed": "Be comprehensive and thorough in your responses. Provide detailed explanations, examples, and cover all relevant aspects of the topic.",
            "technical": "Use precise technical language and terminology. Be formal and focus on accuracy and technical details.",
            "friendly": "Be warm, approachable and conversational. Use casual language, personal examples, and a friendly tone.",
        }
        
        return styles.get(style, "")
    
    async def generate_completion(self, messages: List[Dict[str, str]], 
                           model: str, 
                           style: Optional[str] = None, 
                           temperature: float = 0.7, 
                           max_tokens: Optional[int] = None) -> str:
        """Generate a text completion using Claude"""
        processed_messages = self._prepare_messages(messages, style)
        
        response = await self.client.messages.create(
            model=model,
            messages=processed_messages,
            temperature=temperature,
            max_tokens=max_tokens or 1024,
        )
        
        return response.content[0].text
    
    async def generate_stream(self, messages: List[Dict[str, str]], 
                            model: str, 
                            style: Optional[str] = None,
                            temperature: float = 0.7, 
                            max_tokens: Optional[int] = None) -> AsyncGenerator[str, None]:
        """Generate a streaming text completion using Claude"""
        try:
            from app.main import debug_log  # Import debug logging if available
            debug_log(f"Anthropic: starting streaming generation with model: {model}")
        except ImportError:
            # If debug_log not available, create a no-op function
            debug_log = lambda msg: None
            
        processed_messages = self._prepare_messages(messages, style)
        
        try:
            debug_log(f"Anthropic: requesting stream with {len(processed_messages)} messages")
            # Remove await from this line - it returns the context manager, not an awaitable
            stream = self.client.messages.stream( 
                model=model,
                messages=processed_messages,
                temperature=temperature,
                max_tokens=max_tokens or 1024,
            )
            
            debug_log("Anthropic: stream created successfully, processing chunks using async with")
            async with stream as stream_context: # Use async with
                async for chunk in stream_context: # Iterate over the context
                    try:
                        if chunk.type == "content_block_delta": # Check for delta type
                            # Ensure we always return a string
                            if chunk.delta.text is None:
                                debug_log("Anthropic: skipping empty text delta chunk")
                                continue
                                
                            text = str(chunk.delta.text) # Get text from delta
                            debug_log(f"Anthropic: yielding chunk of length: {len(text)}")
                            yield text
                        else:
                            debug_log(f"Anthropic: skipping non-content_delta chunk of type: {chunk.type}")
                    except Exception as chunk_error: # Restore the except block for chunk processing
                        debug_log(f"Anthropic: error processing chunk: {str(chunk_error)}")
                        # Skip problematic chunks but continue processing
                        continue # This continue is now correctly inside the loop and except block
                    
        except Exception as e:
            debug_log(f"Anthropic: error in generate_stream: {str(e)}")
            raise Exception(f"Anthropic streaming error: {str(e)}")
    
    def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available Claude models"""
        return [
            {"id": "claude-3-opus", "name": "Claude 3 Opus"},
            {"id": "claude-3-sonnet", "name": "Claude 3 Sonnet"},
            {"id": "claude-3-haiku", "name": "Claude 3 Haiku"},
            {"id": "claude-3.7-sonnet", "name": "Claude 3.7 Sonnet"},
        ]
