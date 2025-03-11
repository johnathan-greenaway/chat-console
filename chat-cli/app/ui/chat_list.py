from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
import time

from textual.app import ComposeResult
from textual.containers import Container, ScrollableContainer
from textual.reactive import reactive
from textual.widgets import Button, Input, Label, Static
from textual.widget import Widget
from textual.message import Message

from ..models import Conversation
from ..database import ChatDatabase
from ..config import CONFIG

class ChatListItem(Static):
    """Widget to display a single chat in the list"""
    
    DEFAULT_CSS = """
    ChatListItem {
        width: 100%;
        height: 3;
        padding: 0 1;
        border-bottom: solid $primary-darken-3;
    }
    
    ChatListItem:hover {
        background: $primary-darken-2;
    }
    
    ChatListItem.selected {
        background: $primary-darken-1;
        border-left: wide $primary;
    }
    
    .chat-title {
        width: 100%;
        content-align: center middle;
        text-align: left;
    }
    
    .chat-model {
        width: 100%;
        color: $text-muted;
        text-align: right;
    }
    
    .chat-date {
        width: 100%;
        color: $text-muted;
        text-align: right;
        text-style: italic;
    }
    """
    
    is_selected = reactive(False)
    
    class ChatSelected(Message):
        """Event sent when a chat is selected"""
        def __init__(self, conversation_id: int):
            self.conversation_id = conversation_id
            super().__init__()
    
    def __init__(
        self, 
        conversation: Conversation,
        is_selected: bool = False,
        name: Optional[str] = None
    ):
        super().__init__(name=name)
        self.conversation = conversation
        self.is_selected = is_selected
        
    def compose(self) -> ComposeResult:
        """Set up the chat list item"""
        yield Label(self.conversation.title, classes="chat-title")
        
        model_display = self.conversation.model
        if model_display in CONFIG["available_models"]:
            model_display = CONFIG["available_models"][model_display]["display_name"]
            
        yield Label(model_display, classes="chat-model")
        
        # Format date
        updated_at = self.conversation.updated_at
        if updated_at:
            try:
                dt = datetime.fromisoformat(updated_at)
                formatted_date = dt.strftime("%Y-%m-%d %H:%M")
            except:
                formatted_date = updated_at
        else:
            formatted_date = "Unknown"
            
        yield Label(formatted_date, classes="chat-date")
        
    def on_click(self) -> None:
        """Handle click events"""
        self.post_message(self.ChatSelected(self.conversation.id))
        
    def watch_is_selected(self, is_selected: bool) -> None:
        """Watch the is_selected property"""
        if is_selected:
            self.add_class("selected")
        else:
            self.remove_class("selected")
            
