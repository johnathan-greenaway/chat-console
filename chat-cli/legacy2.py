#!/usr/bin/env python3
"""
A simplified but robust version of the Terminal Chat application
"""
import os
import sys
from typing import List, Dict, Any, Optional
from datetime import datetime
import time

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.reactive import reactive
from textual.widgets import Button, Input, Label, Static, Header, Footer
from textual.binding import Binding

from app.database import ChatDatabase
from app.models import Message, Conversation
from app.config import CONFIG

class MessageView(Static):
    """Widget to display a chat message"""
    
    DEFAULT_CSS = """
    MessageView {
        width: 100%;
        padding: 1;
        margin-bottom: 1;
        border-bottom: solid $primary-darken-3;
        overflow: auto;
    }
    
    .user-message {
        background: $primary-darken-2;
        color: $text;
    }
    
    .assistant-message {
        background: $surface-darken-1;
        color: $text;
    }
    
    .message-role {
        text-style: bold;
        margin-bottom: 1;
    }
    
    .message-content {
        width: 100%;
        text-align: left;
        overflow-wrap: break-word;
    }
    """
    
    def __init__(self, role, content, name=None):
        super().__init__(name=name)
        self.role = role
        self.content = content
        
    def compose(self) -> ComposeResult:
        """Compose the message view"""
        css_class = "user-message" if self.role == "user" else "assistant-message"
        self.add_class(css_class)
        
        display_role = "You" if self.role == "user" else "Assistant"
        yield Label(f"{display_role}:", classes="message-role")
        yield Static(self.content, classes="message-content")

class ChatItem(Static):
    """Widget to display a single chat in the list"""
    
    DEFAULT_CSS = """
    ChatItem {
        width: 100%;
        height: 3;
        padding: 0 1;
        border-bottom: solid $primary-darken-3;
    }
    
    ChatItem:hover {
        background: $primary-darken-2;
    }
    
    ChatItem.selected {
        background: $primary-darken-1;
        border-left: wide $primary;
    }
    
    .chat-title {
        width: 100%;
    }
    """
    
    is_selected = reactive(False)
    
    def __init__(self, chat_id, title, selected=False, name=None):
        super().__init__(name=name)
        self.chat_id = chat_id
        self.title = title
        self.is_selected = selected
        
    def compose(self) -> ComposeResult:
        """Compose the chat item"""
        yield Label(self.title, classes="chat-title")
        
    def on_click(self) -> None:
        """Handle click event"""
        # Using different method to directly tell the app about selection
        app = self.app
        if hasattr(app, "select_chat"):
            app.select_chat(self.chat_id)
            
    def watch_is_selected(self, selected: bool) -> None:
        """Watch for selection changes"""
        if selected:
            self.add_class("selected")
        else:
            self.remove_class("selected")

