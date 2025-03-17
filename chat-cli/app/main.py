#!/usr/bin/env python3
"""
Simplified version of Chat CLI with AI functionality
"""
import os
import asyncio
import typer
from typing import List, Optional, Callable, Awaitable
from datetime import datetime

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer, Center
from textual.reactive import reactive
from textual.widgets import Button, Input, Label, Static, Header, Footer, ListView, ListItem
from textual.binding import Binding
from textual import work
from textual.screen import Screen
from openai import OpenAI
from app.models import Message, Conversation
from app.database import ChatDatabase
from app.config import CONFIG, OPENAI_API_KEY, ANTHROPIC_API_KEY, OLLAMA_BASE_URL
from app.ui.chat_interface import MessageDisplay
from app.ui.model_selector import ModelSelector, StyleSelector
from app.ui.chat_list import ChatList
from app.api.base import BaseModelClient
from app.utils import generate_streaming_response

class SettingsScreen(Screen):
    """Screen for model and style settings."""
    
    CSS = """
    #settings-container {
        width: 60;
        height: auto;
        background: $surface;
        border: solid $primary;
        padding: 1;
    }
    
    #title {
        width: 100%;
        height: 2;
        content-align: center middle;
        text-align: center;
        background: $surface-darken-2;
        border-bottom: solid $primary-darken-2;
    }

    #button-row {
        width: 100%;
        height: auto;
        align-horizontal: right;
        margin-top: 1;
    }

    #button-row Button {
        width: auto;
        min-width: 8;
        height: 2;
        margin-left: 1;
        border: solid $primary;
        color: $text;
        background: $primary-darken-1;
        content-align: center middle;
    }
    """

    def compose(self) -> ComposeResult:
        """Create the settings screen layout."""
        with Center():
            with Container(id="settings-container"):
                yield Static("Settings", id="title")
                yield ModelSelector(self.app.selected_model)
                yield StyleSelector(self.app.selected_style)
                with Horizontal(id="button-row"):
                    yield Button("Cancel", variant="default")
                    yield Button("Done", variant="primary")

    BINDINGS = [
        Binding("escape", "action_cancel", "Cancel"),
    ]

    def action_cancel(self) -> None:
        """Handle cancel action"""
        self.app.pop_screen()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses in settings screen."""
        # Pop screen for both Done and Cancel
        self.app.pop_screen()
        
        # Only update settings if Done was pressed
        if event.button.label == "Done":
            try:
                # Save settings globally
                from app.utils import save_settings_to_config
                save_settings_to_config(self.app.selected_model, self.app.selected_style)
                
                # Update current conversation if one exists
                if self.app.current_conversation:
                    self.app.db.update_conversation(
                        self.app.current_conversation.id,
                        model=self.app.selected_model,
                        style=self.app.selected_style
                    )
                    self.app.current_conversation.model = self.app.selected_model
                    self.app.current_conversation.style = self.app.selected_style
            except Exception as e:
                self.app.notify(f"Error updating settings: {str(e)}", severity="error")

class HistoryScreen(Screen):
    """Screen for viewing chat history."""
    
    BINDINGS = [
        Binding("escape", "pop_screen", "Close"),
    ]
    
    CSS = """
    #history-container {
        width: 80;
        height: 40;
        background: $surface;
        border: round $primary;
        padding: 1;
    }
    
    #title {
        width: 100%;
        content-align: center middle;
        text-align: center;
        padding-bottom: 1;
    }
    
    ListView {
        width: 100%;
        height: 1fr;
        border: solid $primary;
    }
    
    ListItem {
        padding: 1;
        border-bottom: solid $primary-darken-2;
    }
    
    ListItem:hover {
        background: $primary-darken-1;
    }
    
    #button-row {
        width: 100%;
        height: 3;
        align-horizontal: center;
        margin-top: 1;
    }
    """

    def __init__(self, conversations: List[dict], callback: Callable[[int], Awaitable[None]]):
        super().__init__()
        self.conversations = conversations
        self.callback = callback

    def compose(self) -> ComposeResult:
        """Create the history screen layout."""
        with Center():
            with Container(id="history-container"):
                yield Static("Chat History", id="title")
                yield ListView(id="history-list")
                with Horizontal(id="button-row"):
                    yield Button("Cancel", variant="primary")

    async def on_mount(self) -> None:
        """Initialize the history list after mount."""
        list_view = self.query_one("#history-list", ListView)
        for conv in self.conversations:
            title = conv["title"]
            model = conv["model"]
            if model in CONFIG["available_models"]:
                model = CONFIG["available_models"][model]["display_name"]
            item = ListItem(Label(f"{title} ({model})"))
            # Prefix numeric IDs with 'conv-' to make them valid identifiers
            item.id = f"conv-{conv['id']}"
            await list_view.mount(item)

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle conversation selection."""
        # Remove 'conv-' prefix to get the numeric ID
        conv_id = int(event.item.id.replace('conv-', ''))
        self.app.pop_screen()
        await self.callback(conv_id)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.label == "Cancel":
            self.app.pop_screen()