class ChatList(Container):
    """Widget to display the list of chats"""
    
    DEFAULT_CSS = """
    ChatList {
        width: 100%;
        height: 100%;
        background: $surface-darken-1;
    }
    
    #chat-list-header {
        width: 100%;
        height: 3;
        background: $primary-darken-1;
        color: $text;
        content-align: center middle;
        text-align: center;
    }
    
    #chat-list-container {
        width: 100%;
        height: 1fr;
    }
    
    #new-chat-button {
        width: 100%;
        height: 3;
        background: $success;
        color: $text;
        border: none;
    }
    
    #loading-indicator {
        width: 100%;
        height: 1;
        background: $primary-darken-1;
        color: $text;
        display: none;
    }
    
    #no-chats-label {
        width: 100%;
        height: 3;
        color: $text-muted;
        content-align: center middle;
        text-align: center;
    }
    """
    
    conversations = reactive([])
    selected_id = reactive(-1)
    is_loading = reactive(False)
    
    class NewChatRequested(Message):
        """Event sent when a new chat is requested"""
        
    class ChatSelected(Message):
        """Event sent when a chat is selected"""
        def __init__(self, conversation: Conversation):
            self.conversation = conversation
            super().__init__()
    
    def __init__(
        self,
        db: ChatDatabase,
        name: Optional[str] = None,
        id: Optional[str] = None
    ):
        super().__init__(name=name, id=id)
        self.db = db
        
    def compose(self) -> ComposeResult:
        """Set up the chat list"""
        yield Label("Chat History", id="chat-list-header")
        
        with ScrollableContainer(id="chat-list-container"):
            yield Label("No conversations yet.", id="no-chats-label")
        
        with Container(id="loading-indicator"):
            yield Label("Loading...", id="loading-text")
            
        yield Button("+ New Chat", id="new-chat-button")
        
    def on_mount(self) -> None:
        """Load chats when mounted"""
        self.load_conversations()
        
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        button_id = event.button.id
        
        if button_id == "new-chat-button":
            self.post_message(self.NewChatRequested())
            # Return focus to chat input after a short delay
            self.set_timer(0.1, self._return_focus_to_chat)
            
    def load_conversations(self) -> None:
        """Load conversations from database"""
        # Only proceed if we're properly mounted
        if not self.is_mounted:
            return
            
        self.is_loading = True
        
        try:
            # Make sure the container exists before attempting to update UI
            if not self.query("#chat-list-container"):
                return
                
            conversations = self.db.get_all_conversations(
                limit=CONFIG["max_history_items"]
            )
            self.conversations = [Conversation.from_dict(c) for c in conversations]
            
            # Only update UI if we're still mounted
            if self.is_mounted:
                self._update_list_ui()
        except Exception as e:
            # Silently handle errors during startup
            pass
        finally:
            self.is_loading = False
            
    def _update_list_ui(self) -> None:
        """Update the UI with current conversations"""
        try:
            # Only proceed if we're properly mounted
            if not self.is_mounted:
                return
                
            # Get the container safely
            container = self.query_one("#chat-list-container", ScrollableContainer)
            
            # Safely remove existing children
            try:
                container.remove_children()
            except Exception:
                # If remove_children fails, continue anyway
                pass
            
            if not self.conversations:
                container.mount(Label("No conversations yet.", id="no-chats-label"))
                return
                
            # Mount items directly without batch_update
            for conversation in self.conversations:
                is_selected = conversation.id == self.selected_id
                container.mount(ChatListItem(conversation, is_selected=is_selected))
        except Exception as e:
            # Silently handle errors during UI updates
            # These can occur during app initialization/shutdown
            pass
                
    def on_chat_list_item_chat_selected(self, event: ChatListItem.ChatSelected) -> None:
        """Handle chat selection"""
        self.selected_id = event.conversation_id
        
        # Find the selected conversation
        selected_conversation = None
        for conv in self.conversations:
            if conv.id == self.selected_id:
                selected_conversation = conv
                break
                
        if selected_conversation:
            # Get full conversation with messages
            full_conversation = self.db.get_conversation(self.selected_id)
            if full_conversation:
                self.post_message(self.ChatSelected(
                    Conversation.from_dict(full_conversation)
                ))
                # Return focus to chat input after a short delay
                self.set_timer(0.1, self._return_focus_to_chat)
                
    def _return_focus_to_chat(self) -> None:
        """Helper to return focus to chat input"""
        try:
            from .chat_interface import ChatInterface
            chat_interface = self.app.query_one("#chat-interface", expect_type=ChatInterface)
            if chat_interface:
                input_field = chat_interface.query_one("#message-input")
                if input_field and not input_field.has_focus:
                    self.app.set_focus(input_field)
        except Exception:
            pass
                
    def refresh(self, layout: bool = False, **kwargs) -> None:
        """Refresh the conversation list"""
        # Don't call load_conversations() directly to avoid recursion
        if not kwargs.get("_skip_load", False):
            try:
                # Check if container exists before trying to update UI
                self.query_one("#chat-list-container", ScrollableContainer)
                
                conversations = self.db.get_all_conversations(
                    limit=CONFIG["max_history_items"]
                )
                self.conversations = [Conversation.from_dict(c) for c in conversations]
                
                # Only update UI if we're properly mounted
                if self.is_mounted:
                    self._update_list_ui()
            except Exception as e:
                # Might occur during initialization when container is not yet available
                # Don't print error as it's expected during startup
                pass
        
        # Let parent handle layout changes but don't call super().refresh()
        # which would cause infinite recursion
        
    def watch_is_loading(self, is_loading: bool) -> None:
        """Watch the is_loading property"""
        loading = self.query_one("#loading-indicator")
        loading.display = True if is_loading else False
        
    def watch_selected_id(self, selected_id: int) -> None:
        """Watch the selected_id property"""
        try:
            # Get container first to avoid repeating the query
            container = self.query_one("#chat-list-container", ScrollableContainer)
            
            # Update selection state for each chat list item
            for child in container.children:
                if isinstance(child, ChatListItem):
                    child.is_selected = (child.conversation.id == selected_id)
        except Exception as e:
            # Handle case where container might not be mounted yet
            # This prevents errors during initialization
            pass