class SimplifiedTerminalChat(App):
    """Simplified Terminal Chat application with robust error handling"""
    
    TITLE = "Terminal Chat"
    SUB_TITLE = "Simplified Robust Version"
    
    CSS = """
    #main-layout {
        width: 100%;
        height: 100%;
    }
    
    #sidebar {
        width: 30%;
        min-width: 20;
        background: $surface-darken-1;
        border-right: solid $primary-darken-2;
    }
    
    #main-content {
        width: 70%;
    }
    
    #messages-container {
        width: 100%;
        height: 1fr;
        overflow: auto;
    }
    
    #input-area {
        width: 100%;
        height: auto;
        min-height: 3;
        padding: 1;
        border-top: solid $primary-darken-3;
    }
    
    #message-input {
        width: 1fr;
        min-height: 1;
        height: auto;
        padding: 1;
        margin-right: 1;
    }
    
    #message-input:focus {
        border: tall $primary;
    }
    
    #send-button {
        width: auto;
        min-width: 10;
        height: 3;
    }
    """
    
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("n", "new_chat", "New Chat"),
        Binding("s", "toggle_sidebar", "Toggle Sidebar"),
        Binding("escape", "escape", "Cancel"),
        Binding("ctrl+c", "quit", "Quit"),
    ]
    
    current_chat_id = reactive(-1)
    sidebar_visible = reactive(True)
    
    def __init__(self):
        super().__init__()
        self.db = ChatDatabase()
        self.chats = []
        self.messages = []
        self.current_model = CONFIG["default_model"]
        
    class InputWithFocus(Input):
        """Enhanced Input that better handles focus and maintains cursor position"""
        
        def on_blur(self, event) -> None:
            """Restore focus when input is blurred"""
            # This helps prevent the input from losing focus unexpectedly
            self.focus()
            
        def on_key(self, event) -> None:
            """Custom key handling for input"""
            # Process normal input handling first
            super().on_key(event)
            event.stop()  # Prevent event bubbling up which can cause focus issues

    def compose(self) -> ComposeResult:
        """Compose the application layout"""
        yield Header()
        
        with Horizontal(id="main-layout"):
            # Sidebar
            with Vertical(id="sidebar"):
                yield Label("Chat History", id="sidebar-header")
                
                with ScrollableContainer(id="chat-list"):
                    # Will be populated with chat items
                    pass
                    
                yield Button("+ New Chat", id="new-chat-button", variant="success")
                
            # Main chat area
            with Vertical(id="main-content"):
                yield Static("No Conversation Selected", id="chat-title")
                
                with ScrollableContainer(id="messages-container"):
                    # Will be populated with messages
                    pass
                    
                with Container(id="input-area"):
                    yield self.InputWithFocus(placeholder="Type a message...", id="message-input", id_focus_tab="message-input")
                    yield Button("Send", id="send-button", variant="primary")
                    
        yield Footer()
        
    def on_mount(self) -> None:
        """Initialize on mount"""
        try:
            # Initialize layout
            self.refresh_layout()
            
            # Load chat history
            self.load_chats()
            
            # Create new chat if none exists
            if not self.chats:
                self.create_new_chat()
            else:
                # Select the most recent chat
                self.select_chat(self.chats[0]["id"])
                
            # Focus the input
            self.query_one("#message-input").focus()
        except Exception as e:
            self.notify(f"Error during initialization: {str(e)}", severity="error")
            
    def load_chats(self) -> None:
        """Load chat history from database"""
        try:
            chats = self.db.get_all_conversations(limit=50)
            self.chats = chats
            self.update_chat_list()
        except Exception as e:
            self.notify(f"Error loading chats: {str(e)}", severity="error")
            self.chats = []
            
    def update_chat_list(self) -> None:
        """Update the chat list UI"""
        try:
            chat_list = self.query_one("#chat-list")
            
            # Clear existing items
            try:
                chat_list.remove_children()
            except Exception:
                pass
                
            # Add chat items
            for chat in self.chats:
                is_selected = chat["id"] == self.current_chat_id
                chat_list.mount(ChatItem(
                    chat["id"], 
                    chat["title"], 
                    selected=is_selected
                ))
        except Exception as e:
            self.notify(f"Error updating chat list: {str(e)}", severity="error")
            
    def create_new_chat(self) -> None:
        """Create a new chat"""
        try:
            # Create a new chat in the database
            title = f"New Chat ({datetime.now().strftime('%Y-%m-%d %H:%M')})"
            chat_id = self.db.create_conversation(
                title=title,
                model=self.current_model,
                style="default"
            )
            
            # Get the full chat data
            chat_data = self.db.get_conversation(chat_id)
            
            if chat_data:
                # Update local state
                self.chats.insert(0, chat_data)  # Add to beginning
                self.current_chat_id = chat_id
                self.messages = []
                
                # Update UI
                self.update_chat_list()
                self.update_chat_title(title)
                self.clear_messages()
                
                # Focus the input
                self.query_one("#message-input").focus()
                
                self.notify(f"Created new chat: {title}", severity="information")
            else:
                self.notify("Failed to create new chat", severity="error")
        except Exception as e:
            self.notify(f"Error creating new chat: {str(e)}", severity="error")
            
    def load_chat(self, chat_id) -> None:
        """Load a chat's messages"""
        try:
            chat_data = self.db.get_conversation(chat_id)
            
            if not chat_data:
                self.notify(f"Chat {chat_id} not found", severity="error")
                return
                
            # Update current chat
            self.current_chat_id = chat_id
            
            # Update title
            self.update_chat_title(chat_data["title"])
            
            # Load messages
            self.messages = chat_data.get("messages", [])
            
            # Update message view
            self.update_messages_ui()
            
            # Update chat list selection
            self.update_chat_selection()
        except Exception as e:
            self.notify(f"Error loading chat: {str(e)}", severity="error")
            
    def update_chat_title(self, title) -> None:
        """Update the chat title"""
        try:
            title_widget = self.query_one("#chat-title")
            title_widget.update(title)
        except Exception as e:
            self.notify(f"Error updating chat title: {str(e)}", severity="warning")
            
    def update_messages_ui(self) -> None:
        """Update the messages UI"""
        try:
            messages_container = self.query_one("#messages-container")
            
            # Clear existing messages
            try:
                messages_container.remove_children()
            except Exception:
                pass
                
            # Add messages
            for msg in self.messages:
                if "role" in msg and "content" in msg:
                    messages_container.mount(MessageView(msg["role"], msg["content"]))
                    
            # Scroll to bottom
            try:
                messages_container.scroll_end(animate=False)
            except Exception:
                pass
        except Exception as e:
            self.notify(f"Error updating messages: {str(e)}", severity="error")
            
    def update_chat_selection(self) -> None:
        """Update which chat is selected in the list"""
        try:
            for child in self.query("#chat-list").children:
                if hasattr(child, "chat_id") and hasattr(child, "is_selected"):
                    child.is_selected = (child.chat_id == self.current_chat_id)
        except Exception as e:
            self.notify(f"Error updating chat selection: {str(e)}", severity="warning")
            
    def clear_messages(self) -> None:
        """Clear the messages UI"""
        try:
            messages_container = self.query_one("#messages-container")
            messages_container.remove_children()
        except Exception as e:
            self.notify(f"Error clearing messages: {str(e)}", severity="warning")
            
    def send_message(self) -> None:
        """Send a message"""
        try:
            # Check if a chat is selected
            if self.current_chat_id < 0:
                self.notify("No chat selected", severity="warning")
                return
                
            # Get message text
            input_widget = self.query_one("#message-input")
            message = input_widget.value.strip()
            
            if not message:
                return
                
            # Clear input
            input_widget.value = ""
            
            # Add user message to database
            try:
                self.db.add_message(
                    self.current_chat_id,
                    "user",
                    message
                )
                
                # Add to local messages
                self.messages.append({
                    "role": "user",
                    "content": message
                })
                
                # Update UI
                self.update_messages_ui()
            except Exception as e:
                self.notify(f"Error saving message: {str(e)}", severity="error")
                return
                
            # Generate mock response
            try:
                # Create a mock response
                response = f"You said: '{message}'\n\nThis is a simplified response for testing UI interactivity."
                
                # Add to database
                self.db.add_message(
                    self.current_chat_id,
                    "assistant",
                    response
                )
                
                # Add to local messages
                self.messages.append({
                    "role": "assistant",
                    "content": response
                })
                
                # Update UI
                self.update_messages_ui()
                
                # Re-focus the input after message exchange
                self.query_one("#message-input").focus()
            except Exception as e:
                self.notify(f"Error generating response: {str(e)}", severity="error")
        except Exception as e:
            self.notify(f"Error processing message: {str(e)}", severity="error")
            
    def select_chat(self, chat_id) -> None:
        """Select a chat by ID"""
        if chat_id == self.current_chat_id:
            return
            
        try:
            self.load_chat(chat_id)
        except Exception as e:
            self.notify(f"Error selecting chat: {str(e)}", severity="error")
            
    def action_new_chat(self) -> None:
        """Action to create a new chat"""
        self.create_new_chat()
        
    def action_toggle_sidebar(self) -> None:
        """Toggle sidebar visibility"""
        try:
            self.sidebar_visible = not self.sidebar_visible
            sidebar = self.query_one("#sidebar")
            sidebar.display = True if self.sidebar_visible else False
        except Exception as e:
            self.notify(f"Error toggling sidebar: {str(e)}", severity="error")
            
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        try:
            button_id = event.button.id
            
            if button_id == "send-button":
                self.send_message()
            elif button_id == "new-chat-button":
                self.create_new_chat()
        except Exception as e:
            self.notify(f"Error handling button press: {str(e)}", severity="error")
            
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission"""
        try:
            if event.input.id == "message-input":
                self.send_message()
        except Exception as e:
            self.notify(f"Error handling input: {str(e)}", severity="error")
            
    def on_key(self, event) -> None:
        """Handle key events globally"""
        try:
            # Only handle focus restoration at the app level if we're not in an input
            focused = self.focused
            
            # Don't steal focus from our InputWithFocus or any other input
            if focused is None or not isinstance(focused, Input):
                try:
                    self.query_one("#message-input").focus()
                except Exception:
                    pass
                    
            # Let the event propagate to other handlers
            event.prevent_default = False
        except Exception:
            # Don't notify on this one as it could get spammy
            pass

    def on_resize(self, event) -> None:
        """Handle terminal resize events"""
        try:
            # Update layout to fit the new terminal size
            self.refresh_layout()
            
            # Make sure messages scroll to the bottom after resize
            messages_container = self.query_one("#messages-container")
            messages_container.scroll_end(animate=False)
            
            # Ensure input has focus
            self.query_one("#message-input").focus()
        except Exception as e:
            self.notify(f"Error handling resize: {str(e)}", severity="warning")
    
    def refresh_layout(self) -> None:
        """Refresh layout after resize or other UI changes"""
        try:
            # Check if terminal is too small
            min_width = 60
            min_height = 20
            
            if self.size.width < min_width or self.size.height < min_height:
                # Just set sensible defaults for very small terminals
                sidebar = self.query_one("#sidebar")
                main_content = self.query_one("#main-content")
                
                sidebar.styles.width = "30%"
                main_content.styles.width = "70%"
                
                messages_container = self.query_one("#messages-container")
                messages_container.styles.height = "1fr"
                return
            
            # Adjust sidebar width proportionally to terminal width
            sidebar = self.query_one("#sidebar")
            main_content = self.query_one("#main-content")
            
            # Ensure the sidebar doesn't get too narrow
            sidebar_width = max(30, int(self.size.width * 0.25))
            sidebar.styles.width = f"{sidebar_width}vw"
            main_content.styles.width = f"{100 - sidebar_width}vw"
            
            # Make sure messages container fills available height
            messages_container = self.query_one("#messages-container")
            input_area = self.query_one("#input-area")
            
            try:
                input_height = input_area.size.height
            except Exception:
                # Default if we can't get actual height
                input_height = 4
                
            available_height = max(10, self.size.height - input_height - 4)
            messages_container.styles.height = f"{available_height}"
            
            # Force a refresh of the rendering
            self.refresh()
        except Exception as e:
            self.notify(f"Error refreshing layout: {str(e)}", severity="warning")

def main():
    """Run the simplified terminal chat application"""
    app = SimplifiedTerminalChat()
    app.run()

if __name__ == "__main__":
    main()
