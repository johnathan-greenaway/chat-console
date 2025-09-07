#!/usr/bin/env python3
"""
Simplified version of Chat CLI with AI functionality
"""
import os
import asyncio
import typer
import logging
import time
from typing import List, Optional, Callable, Awaitable
from datetime import datetime

# Create a dedicated logger that definitely writes to a file
log_dir = os.path.expanduser("~/.cache/chat-cli")
os.makedirs(log_dir, exist_ok=True)
debug_log_file = os.path.join(log_dir, "debug.log")

# Configure the logger
file_handler = logging.FileHandler(debug_log_file)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# Get the logger and add the handler
debug_logger = logging.getLogger()  # Root logger
debug_logger.setLevel(logging.DEBUG)
debug_logger.addHandler(file_handler)
# CRITICAL: Force all output to the file, not stdout
debug_logger.propagate = False

# Add a convenience function to log to this file
def debug_log(message):
    debug_logger.info(message)

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer, Center
from textual.reactive import reactive
from textual.widgets import Button, Input, Label, Static, Header, Footer, ListView, ListItem
from textual.binding import Binding
from textual import work, log, on
from textual.worker import Worker, WorkerState # Import Worker class and WorkerState enum
from textual.screen import Screen
from openai import OpenAI
from app.models import Message, Conversation
from app.database import ChatDatabase
from app.config import CONFIG, OPENAI_API_KEY, ANTHROPIC_API_KEY, OLLAMA_BASE_URL
# Import InputWithFocus as well
from app.ui.chat_interface import MessageDisplay, InputWithFocus
from app.ui.model_selector import ModelSelector, StyleSelector
from app.ui.chat_list import ChatList
from app.ui.model_browser import ModelBrowser
from app.ui.settings import SettingsScreen
from app.api.base import BaseModelClient
from app.utils import generate_streaming_response, save_settings_to_config, generate_conversation_title, resolve_model_id # Import resolver
# Import version here to avoid potential circular import issues at top level
from app import __version__

# --- Remove SettingsScreen class entirely ---

class ModelBrowserScreen(Screen):
    """Screen for browsing Ollama models."""

    BINDINGS = [
        Binding("escape", "pop_screen", "Close"),
    ]
    
    CSS = """
    #browser-wrapper {
        width: 100%;
        height: 100%;
        background: $surface;
    }
    """
    
    def compose(self) -> ComposeResult:
        """Create the model browser screen layout."""
        with Container(id="browser-wrapper"):
            yield ModelBrowser()

class HistoryScreen(Screen):
    """Screen for viewing chat history."""

    BINDINGS = [
        Binding("escape", "pop_screen", "Close"),
    ]

    CSS = """
    #history-container {
        width: 80; # Keep HistoryScreen CSS
        height: 40;
        background: $surface;
        border: round $primary;
        padding: 1; # Keep HistoryScreen CSS
    }

    #title { # Keep HistoryScreen CSS
        width: 100%; # Keep HistoryScreen CSS
        content-align: center middle;
        text-align: center;
        padding-bottom: 1;
    }

    ListView { # Keep HistoryScreen CSS
        width: 100%; # Keep HistoryScreen CSS
        height: 1fr;
        border: solid $primary;
    }

    ListItem { # Keep HistoryScreen CSS
        padding: 1; # Keep HistoryScreen CSS
        border-bottom: solid $primary-darken-2;
    }

    ListItem:hover { # Keep HistoryScreen CSS
        background: $primary-darken-1; # Keep HistoryScreen CSS
    }

    #button-row { # Keep HistoryScreen CSS
        width: 100%; # Keep HistoryScreen CSS
        height: 3;
        align-horizontal: center;
        margin-top: 1; # Keep HistoryScreen CSS
    }
    """

    def __init__(self, conversations: List[dict], callback: Callable[[int], Awaitable[None]]): # Keep HistoryScreen __init__
        super().__init__() # Keep HistoryScreen __init__
        self.conversations = conversations # Keep HistoryScreen __init__
        self.callback = callback # Keep HistoryScreen __init__

    def compose(self) -> ComposeResult: # Keep HistoryScreen compose
        """Create the history screen layout."""
        with Center():
            with Container(id="history-container"):
                yield Static("Chat History", id="title")
                yield ListView(id="history-list")
                with Horizontal(id="button-row"):
                    yield Button("Cancel", variant="primary")

    async def on_mount(self) -> None: # Keep HistoryScreen on_mount
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

    async def on_list_view_selected(self, event: ListView.Selected) -> None: # Keep HistoryScreen on_list_view_selected
        """Handle conversation selection."""
        # Remove 'conv-' prefix to get the numeric ID
        conv_id = int(event.item.id.replace('conv-', ''))
        self.app.pop_screen()
        await self.callback(conv_id)

    def on_button_pressed(self, event: Button.Pressed) -> None: # Keep HistoryScreen on_button_pressed
        if event.button.label == "Cancel":
            self.app.pop_screen()

