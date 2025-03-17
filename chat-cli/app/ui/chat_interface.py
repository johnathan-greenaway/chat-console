from typing import List, Dict, Any, Optional, Callable, Awaitable
import time
import asyncio
from datetime import datetime
import re
import logging
    
from textual.app import ComposeResult
from textual.containers import Container, ScrollableContainer, Vertical
from textual.reactive import reactive
from textual.widgets import Button, Input, Label, Static
from textual.widget import Widget
from textual.widgets import RichLog
from textual.message import Message
 
from ..models import Message, Conversation
from ..api.base import BaseModelClient
from ..config import CONFIG

# Set up logging
logger = logging.getLogger(__name__)

class MessageDisplay(RichLog):
    """Widget to display a single message"""
    
    DEFAULT_CSS = """
    MessageDisplay {
        width: 100%;
        height: auto;
        margin: 1 0;
        overflow: auto;
        padding: 1;
    }
    
    MessageDisplay.user-message {
        background: $primary-darken-2;
        border-right: wide $primary;
        margin-right: 4;
    }
    
    MessageDisplay.assistant-message {
        background: $surface;
        border-left: wide $secondary;
        margin-left: 4;
    }
    
    MessageDisplay.system-message {
        background: $surface-darken-1;
        border: dashed $primary-background;
        margin: 1 4;
    }
    """
    
    def __init__(
        self, 
        message: Message,
        highlight_code: bool = True,
        name: Optional[str] = None
    ):
        super().__init__(
            highlight=True,
            markup=True,
            wrap=True,
            name=name
        )
        self.message = message
        self.highlight_code = highlight_code
        
    def on_mount(self) -> None:
        """Handle mount event"""
        # Add message type class
        if self.message.role == "user":
            self.add_class("user-message")
        elif self.message.role == "assistant":
            self.add_class("assistant-message")
        elif self.message.role == "system":
            self.add_class("system-message")
        
        # Initial content
        self.write(self._format_content(self.message.content))
        
    async def update_content(self, content: str) -> None:
        """Update the message content"""
        self.message.content = content
        self.clear()
        self.write(self._format_content(content))
        # Force a refresh after writing
        self.refresh(layout=True)
        # Wait a moment for the layout to update
        await asyncio.sleep(0.05)
        
    def _format_content(self, content: str) -> str:
        """Format message content with timestamp"""
        timestamp = datetime.now().strftime("%H:%M")
        return f"[dim]{timestamp}[/dim] {content}"

class InputWithFocus(Input):
    """Enhanced Input that better handles focus and maintains cursor position"""
    
    def on_key(self, event) -> None:
        """Custom key handling for input"""
        # Let control keys pass through
        if event.is_control:
            return super().on_key(event)
            
        # Handle Enter key
        if event.key == "enter":
            self.post_message(self.Submitted(self))
            return
            
        # Normal input handling for other keys
        super().on_key(event)

