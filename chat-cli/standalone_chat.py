#!/usr/bin/env python3
"""
Standalone Chat CLI - A simplified version that works independently
"""
import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional
import os

from textual.app import App, ComposeResult
from textual.containers import Container, Vertical, ScrollableContainer
from textual.reactive import reactive
from textual.widgets import Button, Input, Label, Static, Header, Footer
from textual.binding import Binding

# Simplified database adapter
class SimpleDB:
    """Simplified database access"""
    
    def __init__(self, db_path=None):
        """Initialize with optional db path"""
        self.db_path = db_path or os.path.join(os.path.expanduser("~"), ".chatcli.db")
        self._init_db()
        
    def _init_db(self):
        """Initialize database tables"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            FOREIGN KEY (chat_id) REFERENCES chats (id)
        )
        ''')
        
        conn.commit()
        conn.close()
        
    def _get_connection(self):
        """Get a database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
        
    def create_chat(self, title):
        """Create a new chat"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        cursor.execute(
            'INSERT INTO chats (title, created_at) VALUES (?, ?)',
            (title, now)
        )
        
        chat_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return chat_id
        
    def add_message(self, chat_id, role, content):
        """Add a message to a chat"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        cursor.execute(
            'INSERT INTO messages (chat_id, role, content, timestamp) VALUES (?, ?, ?, ?)',
            (chat_id, role, content, now)
        )
        
        message_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return message_id
        
    def get_chat_messages(self, chat_id):
        """Get all messages for a chat"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            'SELECT * FROM messages WHERE chat_id = ? ORDER BY timestamp',
            (chat_id,)
        )
        
        messages = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return messages

# Message display widget
class MessageView(Static):
    """Widget to display a chat message"""
    
    DEFAULT_CSS = """
    MessageView {
        width: 100%;
        padding: 1;
        margin-bottom: 1;
        border-bottom: solid $primary-darken-3;
    }
    
    .user-message {
        background: $primary-darken-2;
        color: $text;
    }
    
    .bot-message {
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
    }
    """
    
    def __init__(self, role, content, name=None):
        super().__init__(name=name)
        self.role = role
        self.content = content
        
    def compose(self) -> ComposeResult:
        """Compose the message view"""
        css_class = "user-message" if self.role == "user" else "bot-message"
        self.add_class(css_class)
        
        display_role = "You" if self.role == "user" else "Assistant"
        yield Label(f"{display_role}:", classes="message-role")
        yield Static(self.content, classes="message-content")

# Main application
class StandaloneChat(App):
    """A simplified terminal chat application"""
    
    TITLE = "Chat CLI"
    SUB_TITLE = "Standalone Version"
    
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("escape", "escape", "Cancel"),
        Binding("ctrl+c", "quit", "Quit"),
    ]
    
    chat_id = reactive(-1)
    
    def __init__(self):
        super().__init__()
        self.db = SimpleDB()
        
    def compose(self) -> ComposeResult:
        """Compose the application layout"""
        yield Header()
        
        with Vertical():
            # Chat display
            with ScrollableContainer(id="messages-container"):
                # Will be populated with messages
                pass
                
            # Input area
            with Container(id="input-area"):
                yield Input(placeholder="Type a message...", id="message-input")
                yield Button("Send", id="send-button", variant="primary")
                
        yield Footer()
        
    def on_mount(self):
        """Setup on mount"""
        # Create a new chat if none exists
        if self.chat_id < 0:
            title = f"Chat {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            self.chat_id = self.db.create_chat(title)
            
        # Focus input
        self.query_one("#message-input").focus()
        
    def on_button_pressed(self, event: Button.Pressed):
        """Handle button press"""
        if event.button.id == "send-button":
            self.send_message()
    
    def on_input_submitted(self, event: Input.Submitted):
        """Handle input submission"""
        if event.input.id == "message-input":
            self.send_message()
            
    def send_message(self):
        """Send a message"""
        input_field = self.query_one("#message-input", Input)
        message = input_field.value.strip()
        
        if not message:
            return
            
        # Clear input field
        input_field.value = ""
        
        # Add user message
        self.db.add_message(self.chat_id, "user", message)
        self.add_message_to_ui("user", message)
        
        # Generate and add mock response
        response = f"You said: {message}\n\nThis is a simple echo response."
        self.db.add_message(self.chat_id, "assistant", response)
        self.add_message_to_ui("assistant", response)
        
        # Focus back on input
        input_field.focus()
        
    def add_message_to_ui(self, role, content):
        """Add a message to the UI"""
        container = self.query_one("#messages-container")
        container.mount(MessageView(role, content))
        container.scroll_end(animate=False)
        
    def load_messages(self):
        """Load messages for the current chat"""
        if self.chat_id < 0:
            return
            
        container = self.query_one("#messages-container")
        container.remove_children()
        
        messages = self.db.get_chat_messages(self.chat_id)
        for msg in messages:
            container.mount(MessageView(msg["role"], msg["content"]))
            
        container.scroll_end(animate=False)
        
    def action_escape(self):
        """Handle escape key"""
        # Could be expanded to cancel operations, etc.
        pass

# Run the application
if __name__ == "__main__":
    app = StandaloneChat()
    app.run()