class SimpleChatApp(App): # Keep SimpleChatApp class definition
    """Simplified Chat CLI application.""" # Keep SimpleChatApp docstring

    TITLE = "Chat Console"
    SUB_TITLE = "AI Chat Interface" # Keep SimpleChatApp SUB_TITLE
    DARK = True # Keep SimpleChatApp DARK
    
    # Add better terminal handling to fix UI glitches
    SCREENS = {}
    
    # Force full screen mode and prevent background terminal showing through
    FULL_SCREEN = True
    
    # Force capturing all mouse events for better stability
    CAPTURE_MOUSE = True

    # Ensure the log directory exists in a standard cache location
    log_dir = os.path.expanduser("~/.cache/chat-cli")
    os.makedirs(log_dir, exist_ok=True)
    LOG_FILE = os.path.join(log_dir, "textual.log") # Use absolute path

    # Rams-inspired CSS following "As little design as possible"
    CSS = """
    /* Main layout - Clean foundation */
    #main-content {
        width: 100%;
        height: 100%;
        padding: 0;
        background: #0C0C0C;
    }

    /* App header with ASCII border aesthetic */
    #app-info-bar {
        width: 100%;
        height: 3;
        background: #0C0C0C;
        color: #E8E8E8;
        padding: 1 2;
        border-bottom: solid #333333 1;
    }

    #version-info {
        width: auto;
        text-align: left;
        color: #E8E8E8;
    }

    #model-info {
        width: 1fr;
        text-align: right;
        color: #666666;
    }

    /* Conversation title - Functional hierarchy */
    #conversation-title {
        width: 100%;
        height: 3;
        background: #0C0C0C;
        color: #E8E8E8;
        content-align: left middle;
        text-align: left;
        padding: 0 2;
        border-bottom: solid #333333 1;
    }

    /* Action buttons - Minimal design */
    #action-buttons {
        width: 100%;
        height: auto;
        padding: 2;
        align-horizontal: left;
        background: #0C0C0C;
        border-bottom: solid #333333 1;
    }

    #new-chat-button, #change-title-button {
        margin: 0 1 0 0;
        min-width: 12;
        background: transparent;
        color: #E8E8E8;
        border: solid #333333 1;
        padding: 1 2;
    }

    #new-chat-button:hover, #change-title-button:hover {
        background: #1A1A1A;
        border: solid #33FF33 1;
    }

    /* Messages container - Purposeful spacing */
    #messages-container {
        width: 100%;
        height: 1fr;
        min-height: 15;
        overflow: auto;
        padding: 2;
        background: #0C0C0C;
        border-bottom: solid #333333 1;
    }

    /* Loading indicator - Unobtrusive */
    #loading-indicator {
        width: 100%;
        height: 2;
        background: #0C0C0C;
        color: #666666;
        content-align: center middle;
        text-align: center;
        border-bottom: solid #333333 1;
        padding: 0 2;
    }

    #loading-indicator.hidden {
        display: none;
    }
    
    #loading-indicator.model-loading {
        color: #33FF33;
    }

    /* Input area - Clean and functional */
    #input-area {
        width: 100%;
        height: auto;
        min-height: 5;
        max-height: 12;
        padding: 2;
        background: #0C0C0C;
    }

    #message-input {
        width: 1fr;
        min-height: 3;
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

    /* Removed CSS for #send-button, #new-chat-button, #view-history-button, #settings-button */ # Keep SimpleChatApp CSS comment
    /* Removed CSS for #button-row */ # Keep SimpleChatApp CSS comment

    /* Settings panel - Clean modal design */
    #settings-panel {
        display: none;
        align: center middle;
        width: 60;
        height: auto;
        background: #0C0C0C;
        border: solid #333333 1;
        padding: 2;
        layer: settings;
    }

    #settings-panel.visible {
        display: block;
    }

    #settings-title {
        width: 100%;
        content-align: left middle;
        padding-bottom: 1;
        border-bottom: solid #333333 1;
        color: #E8E8E8;
        margin-bottom: 2;
    }

    #settings-buttons {
        width: 100%;
        height: auto;
        align: right middle;
        padding-top: 2;
    }

    #settings-save-button, #settings-cancel-button {
        background: transparent;
        color: #E8E8E8;
        border: solid #333333 1;
        margin-left: 1;
        padding: 1 2;
    }

    #settings-save-button:hover {
        background: #1A1A1A;
        border: solid #33FF33 1;
    }

    #settings-cancel-button:hover {
        background: #1A1A1A;
        border: solid #FF4444 1;
    }

    /* Title Input Modal - Minimal and focused */
    TitleInputModal {
        align: center middle;
        width: 60;
        height: auto;
        background: #0C0C0C;
        border: solid #333333 1;
        padding: 2;
        layer: modal;
    }

    #modal-label {
        width: 100%;
        content-align: left middle;
        padding-bottom: 1;
        color: #E8E8E8;
        border-bottom: solid #333333 1;
        margin-bottom: 2;
    }

    #title-input {
        width: 100%;
        margin-bottom: 2;
        background: #0C0C0C;
        color: #E8E8E8;
        border: solid #333333 1;
        padding: 1;
    }

    #title-input:focus {
        border: solid #33FF33 1;
        outline: none;
    }

    TitleInputModal Horizontal {
        width: 100%;
        height: auto;
        align: right middle;
        padding-top: 2;
    }

    #update-button, #cancel-button {
        background: transparent;
        color: #E8E8E8;
        border: solid #333333 1;
        margin-left: 1;
        padding: 1 2;
    }

    #update-button:hover {
        background: #1A1A1A;
        border: solid #33FF33 1;
    }

    #cancel-button:hover {
        background: #1A1A1A;
        border: solid #FF4444 1;
    }

    /* Message Display - Clean typography */
    MessageDisplay {
        width: 100%;
        height: auto;
        margin: 1 0;
        padding: 2;
        text-wrap: wrap;
        background: transparent;
    }
    
    MessageDisplay.user-message {
        background: #1A1A1A;
        border-left: solid #33FF33 2;
        margin-left: 2;
        margin-right: 8;
    }
    
    MessageDisplay.assistant-message {
        background: transparent;
        border-left: solid #666666 1;
        margin-right: 2;
        margin-left: 8;
    }
    """

    BINDINGS = [ # Keep SimpleChatApp BINDINGS, ensure Enter is not globally bound for settings
        Binding("q", "quit", "Quit", show=True, key_display="q"),
        Binding("c", "action_new_conversation", "New", show=True, key_display="c", priority=True),
        Binding("escape", "action_escape", "Cancel", show=True, key_display="esc"),
        Binding("ctrl+c", "quit", "Quit", show=False),
        Binding("h", "view_history", "History", show=True, key_display="h", priority=True),
        Binding("s", "settings", "Settings", show=True, key_display="s", priority=True),
        Binding("m", "model_browser", "Models", show=True, key_display="m", priority=True),
    ] # Keep SimpleChatApp BINDINGS end

    current_conversation = reactive(None) # Keep SimpleChatApp reactive var
    is_generating = reactive(False) # Keep SimpleChatApp reactive var
    current_generation_task: Optional[asyncio.Task] = None # Add task reference
    _loading_frame = 0 # Track animation frame
    _loading_animation_task: Optional[asyncio.Task] = None # Animation task

    def __init__(self, initial_text: Optional[str] = None): # Keep SimpleChatApp __init__
        super().__init__() # Keep SimpleChatApp __init__
        self.db = ChatDatabase() # Keep SimpleChatApp __init__
        self.messages = [] # Keep SimpleChatApp __init__
        # Resolve the default model ID on initialization
        default_model_from_config = CONFIG["default_model"]
        self.selected_model = resolve_model_id(default_model_from_config)
        self.selected_style = CONFIG["default_style"] # Keep SimpleChatApp __init__
        self.initial_text = initial_text # Keep SimpleChatApp __init__
        
        # Task for model cleanup
        self._model_cleanup_task = None
        
        # Inactivity threshold in minutes before releasing model resources
        # Read from config, default to 30 minutes
        self.MODEL_INACTIVITY_THRESHOLD = CONFIG.get("ollama_inactive_timeout_minutes", 30)

    def compose(self) -> ComposeResult: # Modify SimpleChatApp compose
        """Create the simplified application layout."""
        yield Header()

        with Vertical(id="main-content"):
            # Clean app header following Rams principles
            with Horizontal(id="app-info-bar"):
                yield Static(f"Chat Console v{__version__}", id="version-info")
                yield Static(self.selected_model, id="model-info")

            # Conversation title
            yield Static("New Conversation", id="conversation-title")

            # Action buttons - Minimal and functional
            with Horizontal(id="action-buttons"):
                yield Button("●", id="new-chat-button")  # Solid circle for "new"
                yield Button("✎", id="change-title-button")  # Pencil for "edit"

            # Messages area
            with ScrollableContainer(id="messages-container"):
                # Will be populated with messages
                pass

            # Minimal loading indicator
            yield Static("● Generating", id="loading-indicator", classes="hidden", markup=False)

            # Input area
            with Container(id="input-area"):
                # Use the custom InputWithFocus widget
                yield InputWithFocus(placeholder="Type your message here...", id="message-input")

            # --- Add Settings Panel (hidden initially) ---
            with Container(id="settings-panel"):
                 yield Static("Settings", id="settings-title")
                 yield ModelSelector(self.selected_model)
                 yield StyleSelector(self.selected_style)
                 with Horizontal(id="settings-buttons"):
                     yield Button("Save", id="settings-save-button", variant="success")
                     yield Button("Cancel", id="settings-cancel-button", variant="error")

        yield Footer()

    async def on_mount(self) -> None: # Keep SimpleChatApp on_mount
        """Initialize the application on mount.""" # Keep SimpleChatApp on_mount docstring
        # Add diagnostic logging for bindings
        print(f"Registered bindings: {self.__class__.BINDINGS}") # Corrected access to class attribute

        # Update the version display (already imported at top)
        try:
            version_info = self.query_one("#version-info", Static)
            version_info.update(f"Chat Console v{__version__}")
        except Exception:
            pass # Silently ignore if widget not found yet

        self.update_app_info()  # Update the model info
        
        # Start the background task for model cleanup if model preloading is enabled
        if CONFIG.get("ollama_model_preload", True):
            self._model_cleanup_task = asyncio.create_task(self._check_inactive_models())
            debug_log("Started background task for model cleanup")

        # Check API keys and services # Keep SimpleChatApp on_mount
        api_issues = [] # Keep SimpleChatApp on_mount
        if not OPENAI_API_KEY: # Keep SimpleChatApp on_mount
            api_issues.append("- OPENAI_API_KEY is not set") # Keep SimpleChatApp on_mount
        if not ANTHROPIC_API_KEY: # Keep SimpleChatApp on_mount
            api_issues.append("- ANTHROPIC_API_KEY is not set") # Keep SimpleChatApp on_mount

        # Check Ollama availability and try to start if not running # Keep SimpleChatApp on_mount
        from app.utils import ensure_ollama_running # Keep SimpleChatApp on_mount
        if not await ensure_ollama_running(): # Keep SimpleChatApp on_mount
            api_issues.append("- Ollama server not running and could not be started") # Keep SimpleChatApp on_mount
        else: # Keep SimpleChatApp on_mount
            # Check for available models # Keep SimpleChatApp on_mount
            from app.api.ollama import OllamaClient # Keep SimpleChatApp on_mount
            try: # Keep SimpleChatApp on_mount
                ollama = await OllamaClient.create() # Keep SimpleChatApp on_mount
                models = await ollama.get_available_models() # Keep SimpleChatApp on_mount
                if not models: # Keep SimpleChatApp on_mount
                    api_issues.append("- No Ollama models found") # Keep SimpleChatApp on_mount
            except Exception: # Keep SimpleChatApp on_mount
                api_issues.append("- Error connecting to Ollama server") # Keep SimpleChatApp on_mount

        if api_issues: # Keep SimpleChatApp on_mount
            self.notify( # Keep SimpleChatApp on_mount
                "Service issues detected:\n" + "\n".join(api_issues) +  # Keep SimpleChatApp on_mount
                "\n\nEnsure services are configured and running.", # Keep SimpleChatApp on_mount
                title="Service Warning", # Keep SimpleChatApp on_mount
                severity="warning", # Keep SimpleChatApp on_mount
                timeout=10 # Keep SimpleChatApp on_mount
            ) # Keep SimpleChatApp on_mount

        # Create a new conversation # Keep SimpleChatApp on_mount
        await self.create_new_conversation() # Keep SimpleChatApp on_mount

        # If initial text was provided, send it # Keep SimpleChatApp on_mount
        if self.initial_text: # Keep SimpleChatApp on_mount
            input_widget = self.query_one("#message-input", Input) # Keep SimpleChatApp on_mount
            input_widget.value = self.initial_text # Keep SimpleChatApp on_mount
            await self.action_send_message() # Keep SimpleChatApp on_mount
        else: # Keep SimpleChatApp on_mount
            # Focus the input if no initial text # Keep SimpleChatApp on_mount
            # Removed assignment to self.input_widget
            self.query_one("#message-input").focus() # Keep SimpleChatApp on_mount

    async def create_new_conversation(self) -> None: # Keep SimpleChatApp create_new_conversation
        """Create a new chat conversation.""" # Keep SimpleChatApp create_new_conversation docstring
        log("Entering create_new_conversation") # Added log
        # Create new conversation in database using selected model and style # Keep SimpleChatApp create_new_conversation
        model = self.selected_model # Keep SimpleChatApp create_new_conversation
        style = self.selected_style # Keep SimpleChatApp create_new_conversation

        # Clean title following Rams principles
        title = "New Conversation"

        # Create conversation in database using the correct method # Keep SimpleChatApp create_new_conversation
        log(f"Creating conversation with title: {title}, model: {model}, style: {style}") # Added log
        conversation_id = self.db.create_conversation(title, model, style) # Keep SimpleChatApp create_new_conversation
        log(f"Database returned conversation_id: {conversation_id}") # Added log

        # Get the full conversation data # Keep SimpleChatApp create_new_conversation
        conversation_data = self.db.get_conversation(conversation_id) # Keep SimpleChatApp create_new_conversation

        # Set as current conversation # Keep SimpleChatApp create_new_conversation
        self.current_conversation = Conversation.from_dict(conversation_data) # Keep SimpleChatApp create_new_conversation

        # Update UI # Keep SimpleChatApp create_new_conversation
        title_widget = self.query_one("#conversation-title", Static) # Keep SimpleChatApp create_new_conversation
        title_widget.update(self.current_conversation.title) # Keep SimpleChatApp create_new_conversation

        # Clear messages and update UI # Keep SimpleChatApp create_new_conversation
        self.messages = [] # Keep SimpleChatApp create_new_conversation
        log("Finished updating messages UI in create_new_conversation") # Added log
        await self.update_messages_ui() # Keep SimpleChatApp create_new_conversation
        self.update_app_info() # Update model info after potentially loading conversation

    async def action_new_conversation(self) -> None: # Keep SimpleChatApp action_new_conversation
        """Handle the new conversation action.""" # Keep SimpleChatApp action_new_conversation docstring
        log("--- ENTERING action_new_conversation ---") # Add entry log
        # Focus check removed - relying on priority=True in binding

        log("action_new_conversation EXECUTING") # Add execution log
        await self.create_new_conversation() # Keep SimpleChatApp action_new_conversation
        log("action_new_conversation finished") # Added log

    async def action_escape(self) -> None:
        """Handle escape key globally."""
        log("action_escape triggered")
        settings_panel = self.query_one("#settings-panel")
        log(f"Settings panel visible: {settings_panel.has_class('visible')}")

        if settings_panel.has_class("visible"):
            log("Hiding settings panel")
            settings_panel.remove_class("visible")
            self.query_one("#message-input").focus()
        elif self.is_generating:
            log("Attempting to cancel generation task")
            if self.current_generation_task and not self.current_generation_task.done():
                log("Cancelling active generation task.")
                
                # Get the client for the current model first and cancel the connection
                try:
                    model = self.selected_model
                    client = await BaseModelClient.get_client_for_model(model)
                    
                    # Call the client's cancel method if it's supported
                    if hasattr(client, 'cancel_stream'):
                        log("Calling client.cancel_stream() to terminate API session")
                        try:
                            # This will close the HTTP connection to Ollama server
                            await client.cancel_stream()
                            log("Client stream cancelled successfully")
                        except Exception as e:
                            log.error(f"Error in client.cancel_stream(): {str(e)}")
                except Exception as e:
                    log.error(f"Error setting up client cancellation: {str(e)}")
                
                # Now cancel the asyncio task - this should raise CancelledError in the task
                try:
                    log("Cancelling asyncio task")
                    self.current_generation_task.cancel()
                    # Give a moment for cancellation to propagate
                    await asyncio.sleep(0.1)
                    log(f"Task cancelled. Task done: {self.current_generation_task.done()}")
                except Exception as e:
                    log.error(f"Error cancelling task: {str(e)}")
                
                # Notify user that we're stopping
                self.notify("Stopping generation...", severity="warning", timeout=2)
            else:
                # This happens if is_generating is True, but no active task found to cancel
                log("No active generation task found, but is_generating=True. Resetting state.")
                self.is_generating = False
                
                # Make sure to cancel animation task too
                if self._loading_animation_task and not self._loading_animation_task.done():
                    try:
                        self._loading_animation_task.cancel()
                    except Exception as e:
                        log.error(f"Error cancelling animation task: {str(e)}")
                self._loading_animation_task = None
                
                loading = self.query_one("#loading-indicator")
                loading.add_class("hidden")
        else:
            log("Escape pressed, but settings not visible and not actively generating.")
            # Optionally add other escape behaviors here if needed

    def update_app_info(self) -> None:
        """Update app info following clean information architecture"""
        try:
            model_info = self.query_one("#model-info", Static)
            
            # Clean model display - no unnecessary decoration
            if self.selected_model in CONFIG["available_models"]:
                display_name = CONFIG["available_models"][self.selected_model]["display_name"]
                model_display = display_name
            else:
                model_display = self.selected_model

            model_info.update(model_display)
        except Exception as e:
            log.error(f"Error updating app info: {e}")
            pass

    async def update_messages_ui(self) -> None: # Keep SimpleChatApp update_messages_ui
        """Update the messages UI with improved stability.""" # Keep SimpleChatApp update_messages_ui docstring
        # Clear existing messages # Keep SimpleChatApp update_messages_ui
        messages_container = self.query_one("#messages-container") # Keep SimpleChatApp update_messages_ui
        messages_container.remove_children() # Keep SimpleChatApp update_messages_ui

        # Temporarily disable automatic refresh while mounting messages
        # This avoids excessive layout calculations and reduces flickering
        with self.batch_update():
            # Batch add all messages first without any refresh/layout
            for message in self.messages: # Keep SimpleChatApp update_messages_ui
                display = MessageDisplay(message, highlight_code=CONFIG["highlight_code"]) # Keep SimpleChatApp update_messages_ui
                messages_container.mount(display) # Keep SimpleChatApp update_messages_ui
        
        # A small delay after mounting all messages helps with layout stability
        await asyncio.sleep(0.05)
        
        # Scroll after all messages are added without animation
        messages_container.scroll_end(animate=False) # Keep SimpleChatApp update_messages_ui
        
        # Minimal refresh without full layout recalculation
        self.refresh(layout=False)

    async def on_input_submitted(self, event: Input.Submitted) -> None: # Keep SimpleChatApp on_input_submitted
        """Handle input submission (Enter key in the main input).""" # Keep SimpleChatApp on_input_submitted docstring
        await self.action_send_message() # Restore direct call # Keep SimpleChatApp on_input_submitted

    async def action_send_message(self) -> None: # Keep SimpleChatApp action_send_message
        """Initiate message sending.""" # Keep SimpleChatApp action_send_message docstring
        input_widget = self.query_one("#message-input", Input) # Keep SimpleChatApp action_send_message
        content = input_widget.value.strip() # Keep SimpleChatApp action_send_message

        if not content or not self.current_conversation: # Keep SimpleChatApp action_send_message
            return # Keep SimpleChatApp action_send_message

        # Check for commands
        if content.lower() == "/settings":
            input_widget.value = ""  # Clear input
            self.push_screen(SettingsScreen())
            return
        elif content.lower() == "/models":
            input_widget.value = ""  # Clear input  
            self.action_model_browser()
            return
        elif content.lower() == "/history":
            input_widget.value = ""  # Clear input
            await self.view_chat_history()
            return
        elif content.lower() == "/help":
            input_widget.value = ""  # Clear input
            # Display help message
            help_text = """Available commands:
• /settings - Open settings to configure Custom API
• /models - Browse available models
• /history - View chat history
• /help - Show this help message

Keyboard shortcuts:
• s - Open settings
• m - Browse models
• h - View history
• c - New conversation
• q - Quit"""
            help_message = Message(role="assistant", content=help_text)
            self.messages.append(help_message)
            message_display = self.query_one("#message-display", MessageDisplay)
            await message_display.display_message(help_message)
            return

        # Clear input # Keep SimpleChatApp action_send_message
        input_widget.value = "" # Keep SimpleChatApp action_send_message

        # Create user message # Keep SimpleChatApp action_send_message
        user_message = Message(role="user", content=content) # Keep SimpleChatApp action_send_message
        self.messages.append(user_message) # Keep SimpleChatApp action_send_message

        # Save to database # Keep SimpleChatApp action_send_message
        self.db.add_message( # Keep SimpleChatApp action_send_message
            self.current_conversation.id, # Keep SimpleChatApp action_send_message
            "user", # Keep SimpleChatApp action_send_message
            content # Keep SimpleChatApp action_send_message
        ) # Keep SimpleChatApp action_send_message

        # Check if this is the first message in the conversation
        # Note: We check length *before* adding the potential assistant message
        is_first_message = len(self.messages) == 1

        # Update UI with user message first
        await self.update_messages_ui()

        # If this is the first message and dynamic titles are enabled, start background title generation
        if is_first_message and self.current_conversation and CONFIG.get("generate_dynamic_titles", True) and len(content) >= 3:
            log("First message detected, starting background title generation...")
            debug_log(f"First message detected with length {len(content)}, creating background title task")
            asyncio.create_task(self._generate_title_background(content))

        # Start main response generation immediately
        debug_log(f"About to call generate_response with model: '{self.selected_model}'")
        await self.generate_response()

        # Focus back on input
        input_widget.focus()

    async def _generate_title_background(self, content: str) -> None:
        """Generates the conversation title in the background."""
        if not self.current_conversation or not CONFIG.get("generate_dynamic_titles", True):
            return

        log("Starting background title generation...")
        debug_log(f"Background title generation started for content: {content[:30]}...")

        try:
            # Use the logic from generate_conversation_title in utils.py
            # It already prioritizes faster models (OpenAI/Anthropic)
            # We need a client instance here. Let's get one based on priority.
            title_client = None
            title_model = None
            from app.config import OPENAI_API_KEY, ANTHROPIC_API_KEY
            from app.api.base import BaseModelClient

            # Determine title client and model based on available keys
            if OPENAI_API_KEY:
                # For highest success rate, use OpenAI for title generation when available
                from app.api.openai import OpenAIClient
                title_client = await OpenAIClient.create()
                title_model = "gpt-3.5-turbo"
                debug_log("Using OpenAI for background title generation")
            elif ANTHROPIC_API_KEY:
                # Next best option is Anthropic
                from app.api.anthropic import AnthropicClient
                title_client = await AnthropicClient.create()
                title_model = "claude-3-haiku-20240307"
                debug_log("Using Anthropic for background title generation")
            else:
                # Fallback to the currently selected model's client if no API keys
                # Get client type first to ensure we correctly identify Ollama models
                from app.api.ollama import OllamaClient
                selected_model_resolved = resolve_model_id(self.selected_model)
                client_type = BaseModelClient.get_client_type_for_model(selected_model_resolved)
                
                # For Ollama models, special handling is required
                if client_type == OllamaClient:
                    debug_log(f"Title generation with Ollama model detected: {selected_model_resolved}")
                    
                    # Always try to use smalllm2:135m first, then fall back to other small models
                    try:
                        # Check if we have smalllm2:135m or other smaller models available
                        ollama_client = await OllamaClient.create()
                        available_models = await ollama_client.get_available_models()
                        
                        # Use smalllm2:135m if available (extremely small and fast)
                        preferred_model = "smalllm2:135m"
                        fallback_models = ["tinyllama", "gemma:2b", "phi3:mini", "llama3:8b", "orca-mini:3b", "phi2"]
                        
                        # First check for our preferred smallest model
                        small_model_found = False
                        if any(model["id"] == preferred_model for model in available_models):
                            debug_log(f"Found optimal small model for title generation: {preferred_model}")
                            title_model = preferred_model
                            small_model_found = True
                        
                        # If not found, try fallbacks in order
                        if not small_model_found:
                            for model_name in fallback_models:
                                if any(model["id"] == model_name for model in available_models):
                                    debug_log(f"Found alternative small model for title generation: {model_name}")
                                    title_model = model_name
                                    small_model_found = True
                                    break
                                    
                        if not small_model_found:
                            # Use the current model if no smaller models found
                            title_model = selected_model_resolved
                            debug_log(f"No smaller models found, using current model: {title_model}")
                            
                        # Always create a fresh client instance to avoid interference with model preloading
                        title_client = ollama_client
                        debug_log(f"Created dedicated Ollama client for title generation with model: {title_model}")
                    except Exception as e:
                        debug_log(f"Error finding optimized Ollama model for title generation: {str(e)}")
                        # Fallback to standard approach
                        title_client = await OllamaClient.create()
                        title_model = selected_model_resolved
                else:
                    # For other providers, use normal client acquisition
                    title_client = await BaseModelClient.get_client_for_model(selected_model_resolved)
                    title_model = selected_model_resolved
                    debug_log(f"Using selected model's client ({type(title_client).__name__}) for background title generation")

            if not title_client or not title_model:
                raise Exception("Could not determine a client/model for title generation.")

            # Call the utility function
            from app.utils import generate_conversation_title # Import locally if needed
            
            # Add timeout handling for title generation to prevent hangs
            try:
                # Create a task with timeout
                import asyncio
                title_generation_task = asyncio.create_task(
                    generate_conversation_title(content, title_model, title_client)
                )
                
                # Wait for completion with timeout (30 seconds)
                new_title = await asyncio.wait_for(title_generation_task, timeout=30)
                debug_log(f"Background generated title: {new_title}")
            except asyncio.TimeoutError:
                debug_log("Title generation timed out after 30 seconds")
                # Use default title in case of timeout
                new_title = f"Conversation ({datetime.now().strftime('%Y-%m-%d %H:%M')})"
                # Try to cancel the task
                if not title_generation_task.done():
                    title_generation_task.cancel()
                    debug_log("Cancelled timed out title generation task")

            # Check if title generation returned the default or a real title
            if new_title and not new_title.startswith("Conversation ("):
                # Update conversation title in database
                self.db.update_conversation(
                    self.current_conversation.id,
                    title=new_title
                )

                # Update UI title (if conversation hasn't changed)
                # Check if the current conversation ID still matches
                # Need to fetch the conversation again to be sure, or check against self.current_conversation.id
                current_conv_id = self.current_conversation.id if self.current_conversation else None
                if current_conv_id and self.db.get_conversation(current_conv_id): # Check if conversation still exists
                    # Check if the app's current conversation is still the same one
                    if self.current_conversation and self.current_conversation.id == current_conv_id:
                        title_widget = self.query_one("#conversation-title", Static)
                        title_widget.update(new_title)
                        self.current_conversation.title = new_title # Update local object too
                        log(f"Background title update successful: {new_title}")
                        # Subtle notification to show title was updated
                        self.notify(f"Conversation titled: {new_title}", severity="information", timeout=2)
                    else:
                        log("Conversation changed before background title update could apply.")
                else:
                    log(f"Conversation with ID {current_conv_id} no longer exists. Skipping title update.")
            else:
                log(f"Background title generation resulted in default or empty title: '{new_title}'. Not updating.")

        except Exception as e:
            debug_log(f"Background title generation failed: {str(e)}")
            log.error(f"Background title generation failed: {str(e)}")
            # Do not notify the user, just log the error.

    async def generate_response(self) -> None:
        """Generate an AI response using a non-blocking worker with fallback."""
        # Import debug_log function from main
        debug_log(f"Entering generate_response method")
        
        if not self.current_conversation or not self.messages:
            debug_log("No current conversation or messages, returning")
            return

        # Track if we've already attempted a fallback to avoid infinite loops
        if not hasattr(self, 'fallback_attempted'):
            self.fallback_attempted = False

        self.is_generating = True
        log("Setting is_generating to True")
        debug_log("Setting is_generating to True")
        loading = self.query_one("#loading-indicator")
        loading.remove_class("hidden")
        
        # For Ollama models, show the loading indicator immediately
        from app.api.ollama import OllamaClient
        debug_log(f"Current selected model: '{self.selected_model}'")
        client_type = BaseModelClient.get_client_type_for_model(self.selected_model)
        debug_log(f"Client type: {client_type.__name__ if client_type else 'None'}")
        
        if self.selected_model and client_type == OllamaClient:
            log("Ollama model detected, showing immediate loading indicator")
            debug_log("Ollama model detected, showing immediate loading indicator")
            loading.add_class("model-loading")
            # Update the loading indicator text directly
            loading.update("⚙️ Preparing Ollama model...")
        else:
            loading.remove_class("model-loading")
            # Start with a simple animation pattern that won't cause markup issues
            self._loading_frame = 0
            # Stop any existing animation task
            if self._loading_animation_task and not self._loading_animation_task.done():
                self._loading_animation_task.cancel()
            # Start the animation
            self._loading_animation_task = asyncio.create_task(self._animate_loading_task(loading))

        try:
            # Get conversation parameters
            # Ensure the model ID is resolved before passing to the API client
            unresolved_model = self.selected_model
            model = resolve_model_id(unresolved_model)
            log(f"Using model for generation: {model} (Resolved from: {unresolved_model})")
            style = self.selected_style
            
            debug_log(f"Using model: '{model}', style: '{style}'")
            
            # Determine the expected client type for this model
            expected_client_type = BaseModelClient.get_client_type_for_model(model)
            debug_log(f"Expected client type for {model}: {expected_client_type.__name__ if expected_client_type else 'None'}")

            # Ensure we have a valid model
            if not model:
                debug_log("Model is empty, selecting a default model")
                # Check which providers are available and select an appropriate default
                if OPENAI_API_KEY:
                    model = "gpt-3.5-turbo"
                    expected_client_type = BaseModelClient.get_client_type_for_model(model)
                    debug_log(f"Falling back to OpenAI gpt-3.5-turbo with client type {expected_client_type.__name__ if expected_client_type else 'None'}")
                elif ANTHROPIC_API_KEY:
                    model = "claude-3-haiku-20240307"  # Updated to newer Claude model
                    expected_client_type = BaseModelClient.get_client_type_for_model(model)
                    debug_log(f"Falling back to Anthropic Claude 3 Haiku with client type {expected_client_type.__name__ if expected_client_type else 'None'}")
                else:
                    # Check for a common Ollama model
                    try:
                        ollama = await OllamaClient.create()
                        models = await ollama.get_available_models()
                        if models and len(models) > 0:
                            debug_log(f"Found {len(models)} Ollama models, using first one")
                            model = models[0].get("id", "llama3")
                        else:
                            model = "llama3"  # Common default
                        expected_client_type = BaseModelClient.get_client_type_for_model(model)
                        debug_log(f"Falling back to Ollama model: {model} with client type {expected_client_type.__name__ if expected_client_type else 'None'}")
                    except Exception as ollama_err:
                        debug_log(f"Error getting Ollama models: {str(ollama_err)}")
                        model = "llama3"  # Final fallback
                        expected_client_type = BaseModelClient.get_client_type_for_model(model)
                        debug_log(f"Final fallback to llama3 with client type {expected_client_type.__name__ if expected_client_type else 'None'}")

            # Convert messages to API format with enhanced error checking
            api_messages = []
            debug_log(f"Converting {len(self.messages)} messages to API format")
            
            for i, msg in enumerate(self.messages):
                try:
                    debug_log(f"Processing message {i}: type={type(msg).__name__}, dir={dir(msg)}")
                    debug_log(f"Adding message to API format: role={msg.role}, content_len={len(msg.content)}")
                    
                    # Create a fully validated message dict
                    message_dict = {
                        "role": msg.role if hasattr(msg, 'role') and msg.role else "user",
                        "content": msg.content if hasattr(msg, 'content') and msg.content else ""
                    }
                    
                    api_messages.append(message_dict)
                    debug_log(f"Successfully added message {i}")
                except Exception as e:
                    debug_log(f"Error adding message {i} to API format: {str(e)}")
                    # Create a safe fallback message
                    fallback_msg = {
                        "role": "user",
                        "content": str(msg) if msg is not None else "Error retrieving message content"
                    }
                    api_messages.append(fallback_msg)
                    debug_log(f"Added fallback message for {i}")
            
            debug_log(f"Prepared {len(api_messages)} messages for API")

            # Get appropriate client
            debug_log(f"Getting client for model: {model}")
            try:
                client = await BaseModelClient.get_client_for_model(model)
                debug_log(f"Client: {client.__class__.__name__ if client else 'None'}")
                
                if client is None:
                    debug_log(f"No client available for model: {model}, trying to initialize")
                    # Try to determine client type and initialize manually
                    client_type = BaseModelClient.get_client_type_for_model(model)
                    if client_type:
                        debug_log(f"Found client type {client_type.__name__} for {model}, initializing")
                        try:
                            client = await client_type.create()
                            debug_log(f"Successfully initialized {client_type.__name__}")
                        except Exception as init_err:
                            debug_log(f"Error initializing client: {str(init_err)}")
                    
                    if client is None:
                        debug_log("Could not initialize client, falling back to safer model")
                        # Try a different model as last resort
                        if OPENAI_API_KEY:
                            from app.api.openai import OpenAIClient
                            client = await OpenAIClient.create()
                            model = "gpt-3.5-turbo"
                            debug_log("Falling back to OpenAI client")
                        elif ANTHROPIC_API_KEY:
                            from app.api.anthropic import AnthropicClient
                            client = await AnthropicClient.create()
                            model = "claude-instant-1.2"
                            debug_log("Falling back to Anthropic client")
                        else:
                            raise Exception("No valid API clients available")
            except Exception as e:
                debug_log(f"Failed to initialize model client: {str(e)}")
                self.notify(f"Failed to initialize model client: {str(e)}", severity="error")
                self.is_generating = False
                loading.add_class("hidden")
                return

            # Start streaming response
            debug_log("Creating assistant message with 'Thinking...'")
            print("Creating assistant message with 'Thinking...'")
            assistant_message = Message(role="assistant", content="Thinking...")
            self.messages.append(assistant_message)
            messages_container = self.query_one("#messages-container")
            message_display = MessageDisplay(assistant_message, highlight_code=CONFIG["highlight_code"])
            messages_container.mount(message_display)
            
            # Force multiple layout refreshes and scroll to end to ensure visibility
            self.refresh(layout=False)
            await asyncio.sleep(0.01)
            self.refresh(layout=True)
            messages_container.scroll_end(animate=False)
            await asyncio.sleep(0.01)
            self.refresh(layout=True)
            
            # Add small delay to show thinking state
            await asyncio.sleep(0.3)

            # Stream chunks to the UI with synchronization
            update_lock = asyncio.Lock()
            last_refresh_time = time.time()  # Initialize refresh throttling timer

            async def update_ui(content: str):
                # This function is called by the worker with each content update
                if not self.is_generating:
                    debug_log("update_ui called but is_generating is False, returning.")
                    return
                
                async with update_lock:
                    try:
                        # Add more verbose logging
                        debug_log(f"update_ui called with content length: {len(content)}")
                        print(f"update_ui: Updating with content length {len(content)}")
                        
                        # Clear thinking indicator on first content
                        if assistant_message.content == "Thinking...":
                            debug_log("First content received, clearing 'Thinking...'")
                            print("First content received, clearing 'Thinking...'")
                            # We'll let the MessageDisplay.update_content handle this special case
                        
                        # Update the message object with the full content
                        assistant_message.content = content

                        # Update UI with the content - this now has special handling for "Thinking..."
                        debug_log("Calling message_display.update_content")
                        await message_display.update_content(content)
                        
                        # More aggressive UI refresh sequence
                        debug_log("Performing UI refresh sequence")
                        # First do a lightweight refresh
                        self.refresh(layout=False)
                        # Then scroll to end
                        messages_container.scroll_end(animate=False)
                        # Then do a full layout refresh
                        self.refresh(layout=True)
                        # Final scroll to ensure visibility
                        messages_container.scroll_end(animate=False)
                        
                    except Exception as e:
                        debug_log(f"Error updating UI: {str(e)}")
                        log.error(f"Error updating UI: {str(e)}")
                        print(f"Error updating UI: {str(e)}")

            # --- Remove the inner run_generation_worker function ---

            # Start the worker using Textual's run_worker to ensure state tracking
            debug_log("Starting generate_streaming_response worker with run_worker")
            worker = self.run_worker(
                generate_streaming_response(
                    self,
                    api_messages,
                    model,
                    style,
                    client,
                    update_ui  # Pass the callback function
                ),
                name="generate_response"
            )
            self.current_generation_task = worker
            # Worker completion will be handled by on_worker_state_changed

        except Exception as e:
            # This catches errors during the *setup* before the worker starts
            debug_log(f"Error setting up generation worker: {str(e)}")
            log.error(f"Error setting up generation worker: {str(e)}")
            self.notify(f"Error: {str(e)}", severity="error")
            # Ensure cleanup if setup fails
            self.is_generating = False # Reset state
            self.current_generation_task = None
            if self._loading_animation_task and not self._loading_animation_task.done():
                self._loading_animation_task.cancel()
            self._loading_animation_task = None
            try:
                # Explicitly hide loading indicator
                loading = self.query_one("#loading-indicator")
                loading.add_class("hidden")
                loading.remove_class("model-loading")  # Also remove model-loading class if present
                self.refresh(layout=True)  # Force a refresh to ensure UI updates
                self.query_one("#message-input").focus()
            except Exception as ui_err:
                debug_log(f"Error hiding loading indicator: {str(ui_err)}")
                log.error(f"Error hiding loading indicator: {str(ui_err)}")

    # Rename this method slightly to avoid potential conflicts and clarify purpose
    async def _handle_generation_result(self, worker: Worker[Optional[str]]) -> None:
        """Handles the result of the generation worker (success, error, cancelled)."""
        # Import debug_log again for safety within this callback context
        try:
            from app.main import debug_log
        except ImportError:
            debug_log = lambda msg: None

        debug_log(f"Generation worker completed. State: {worker.state}")

        try:
            if worker.state == "cancelled":
                debug_log("Generation worker was cancelled")
                log.warning("Generation worker was cancelled")
                # Remove the incomplete message
                if self.messages and self.messages[-1].role == "assistant":
                    debug_log("Removing incomplete assistant message")
                    self.messages.pop()
                await self.update_messages_ui()
                self.notify("Generation stopped by user", severity="warning", timeout=2)

            elif worker.state == "error":
                error = worker.error
                debug_log(f"Error in generation worker: {error}")
                log.error(f"Error in generation worker: {error}")
                
                # Check if this is a model not found error that we can try to recover from
                error_str = str(error)
                is_model_not_found = "not found" in error_str.lower() or "404" in error_str
                
                # Try fallback if this is a model not found error and we haven't tried fallback yet
                if is_model_not_found and not self.fallback_attempted:
                    debug_log("Model not found error detected, attempting fallback")
                    self.fallback_attempted = True
                    
                    # Choose an appropriate fallback based on available providers
                    fallback_model = None
                    from app.config import OPENAI_API_KEY, ANTHROPIC_API_KEY
                    
                    if OPENAI_API_KEY:
                        fallback_model = "gpt-3.5-turbo"
                        debug_log(f"Falling back to OpenAI model: {fallback_model}")
                    elif ANTHROPIC_API_KEY:
                        fallback_model = "claude-3-haiku-20240307"
                        debug_log(f"Falling back to Anthropic model: {fallback_model}")
                    else:
                        # Find a common Ollama model that should exist
                        try:
                            from app.api.ollama import OllamaClient
                            ollama = await OllamaClient.create()
                            models = await ollama.get_available_models()
                            for model_name in ["gemma:2b", "phi3:mini", "llama3:8b"]:
                                if any(m["id"] == model_name for m in models):
                                    fallback_model = model_name
                                    debug_log(f"Found available Ollama model for fallback: {fallback_model}")
                                    break
                        except Exception as e:
                            debug_log(f"Error finding Ollama fallback model: {str(e)}")
                    
                    if fallback_model:
                        # Update UI to show fallback is happening
                        loading = self.query_one("#loading-indicator")
                        loading.remove_class("hidden")
                        loading.update(f"⚙️ Falling back to {fallback_model}...")
                        
                        # Update the selected model
                        self.selected_model = fallback_model
                        self.update_app_info()  # Update the displayed model info
                        
                        # Remove the "Thinking..." message
                        if self.messages and self.messages[-1].role == "assistant":
                            debug_log("Removing thinking message before fallback")
                            self.messages.pop()
                            await self.update_messages_ui()
                        
                        # Try again with the new model
                        debug_log(f"Retrying with fallback model: {fallback_model}")
                        self.notify(f"Trying fallback model: {fallback_model}", severity="warning", timeout=3)
                        await self.generate_response()
                        return
                
                # If we get here, either it's not a model error or fallback already attempted
                # Explicitly hide loading indicator
                try:
                    loading = self.query_one("#loading-indicator")
                    loading.add_class("hidden")
                    loading.remove_class("model-loading")  # Also remove model-loading class if present
                except Exception as ui_err:
                    debug_log(f"Error hiding loading indicator: {str(ui_err)}")
                    log.error(f"Error hiding loading indicator: {str(ui_err)}")
                
                # Create a user-friendly error message
                if is_model_not_found:
                    # For model not found errors, provide a more user-friendly message
                    user_error = "Unable to generate response. The selected model may not be available."
                    debug_log(f"Sanitizing model not found error to user-friendly message: {user_error}")
                    # Show technical details only in notification, not in chat
                    self.notify(f"Model error: {error_str}", severity="error", timeout=5)
                else:
                    # For other errors, show a generic message
                    user_error = f"Error generating response: {error_str}"
                    self.notify(f"Generation error: {error_str}", severity="error", timeout=5)
                
                # Add error message to UI
                if self.messages and self.messages[-1].role == "assistant":
                    debug_log("Removing thinking message")
                    self.messages.pop()  # Remove thinking message
                
                debug_log(f"Adding error message: {user_error}")
                self.messages.append(Message(role="assistant", content=user_error))
                await self.update_messages_ui()
                
                # Force a refresh to ensure UI updates
                self.refresh(layout=True)

            elif worker.state == "success":
                full_response = worker.result
                debug_log("Generation completed normally, saving to database")
                log("Generation completed normally, saving to database")
                # Save complete response to database (check if response is valid)
                if full_response and isinstance(full_response, str):
                    self.db.add_message(
                        self.current_conversation.id,
                        "assistant",
                        full_response
                    )
                    # Update the final message object content (optional, UI should be up-to-date)
                    if self.messages and self.messages[-1].role == "assistant":
                        self.messages[-1].content = full_response
                        
                    # Force a UI refresh with the message display to ensure it's fully rendered
                    try:
                        # Get the message display for the assistant message
                        messages_container = self.query_one("#messages-container")
                        message_displays = messages_container.query("MessageDisplay")
                        # Check if we found any message displays
                        if message_displays and len(message_displays) > 0:
                            # Get the last message display which should be our assistant message
                            last_message_display = message_displays[-1]
                            debug_log("Forcing final content update on message display")
                            # Force a final content update
                            await last_message_display.update_content(full_response)
                    except Exception as disp_err:
                        debug_log(f"Error updating final message display: {str(disp_err)}")
                else:
                    debug_log("Worker finished successfully but response was empty or invalid.")
                    # Handle case where 'Thinking...' might still be the last message
                    if self.messages and self.messages[-1].role == "assistant" and self.messages[-1].content == "Thinking...":
                         self.messages.pop() # Remove 'Thinking...' if no content arrived
                         await self.update_messages_ui()

                # Force a full UI refresh to ensure content is visible
                messages_container = self.query_one("#messages-container")
                
                # Sequence of UI refreshes to ensure content is properly displayed
                # 1. First do a lightweight refresh
                self.refresh(layout=False)
                
                # 2. Short delay to allow the UI to process
                await asyncio.sleep(0.1)  
                
                # 3. Ensure we're scrolled to the end
                messages_container.scroll_end(animate=False)
                
                # 4. Full layout refresh
                self.refresh(layout=True)
                
                # 5. Final delay and scroll to ensure everything is visible
                await asyncio.sleep(0.1)
                messages_container.scroll_end(animate=False)

        except Exception as e:
            # Catch any unexpected errors during the callback itself
            debug_log(f"Error in on_generation_complete callback: {str(e)}")
            log.error(f"Error in on_generation_complete callback: {str(e)}")
            self.notify(f"Internal error handling response: {str(e)}", severity="error")

        finally:
            # Always clean up state and UI, regardless of worker outcome
            debug_log("Cleaning up after generation worker")
            self.is_generating = False
            self.current_generation_task = None

            # Stop the animation task
            if self._loading_animation_task and not self._loading_animation_task.done():
                debug_log("Cancelling loading animation task")
                self._loading_animation_task.cancel()
            self._loading_animation_task = None

            try:
                loading = self.query_one("#loading-indicator")
                loading.add_class("hidden")
                self.refresh(layout=True) # Refresh after hiding loading
                self.query_one("#message-input").focus()
            except Exception as ui_err:
                debug_log(f"Error during final UI cleanup: {str(ui_err)}")
                log.error(f"Error during final UI cleanup: {str(ui_err)}")

    @on(Worker.StateChanged)
    async def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Handle worker state changes."""
        # Import debug_log again for safety within this callback context
        try:
            from app.main import debug_log
        except ImportError:
            debug_log = lambda msg: None

        debug_log(f"Worker {event.worker.name} state changed to {event.state}")

        # Check if this is the generation worker we are tracking
        if event.worker is self.current_generation_task:
            # Check if the worker has reached a final state by comparing against enum values
            final_states = {WorkerState.SUCCESS, WorkerState.ERROR, WorkerState.CANCELLED}
            if event.state in final_states:
                debug_log(f"Generation worker ({event.worker.name}) reached final state: {event.state}")
                # Call the handler function
                await self._handle_generation_result(event.worker)
            else:
                 debug_log(f"Generation worker ({event.worker.name}) is in intermediate state: {event.state}")
        else:
            debug_log(f"State change event from unrelated worker: {event.worker.name}")


    async def on_settings_screen_settings_updated(self, event: SettingsScreen.SettingsUpdated) -> None:
        """Handle settings update from SettingsScreen"""
        # Reload provider availability
        from app.config import check_provider_availability, AVAILABLE_PROVIDERS, CONFIG
        
        # Update available providers
        new_providers = check_provider_availability()
        AVAILABLE_PROVIDERS.clear()
        AVAILABLE_PROVIDERS.update(new_providers)
        
        # Refresh the model selector if it exists
        try:
            model_selector = self.query_one(ModelSelector)
            # Force refresh by re-getting model options
            current_provider = model_selector.selected_provider
            if current_provider == "openai-compatible":
                # Refresh the model options for custom provider
                model_options = await model_selector._get_model_options(current_provider)
                model_select = model_selector.query_one("#model-select", Select)
                model_select.set_options(model_options)
        except Exception as e:
            logger.debug(f"Could not refresh model selector: {e}")
    
    def on_model_selector_model_selected(self, event: ModelSelector.ModelSelected) -> None:
        """Handle model selection"""
        self.selected_model = event.model_id
        
        # Store the selected provider for use in client resolution
        model_selector = self.query_one(ModelSelector)
        if model_selector:
            self.selected_provider = model_selector.selected_provider
            log(f"Stored selected provider: {self.selected_provider} for model: {self.selected_model}")
        
        self.update_app_info()  # Update the displayed model info
        
        # Preload the model if it's an Ollama model and preloading is enabled
        if self.selected_provider == "ollama" and CONFIG.get("ollama_model_preload", True):
            # Start the background task to preload the model
            debug_log(f"Starting background task to preload Ollama model: {self.selected_model}")
            asyncio.create_task(self._preload_ollama_model(self.selected_model))
    
    async def _preload_ollama_model(self, model_id: str) -> None:
        """Preload an Ollama model in the background"""
        from app.api.ollama import OllamaClient
        
        debug_log(f"Preloading Ollama model: {model_id}")
        # Show a subtle notification to the user
        self.notify("Preparing model for use...", severity="information", timeout=3)
        
        try:
            # Initialize the client
            client = await OllamaClient.create()
            
            # Update the loading indicator to show model loading
            loading = self.query_one("#loading-indicator")
            loading.remove_class("hidden")
            loading.add_class("model-loading")
            loading.update(f"⚙️ Loading Ollama model...")
            
            # Preload the model
            success = await client.preload_model(model_id)
            
            # Hide the loading indicator
            loading.add_class("hidden")
            loading.remove_class("model-loading")
            
            if success:
                debug_log(f"Successfully preloaded model: {model_id}")
                self.notify(f"Model ready for use", severity="success", timeout=2)
            else:
                debug_log(f"Failed to preload model: {model_id}")
                # No need to notify the user about failure - will happen naturally on first use
        except Exception as e:
            debug_log(f"Error preloading model: {str(e)}")
            # Make sure to hide the loading indicator
            try:
                loading = self.query_one("#loading-indicator")
                loading.add_class("hidden")
                loading.remove_class("model-loading")
            except Exception:
                pass
                
    async def _check_inactive_models(self) -> None:
        """Background task to check for and release inactive models"""
        from app.api.ollama import OllamaClient
        
        # How often to check for inactive models (in seconds)
        CHECK_INTERVAL = 600  # 10 minutes
        
        debug_log(f"Starting inactive model check task with interval {CHECK_INTERVAL}s")
        
        try:
            while True:
                await asyncio.sleep(CHECK_INTERVAL)
                
                debug_log("Checking for inactive models...")
                
                try:
                    # Initialize the client
                    client = await OllamaClient.create()
                    
                    # Get the threshold from instance variable
                    threshold = getattr(self, "MODEL_INACTIVITY_THRESHOLD", 30)
                    
                    # Check and release inactive models
                    released_models = await client.release_inactive_models(threshold)
                    
                    if released_models:
                        debug_log(f"Released {len(released_models)} inactive models: {released_models}")
                    else:
                        debug_log("No inactive models to release")
                        
                except Exception as e:
                    debug_log(f"Error checking for inactive models: {str(e)}")
                    # Continue loop even if this check fails
                    
        except asyncio.CancelledError:
            debug_log("Model cleanup task cancelled")
            # Normal task cancellation, clean exit
        except Exception as e:
            debug_log(f"Unexpected error in model cleanup task: {str(e)}")
            # Log but don't crash

    def on_style_selector_style_selected(self, event: StyleSelector.StyleSelected) -> None: # Keep SimpleChatApp on_style_selector_style_selected
        """Handle style selection""" # Keep SimpleChatApp on_style_selector_style_selected docstring
        self.selected_style = event.style_id # Keep SimpleChatApp on_style_selector_style_selected

    async def on_button_pressed(self, event: Button.Pressed) -> None: # Modify SimpleChatApp on_button_pressed
        """Handle button presses."""
        button_id = event.button.id

        if button_id == "new-chat-button":
            # Create a new chat
            await self.create_new_conversation()
            # Focus back on input after creating new chat
            self.query_one("#message-input").focus()
        elif button_id == "change-title-button":
            # Change title
            # Note: action_update_title already checks self.current_conversation
            await self.action_update_title()
        # --- Handle Settings Panel Buttons ---
        elif button_id == "settings-cancel-button":
            settings_panel = self.query_one("#settings-panel")
            settings_panel.remove_class("visible")
            self.query_one("#message-input").focus() # Focus input after closing
        elif button_id == "settings-save-button":
            # --- Save Logic ---
            try:
                # Get selected values (assuming selectors update self.selected_model/style directly via events)
                model_to_save = self.selected_model
                style_to_save = self.selected_style

                # Save globally
                save_settings_to_config(model_to_save, style_to_save)

                # Update current conversation if one exists
                if self.current_conversation:
                    self.db.update_conversation(
                        self.current_conversation.id,
                        model=model_to_save,
                        style=style_to_save
                    )
                    self.current_conversation.model = model_to_save
                    self.current_conversation.style = style_to_save
                self.notify("Settings saved.", severity="information")
            except Exception as e:
                self.notify(f"Error saving settings: {str(e)}", severity="error")
            finally:
                # Hide panel regardless of save success/failure
                settings_panel = self.query_one("#settings-panel")
                settings_panel.remove_class("visible")
                self.query_one("#message-input").focus() # Focus input after closing

        # --- Keep other button logic if needed (currently none) ---
        # elif button_id == "send-button": # Example if send button existed
        #     await self.action_send_message()

    async def view_chat_history(self) -> None: # Keep SimpleChatApp view_chat_history
        """Show chat history in a popup.""" # Keep SimpleChatApp view_chat_history docstring
        # Get recent conversations # Keep SimpleChatApp view_chat_history
        conversations = self.db.get_all_conversations(limit=CONFIG["max_history_items"]) # Keep SimpleChatApp view_chat_history
        if not conversations: # Keep SimpleChatApp view_chat_history
            self.notify("No chat history found", severity="warning") # Keep SimpleChatApp view_chat_history
            return # Keep SimpleChatApp view_chat_history

        async def handle_selection(selected_id: int) -> None: # Keep SimpleChatApp view_chat_history
            if not selected_id: # Keep SimpleChatApp view_chat_history
                return # Keep SimpleChatApp view_chat_history

            # Get full conversation # Keep SimpleChatApp view_chat_history
            conversation_data = self.db.get_conversation(selected_id) # Keep SimpleChatApp view_chat_history
            if not conversation_data: # Keep SimpleChatApp view_chat_history
                self.notify("Could not load conversation", severity="error") # Keep SimpleChatApp view_chat_history
                return # Keep SimpleChatApp view_chat_history

            # Update current conversation # Keep SimpleChatApp view_chat_history
            self.current_conversation = Conversation.from_dict(conversation_data) # Keep SimpleChatApp view_chat_history

            # Update title # Keep SimpleChatApp view_chat_history
            title = self.query_one("#conversation-title", Static) # Keep SimpleChatApp view_chat_history
            title.update(self.current_conversation.title) # Keep SimpleChatApp view_chat_history

            # Load messages # Keep SimpleChatApp view_chat_history
            self.messages = [Message(**msg) for msg in self.current_conversation.messages] # Keep SimpleChatApp view_chat_history
            await self.update_messages_ui() # Keep SimpleChatApp view_chat_history

            # Update model and style selectors # Keep SimpleChatApp view_chat_history
            # Resolve the model ID loaded from the conversation data
            loaded_model_id = self.current_conversation.model
            resolved_model_id = resolve_model_id(loaded_model_id)
            log(f"Loaded model ID from history: {loaded_model_id}, Resolved to: {resolved_model_id}")

            self.selected_model = resolved_model_id # Use the resolved ID
            self.selected_style = self.current_conversation.style # Keep SimpleChatApp view_chat_history

            # Update settings panel selectors if they exist
            try:
                model_selector = self.query_one(ModelSelector)
                model_selector.set_selected_model(self.selected_model) # Use resolved ID here too
                style_selector = self.query_one(StyleSelector)
                style_selector.set_selected_style(self.selected_style)
            except Exception as e:
                log(f"Error updating selectors after history load: {e}")

            self.update_app_info() # Update info bar after loading history

        self.push_screen(HistoryScreen(conversations, handle_selection)) # Keep SimpleChatApp view_chat_history

    async def action_view_history(self) -> None: # Keep SimpleChatApp action_view_history
        """Action to view chat history via key binding.""" # Keep SimpleChatApp action_view_history docstring
        # Only trigger if message input is not focused # Keep SimpleChatApp action_view_history
        input_widget = self.query_one("#message-input", Input) # Keep SimpleChatApp action_view_history
        if not input_widget.has_focus: # Keep SimpleChatApp action_view_history
            await self.view_chat_history() # Keep SimpleChatApp action_view_history
            
    def action_model_browser(self) -> None:
        """Open the Ollama model browser screen."""
        # Always trigger regardless of focus
        self.push_screen(ModelBrowserScreen())
        
    async def _animate_loading_task(self, loading_widget: Static) -> None:
        """Minimal loading animation following Rams principles"""
        try:
            # Minimal loading frames - "Less but better"
            frames = [
                "● Generating",
                "○ Generating", 
                "● Generating",
                "○ Generating"
            ]
            
            while self.is_generating:
                try:
                    frame_idx = self._loading_frame % len(frames)
                    loading_widget.update(frames[frame_idx])
                    self._loading_frame += 1
                    # Slower, less distracting animation
                    await asyncio.sleep(0.8)
                except Exception as e:
                    log.error(f"Animation frame error: {str(e)}")
                    try:
                        loading_widget.update("● Generating")
                    except:
                        pass
                    await asyncio.sleep(0.8)
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.error(f"Error in loading animation: {str(e)}")
            try:
                loading_widget.update("● Generating")
            except:
                pass

    def action_settings(self) -> None: # Modify SimpleChatApp action_settings
        """Action to open settings screen via key binding."""
        # Only trigger if message input is not focused
        input_widget = self.query_one("#message-input", Input)
        if not input_widget.has_focus:
            # Push the SettingsScreen
            self.push_screen(SettingsScreen())

    async def action_update_title(self) -> None:
        """Allow users to manually change the conversation title"""
        log("--- ENTERING action_update_title ---") # Add entry log
        # Focus check removed - relying on priority=True in binding

        log("action_update_title EXECUTING") # Add execution log

        if not self.current_conversation:
            self.notify("No active conversation", severity="warning")
            return
            
        # Create and mount the title input modal
        modal = TitleInputModal(self.current_conversation.title)
        await self.mount(modal)

        # --- Define the Modal Class ---
        class ConfirmDialog(Static):
            """A simple confirmation dialog."""
            
            class Confirmed(Message):
                """Message sent when the dialog is confirmed."""
                def __init__(self, confirmed: bool):
                    self.confirmed = confirmed
                    super().__init__()
            
            def __init__(self, message: str):
                super().__init__()
                self.message = message
            
            def compose(self) -> ComposeResult:
                with Vertical(id="confirm-dialog"):
                    yield Static(self.message, id="confirm-message")
                    with Horizontal():
                        yield Button("No", id="no-button", variant="error")
                        yield Button("Yes", id="yes-button", variant="success")
            
            @on(Button.Pressed, "#yes-button")
            def confirm(self, event: Button.Pressed) -> None:
                self.post_message(self.Confirmed(True))
                self.remove() # Close the dialog
            
            @on(Button.Pressed, "#no-button")
            def cancel(self, event: Button.Pressed) -> None:
                self.post_message(self.Confirmed(False))
                self.remove() # Close the dialog
                
            def on_confirmed(self, event: Confirmed) -> None:
                """Event handler for confirmation - used by the app to get the result."""
                pass
                
            def on_mount(self) -> None:
                """Set the CSS style when mounted."""
                self.styles.width = "40"
                self.styles.height = "auto"
                self.styles.background = "var(--surface)"
                self.styles.border = "thick var(--primary)"
                self.styles.align = "center middle"
                self.styles.padding = "1 2"
                self.styles.layer = "modal"

class TitleInputModal(Static):
    def __init__(self, current_title: str):
        super().__init__()
        self.current_title = current_title

    def compose(self) -> ComposeResult:
        with Vertical(id="title-modal"):
            yield Static("Enter new conversation title:", id="modal-label")
            yield Input(value=self.current_title, id="title-input")
            with Horizontal():
                yield Button("Cancel", id="cancel-button", variant="error")
                yield Button("Update", id="update-button", variant="success")

    @on(Button.Pressed, "#update-button")
    def update_title(self, event: Button.Pressed) -> None:
        input_widget = self.query_one("#title-input", Input)
        new_title = input_widget.value.strip()
        if new_title:
            # Call the app's update method asynchronously
            asyncio.create_task(self.app.update_conversation_title(new_title))
        self.remove() # Close the modal

    @on(Button.Pressed, "#cancel-button")
    def cancel(self, event: Button.Pressed) -> None:
        self.remove() # Close the modal

    async def on_mount(self) -> None:
        """Focus the input when the modal appears."""
        self.query_one("#title-input", Input).focus()

    async def run_modal(self, modal_type: str, *args, **kwargs) -> bool:
        """Run a modal dialog and return the result."""
        if modal_type == "confirm_dialog":
            # Create a confirmation dialog with the message from args
            message = args[0] if args else "Are you sure?"
            dialog = ConfirmDialog(message)
            await self.mount(dialog)
            
            # Setup event handler to receive the result
            result = False
            
            def on_confirm(event: ConfirmDialog.Confirmed) -> None:
                nonlocal result
                result = event.confirmed
            
            # Add listener for the confirmation event
            dialog.on_confirmed = on_confirm
            
            # Wait for the dialog to close
            while dialog.is_mounted:
                await self.sleep(0.1)
            
            return result
        
        return False
    
    async def update_conversation_title(self, new_title: str) -> None:
        """Update the current conversation title"""
        if not self.current_conversation:
            return

        try:
            # Update in database
            self.db.update_conversation(
                self.current_conversation.id,
                title=new_title
            )

            # Update local object
            self.current_conversation.title = new_title

            # Update UI
            title_widget = self.query_one("#conversation-title", Static)
            title_widget.update(new_title)

            # Update any chat list if visible
            # Attempt to refresh ChatList if it exists
            try:
                chat_list = self.query_one(ChatList)
                chat_list.refresh() # Call the refresh method
            except Exception:
                pass # Ignore if ChatList isn't found or refresh fails

            self.notify("Title updated successfully", severity="information")
        except Exception as e:
            self.notify(f"Failed to update title: {str(e)}", severity="error")


def main(
    initial_text: Optional[str] = typer.Argument(None, help="Initial text to start the chat with"),
    console: bool = typer.Option(False, "--console", "-c", help="Use pure console mode (no Textual)")
):
    """Entry point for the chat-cli application"""
    if console:
        # Launch pure console version
        import asyncio
        import sys
        import os
        
        # Add current directory to path for console_chat import
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        
        try:
            from .console_interface import ConsoleUI
            
            async def run_console():
                console_ui = ConsoleUI()
                if initial_text and not isinstance(initial_text, typer.models.ArgumentInfo):
                    # If initial text provided, create conversation and add message
                    await console_ui.create_new_conversation()
                    await console_ui.generate_response(str(initial_text))
                await console_ui.run()
            
            asyncio.run(run_console())
            
        except ImportError:
            print("Error: Could not import console version. Make sure all dependencies are installed.")
            sys.exit(1)
        except Exception as e:
            print(f"Error running console version: {e}")
            sys.exit(1)
    else:
        # Original Textual version
        if isinstance(initial_text, typer.models.ArgumentInfo):
            initial_value = None
        else:
            initial_value = str(initial_text) if initial_text is not None else None
            
        app = SimpleChatApp(initial_text=initial_value)
        app.run()

if __name__ == "__main__": # Keep main function entry point
    typer.run(main) # Keep main function entry point