class ChatInterface(Container):
    """Main chat interface container"""
    
    DEFAULT_CSS = """
    ChatInterface {
        width: 100%;
        height: 100%;
        background: $surface;
    }
    
    #messages-container {
        width: 100%;
        height: 1fr;
        min-height: 10;
        border-bottom: solid $primary-darken-2;
        overflow: auto;
        padding: 0 1;
    }
    
    #input-area {
        width: 100%;
        height: auto;
        min-height: 4;
        max-height: 10;
        padding: 1;
    }
    
    #message-input {
        width: 1fr;
        min-height: 2;
        height: auto;
        margin-right: 1;
        border: solid $primary-darken-2;
    }
    
    #message-input:focus {
        border: solid $primary;
    }
    
    #send-button {
        background: $warning;
        color: $text;
        border: none;
        min-width: 8;
        height: 3;
        margin: 0 1;
        content-align: center middle;
        text-style: bold;
        text-opacity: 100%;
    }

    #send-button:hover {
        background: $warning-lighten-1;
    }
    
    #loading-indicator {
        width: 100%;
        height: 1;
        background: $primary-darken-1;
        color: $text;
        display: none;
        padding: 0 1;
    }
    """
    
    class MessageSent(Message):
        """Sent when a message is sent"""
        def __init__(self, content: str):
            self.content = content
            super().__init__()
            
    class StopGeneration(Message):
        """Sent when generation should be stopped"""
        
    conversation = reactive(None)
    is_loading = reactive(False)
    
    def __init__(
        self,
        conversation: Optional[Conversation] = None, 
        name: Optional[str] = None,
        id: Optional[str] = None
    ):
        super().__init__(name=name, id=id)
        self.conversation = conversation
        self.messages: List[Message] = []
        self.current_message_display = None
        if conversation and conversation.messages:
            self.messages = conversation.messages
            
    def compose(self) -> ComposeResult:
        with ScrollableContainer(id="messages-container"):
            for message in self.messages:
                yield MessageDisplay(message, highlight_code=CONFIG["highlight_code"])
        with Container(id="input-area"):
            yield Container(
                Label("Generating response...", id="loading-text"),
                id="loading-indicator"
            )
            with Container(id="controls"):
                yield InputWithFocus(placeholder="Type your message here...", id="message-input")
                yield Button("[on yellow black]SEND[/]", id="send-button", markup=True)


                
    def on_mount(self) -> None:
        """Initialize on mount"""
        # Scroll to bottom initially
        self.scroll_to_bottom()
        
    def _request_focus(self) -> None:
        """Request focus for the input field"""
        try:
            input_field = self.query_one("#message-input")
            if input_field and not input_field.has_focus:
                # Only focus if not already focused and no other widget has focus
                if not self.app.focused or self.app.focused.id == "message-input":
                    self.app.set_focus(input_field)
        except Exception:
            pass
                
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        button_id = event.button.id
        if button_id == "send-button":
            await self.send_message()
            
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission"""
        if event.input.id == "message-input":
            await self.send_message()
            
    async def add_message(self, role: str, content: str, update_last: bool = False) -> None:
        """Add or update a message in the chat"""
        messages_container = self.query_one("#messages-container")
        
        if update_last and self.current_message_display and role == "assistant":
            # Update existing message
            await self.current_message_display.update_content(content)
            # Update message in history
            if self.messages and self.messages[-1].role == "assistant":
                self.messages[-1].content = content
        else:
            # Add new message
            message = Message(role=role, content=content)
            self.messages.append(message)
            self.current_message_display = MessageDisplay(
                message, 
                highlight_code=CONFIG["highlight_code"]
            )
            messages_container.mount(self.current_message_display)
            
            # Force a layout refresh and wait for it to complete
            self.refresh(layout=True)
            await asyncio.sleep(0.1)
            
        # Save to conversation if exists
        if self.conversation and self.conversation.id:
            from ..database import ChatDatabase
            db = ChatDatabase()
            db.add_message(self.conversation.id, role, content)
            
        await self.scroll_to_bottom()
        
    async def send_message(self) -> None:
        """Send a message"""
        input_widget = self.query_one("#message-input")
        content = input_widget.value.strip()
        
        if not content:
            return
            
        # Clear input
        input_widget.value = ""
        
        # Add user message to chat
        await self.add_message("user", content)
        
        # Reset current message display for next assistant response
        self.current_message_display = None
        
        # Emit message sent event
        self.post_message(self.MessageSent(content))
        
        # Re-focus the input after sending if it was focused before
        if input_widget.has_focus:
            input_widget.focus()
        
    def start_loading(self) -> None:
        """Show loading indicator"""
        self.is_loading = True
        loading = self.query_one("#loading-indicator")
        loading.display = True
        
    def stop_loading(self) -> None:
        """Hide loading indicator"""
        self.is_loading = False
        loading = self.query_one("#loading-indicator")
        loading.display = False
        
    def clear_messages(self) -> None:
        """Clear all messages"""
        self.messages = []
        self.current_message_display = None
        messages_container = self.query_one("#messages-container")
        messages_container.remove_children()
        
    async def set_conversation(self, conversation: Conversation) -> None:
        """Set the current conversation"""
        self.conversation = conversation
        self.messages = conversation.messages if conversation else []
        self.current_message_display = None
        
        # Update UI
        messages_container = self.query_one("#messages-container")
        messages_container.remove_children()
        
        if self.messages:
            # Mount messages with a small delay between each
            for message in self.messages:
                display = MessageDisplay(message, highlight_code=CONFIG["highlight_code"])
                messages_container.mount(display)
                await self.scroll_to_bottom()
                await asyncio.sleep(0.05)  # Small delay to prevent UI freezing
                    
        await self.scroll_to_bottom()
        
        # Re-focus the input field after changing conversation
        self.query_one("#message-input").focus()
        
    def on_resize(self, event) -> None:
        """Handle terminal resize events"""
        try:
            # Re-focus the input if it lost focus during resize
            self.query_one("#message-input").focus()
            
            # Scroll to bottom to ensure the latest messages are visible
            asyncio.create_task(self.scroll_to_bottom())
        except Exception as e:
            logger.error(f"Error handling resize: {str(e)}")
            
    async def scroll_to_bottom(self) -> None:
        """Scroll to the bottom of the messages container"""
        try:
            messages_container = self.query_one("#messages-container")
            # Force a layout refresh
            self.refresh(layout=True)
            # Wait a moment for layout to update
            await asyncio.sleep(0.1)
            # Scroll to bottom
            messages_container.scroll_end(animate=False)
            # Force another refresh
            self.refresh(layout=True)
        except Exception as e:
            logger.error(f"Error scrolling to bottom: {str(e)}")
        
    def watch_is_loading(self, is_loading: bool) -> None:
        """Watch the is_loading property"""
        if is_loading:
            self.start_loading()
        else:
            self.stop_loading()
