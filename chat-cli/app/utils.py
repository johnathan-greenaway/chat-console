import os
import json
import subprocess
from typing import Optional, Dict, Any, List
from .config import CONFIG, save_config
from datetime import datetime
import re
import asyncio
import time
from typing import List, Dict, Any, Optional, Generator, Awaitable, Callable
import textwrap
import threading
from rich.text import Text
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.panel import Panel
from rich.console import Console

from .models import Message, Conversation
from .database import ChatDatabase
from .api.base import BaseModelClient

def generate_conversation_title(messages: List[Message], model: str) -> str:
    """Generate a title for a conversation based on its content"""
    # Find the first user message
    first_user_message = None
    for msg in messages:
        if msg.role == "user":
            first_user_message = msg
            break
            
    if first_user_message is None:
        return f"New conversation ({datetime.now().strftime('%Y-%m-%d %H:%M')})"
    
    # Use first line of the first user message (up to 40 chars)
    content = first_user_message.content.strip()
    
    # Get first line
    first_line = content.split('\n')[0]
    
    # Truncate if needed
    if len(first_line) > 40:
        title = first_line[:37] + "..."
    else:
        title = first_line
        
    return title

def format_code_blocks(text: str) -> str:
    """Ensure code blocks have proper formatting"""
    # Make sure code blocks are properly formatted with triple backticks
    pattern = r"```(\w*)\n(.*?)\n```"
    
    def code_replace(match):
        lang = match.group(1)
        code = match.group(2)
        # Ensure code has proper indentation
        code_lines = code.split('\n')
        code = '\n'.join([line.rstrip() for line in code_lines])
        return f"```{lang}\n{code}\n```"
        
    return re.sub(pattern, code_replace, text, flags=re.DOTALL)

def extract_code_blocks(text: str) -> List[Dict[str, str]]:
    """Extract code blocks from text content"""
    blocks = []
    pattern = r"```(\w*)\n(.*?)\n```"
    matches = re.finditer(pattern, text, re.DOTALL)
    
    for match in matches:
        lang = match.group(1) or "text"
        code = match.group(2).strip()
        blocks.append({
            "language": lang,
            "code": code,
            "start": match.start(),
            "end": match.end()
        })
    
    return blocks

def format_text(text: str, highlight_code: bool = True) -> Text:
    """Format text with optional code highlighting"""
    result = Text()
    
    if not highlight_code:
        return Text(text)
    
    # Split by code blocks
    parts = re.split(r'(```\w*\n.*?\n```)', text, flags=re.DOTALL)
    
    for part in parts:
        if part.startswith('```'):
            # Handle code block
            match = re.match(r'```(\w*)\n(.*?)\n```', part, re.DOTALL)
            if match:
                lang = match.group(1) or "text"
                code = match.group(2).strip()
                syntax = Syntax(
                    code,
                    lang,
                    theme="monokai",
                    line_numbers=True,
                    word_wrap=True,
                    indent_guides=True
                )
                result.append("\n")
                result.append(syntax)
                result.append("\n")
        else:
            # Handle regular text
            if part.strip():
                result.append(Text(part.strip()))
                result.append("\n")
    
    return result

def create_new_conversation(db: ChatDatabase, model: str, style: str = "default") -> Conversation:
    """Create a new conversation in the database"""
    title = f"New conversation ({datetime.now().strftime('%Y-%m-%d %H:%M')})"
    conversation_id = db.create_conversation(title, model, style)
    
    # Get full conversation object
    conversation_data = db.get_conversation(conversation_id)
    return Conversation.from_dict(conversation_data)

def update_conversation_title(db: ChatDatabase, conversation: Conversation) -> None:
    """Update the title of a conversation based on its content"""
    if not conversation.messages:
        return
        
    title = generate_conversation_title(conversation.messages, conversation.model)
    db.update_conversation(conversation.id, title=title)
    conversation.title = title

def add_message_to_conversation(
    db: ChatDatabase, 
    conversation: Conversation, 
    role: str, 
    content: str
) -> Message:
    """Add a message to a conversation in the database"""
    message_id = db.add_message(conversation.id, role, content)
    
    # Create message object
    message = Message(
        id=message_id,
        conversation_id=conversation.id,
        role=role,
        content=content,
        timestamp=datetime.now().isoformat()
    )
    
    # Add to conversation
    conversation.messages.append(message)
    
    # Update conversation title if it's the default
    if conversation.title.startswith("New conversation"):
        update_conversation_title(db, conversation)
        
    return message

def run_in_thread(func: Callable, *args, **kwargs) -> threading.Thread:
    """Run a function in a separate thread"""
    thread = threading.Thread(target=func, args=args, kwargs=kwargs)
    thread.daemon = True
    thread.start()
    return thread

async def generate_streaming_response(
    messages: List[Dict[str, str]],
    model: str,
    style: str,
    client: BaseModelClient,
    callback: Callable[[str], Awaitable[None]]
) -> str:
    """Generate a streaming response and call the callback for each chunk"""
    full_response = ""
    
    try:
        # Get the async generator from the client
        stream = client.generate_stream(messages, model, style)
        # Iterate over the generator properly
        async for chunk in stream:
            if chunk:  # Only process non-empty chunks
                full_response += chunk
                # Update UI and ensure event loop processes it
                await callback(chunk)
                # Small delay to prevent overwhelming the event loop
                await asyncio.sleep(0.01)
    except Exception as e:
        error_msg = f"\n\nError generating response: {str(e)}"
        full_response += error_msg
        await callback(error_msg)
        
    return full_response

def get_elapsed_time(start_time: float) -> str:
    """Get the elapsed time as a formatted string"""
    elapsed = time.time() - start_time
    
    if elapsed < 60:
        return f"{elapsed:.1f}s"
    else:
        minutes = int(elapsed // 60)
        seconds = elapsed % 60
        return f"{minutes}m {seconds:.1f}s"
async def generate_streaming_response(messages: List[Dict], model: str, style: str, client: Any, callback: Any) -> str:
    """Generate a streaming response from the model"""
    full_response = ""
    async for chunk in client.generate_stream(messages, model, style):
        await callback(chunk)
        full_response += chunk
    return full_response

def ensure_ollama_running() -> bool:
    """
    Check if Ollama is running and try to start it if not.
    Returns True if Ollama is running after check/start attempt.
    """
    import requests
    try:
        # Try to connect to Ollama
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        return response.status_code == 200
    except:
        try:
            # Try to start Ollama
            subprocess.Popen(["ollama", "serve"], 
                           stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)
            # Wait a moment for it to start
            import time
            time.sleep(2)
            # Check again
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            return response.status_code == 200
        except:
            return False

def save_settings_to_config(model: str, style: str) -> None:
    """Save settings to global config file"""
    CONFIG["default_model"] = model
    CONFIG["default_style"] = style
    save_config(CONFIG)
