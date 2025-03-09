from rich.style import Style
from rich.theme import Theme
from textual.widget import Widget
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.css.query import NoMatches

# Define color palette
COLORS = {
    "dark": {
        "background": "#1E1E1E",
        "foreground": "#FFFFFF",
        "user_msg": "#9CDCFE",
        "assistant_msg": "#DCDCAA",
        "system_msg": "#6A9955",
        "highlight": "#569CD6",
        "selection": "#264F78",
        "border": "#444444",
        "error": "#F14C4C",
        "success": "#6A9955",
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
    padding: 1;
}

.message-content {
    width: 100%;
    text-align: left;
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
    border-top: solid $primary;
    padding: 1;
}

#message-input {
    background: $surface-darken-1;
    color: $text;
    border: tall $primary-darken-2;
    min-height: 3;
    padding: 1;
}

#message-input:focus {
    border: tall $primary;
}

/* Action buttons */
.action-button {
    background: $primary;
    color: $text;
    border: none;
    min-width: 10;
    margin-left: 1;
}

.action-button:hover {
    background: $primary-lighten-1;
}

/* Sidebar */
#sidebar {
    width: 30%;
    min-width: 20;
    background: $surface-darken-1;
    border-right: solid $primary-darken-2;
}

/* Chat list */
.chat-item {
    padding: 1;
    height: 3;
    border-bottom: solid $primary-darken-3;
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
    border: solid $primary-darken-2;
    margin: 1 1 0 1;
    height: 3;
}

#search-input:focus {
    border: solid $primary;
}

/* Model selector */
#model-selector {
    width: 100%;
    height: 3;
    margin: 0 1;
    background: $surface-darken-1;
    border: solid $primary-darken-2;
}

/* Style selector */
#style-selector {
    width: 100%;
    height: 3;
    margin: 0 1 1 1;
    background: $surface-darken-1;
    border: solid $primary-darken-2;
}

/* Header */
#app-header {
    width: 100%;
    height: 3;
    background: $primary-darken-1;
    color: $text;
    content-align: center middle;
    text-align: center;
}

/* Loading indicator */
#loading-indicator {
    background: $surface-darken-1;
    color: $text;
    padding: 1;
    height: auto;
    width: 100%;
    border-top: solid $primary-darken-2;
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
    background: $primary;
    color: $text;
    min-width: 8;
    margin-left: 1;
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
