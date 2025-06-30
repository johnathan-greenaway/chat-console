from typing import List, Dict, Any, Optional, Callable, Awaitable
import asyncio
from datetime import datetime
import re
import logging
    
from textual.app import ComposeResult
from textual.containers import Container, ScrollableContainer, Vertical
from textual.reactive import reactive
from textual.widgets import Button, Input, Label, Static # Removed RichLog from here
from textual.widget import Widget
# Removed RichLog import as MessageDisplay will inherit from Static
from textual.message import Message
from textual.binding import Binding
 
from .. import __version__
from ..models import Message, Conversation
from ..api.base import BaseModelClient
from ..config import CONFIG

# Set up logging
logger = logging.getLogger(__name__)

class SendButton(Button):
    """Minimal send button following Rams design principles"""
    
    DEFAULT_CSS = """
    SendButton {
        background: transparent;
        color: #E8E8E8;
        border: solid #333333 1;
        margin: 0 1;
        padding: 1 2;
    }

    SendButton:hover {
        background: #1A1A1A;
        border: solid #33FF33 1;
        color: #E8E8E8;
    }

    SendButton:focus {
        border: solid #33FF33 1;
        outline: none;
    }
    """

    def __init__(self, name: Optional[str] = None):
        super().__init__(
            "→",  # Simple arrow - functional and clear
            name=name
        )

class MessageDisplay(Static): # Inherit from Static instead of RichLog
    """Widget to display a single message using Static"""
    
    DEFAULT_CSS = """
    /* Rams-inspired message styling - "Less but better" */
    MessageDisplay {
        width: 100%;
        height: auto;
        margin: 2 0;           /* Generous vertical spacing */
        padding: 2 3;          /* Intentional padding for readability */
        text-wrap: wrap;
        content-align: left top;
        overflow-y: auto;
        box-sizing: border-box;
        background: transparent; /* Clean default */
        border: none;           /* Remove unnecessary borders */
    }
    
    MessageDisplay.user-message {
        background: #1A1A1A;   /* Subtle distinction */
        border-left: solid #33FF33 2;  /* Minimal accent line */
        margin-left: 2;        /* Slight indent */
        margin-right: 8;       /* Asymmetric layout for hierarchy */
    }
    
    MessageDisplay.assistant-message {
        background: transparent; /* Clean background */
        border-left: solid #666666 1;  /* Subtle indicator */
        margin-right: 2;       /* Opposite indent */
        margin-left: 8;        /* Asymmetric layout */
    }
    
    MessageDisplay.system-message {
        background: transparent;
        border: solid #333333 1;
        margin: 1 4;
        color: #666666;        /* Muted for less important messages */
    }
    """
    
    def __init__(
        self, 
        message: Message,
        highlight_code: bool = True,
        name: Optional[str] = None
    ):
        # Initialize Static with empty content and necessary parameters
        # Static supports markup but handles wrap differently via styles
        super().__init__(
            "",  # Initialize with empty content initially
            markup=True,
            name=name
        )
        # Enable text wrapping via CSS (already set in DEFAULT_CSS)
        self.message = message
        self.highlight_code = highlight_code # Keep this for potential future use or logic
        
    def on_mount(self) -> None:
        """Handle mount event"""
        # Add message type class
        if self.message.role == "user":
            self.add_class("user-message")
        elif self.message.role == "assistant":
            self.add_class("assistant-message")
        elif self.message.role == "system":
            self.add_class("system-message")
        
        # Initial content using Static's update method
        self.update(self._format_content(self.message.content))
        
    async def update_content(self, content: str) -> None:
        """Update the message content using Static.update() with optimizations for streaming"""
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"MessageDisplay.update_content called with content length: {len(content)}")
        
        # Use a lock to prevent race conditions during updates
        if not hasattr(self, '_update_lock'):
            self._update_lock = asyncio.Lock()
        
        async with self._update_lock:
            # Special handling for "Thinking..." to ensure it gets replaced
            if self.message.content == "Thinking..." and content:
                logger.debug("Replacing 'Thinking...' with actual content")
                # Force a complete replacement
                self.message.content = content
                formatted_content = self._format_content(content)
                self.update(formatted_content)
                
                # Force app-level refresh
                try:
                    if self.app:
                        self.app.refresh(layout=True)
                        # Find container and scroll
                        messages_container = self.app.query_one("#messages-container")
                        if messages_container:
                            messages_container.scroll_end(animate=False)
                except Exception as e:
                    logger.error(f"Error refreshing app: {str(e)}")
                return
                
            # For all other updates - ALWAYS update
            self.message.content = content
            formatted_content = self._format_content(content)
            # Ensure the update call doesn't have refresh=True
            self.update(formatted_content) 
            
            # Force refresh using app.refresh() instead of passing to update()
            try:
                if self.app:
                    self.app.refresh(layout=True)
                    # Find container and scroll
                    messages_container = self.app.query_one("#messages-container")
                    if messages_container:
                        messages_container.scroll_end(animate=False)
            except Exception as e:
                logger.error(f"Error refreshing app: {str(e)}")
        
    def _format_content(self, content: str) -> str:
        """Format message content following Rams principles - clean and functional"""
        timestamp = datetime.now().strftime("%H:%M")
        
        # Special handling for "Thinking..." - minimal styling
        if content == "Thinking...":
            return f"  {timestamp}  [dim]{content}[/dim]"
            
        # Clean up markdown-style links for better readability
        content = re.sub(
            r'\[([^\]]+)\]\(([^)]+)\)',
            lambda m: f"{m.group(1)} ({m.group(2)})",
            content
        )
        
        # Escape markup characters but keep content clean
        content = content.replace("[", "\\[").replace("]", "\\]")
        
        # Rams principle: "As little design as possible"
        # Simple timestamp with generous spacing for readability
        return f"  {timestamp}  {content}"
        
    def _get_clean_border(self, width: int = 60) -> str:
        """Create a clean ASCII border following the design spec"""
        from .borders import create_border_line
        return create_border_line(width, 'light', 'top')