class SimpleChatApp(App):
    """Simplified Chat CLI application."""
    
    TITLE = "Chat CLI"
    SUB_TITLE = "AI Chat Interface"
    DARK = True
    
    CSS = """
    #main-content {
        width: 100%;
        height: 100%;
        padding: 0 1;
    }

    #conversation-title {
        width: 100%;
        height: 2;
        background: $surface-darken-2;
        color: $text;
        content-align: center middle;
        text-align: center;
        border-bottom: solid $primary-darken-2;
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
        min-height: 2;
        height: auto;
        margin-right: 1;
        border: solid $primary-darken-2;
    }

    #message-input:focus {
        border: solid $primary;
    }

    #send-button {
        width: auto;
        min-width: 8;
        height: 2;
        color: #FFFFFF !important;
        background: $primary;
        border: solid $primary;
        content-align: center middle;
        text-style: bold;  /* Add this line */
    }


    #button-row {
        width: 100%;
        height: auto;
        align-horizontal: right;
    }

    #new-chat-button {
        width: auto;
        min-width: 8;
        height: 2;
        color: #FFFFFF !important;  /* Force white text */
        background: $success;
        border: solid $success-lighten-1;
        content-align: center middle;
        text-style: bold;
    }

    #view-history-button, #settings-button {
        width: auto;
        min-width: 8;
        height: 2;
        color: #FFFFFF !important;  /* Force white text */
        background: $primary-darken-1;
        border: solid $primary;
        margin-right: 1;
        content-align: center middle;
        text-style: bold;
    }
    """
    
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("n", "action_new_conversation", "New Chat"),
        Binding("escape", "escape", "Cancel"),
        Binding("ctrl+c", "quit", "Quit"),
    ]
    
    current_conversation = reactive(None)
    is_generating = reactive(False)
    
    def __init__(self, initial_text: Optional[str] = None):
        super().__init__()
        self.db = ChatDatabase()
        self.messages = []
        self.selected_model = CONFIG["default_model"]
        self.selected_style = CONFIG["default_style"]
        self.initial_text = initial_text
        
    def compose(self) -> ComposeResult:
        """Create the simplified application layout."""
        yield Header()
        
        with Vertical(id="main-content"):
            # Conversation title
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
                with Horizontal(id="button-row"):
                    yield Button("Settings", id="settings-button", variant="primary")
                    yield Button("View History", id="view-history-button", variant="primary")
                    yield Button("+ New Chat", id="new-chat-button")
        
        yield Footer()
        
    async def on_mount(self) -> None:
        """Initialize the application on mount."""
        # Check API keys and services
        api_issues = []
        if not OPENAI_API_KEY:
            api_issues.append("- OPENAI_API_KEY is not set")
        if not ANTHROPIC_API_KEY:
            api_issues.append("- ANTHROPIC_API_KEY is not set")
            
        # Check Ollama availability and try to start if not running
        from app.utils import ensure_ollama_running
        if not ensure_ollama_running():
            api_issues.append("- Ollama server not running and could not be started")
        else:
            # Check for available models
            from app.api.ollama import OllamaClient
            try:
                ollama = OllamaClient()
                models = await ollama.get_available_models()
                if not models:
                    api_issues.append("- No Ollama models found")
            except Exception:
                api_issues.append("- Error connecting to Ollama server")
        
        if api_issues:
            self.notify(
                "Service issues detected:\n" + "\n".join(api_issues) + 
                "\n\nEnsure services are configured and running.",
                title="Service Warning",
                severity="warning",
                timeout=10
            )
            
        # Create a new conversation
        await self.create_new_conversation()
        
        # If initial text was provided, send it
        if self.initial_text:
            input_widget = self.query_one("#message-input", Input)
            input_widget.value = self.initial_text
            await self.action_send_message()
        else:
            # Focus the input if no initial text
            self.query_one("#message-input").focus()
        
    async def create_new_conversation(self) -> None:
        """Create a new chat conversation."""
        # Create new conversation in database using selected model and style
        model = self.selected_model
        style = self.selected_style
        
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
        
        # Clear messages and update UI
        self.messages = []
        await self.update_messages_ui()
        
    async def action_new_conversation(self) -> None:
        """Handle the new conversation action."""
        await self.create_new_conversation()
        
    def action_escape(self) -> None:
        """Handle escape key."""
        if self.is_generating:
            self.is_generating = False
            self.notify("Generation stopped", severity="warning")
            loading = self.query_one("#loading-indicator")
            loading.add_class("hidden")
        elif self.screen is not self.screen_stack[-1]:
            # If we're in a sub-screen, pop it
            self.pop_screen()
    
    async def update_messages_ui(self) -> None:
        """Update the messages UI."""
        # Clear existing messages
        messages_container = self.query_one("#messages-container")
        messages_container.remove_children()
        
        # Add messages with a small delay between each
        for message in self.messages:
            display = MessageDisplay(message, highlight_code=CONFIG["highlight_code"])
            messages_container.mount(display)
            messages_container.scroll_end(animate=False)
            await asyncio.sleep(0.01)  # Small delay to prevent UI freezing
            
        # Final scroll to bottom
        messages_container.scroll_end(animate=False)
    
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        await self.action_send_message()
    
    async def action_send_message(self) -> None:
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
        await self.update_messages_ui()
        
        # Generate AI response
        await self.generate_response()
        
        # Focus back on input
        input_widget.focus()
    
    async def generate_response(self) -> None:
        """Generate an AI response."""
        if not self.current_conversation or not self.messages:
            return
            
        self.is_generating = True
        loading = self.query_one("#loading-indicator")
        loading.remove_class("hidden")
        
        try:
            # Get conversation parameters
            model = self.selected_model
            style = self.selected_style
            
            # Convert messages to API format
            api_messages = []
            for msg in self.messages:
                api_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
                
            # Get appropriate client
            try:
                client = BaseModelClient.get_client_for_model(model)
                if client is None:
                    raise Exception(f"No client available for model: {model}")
            except Exception as e:
                self.notify(f"Failed to initialize model client: {str(e)}", severity="error")
                return
                
            # Start streaming response
            assistant_message = Message(role="assistant", content="Thinking...")
            self.messages.append(assistant_message)
            messages_container = self.query_one("#messages-container")
            message_display = MessageDisplay(assistant_message, highlight_code=CONFIG["highlight_code"])
            messages_container.mount(message_display)
            messages_container.scroll_end(animate=False)
            
            # Add small delay to show thinking state
            await asyncio.sleep(0.5)
            
            # Stream chunks to the UI with synchronization
            update_lock = asyncio.Lock()
            
            async def update_ui(content: str):
                if not self.is_generating:
                    return
                
                async with update_lock:
                    try:
                        # Clear thinking indicator on first content
                        if assistant_message.content == "Thinking...":
                            assistant_message.content = ""
                        
                        # Update message with full content so far
                        assistant_message.content = content
                        # Update UI with full content
                        await message_display.update_content(content)
                        # Force a refresh and scroll
                        self.refresh(layout=True)
                        await asyncio.sleep(0.05)  # Longer delay for UI stability
                        messages_container.scroll_end(animate=False)
                        # Force another refresh to ensure content is visible
                        self.refresh(layout=True)
                    except Exception as e:
                        logger.error(f"Error updating UI: {str(e)}")
                
            # Generate the response with timeout and cleanup
            generation_task = None
            try:
                # Create a task for the response generation
                generation_task = asyncio.create_task(
                    generate_streaming_response(
                        api_messages,
                        model,
                        style,
                        client,
                        update_ui
                    )
                )
                
                # Wait for response with timeout
                full_response = await asyncio.wait_for(generation_task, timeout=60)  # Longer timeout
                
                # Save to database only if we got a complete response
                if self.is_generating and full_response:
                    self.db.add_message(
                        self.current_conversation.id,
                        "assistant",
                        full_response
                    )
                    # Force a final refresh
                    self.refresh(layout=True)
                    await asyncio.sleep(0.1)  # Wait for UI to update
                    
            except asyncio.TimeoutError:
                logger.error("Response generation timed out")
                error_msg = "Response generation timed out. The model may be busy or unresponsive. Please try again."
                self.notify(error_msg, severity="error")
                
                # Remove the incomplete message
                if self.messages and self.messages[-1].role == "assistant":
                    self.messages.pop()
                
                # Update UI to remove the incomplete message
                await self.update_messages_ui()
                
            finally:
                # Ensure task is properly cancelled and cleaned up
                if generation_task:
                    if not generation_task.done():
                        generation_task.cancel()
                        try:
                            await generation_task
                        except (asyncio.CancelledError, Exception) as e:
                            logger.error(f"Error cleaning up generation task: {str(e)}")
                    
                # Force a final UI refresh
                self.refresh(layout=True)
                
        except Exception as e:
            self.notify(f"Error generating response: {str(e)}", severity="error")
            # Add error message
            error_msg = f"Error generating response: {str(e)}"
            self.messages.append(Message(role="assistant", content=error_msg))
            await self.update_messages_ui()
        finally:
            self.is_generating = False
            loading = self.query_one("#loading-indicator")
            loading.add_class("hidden")
            
    def on_model_selector_model_selected(self, event: ModelSelector.ModelSelected) -> None:
        """Handle model selection"""
        self.selected_model = event.model_id
        
    def on_style_selector_style_selected(self, event: StyleSelector.StyleSelected) -> None:
        """Handle style selection"""
        self.selected_style = event.style_id
        
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id
        
        if button_id == "send-button":
            await self.action_send_message()
        elif button_id == "new-chat-button":
            await self.create_new_conversation()
        elif button_id == "settings-button":
            self.push_screen(SettingsScreen())
        elif button_id == "view-history-button":
            await self.view_chat_history()
            
    async def view_chat_history(self) -> None:
        """Show chat history in a popup."""
        # Get recent conversations
        conversations = self.db.get_all_conversations(limit=CONFIG["max_history_items"])
        if not conversations:
            self.notify("No chat history found", severity="warning")
            return
            
        async def handle_selection(selected_id: int) -> None:
            if not selected_id:
                return
                
            # Get full conversation
            conversation_data = self.db.get_conversation(selected_id)
            if not conversation_data:
                self.notify("Could not load conversation", severity="error")
                return
                
            # Update current conversation
            self.current_conversation = Conversation.from_dict(conversation_data)
            
            # Update title
            title = self.query_one("#conversation-title", Static)
            title.update(self.current_conversation.title)
            
            # Load messages
            self.messages = [Message(**msg) for msg in self.current_conversation.messages]
            await self.update_messages_ui()
            
            # Update model and style selectors
            self.selected_model = self.current_conversation.model
            self.selected_style = self.current_conversation.style
            
        self.push_screen(HistoryScreen(conversations, handle_selection))

def main(initial_text: Optional[str] = typer.Argument(None, help="Initial text to start the chat with")):
    """Entry point for the chat-cli application"""
    # When no argument is provided, typer passes the ArgumentInfo object
    # When an argument is provided, typer passes the actual value
    if isinstance(initial_text, typer.models.ArgumentInfo):
        initial_value = None  # No argument provided
    else:
        initial_value = str(initial_text) if initial_text is not None else None
        
    app = SimpleChatApp(initial_text=initial_value)
    app.run()

if __name__ == "__main__":
    typer.run(main)
