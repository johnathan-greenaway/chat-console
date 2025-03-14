from rich.style import Style
from rich.theme import Theme
from textual.widget import Widget
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.css.query import NoMatches

# Define color palette
COLORS = {
    "dark": {
        "background": "#0C0C0C",
        "foreground": "#33FF33",
        "user_msg": "#00FFFF",
        "assistant_msg": "#33FF33",
        "system_msg": "#FF8C00",
        "highlight": "#FFD700",
        "selection": "#1A1A1A",
        "border": "#33FF33",
        "error": "#FF0000",
        "success": "#33FF33",
    },
    "light": {
        "background": "#F0F0F0",
        "foreground": "#000000",
        "user_msg": "#0000FF",
        "assistant_msg": "#008000",
        "system_msg": "#800080",
        "highlight": "#0078D7",
        "selection": "#ADD6FF",
        "border": "#D0D0D0",
        "error": "#D32F2F",
        "success": "#388E3C",
    }
}

def get_theme(theme_name="dark"):
    """Get Rich theme based on theme name"""
    colors = COLORS.get(theme_name, COLORS["dark"])
    
    return Theme({
        "user": Style(color=colors["user_msg"], bold=True),
        "assistant": Style(color=colors["assistant_msg"]),
        "system": Style(color=colors["system_msg"], italic=True),
        "highlight": Style(color=colors["highlight"], bold=True),
        "selection": Style(bgcolor=colors["selection"]),
        "border": Style(color=colors["border"]),
        "error": Style(color=colors["error"], bold=True),
        "success": Style(color=colors["success"]),
        "prompt": Style(color=colors["highlight"]),
        "heading": Style(color=colors["highlight"], bold=True),
        "dim": Style(color=colors["border"]),
        "code": Style(bgcolor="#2D2D2D", color="#D4D4D4"),
        "code.syntax": Style(color="#569CD6"),
        "link": Style(color=colors["highlight"], underline=True),
    })

# Textual CSS for the application
CSS = """
/* Base styles */
Screen {
    background: $surface;
    color: $text;
}

/* Chat message styles */
.message {
    width: 100%;
    padding: 0 1;
    margin: 0;
}

.message-content {
    width: 100%;
    text-align: left;
    padding: 0;
}

/* Code blocks */
.code-block {
    background: $surface-darken-3;
    color: $text-muted;
    border: solid $primary-darken-3;
    margin: 1 2;
    padding: 1;
    overflow: auto;
}

/* Input area */
#input-container {
    height: auto;
    background: $surface;
    border-top: solid $primary-darken-2;
    padding: 0;
}

#message-input {
    background: $surface-darken-1;
    color: $text;
    border: solid $primary-darken-2;
    min-height: 2;
    padding: 0 1;
}

#message-input:focus {
    border: tall $primary;
}

/* Action buttons */
.action-button {
    background: $primary;
    color: #FFFFFF !important; /* Explicit white text */
    border: none;
    min-width: 10;
    margin-left: 1;
    padding: 0 1; /* Add padding */
    text-style: bold;
    font-size: 1.1;
}

.action-button:hover {
    background: $primary-lighten-1;
    color: #FFFFFF !important;
    text-style: bold;
}

/* Sidebar */
#sidebar {
    width: 25%;
    min-width: 18;
    background: $surface-darken-1;
    border-right: solid $primary-darken-2 1;
}

/* Chat list */
.chat-item {
    padding: 0 1;
    height: 2;
    border-bottom: solid $primary-darken-3 1;
}

.chat-item:hover {
    background: $primary-darken-2;
}

.chat-item.selected {
    background: $primary-darken-1;
    border-left: wide $primary;
}

.chat-title {
    width: 100%;
    content-align: center middle;
    text-align: left;
}

.chat-model {
    color: $text-muted;
    text-align: right;
}

.chat-date {
    color: $text-muted;
    text-align: right;
}

/* Search input */
#search-input {
    width: 100%;
    border: solid $primary-darken-2 1;
    margin: 0 1;
    height: 2;
}

#search-input:focus {
    border: solid $primary;
}

/* Model selector */
#model-selector {
    width: 100%;
    height: 2;
    margin: 0 1;
    background: $surface-darken-1;
    border: solid $primary-darken-2 1;
}

/* Style selector */
#style-selector {
    width: 100%;
    height: 2;
    margin: 0 1;
    background: $surface-darken-1;
    border: solid $primary-darken-2 1;
}

/* Header */
#app-header {
    width: 100%;
    height: 2;
    background: $surface-darken-2;
    color: $text;
    content-align: center middle;
    text-align: center;
    border-bottom: solid $primary-darken-2 1;
}

/* Loading indicator */
#loading-indicator {
    background: $surface-darken-1;
    color: $text;
    padding: 0 1;
    height: auto;
    width: 100%;
    border-top: solid $primary-darken-2 1;
    display: none;
}

/* Settings modal */
.modal {
    background: $surface;
    border: solid $primary;
    padding: 1;
    height: auto;
    min-width: 40;
    max-width: 60;
}

.modal-title {
    background: $primary;
    color: $text;
    width: 100%;
    height: 3;
    content-align: center middle;
    text-align: center;
}

.form-label {
    width: 100%;
    padding: 1 0;
}

.form-input {
    width: 100%;
    background: $surface-darken-1;
    border: solid $primary-darken-2;
    height: 3;
    margin-bottom: 1;
}

.form-input:focus {
    border: solid $primary;
}

.button-container {
    width: 100%;
    height: 3;
    align: right middle;
}

.button {
    background: $primary-darken-1;
    color: $text;
    min-width: 6;
    margin-left: 1;
    border: solid $primary 1;
}

.button.cancel {
    background: $error;
}

/* Tags */
.tag {
    background: $primary-darken-1;
    color: $text;
    padding: 0 1;
    margin: 0 1 0 0;
    border: solid $border;
}
"""