class InputWithFocus(Input):
    """Enhanced Input that better handles focus and maintains cursor position"""
    # Reverted on_key to default Input behavior for 'n' and 't'
    # Let the standard Input handle key presses when focused.
    # We will rely on focus checks within the App's action methods.

    # Keep custom handling only for Enter submission if needed,
    # but standard Input might already do this. Let's simplify
    # and remove the custom on_key entirely for now unless
    def on_key(self, event) -> None:
        # Let global hotkeys 'n' and 't' pass through even when input has focus
        # by simply *not* stopping the event here.
        if event.key == "n" or event.key == "t":
            # Do nothing, allow the event to bubble up to the app level bindings.
            return # Explicitly return to prevent further processing in this method

        # For all other keys, the event continues to be processed by the Input
        # widget's internal handlers (like _on_key shown in the traceback)
        # because we didn't stop it in this method.

class ChatInterface(Container):
    """Main chat interface container"""
    
    DEFAULT_CSS = """
    /* Clean chat interface following Rams principles */
    ChatInterface {
        width: 100%;
        height: 100%;
        background: #0C0C0C;
    }
    
    #messages-container {
        width: 100%;
        height: 1fr;
        min-height: 15;         /* More breathing room */
        border-bottom: solid #333333 1;
        overflow: auto;
        padding: 2;             /* Generous padding */
        content-align: left top;
        box-sizing: border-box;
        background: #0C0C0C;
    }
    
    #input-area {
        width: 100%;
        height: auto;
        min-height: 5;          /* Comfortable minimum */
        max-height: 12;
        padding: 2;             /* Consistent padding */
        background: #0C0C0C;
        border-top: solid #333333 1;
    }
    
    #message-input {
        width: 1fr;
        min-height: 3;          /* Comfortable input height */
        height: auto;
        margin-right: 1;
        border: solid #333333 1;
        background: #0C0C0C;
        color: #E8E8E8;
        padding: 1;
    }
    
    #message-input:focus {
        border: solid #33FF33 1;
        outline: none;
    }
    
    #version-label {
        width: 100%;
        height: auto;
        background: #0C0C0C;
        color: #666666;         /* Muted version info */
        text-align: right;
        padding: 1;
        border-bottom: solid #333333 1;
    }
    
    #loading-indicator {
        width: 100%;
        height: 2;
        background: #0C0C0C;
        color: #666666;         /* Subtle loading indicator */
        display: none;
        padding: 0 2;
        text-align: center;
        border-bottom: solid #333333 1;
    }
    
    #loading-indicator.model-loading {
        color: #33FF33;         /* Accent for model loading */
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
        yield Label(f"Chat CLI v{__version__}", id="version-label")
        with ScrollableContainer(id="messages-container"):
            for message in self.messages:
                yield MessageDisplay(message, highlight_code=CONFIG["highlight_code"])
        with Container(id="input-area"):
            yield Container(
                Label("▪▪▪ Generating response...", id="loading-text", markup=False),
                id="loading-indicator"
            )
            with Container(id="controls"):
                yield InputWithFocus(placeholder="Type your message here...", id="message-input")
                yield SendButton(id="send-button")
                
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
        
    def start_loading(self, model_loading: bool = False) -> None:
        """Show minimal loading indicator following Rams principles"""
        self.is_loading = True
        loading = self.query_one("#loading-indicator")
        loading_text = self.query_one("#loading-text")
        
        if model_loading:
            loading.add_class("model-loading")
            loading_text.update("● Preparing model")
        else:
            loading.remove_class("model-loading")
            loading_text.update("● Generating")
            
        loading.display = True
        
    def stop_loading(self) -> None:
        """Hide loading indicator"""
        self.is_loading = False
        loading = self.query_one("#loading-indicator")
        loading.remove_class("model-loading")
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
