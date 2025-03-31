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
from textual import work, log, on
from textual.screen import Screen
from openai import OpenAI
from app.models import Message, Conversation
from app.database import ChatDatabase
from app.config import CONFIG, OPENAI_API_KEY, ANTHROPIC_API_KEY, OLLAMA_BASE_URL
from app.ui.chat_interface import MessageDisplay
from app.ui.model_selector import ModelSelector, StyleSelector
from app.ui.chat_list import ChatList
from app.api.base import BaseModelClient
from app.utils import generate_streaming_response, save_settings_to_config, generate_conversation_title # Import title function

# --- Remove SettingsScreen class entirely ---

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
    
    TITLE = "Chat CLI" # Keep SimpleChatApp TITLE
    SUB_TITLE = "AI Chat Interface" # Keep SimpleChatApp SUB_TITLE
    DARK = True # Keep SimpleChatApp DARK
    
    CSS = """ # Keep SimpleChatApp CSS start
    #main-content { # Keep SimpleChatApp CSS
        width: 100%;
        height: 100%;
        padding: 0 1;
    }

    #conversation-title { # Keep SimpleChatApp CSS
        width: 100%; # Keep SimpleChatApp CSS
        height: 2;
        background: $surface-darken-2;
        color: $text;
        content-align: center middle;
        text-align: center;
        border-bottom: solid $primary-darken-2;
    }

    #messages-container { # Keep SimpleChatApp CSS
        width: 100%; # Keep SimpleChatApp CSS
        height: 1fr;
        min-height: 10;
        border-bottom: solid $primary-darken-2;
        overflow: auto;
        padding: 0 1;
    }

    #loading-indicator { # Keep SimpleChatApp CSS
        width: 100%; # Keep SimpleChatApp CSS
        height: 1;
        background: $primary-darken-1;
        color: $text;
        content-align: center middle;
        text-align: center;
    }

    #loading-indicator.hidden { # Keep SimpleChatApp CSS
        display: none;
    }

    #input-area { # Keep SimpleChatApp CSS
        width: 100%; # Keep SimpleChatApp CSS
        height: auto;
        min-height: 4;
        max-height: 10;
        padding: 1;
    }

    #message-input { # Keep SimpleChatApp CSS
        width: 1fr; # Keep SimpleChatApp CSS
        min-height: 2;
        height: auto;
        margin-right: 1;
        border: solid $primary-darken-2;
    }

    #message-input:focus { # Keep SimpleChatApp CSS
        border: solid $primary;
    }

    /* Removed CSS for #send-button, #new-chat-button, #view-history-button, #settings-button */ # Keep SimpleChatApp CSS comment
    /* Removed CSS for #button-row */ # Keep SimpleChatApp CSS comment

    #settings-panel { /* Add CSS for the new settings panel */
        display: none; /* Hidden by default */
        align: center middle;
        width: 60;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
        layer: settings; /* Ensure it's above other elements */
    }

    #settings-panel.visible { /* Class to show the panel */
        display: block;
    }

    #settings-title {
        width: 100%;
        content-align: center middle;
        padding-bottom: 1;
        border-bottom: thick $primary-darken-2; /* Correct syntax for bottom border */
    }

    #settings-buttons {
        width: 100%;
        height: auto;
        align: center middle;
        padding-top: 1;
    }

    /* --- Title Input Modal CSS --- */
    TitleInputModal {
        align: center middle;
        width: 60;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
        layer: modal; /* Ensure it's above other elements */
    }

    #modal-label {
        width: 100%;
        content-align: center middle;
        padding-bottom: 1;
    }

    #title-input {
        width: 100%;
        margin-bottom: 1;
    }

    TitleInputModal Horizontal {
        width: 100%;
        height: auto;
        align: center middle;
    }
    """
    
    BINDINGS = [ # Keep SimpleChatApp BINDINGS, ensure Enter is not globally bound for settings
        Binding("q", "quit", "Quit", show=True, key_display="q"),
        Binding("n", "action_new_conversation", "New Chat", show=True, key_display="n"),
        Binding("c", "action_new_conversation", "New Chat", show=False, key_display="c"),
        Binding("escape", "escape", "Cancel / Stop", show=True, key_display="esc"), # Escape might close settings panel too
        Binding("ctrl+c", "quit", "Quit", show=False),
        Binding("h", "view_history", "History", show=True, key_display="h"),
        Binding("s", "settings", "Settings", show=True, key_display="s"),
        Binding("t", "action_update_title", "Update Title", show=True, key_display="t"),
    ] # Keep SimpleChatApp BINDINGS end
    
    current_conversation = reactive(None) # Keep SimpleChatApp reactive var
    is_generating = reactive(False) # Keep SimpleChatApp reactive var
    
    def __init__(self, initial_text: Optional[str] = None): # Keep SimpleChatApp __init__
        super().__init__() # Keep SimpleChatApp __init__
        self.db = ChatDatabase() # Keep SimpleChatApp __init__
        self.messages = [] # Keep SimpleChatApp __init__
        self.selected_model = CONFIG["default_model"] # Keep SimpleChatApp __init__
        self.selected_style = CONFIG["default_style"] # Keep SimpleChatApp __init__
        self.initial_text = initial_text # Keep SimpleChatApp __init__
        
    def compose(self) -> ComposeResult: # Modify SimpleChatApp compose
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
                # Removed Static widgets previously used for diagnosis

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
        # Check API keys and services # Keep SimpleChatApp on_mount
        api_issues = [] # Keep SimpleChatApp on_mount
        if not OPENAI_API_KEY: # Keep SimpleChatApp on_mount
            api_issues.append("- OPENAI_API_KEY is not set") # Keep SimpleChatApp on_mount
        if not ANTHROPIC_API_KEY: # Keep SimpleChatApp on_mount
            api_issues.append("- ANTHROPIC_API_KEY is not set") # Keep SimpleChatApp on_mount
            
        # Check Ollama availability and try to start if not running # Keep SimpleChatApp on_mount
        from app.utils import ensure_ollama_running # Keep SimpleChatApp on_mount
        if not ensure_ollama_running(): # Keep SimpleChatApp on_mount
            api_issues.append("- Ollama server not running and could not be started") # Keep SimpleChatApp on_mount
        else: # Keep SimpleChatApp on_mount
            # Check for available models # Keep SimpleChatApp on_mount
            from app.api.ollama import OllamaClient # Keep SimpleChatApp on_mount
            try: # Keep SimpleChatApp on_mount
                ollama = OllamaClient() # Keep SimpleChatApp on_mount
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
            self.query_one("#message-input").focus() # Keep SimpleChatApp on_mount
        
    async def create_new_conversation(self) -> None: # Keep SimpleChatApp create_new_conversation
        """Create a new chat conversation.""" # Keep SimpleChatApp create_new_conversation docstring
        # Create new conversation in database using selected model and style # Keep SimpleChatApp create_new_conversation
        model = self.selected_model # Keep SimpleChatApp create_new_conversation
        style = self.selected_style # Keep SimpleChatApp create_new_conversation
        
        # Create a title for the new conversation # Keep SimpleChatApp create_new_conversation
        title = f"New conversation ({datetime.now().strftime('%Y-%m-%d %H:%M')})" # Keep SimpleChatApp create_new_conversation
        
        # Create conversation in database using the correct method # Keep SimpleChatApp create_new_conversation
        conversation_id = self.db.create_conversation(title, model, style) # Keep SimpleChatApp create_new_conversation
        
        # Get the full conversation data # Keep SimpleChatApp create_new_conversation
        conversation_data = self.db.get_conversation(conversation_id) # Keep SimpleChatApp create_new_conversation
        
        # Set as current conversation # Keep SimpleChatApp create_new_conversation
        self.current_conversation = Conversation.from_dict(conversation_data) # Keep SimpleChatApp create_new_conversation
        
        # Update UI # Keep SimpleChatApp create_new_conversation
        title = self.query_one("#conversation-title", Static) # Keep SimpleChatApp create_new_conversation
        title.update(self.current_conversation.title) # Keep SimpleChatApp create_new_conversation
        
        # Clear messages and update UI # Keep SimpleChatApp create_new_conversation
        self.messages = [] # Keep SimpleChatApp create_new_conversation
        await self.update_messages_ui() # Keep SimpleChatApp create_new_conversation
        
    async def action_new_conversation(self) -> None: # Keep SimpleChatApp action_new_conversation
        """Handle the new conversation action.""" # Keep SimpleChatApp action_new_conversation docstring
        await self.create_new_conversation() # Keep SimpleChatApp action_new_conversation
        
    def action_escape(self) -> None: # Modify SimpleChatApp action_escape
        """Handle escape key globally."""
        settings_panel = self.query_one("#settings-panel")
        if settings_panel.has_class("visible"):
            # If settings panel is visible, hide it
            settings_panel.remove_class("visible")
            self.query_one("#message-input").focus() # Focus input after closing settings
        elif self.is_generating:
            # Otherwise, stop generation if running
            self.is_generating = False # Keep SimpleChatApp action_escape
            self.notify("Generation stopped", severity="warning") # Keep SimpleChatApp action_escape
            loading = self.query_one("#loading-indicator") # Keep SimpleChatApp action_escape
            loading.add_class("hidden") # Keep SimpleChatApp action_escape
        # else: # Optional: Add other escape behavior for the main screen if desired # Keep SimpleChatApp action_escape comment
            # pass # Keep SimpleChatApp action_escape comment

    # Removed action_confirm_or_send - Enter is handled by Input submission # Keep SimpleChatApp comment

    async def update_messages_ui(self) -> None: # Keep SimpleChatApp update_messages_ui
        """Update the messages UI.""" # Keep SimpleChatApp update_messages_ui docstring
        # Clear existing messages # Keep SimpleChatApp update_messages_ui
        messages_container = self.query_one("#messages-container") # Keep SimpleChatApp update_messages_ui
        messages_container.remove_children() # Keep SimpleChatApp update_messages_ui
        
        # Add messages with a small delay between each # Keep SimpleChatApp update_messages_ui
        for message in self.messages: # Keep SimpleChatApp update_messages_ui
            display = MessageDisplay(message, highlight_code=CONFIG["highlight_code"]) # Keep SimpleChatApp update_messages_ui
            messages_container.mount(display) # Keep SimpleChatApp update_messages_ui
            messages_container.scroll_end(animate=False) # Keep SimpleChatApp update_messages_ui
            await asyncio.sleep(0.01)  # Small delay to prevent UI freezing # Keep SimpleChatApp update_messages_ui
            
        # Final scroll to bottom # Keep SimpleChatApp update_messages_ui
        messages_container.scroll_end(animate=False) # Keep SimpleChatApp update_messages_ui
    
    async def on_input_submitted(self, event: Input.Submitted) -> None: # Keep SimpleChatApp on_input_submitted
        """Handle input submission (Enter key in the main input).""" # Keep SimpleChatApp on_input_submitted docstring
        await self.action_send_message() # Restore direct call # Keep SimpleChatApp on_input_submitted

    async def action_send_message(self) -> None: # Keep SimpleChatApp action_send_message
        """Initiate message sending.""" # Keep SimpleChatApp action_send_message docstring
        input_widget = self.query_one("#message-input", Input) # Keep SimpleChatApp action_send_message
        content = input_widget.value.strip() # Keep SimpleChatApp action_send_message
        
        if not content or not self.current_conversation: # Keep SimpleChatApp action_send_message
            return # Keep SimpleChatApp action_send_message
        
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
        
        # If this is the first message and dynamic titles are enabled, generate one
        if is_first_message and self.current_conversation and CONFIG.get("generate_dynamic_titles", True):
            log("First message detected, generating title...")
            title_generation_in_progress = True # Use a local flag
            loading = self.query_one("#loading-indicator")
            loading.remove_class("hidden") # Show loading for title gen
            
            try:
                # Get appropriate client
                model = self.selected_model
                client = BaseModelClient.get_client_for_model(model)
                if client is None:
                    raise Exception(f"No client available for model: {model}")

                # Generate title
                log(f"Calling generate_conversation_title with model: {model}")
                title = await generate_conversation_title(content, model, client)
                log(f"Generated title: {title}")

                # Update conversation title in database
                self.db.update_conversation(
                    self.current_conversation.id,
                    title=title
                )
                
                # Update UI title
                title_widget = self.query_one("#conversation-title", Static)
                title_widget.update(title)
                
                # Update conversation object
                self.current_conversation.title = title
                
                self.notify(f"Conversation title set to: {title}", severity="information", timeout=3)
                
            except Exception as e:
                log.error(f"Failed to generate title: {str(e)}")
                self.notify(f"Failed to generate title: {str(e)}", severity="warning")
            finally:
                title_generation_in_progress = False
                # Hide loading indicator *only if* AI response generation isn't about to start
                # This check might be redundant if generate_response always shows it anyway
                if not self.is_generating:
                     loading.add_class("hidden")

        # Generate AI response (will set self.is_generating and handle loading indicator)
        await self.generate_response()
        
        # Focus back on input
        input_widget.focus()
    
    async def generate_response(self) -> None: # Keep SimpleChatApp generate_response
        """Generate an AI response.""" # Keep SimpleChatApp generate_response docstring
        if not self.current_conversation or not self.messages: # Keep SimpleChatApp generate_response
            return # Keep SimpleChatApp generate_response
            
        self.is_generating = True # Keep SimpleChatApp generate_response
        loading = self.query_one("#loading-indicator") # Keep SimpleChatApp generate_response
        loading.remove_class("hidden") # Keep SimpleChatApp generate_response
        
        try: # Keep SimpleChatApp generate_response
            # Get conversation parameters # Keep SimpleChatApp generate_response
            model = self.selected_model # Keep SimpleChatApp generate_response
            style = self.selected_style # Keep SimpleChatApp generate_response
            
            # Convert messages to API format # Keep SimpleChatApp generate_response
            api_messages = [] # Keep SimpleChatApp generate_response
            for msg in self.messages: # Keep SimpleChatApp generate_response
                api_messages.append({ # Keep SimpleChatApp generate_response
                    "role": msg.role, # Keep SimpleChatApp generate_response
                    "content": msg.content # Keep SimpleChatApp generate_response
                }) # Keep SimpleChatApp generate_response
                
            # Get appropriate client # Keep SimpleChatApp generate_response
            try: # Keep SimpleChatApp generate_response
                client = BaseModelClient.get_client_for_model(model) # Keep SimpleChatApp generate_response
                if client is None: # Keep SimpleChatApp generate_response
                    raise Exception(f"No client available for model: {model}") # Keep SimpleChatApp generate_response
            except Exception as e: # Keep SimpleChatApp generate_response
                self.notify(f"Failed to initialize model client: {str(e)}", severity="error") # Keep SimpleChatApp generate_response
                return # Keep SimpleChatApp generate_response
                
            # Start streaming response # Keep SimpleChatApp generate_response
            assistant_message = Message(role="assistant", content="Thinking...") # Keep SimpleChatApp generate_response
            self.messages.append(assistant_message) # Keep SimpleChatApp generate_response
            messages_container = self.query_one("#messages-container") # Keep SimpleChatApp generate_response
            message_display = MessageDisplay(assistant_message, highlight_code=CONFIG["highlight_code"]) # Keep SimpleChatApp generate_response
            messages_container.mount(message_display) # Keep SimpleChatApp generate_response
            messages_container.scroll_end(animate=False) # Keep SimpleChatApp generate_response
            
            # Add small delay to show thinking state # Keep SimpleChatApp generate_response
            await asyncio.sleep(0.5) # Keep SimpleChatApp generate_response
            
            # Stream chunks to the UI with synchronization # Keep SimpleChatApp generate_response
            update_lock = asyncio.Lock() # Keep SimpleChatApp generate_response
            
            async def update_ui(content: str): # Keep SimpleChatApp generate_response
                if not self.is_generating: # Keep SimpleChatApp generate_response
                    return # Keep SimpleChatApp generate_response
                
                async with update_lock: # Keep SimpleChatApp generate_response
                    try: # Keep SimpleChatApp generate_response
                        # Clear thinking indicator on first content # Keep SimpleChatApp generate_response
                        if assistant_message.content == "Thinking...": # Keep SimpleChatApp generate_response
                            assistant_message.content = "" # Keep SimpleChatApp generate_response
                        
                        # Update message with full content so far # Keep SimpleChatApp generate_response
                        assistant_message.content = content # Keep SimpleChatApp generate_response
                        # Update UI with full content # Keep SimpleChatApp generate_response
                        await message_display.update_content(content) # Keep SimpleChatApp generate_response
                        # Force a refresh and scroll # Keep SimpleChatApp generate_response
                        self.refresh(layout=True) # Keep SimpleChatApp generate_response
                        await asyncio.sleep(0.05)  # Longer delay for UI stability # Keep SimpleChatApp generate_response
                        messages_container.scroll_end(animate=False) # Keep SimpleChatApp generate_response
                        # Force another refresh to ensure content is visible # Keep SimpleChatApp generate_response
                        self.refresh(layout=True) # Keep SimpleChatApp generate_response
                    except Exception as e: # Keep SimpleChatApp generate_response
                        logger.error(f"Error updating UI: {str(e)}") # Keep SimpleChatApp generate_response
                
            # Generate the response with timeout and cleanup # Keep SimpleChatApp generate_response
            generation_task = None # Keep SimpleChatApp generate_response
            try: # Keep SimpleChatApp generate_response
                # Create a task for the response generation # Keep SimpleChatApp generate_response
                generation_task = asyncio.create_task( # Keep SimpleChatApp generate_response
                    generate_streaming_response( # Keep SimpleChatApp generate_response
                        api_messages, # Keep SimpleChatApp generate_response
                        model, # Keep SimpleChatApp generate_response
                        style, # Keep SimpleChatApp generate_response
                        client, # Keep SimpleChatApp generate_response
                        update_ui # Keep SimpleChatApp generate_response
                    ) # Keep SimpleChatApp generate_response
                ) # Keep SimpleChatApp generate_response
                
                # Wait for response with timeout # Keep SimpleChatApp generate_response
                full_response = await asyncio.wait_for(generation_task, timeout=60)  # Longer timeout # Keep SimpleChatApp generate_response
                
                # Save to database only if we got a complete response # Keep SimpleChatApp generate_response
                if self.is_generating and full_response: # Keep SimpleChatApp generate_response
                    self.db.add_message( # Keep SimpleChatApp generate_response
                        self.current_conversation.id, # Keep SimpleChatApp generate_response
                        "assistant", # Keep SimpleChatApp generate_response
                        full_response # Keep SimpleChatApp generate_response
                    ) # Keep SimpleChatApp generate_response
                    # Force a final refresh # Keep SimpleChatApp generate_response
                    self.refresh(layout=True) # Keep SimpleChatApp generate_response
                    await asyncio.sleep(0.1)  # Wait for UI to update # Keep SimpleChatApp generate_response
                    
            except asyncio.TimeoutError: # Keep SimpleChatApp generate_response
                logger.error("Response generation timed out") # Keep SimpleChatApp generate_response
                error_msg = "Response generation timed out. The model may be busy or unresponsive. Please try again." # Keep SimpleChatApp generate_response
                self.notify(error_msg, severity="error") # Keep SimpleChatApp generate_response
                
                # Remove the incomplete message # Keep SimpleChatApp generate_response
                if self.messages and self.messages[-1].role == "assistant": # Keep SimpleChatApp generate_response
                    self.messages.pop() # Keep SimpleChatApp generate_response
                
                # Update UI to remove the incomplete message # Keep SimpleChatApp generate_response
                await self.update_messages_ui() # Keep SimpleChatApp generate_response
                
            finally: # Keep SimpleChatApp generate_response
                # Ensure task is properly cancelled and cleaned up # Keep SimpleChatApp generate_response
                if generation_task: # Keep SimpleChatApp generate_response
                    if not generation_task.done(): # Keep SimpleChatApp generate_response
                        generation_task.cancel() # Keep SimpleChatApp generate_response
                        try: # Keep SimpleChatApp generate_response
                            await generation_task # Keep SimpleChatApp generate_response
                        except (asyncio.CancelledError, Exception) as e: # Keep SimpleChatApp generate_response
                            logger.error(f"Error cleaning up generation task: {str(e)}") # Keep SimpleChatApp generate_response
                    
                # Force a final UI refresh # Keep SimpleChatApp generate_response
                self.refresh(layout=True) # Keep SimpleChatApp generate_response
                
        except Exception as e: # Keep SimpleChatApp generate_response
            self.notify(f"Error generating response: {str(e)}", severity="error") # Keep SimpleChatApp generate_response
            # Add error message # Keep SimpleChatApp generate_response
            error_msg = f"Error generating response: {str(e)}" # Keep SimpleChatApp generate_response
            self.messages.append(Message(role="assistant", content=error_msg)) # Keep SimpleChatApp generate_response
            await self.update_messages_ui() # Keep SimpleChatApp generate_response
        finally: # Keep SimpleChatApp generate_response
            self.is_generating = False # Keep SimpleChatApp generate_response
            loading = self.query_one("#loading-indicator") # Keep SimpleChatApp generate_response
            loading.add_class("hidden") # Keep SimpleChatApp generate_response
            
    def on_model_selector_model_selected(self, event: ModelSelector.ModelSelected) -> None: # Keep SimpleChatApp on_model_selector_model_selected
        """Handle model selection""" # Keep SimpleChatApp on_model_selector_model_selected docstring
        self.selected_model = event.model_id # Keep SimpleChatApp on_model_selector_model_selected
        
    def on_style_selector_style_selected(self, event: StyleSelector.StyleSelected) -> None: # Keep SimpleChatApp on_style_selector_style_selected
        """Handle style selection""" # Keep SimpleChatApp on_style_selector_style_selected docstring
        self.selected_style = event.style_id # Keep SimpleChatApp on_style_selector_style_selected
            
    async def on_button_pressed(self, event: Button.Pressed) -> None: # Modify SimpleChatApp on_button_pressed
        """Handle button presses."""
        button_id = event.button.id
        
        # --- Handle Settings Panel Buttons ---
        if button_id == "settings-cancel-button":
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
            self.selected_model = self.current_conversation.model # Keep SimpleChatApp view_chat_history
            self.selected_style = self.current_conversation.style # Keep SimpleChatApp view_chat_history
            
        self.push_screen(HistoryScreen(conversations, handle_selection)) # Keep SimpleChatApp view_chat_history

    async def action_view_history(self) -> None: # Keep SimpleChatApp action_view_history
        """Action to view chat history via key binding.""" # Keep SimpleChatApp action_view_history docstring
        # Only trigger if message input is not focused # Keep SimpleChatApp action_view_history
        input_widget = self.query_one("#message-input", Input) # Keep SimpleChatApp action_view_history
        if not input_widget.has_focus: # Keep SimpleChatApp action_view_history
            await self.view_chat_history() # Keep SimpleChatApp action_view_history

    def action_settings(self) -> None: # Modify SimpleChatApp action_settings
        """Action to open/close settings panel via key binding."""
        # Only trigger if message input is not focused
        input_widget = self.query_one("#message-input", Input)
        if not input_widget.has_focus:
            settings_panel = self.query_one("#settings-panel")
            settings_panel.toggle_class("visible") # Toggle visibility class
            if settings_panel.has_class("visible"):
                 # Try focusing the first element in the panel (e.g., ModelSelector)
                 try:
                     model_selector = settings_panel.query_one(ModelSelector)
                     model_selector.focus()
                 except Exception:
                     pass # Ignore if focus fails
            else:
                 input_widget.focus() # Focus input when closing

    async def action_update_title(self) -> None:
        """Allow users to manually change the conversation title"""
        if not self.current_conversation:
            self.notify("No active conversation", severity="warning")
            return

        # --- Define the Modal Class ---
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

            def on_mount(self) -> None:
                """Focus the input when the modal appears."""
                self.query_one("#title-input", Input).focus()

        # --- Show the modal ---
        modal = TitleInputModal(self.current_conversation.title)
        await self.mount(modal) # Use await for mounting

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


def main(initial_text: Optional[str] = typer.Argument(None, help="Initial text to start the chat with")): # Keep main function
    """Entry point for the chat-cli application""" # Keep main function docstring
    # When no argument is provided, typer passes the ArgumentInfo object # Keep main function
    # When an argument is provided, typer passes the actual value # Keep main function
    if isinstance(initial_text, typer.models.ArgumentInfo): # Keep main function
        initial_value = None  # No argument provided # Keep main function
    else: # Keep main function
        initial_value = str(initial_text) if initial_text is not None else None # Keep main function
        
    app = SimpleChatApp(initial_text=initial_value) # Keep main function
    app.run() # Keep main function

if __name__ == "__main__": # Keep main function entry point
    typer.run(main) # Keep main function entry point
