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
    """Extract code blocks from a string"""
    pattern = r"```(\w*)\n(.*?)\n```"
    matches = re.findall(pattern, text, re.DOTALL)
    
    result = []
    for lang, code in matches:
        result.append({
            "language": lang or "text",
            "code": code
        })
        
    return result

def wrap_text(text: str, width: int = 80) -> str:
    """Wrap text to the specified width"""
    return '\n'.join(textwrap.wrap(text, width=width))

def render_markdown(markdown_str: str) -> Text:
    """Render a markdown string to a Rich Text object"""
    return Markdown(markdown_str)

def render_code(code: str, language: str = "text") -> Syntax:
    """Render code with syntax highlighting"""
    return Syntax(code, language, theme="monokai", line_numbers=True)

def render_message(message: Message, highlight_code: bool = True) -> Any:
    """Render a message to a Rich renderable"""
    if not highlight_code:
        return Markdown(message.content)
        
    # Extract code blocks and replace with placeholders
    code_blocks = []
    code_pattern = r"```(\w*)\n(.*?)\n```"
    
    def code_replace(match):
        lang = match.group(1) or "text"
        code = match.group(2)
        placeholder = f"__CODE_BLOCK_{len(code_blocks)}__"
        code_blocks.append((lang, code))
        return placeholder
        
    content_with_placeholders = re.sub(
        code_pattern, 
        code_replace, 
        message.content, 
        flags=re.DOTALL
    )
    
    # Convert the rest to markdown
    content_md = Markdown(content_with_placeholders)
    
    # If no code blocks, return the markdown directly
    if not code_blocks:
        return content_md
        
    # Otherwise, create a new Text object and replace the placeholders
    result = Text.from_markup(str(content_md))
    
    for i, (lang, code) in enumerate(code_blocks):
        placeholder = f"__CODE_BLOCK_{i}__"
        syntax = Syntax(
            code, 
            lang, 
            theme="monokai", 
            line_numbers=True,
            word_wrap=True,
            indent_guides=True
        )
        try:
            placeholder_idx = str(result).find(placeholder)
            if placeholder_idx != -1:
                result.replace_range(
                    placeholder_idx, 
                    placeholder_idx + len(placeholder), 
                    syntax
                )
        except Exception:
            # If replacement fails, just append the syntax highlighted code
            result.append(syntax)
            
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
        for chunk in client.generate_stream(messages, model, style):
            full_response += chunk
            await callback(chunk)
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
