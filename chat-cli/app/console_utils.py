"""
Console-specific utilities for the pure terminal version
No Textual dependencies
"""

import asyncio
import time
from typing import Dict, List, Any, Optional, Callable, AsyncGenerator
from .api.base import BaseModelClient

async def console_streaming_response(
    messages: List[Dict[str, str]],
    model: str,
    style: Optional[str],
    client: BaseModelClient,
    update_callback: Optional[Callable[[str], None]] = None
) -> AsyncGenerator[str, None]:
    """
    Enhanced streaming response for console UI with provider-specific optimizations
    """
    try:
        # Detect provider type for optimizations
        client_type = type(client).__name__.lower()
        is_ollama = 'ollama' in client_type
        is_openai = 'openai' in client_type
        is_anthropic = 'anthropic' in client_type
        
        # Initialize tracking variables
        full_content = ""
        buffer = []
        last_update = time.time()
        
        # Provider-specific configuration
        if is_ollama:
            update_interval = 0.15  # Slower updates for Ollama (model loading)
            buffer_size = 3  # Smaller buffer for Ollama
        elif is_openai:
            update_interval = 0.08  # Fast updates for OpenAI
            buffer_size = 5  # Medium buffer for OpenAI
        elif is_anthropic:
            update_interval = 0.1   # Medium updates for Anthropic
            buffer_size = 4  # Medium buffer for Anthropic
        else:
            update_interval = 0.1   # Default timing
            buffer_size = 4  # Default buffer
        
        # Special handling for reasoning models (slower, more deliberate)
        if model.startswith(("o1", "o3", "o4")) or model in ["o1", "o3", "o4-mini"]:
            update_interval = 0.2  # Slower updates for reasoning models
            buffer_size = 2  # Smaller buffer for reasoning
        
        async for chunk in client.generate_stream(
            messages=messages,
            model=model,
            style=style
        ):
            if chunk:
                # Check if this is an error message that should not be streamed word by word
                is_error_message = (
                    "The model is still loading" in chunk or
                    "I'm sorry, but I couldn't generate a response" in chunk or
                    chunk.startswith("Error:") or
                    chunk.startswith("Could not connect")
                )
                
                # For Ollama, only break down chunks if they contain multiple words AND are not error messages
                if (is_ollama and len(chunk) > 10 and ' ' in chunk and 
                    chunk.count(' ') > 1 and not is_error_message):
                    # Split large multi-word chunks into individual words for smoother streaming
                    words = chunk.split(' ')
                    for i, word in enumerate(words):
                        if i > 0:
                            word = ' ' + word  # Add space back except for first word
                        
                        full_content += word
                        
                        # Update display with gradual content
                        if update_callback:
                            update_callback(full_content)
                        
                        yield word
                        
                        # Small delay between words for streaming effect
                        await asyncio.sleep(0.02)
                else:
                    # Use the chunk as-is (for normal content or error messages)
                    full_content += chunk
                    
                    # Update display immediately for each chunk
                    if update_callback:
                        update_callback(full_content)
                    
                    yield chunk
                    
                    # Small delay to make streaming visible (but not for error messages)
                    if is_ollama and not is_error_message:
                        await asyncio.sleep(0.01)
        
        # Process any remaining buffer content
        if buffer:
            final_content = ''.join(buffer)
            full_content += final_content
            if update_callback:
                update_callback(full_content)
            yield final_content
                
    except asyncio.CancelledError:
        # Handle cancellation gracefully
        if update_callback:
            update_callback(full_content + "\n[Generation cancelled]")
        raise
        
    except Exception as e:
        error_msg = f"Error generating response: {str(e)}"
        if update_callback:
            update_callback(error_msg)
        yield error_msg

def apply_style_prefix(messages: List[Dict[str, str]], style: str) -> List[Dict[str, str]]:
    """Apply style instructions to the message list"""
    if not style or style == "default":
        return messages
    
    style_instructions = {
        "concise": "Please provide a brief and concise response.",
        "detailed": "Please provide a comprehensive and detailed response.",
        "technical": "Please provide a technical response with precise terminology.",
        "friendly": "Please provide a warm and friendly response."
    }
    
    instruction = style_instructions.get(style, "")
    if instruction and messages:
        # Add style instruction to the first user message
        modified_messages = messages.copy()
        for msg in modified_messages:
            if msg["role"] == "user":
                msg["content"] = f"{instruction}\n\n{msg['content']}"
                break
        return modified_messages
    
    return messages

async def test_model_connection(model: str) -> bool:
    """Test if we can connect to the specified model"""
    try:
        client = await BaseModelClient.get_client_for_model(model)
        # Try a simple test message
        test_messages = [{"role": "user", "content": "Hello"}]
        async for _ in client.generate_stream(test_messages, model):
            break  # Just test that we can start streaming
        return True
    except Exception:
        return False

def format_model_list() -> List[str]:
    """Format the available models for console display"""
    from .config import CONFIG
    
    formatted = []
    for model_id, model_info in CONFIG["available_models"].items():
        provider = model_info["provider"].capitalize()
        display_name = model_info["display_name"]
        formatted.append(f"{display_name} ({provider})")
    
    return formatted

def get_terminal_size():
    """Get terminal size with fallback"""
    try:
        import shutil
        return shutil.get_terminal_size()
    except Exception:
        # Fallback size
        class Size:
            columns = 80
            lines = 24
        return Size()

def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate text to fit within max_length"""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix

def word_wrap(text: str, width: int) -> List[str]:
    """Wrap text to specified width"""
    words = text.split()
    lines = []
    current_line = ""
    
    for word in words:
        if len(current_line) + len(word) + 1 <= width:
            if current_line:
                current_line += " "
            current_line += word
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    
    if current_line:
        lines.append(current_line)
    
    return lines or [""]