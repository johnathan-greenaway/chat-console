#!/usr/bin/env python3
"""
Simplified version of Terminal Chat with AI functionality
"""
import os
from typing import List, Optional
from datetime import datetime

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.reactive import reactive
from textual.widgets import Button, Input, Label, Static, Header, Footer
from textual.binding import Binding
from textual import work

from app.models import Message, Conversation
from app.database import ChatDatabase
from app.config import CONFIG, OPENAI_API_KEY, ANTHROPIC_API_KEY
from app.ui.chat_interface import MessageDisplay
from app.api.base import BaseModelClient
from app.utils import generate_streaming_response

class SimpleChatApp(App):
    """Simplified Terminal Chat application."""
    
    TITLE = "Simple Terminal Chat"
    SUB_TITLE = "AI-powered chat"
    
    CSS = """
    #main-content {
        width: 100%;
        height: 100%;
        padding: 0 1;
    }
    
    #conversation-title {
        width: 100%;
        height: 3;
        background: $primary-darken-1;
        color: $text;
        content-align: center middle;
        text-align: center;
    }
    
    #messages-container {
        width: 100%;
        height: 1fr;
        min-height: 10;
        border-bottom: solid $primary-darken-2;
        overflow: auto;
        padding: 0 1;
    }
    
    #loading-indicator {
        width: 100%;
        height: 1;
        background: $primary-darken-1;
        color: $text;
        content-align: center middle;
        text-align: center;
    }
    
    #loading-indicator.hidden {
        display: none;
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
        min-height: 3;
        height: auto;
        margin-right: 1;
        border: solid $primary-darken-2;
    }
    
    #message-input:focus {
        border: tall $primary;
    }
    
    #send-button {
        width: auto;
        min-width: 10;
        height: 3;
    }
    
    #new-chat-button {
        width: auto;
        min-width: 10;
        height: 3;
        background: $success;
    }
    """
    
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("n", "new_conversation", "New Chat"),
        Binding("escape", "escape", "Cancel"),
        Binding("ctrl+c", "quit", "Quit"),
    ]
    
    current_conversation = reactive(None)
    is_generating = reactive(False)
    
    def __init__(self):
        super().__init__()
        self.db = ChatDatabase()
        self.messages = []
        
    def compose(self) -> ComposeResult:
        """Create the simplified application layout."""
        yield Header()
        
        with Vertical(id="main-content"):
            # Simple header with conversation title
            yield Static("New Conversation", id="conversation-title")
            
            # Messages area
            with ScrollableContainer(id="messages-container"):
                # Will be populated with messages
                pass
            
            # Loading indicator
            yield Static("Generating response...", id="loading-indicator", classes="hidden")
            
            # Input area
            with Container(id="input-area"):
                yield Input(placeholder="Type your message here...", id="message-input")
                yield Button("Send", id="send-button", variant="primary")
                with Horizontal():
                    yield Button("+ New Chat", id="new-chat-button")
        
        yield Footer()
        
    def on_mount(self) -> None:
        """Initialize the application on mount."""
        # Check API keys
        if not OPENAI_API_KEY and not ANTHROPIC_API_KEY:
            self.notify(
                "No API keys found. Set OPENAI_API_KEY or ANTHROPIC_API_KEY in .env file.",
                severity="error"
            )
            
        # Create a new conversation
        self.create_new_conversation()
        # Focus the input
        self.query_one("#message-input").focus()
        
    def create_new_conversation(self) -> None:
        """Create a new chat conversation."""
        # Create new conversation in database
        model = CONFIG["default_model"]
        style = CONFIG["default_style"]
        
        # Create a title for the new conversation
        title = f"New conversation ({datetime.now().strftime('%Y-%m-%d %H:%M')})"
        
        # Create conversation in database using the correct method
        conversation_id = self.db.create_conversation(title, model, style)
        
        # Get the full conversation data
        conversation_data = self.db.get_conversation(conversation_id)
        
        # Set as current conversation
        self.current_conversation = Conversation.from_dict(conversation_data)
        
        # Update UI
        title = self.query_one("#conversation-title", Static)
        title.update(self.current_conversation.title)
        
        # Clear messages
        self.messages = []
        self.update_messages_ui()
    
    def action_new_conversation(self) -> None:
        """Handle the new conversation action."""
        self.create_new_conversation()
        
    def action_escape(self) -> None:
        """Handle escape key."""
        if self.is_generating:
            self.is_generating = False
            self.notify("Generation stopped", severity="warning")
            loading = self.query_one("#loading-indicator")
            loading.add_class("hidden")
    
    def update_messages_ui(self) -> None:
        """Update the messages UI."""
        # Clear existing messages
        messages_container = self.query_one("#messages-container")
        messages_container.remove_children()
        
        # Add messages
        for message in self.messages:
            messages_container.mount(
                MessageDisplay(message, highlight_code=CONFIG["highlight_code"])
            )
            
        # Scroll to bottom
        messages_container.scroll_end(animate=False)
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id
        
        if button_id == "send-button":
            self.action_send_message()
        elif button_id == "new-chat-button":
            self.create_new_conversation()
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        self.action_send_message()
    
    def action_send_message(self) -> None:
        """Initiate message sending."""
        input_widget = self.query_one("#message-input", Input)
        content = input_widget.value.strip()
        
        if not content or not self.current_conversation:
            return
        
        # Clear input
        input_widget.value = ""
        
        # Create user message
        user_message = Message(role="user", content=content)
        self.messages.append(user_message)
        
        # Save to database
        self.db.add_message(
            self.current_conversation.id,
            "user",
            content
        )
        
        # Update UI
        self.update_messages_ui()
        
        # Generate AI response
        self.generate_response()
        
        # Focus back on input
        input_widget.focus()
    
    @work
    async def generate_response(self) -> None:
        """Generate an AI response."""
        if not self.current_conversation or not self.messages:
            return
            
        self.is_generating = True
        loading = self.query_one("#loading-indicator")
        loading.remove_class("hidden")
        
        try:
            # Get conversation parameters
            model = CONFIG["default_model"]
            style = CONFIG["default_style"]
            
            # Convert messages to API format
            api_messages = []
            for msg in self.messages:
                api_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
                
            # Get appropriate client
            client = BaseModelClient.get_client_for_model(model)
            
            # Start streaming response
            assistant_message = Message(role="assistant", content="")
            self.messages.append(assistant_message)
            
            # Stream chunks to the UI
            async def update_ui(chunk: str):
                if not self.is_generating:
                    return
                
                try:
                    assistant_message.content += chunk
                    self.update_messages_ui()
                except Exception as e:
                    self.notify(f"Error updating UI: {str(e)}", severity="error")
                
            # Generate the response
            full_response = await generate_streaming_response(
                api_messages,
                model,
                style,
                client,
                update_ui
            )
            
            # Save to database
            if self.is_generating:  # Only save if not cancelled
                self.db.add_message(
                    self.current_conversation.id,
                    "assistant",
                    full_response
                )
                
        except Exception as e:
            self.notify(f"Error generating response: {str(e)}", severity="error")
            # Add error message
            error_msg = f"Error generating response: {str(e)}"
            self.messages.append(Message(role="assistant", content=error_msg))
            self.update_messages_ui()
        finally:
            self.is_generating = False
            loading = self.query_one("#loading-indicator")
            loading.add_class("hidden")

if __name__ == "__main__":
    app = SimpleChatApp()
    app.run()
