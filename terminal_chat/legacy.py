
#!/usr/bin/env python3
import os
import sys
import asyncio
import logging
from typing import List, Dict, Any, Optional
import time
from pathlib import Path
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Header, Footer, Static
from textual.binding import Binding
from textual import work

from app.config import CONFIG, OPENAI_API_KEY, ANTHROPIC_API_KEY, APP_DIR

# Set up logging
log_path = APP_DIR / "debug.log"
logging.basicConfig(
    filename=str(log_path),
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('terminal_chat')

# Also log to stderr for immediate feedback
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
logger.addHandler(console_handler)
from app.database import ChatDatabase
from app.models import Message, Conversation
from app.api.base import BaseModelClient
from app.ui.chat_interface import ChatInterface
from app.ui.chat_list import ChatList
from app.ui.model_selector import ModelSelector, StyleSelector
from app.ui.search import SearchBar
from app.ui.styles import CSS
from app.utils import (
    create_new_conversation, 
    add_message_to_conversation,
    update_conversation_title,
    generate_streaming_response
)

class TerminalChatApp(App):
    """The main Terminal Chat application."""
    
    TITLE = "Terminal Chat"
    SUB_TITLE = "A ChatGPT/Claude experience in your terminal"
    CSS = CSS + """
    #main-layout {
        width: 100%;
        height: 100%;
        layout: vertical;
    }
    
    #main-content {
        width: 1fr;
        height: 100%;
        overflow: auto;
        padding: 0 1;
    }
    
    #sidebar {
        width: 30%;
        min-width: 20;
        max-width: 40%; 
        height: 100%;
        overflow: auto;
    }
    
    #chat-interface {
        width: 100%;
        height: 100%;
    }
    """
    
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("n", "new_conversation", "New Chat"),
        Binding("s", "toggle_sidebar", "Toggle Sidebar"),
        Binding("f", "search", "Search"),
        Binding("escape", "escape", "Cancel"),
        Binding("ctrl+c", "quit", "Quit"),
    ]
    
    current_conversation = reactive(None)
    sidebar_visible = reactive(True)
    
    def __init__(self):
        try:
            super().__init__()
            self.db = ChatDatabase()
            self.is_generating = False
            logger.info("TerminalChatApp initialized")
        except Exception as e:
            logger.error(f"Error initializing app: {e}", exc_info=True)
            raise
        
    def compose(self) -> ComposeResult:
        """Create the application layout."""
        yield Header()
        
        with Container(id="main-layout"):
            with Horizontal():
                # Sidebar
                with Container(id="sidebar"):
                    yield SearchBar(self.db, id="search-bar")
                    yield ChatList(self.db, id="chat-list")
                    with Container(id="model-container"):
                        yield ModelSelector(id="model-selector")
                        yield StyleSelector(id="style-selector")
                
                # Main content area
                with Container(id="main-content"):
                    yield ChatInterface(id="chat-interface")
        
        yield Footer()
        
    def on_mount(self) -> None:
        """Initialize the application on mount."""
        try:
            logger.info("App mounting")
            # Apply initial layout
            self.refresh_layout()
            
            # Check if API keys are set
            api_issues = []
            
            if not OPENAI_API_KEY:
                api_issues.append("- OPENAI_API_KEY is not set")
                
            if not ANTHROPIC_API_KEY:
                api_issues.append("- ANTHROPIC_API_KEY is not set")
                
            if api_issues:
                self.notify(
                    "API key issues detected:\n" + "\n".join(api_issues) + 
                    "\n\nSet them in your .env file or environment variables.",
                    title="API Key Warning",
                    severity="warning",
                    timeout=10
                )
            
            # Create a new conversation if none exists
            self.create_new_conversation()
            
            # Focus the input field after layout is ready
            self.call_after_refresh(self.focus_input)
            
        except Exception as e:
            logger.error(f"Error during app mount: {e}", exc_info=True)
            self.notify(f"Error initializing app: {str(e)}", severity="error")
        
    def focus_input(self) -> None:
        """Focus the input field"""
        try:
            logger.debug("Attempting to focus input")
            chat_interface = self.query_one("#chat-interface", ChatInterface)
            if chat_interface:
                input_field = chat_interface.query_one("#message-input")
                if input_field:
                    logger.debug("Found input field, setting focus")
                    # Clear any existing focus first
                    if self.focused:
                        self.focused.blur()
                    # Set focus to input field
                    input_field.focus()
                    logger.debug("Focus set successfully")
                else:
                    logger.error("Input field not found")
            else:
                logger.error("Chat interface not found")
        except Exception as e:
            logger.error(f"Error focusing input: {e}", exc_info=True)
            self.notify(f"Error focusing input: {str(e)}", severity="warning")
        
    def create_new_conversation(self) -> None:
        """Create a new chat conversation."""
        # Get selected model and style with robust error handling
        model = CONFIG["default_model"]
        style = CONFIG["default_style"]
        
        try:
            model_selector = self.query_one("#model-selector", ModelSelector)
            if model_selector:
                model = model_selector.get_selected_model()
        except Exception as e:
            self.notify(f"Error getting model: {str(e)}", severity="warning")
            
        try:
            style_selector = self.query_one("#style-selector", StyleSelector)
            if style_selector:
                style = style_selector.get_selected_style()
        except Exception as e:
            self.notify(f"Error getting style: {str(e)}", severity="warning")
        
        try:
            # Create new conversation in database
            conversation = create_new_conversation(self.db, model, style)
            self.current_conversation = conversation
            
            # Update UI safely
            try:
                chat_interface = self.query_one("#chat-interface", ChatInterface)
                if chat_interface:
                    chat_interface.set_conversation(conversation)
            except Exception as e:
                self.notify(f"Error updating chat interface: {str(e)}", severity="error")
            
            try:
                chat_list = self.query_one("#chat-list", ChatList)
                if chat_list:
                    chat_list.refresh()
                    chat_list.selected_id = conversation.id
            except Exception as e:
                self.notify(f"Error updating chat list: {str(e)}", severity="error")
        except Exception as e:
            self.notify(f"Failed to create conversation: {str(e)}", severity="error")
        
    def action_new_conversation(self) -> None:
        """Handle the new conversation action."""
        self.create_new_conversation()
        
    def action_toggle_sidebar(self) -> None:
        """Toggle the sidebar visibility."""
        self.sidebar_visible = not self.sidebar_visible
        sidebar = self.query_one("#sidebar")
        sidebar.display = True if self.sidebar_visible else False
        
    def action_search(self) -> None:
        """Focus the search input."""
        search_input = self.query_one("#search-bar #search-input")
        self.set_focus(search_input)
        
    def action_escape(self) -> None:
        """Handle escape key."""
        if self.is_generating:
            # Stop generation
            self.is_generating = False
            chat_interface = self.query_one("#chat-interface", ChatInterface)
            chat_interface.stop_loading()
            self.notify("Generation stopped.", severity="warning")
            
    def on_resize(self, event) -> None:
        """Handle terminal resize events"""
        try:
            # Update the layout to fit the new terminal size
            self.refresh_layout()
            
            # Re-focus the input field
            chat_interface = self.query_one("#chat-interface", ChatInterface)
            input_field = chat_interface.query_one("#message-input")
            input_field.focus()
        except Exception as e:
            self.notify(f"Error handling resize: {str(e)}", severity="warning")
            
    def refresh_layout(self) -> None:
        """Refresh the layout based on terminal size"""
        try:
            # Adjust sidebar width proportionally to terminal width
            sidebar = self.query_one("#sidebar")
            main_content = self.query_one("#main-content")
            
            # Set sidebar width based on terminal width
            # Larger terminals get proportionally smaller sidebar
            terminal_width = self.size.width
            
            if terminal_width < 80:  # Small terminal
                sidebar_pct = 40
            elif terminal_width < 120:  # Medium terminal
                sidebar_pct = 35
            else:  # Large terminal
                sidebar_pct = 30
                
            sidebar.styles.width = f"{sidebar_pct}%"
            main_content.styles.width = f"{100 - sidebar_pct}%"
            
            # Force a refresh of the rendering
            self.refresh()
        except Exception as e:
            # Don't notify as this could be spammy
            pass
        
    def on_chat_interface_message_sent(self, event: ChatInterface.MessageSent) -> None:
        """Handle message sent from chat interface."""
        if not self.current_conversation:
            self.create_new_conversation()
            
        # Add user message to conversation
        add_message_to_conversation(
            self.db, 
            self.current_conversation, 
            "user", 
            event.content
        )
        
        # Generate assistant response
        self.generate_assistant_response()
        
    @work
    async def generate_assistant_response(self) -> None:
        """Generate an assistant response to the current conversation."""
        if not self.current_conversation or not self.current_conversation.messages:
            return
            
        self.is_generating = True
        chat_interface = self.query_one("#chat-interface", ChatInterface)
        chat_interface.start_loading()
        
        # Ensure scrolled to bottom before generation starts
        chat_interface.scroll_to_bottom()
        
        try:
            # Get conversation parameters
            model = self.current_conversation.model
            style = self.current_conversation.style
            
            # Convert messages to API format
            api_messages = []
            for msg in self.current_conversation.messages:
                api_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
                
            # Get appropriate client
            client = BaseModelClient.get_client_for_model(model)
            
            # Start streaming response
            assistant_message = Message(role="assistant", content="")
            
            # Stream chunks to the UI
            async def update_ui(chunk: str):
                if not self.is_generating:
                    return
                
                try:
                    assistant_message.content += chunk
                    chat_interface.add_message("assistant", assistant_message.content, update_last=True)
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
            
            # Add the full response to the database
            if self.is_generating:  # Only save if not cancelled
                add_message_to_conversation(
                    self.db,
                    self.current_conversation,
                    "assistant",
                    full_response
                )
                
                # Update chat list
                chat_list = self.query_one("#chat-list", ChatList)
                chat_list.refresh()
                
                # Make sure we're scrolled to the bottom after response
                chat_interface.scroll_to_bottom()
                
                # Re-focus the input field
                input_field = chat_interface.query_one("#message-input")
                input_field.focus()
                
        except Exception as e:
            self.notify(f"Error generating response: {str(e)}", severity="error")
        finally:
            self.is_generating = False
            chat_interface.stop_loading()
            
    def on_chat_list_new_chat_requested(self, event) -> None:
        """Handle new chat request from the chat list."""
        self.create_new_conversation()
        
    def on_chat_list_chat_selected(self, event: ChatList.ChatSelected) -> None:
        """Handle chat selection from the chat list."""
        try:
            if not event or not event.conversation:
                return
                
            self.current_conversation = event.conversation
            
            # Update UI with robust error handling
            try:
                chat_interface = self.query_one("#chat-interface", ChatInterface)
                if chat_interface:
                    chat_interface.set_conversation(event.conversation)
            except Exception as e:
                self.notify(f"Error updating chat interface: {str(e)}", severity="error")
            
            # Update model selector with robust error handling
            try:
                if event.conversation.model:
                    model_selector = self.query_one("#model-selector", ModelSelector)
                    if model_selector:
                        model_selector.set_selected_model(event.conversation.model)
            except Exception as e:
                self.notify(f"Error updating model selector: {str(e)}", severity="warning")
            
            # Update style selector with robust error handling
            try:
                if event.conversation.style:
                    style_selector = self.query_one("#style-selector", StyleSelector)
                    if style_selector:
                        style_selector.set_selected_style(event.conversation.style)
            except Exception as e:
                self.notify(f"Error updating style selector: {str(e)}", severity="warning")
        except Exception as e:
            self.notify(f"Error selecting chat: {str(e)}", severity="error")
        
    def on_search_bar_search_result_selected(self, event: SearchBar.SearchResultSelected) -> None:
        """Handle search result selection."""
        try:
            if not event or not hasattr(event, 'conversation_id'):
                return
                
            conversation_data = self.db.get_conversation(event.conversation_id)
            if not conversation_data:
                self.notify("Conversation not found", severity="warning")
                return
                
            # Update chat list selection safely
            try:
                chat_list = self.query_one("#chat-list", ChatList)
                if chat_list:
                    chat_list.selected_id = event.conversation_id
            except Exception as e:
                self.notify(f"Error updating chat list: {str(e)}", severity="error")
            
            # Load conversation
            try:
                self.current_conversation = Conversation.from_dict(conversation_data)
            except Exception as e:
                self.notify(f"Error parsing conversation data: {str(e)}", severity="error")
                return
            
            # Update UI components safely
            try:
                chat_interface = self.query_one("#chat-interface", ChatInterface)
                if chat_interface:
                    chat_interface.set_conversation(self.current_conversation)
            except Exception as e:
                self.notify(f"Error updating chat interface: {str(e)}", severity="error")
            
            # Update model selector safely
            try:
                if self.current_conversation.model:
                    model_selector = self.query_one("#model-selector", ModelSelector)
                    if model_selector:
                        model_selector.set_selected_model(self.current_conversation.model)
            except Exception as e:
                self.notify(f"Error updating model selector: {str(e)}", severity="warning")
            
            # Update style selector safely
            try:
                if self.current_conversation.style:
                    style_selector = self.query_one("#style-selector", StyleSelector)
                    if style_selector:
                        style_selector.set_selected_style(self.current_conversation.style)
            except Exception as e:
                self.notify(f"Error updating style selector: {str(e)}", severity="warning")
        except Exception as e:
            self.notify(f"Error handling search result: {str(e)}", severity="error")
            
    def on_model_selector_model_selected(self, event: ModelSelector.ModelSelected) -> None:
        """Handle model selection."""
        try:
            if not event or not hasattr(event, 'model_id'):
                return
                
            if not self.current_conversation:
                self.notify("No active conversation to set model", severity="warning")
                return
                
            model_id = event.model_id
            
            # Update model in the database with error handling
            try:
                self.db.update_conversation(self.current_conversation.id, model=model_id)
                self.current_conversation.model = model_id
                self.notify(f"Model changed to {model_id}", severity="information")
            except Exception as e:
                self.notify(f"Error updating model in database: {str(e)}", severity="error")
        except Exception as e:
            self.notify(f"Error handling model selection: {str(e)}", severity="error")
            
    def on_style_selector_style_selected(self, event: StyleSelector.StyleSelected) -> None:
        """Handle style selection."""
        try:
            if not event or not hasattr(event, 'style_id'):
                return
                
            if not self.current_conversation:
                self.notify("No active conversation to set style", severity="warning")
                return
                
            style_id = event.style_id
            
            # Update style in the database with error handling
            try:
                self.db.update_conversation(self.current_conversation.id, style=style_id)
                self.current_conversation.style = style_id
                self.notify(f"Style changed to {style_id}", severity="information")
            except Exception as e:
                self.notify(f"Error updating style in database: {str(e)}", severity="error")
        except Exception as e:
            self.notify(f"Error handling style selection: {str(e)}", severity="error")
            
def main():
    """Run the application."""
    try:
        logger.info("Starting Terminal Chat")
        app = TerminalChatApp()
        app.run()
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    main()
