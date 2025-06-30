from rich.style import Style
from rich.theme import Theme
from textual.widget import Widget
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.css.query import NoMatches

# Rams-inspired minimal color palette
# Following "Less but better" - functional colors with clear hierarchy
RAMS_COLORS = {
    "dark": {
        "background": "#0C0C0C",      # Deep black
        "foreground": "#E8E8E8",      # Clean white
        "accent": "#33FF33",          # Minimal green accent
        "muted": "#666666",           # Subtle gray
        "border": "#333333",          # Dark gray borders
        "selection": "#1A1A1A",       # Subtle selection
        "user_msg": "#E8E8E8",        # Same as foreground for consistency
        "assistant_msg": "#E8E8E8",   # Same as foreground for consistency
        "system_msg": "#666666",      # Muted for less important info
        "highlight": "#33FF33",       # Use accent for highlights
        "error": "#FF4444",           # Minimal red for errors
        "success": "#33FF33",         # Use accent for success
        "timestamp": "#666666",       # Muted for timestamps
    },
    "light": {
        "background": "#FFFFFF",      # Pure white
        "foreground": "#000000",      # Pure black
        "accent": "#007ACC",          # Minimal blue accent
        "muted": "#999999",           # Subtle gray
        "border": "#CCCCCC",          # Light gray borders
        "selection": "#F0F0F0",       # Subtle selection
        "user_msg": "#000000",        # Same as foreground
        "assistant_msg": "#000000",   # Same as foreground
        "system_msg": "#999999",      # Muted
        "highlight": "#007ACC",       # Use accent
        "error": "#CC0000",           # Minimal red
        "success": "#007ACC",         # Use accent
        "timestamp": "#999999",       # Muted for timestamps
    }
}

# Legacy alias for backward compatibility
COLORS = RAMS_COLORS

def get_theme(theme_name="dark"):
    """Get Rich theme based on Rams design principles"""
    colors = RAMS_COLORS.get(theme_name, RAMS_COLORS["dark"])
    
    return Theme({
        "user": Style(color=colors["user_msg"]),           # No bold - cleaner
        "assistant": Style(color=colors["assistant_msg"]),   # Consistent with user
        "system": Style(color=colors["muted"], italic=True), # Subtle for system msgs
        "highlight": Style(color=colors["accent"]),          # Use accent sparingly
        "selection": Style(bgcolor=colors["selection"]),     # Subtle selection
        "border": Style(color=colors["border"]),            # Functional borders
        "error": Style(color=colors["error"]),              # Clear error indication
        "success": Style(color=colors["success"]),          # Minimal success
        "prompt": Style(color=colors["accent"]),            # Use accent for prompts
        "heading": Style(color=colors["accent"]),           # Minimal headings
        "dim": Style(color=colors["muted"]),               # Muted for less important
        "timestamp": Style(color=colors["timestamp"]),      # Subtle timestamps
        "code": Style(bgcolor=colors["selection"], color=colors["foreground"]),  # Minimal code styling
        "code.syntax": Style(color=colors["accent"]),       # Use accent for syntax
        "link": Style(color=colors["accent"]),             # Clean links
    })

# Rams-inspired CSS following "As little design as possible"
CSS = """
/* Base styles - Clean foundation */
Screen {
    background: #0C0C0C;  /* Deep black */
    color: #E8E8E8;       /* Clean white */
}

/* Message display - Purposeful spacing */
.message {
    width: 100%;
    padding: 2 3;         /* Generous padding for readability */
    margin: 1 0;          /* Vertical breathing room */
    text-wrap: wrap;
}

.message-content {
    width: 100%;
    text-align: left;
    padding: 0;
    line-height: 1.4;     /* Better readability */
}

/* User messages - Minimal accent */
.user-message {
    background: #1A1A1A;  /* Subtle background */
    border-left: solid #33FF33 2;  /* Minimal accent line */
    margin-left: 2;       /* Slight indent */
}

/* Assistant messages - Clean distinction */
.assistant-message {
    background: #0C0C0C;  /* Clean background */
    border-left: solid #666666 1;  /* Subtle indicator */
    margin-right: 2;      /* Opposite indent */
}

/* Code blocks - Functional styling */
.code-block {
    background: #1A1A1A;
    color: #E8E8E8;
    border: solid #333333 1;
    margin: 1 0;
    padding: 2;
    overflow: auto;
    font-family: monospace;
}

/* Input area - Clean and functional */
#input-container {
    height: auto;
    background: #0C0C0C;
    border-top: solid #333333 1;
    padding: 2;           /* Generous padding */
}

#message-input {
    background: #0C0C0C;
    color: #E8E8E8;
    border: solid #333333 1;  /* Single, clean border */
    min-height: 2;
    padding: 1 2;         /* Comfortable padding */
}

#message-input:focus {
    border: solid #33FF33 1;  /* Minimal focus indicator */
    outline: none;
}

/* Buttons - Minimal and functional */
.action-button {
    background: transparent;
    color: #E8E8E8;
    border: solid #333333 1;
    min-width: 8;
    margin: 0 1;
    padding: 1 2;
    text-style: normal;   /* No bold - cleaner */
}

.action-button:hover {
    background: #1A1A1A;
    border: solid #33FF33 1;
    color: #E8E8E8;
}

.action-button:focus {
    border: solid #33FF33 1;
}

/* Sidebar - Clean hierarchy */
#sidebar {
    width: 25%;
    min-width: 20;
    background: #0C0C0C;
    border-right: solid #333333 1;
}

/* Chat list - Functional design */
.chat-item {
    padding: 1 2;         /* Comfortable padding */
    height: auto;
    min-height: 3;
    border-bottom: solid #1A1A1A 1;
}

.chat-item:hover {
    background: #1A1A1A;  /* Subtle hover */
}

.chat-item.selected {
    background: #1A1A1A;
    border-left: solid #33FF33 2;  /* Minimal selection indicator */
}

.chat-title {
    width: 100%;
    content-align: left top;
    text-align: left;
    color: #E8E8E8;
}

.chat-model {
    color: #666666;       /* Muted secondary info */
    text-align: left;
    font-size: 0.9;
}

.chat-date {
    color: #666666;       /* Consistent muted color */
    text-align: right;
    font-size: 0.9;
}

/* Search input - Clean and functional */
#search-input {
    width: 100%;
    border: solid #333333 1;
    margin: 1;
    height: 3;
    padding: 1;
    background: #0C0C0C;
    color: #E8E8E8;
}

#search-input:focus {
    border: solid #33FF33 1;
    outline: none;
}

/* Selectors - Consistent minimal styling */
#model-selector {
    width: 100%;
    height: 3;
    margin: 1;
    background: #0C0C0C;
    border: solid #333333 1;
    color: #E8E8E8;
    padding: 1;
}

#style-selector {
    width: 100%;
    height: 3;
    margin: 1;
    background: #0C0C0C;
    border: solid #333333 1;
    color: #E8E8E8;
    padding: 1;
}

/* Header - Clean information architecture */
#app-header {
    width: 100%;
    height: 3;
    background: #0C0C0C;
    color: #E8E8E8;
    content-align: left middle;
    text-align: left;
    border-bottom: solid #333333 1;
    padding: 0 2;
}

/* Loading indicator - Minimal and unobtrusive */
#loading-indicator {
    background: #0C0C0C;
    color: #666666;       /* Muted for less distraction */
    padding: 1 2;
    height: auto;
    width: 100%;
    border-top: solid #333333 1;
    display: none;
    text-align: center;
}

/* Modal - Clean and focused */
.modal {
    background: #0C0C0C;
    border: solid #333333 1;
    padding: 2;
    height: auto;
    min-width: 40;
    max-width: 60;
}

.modal-title {
    background: #0C0C0C;
    color: #E8E8E8;
    width: 100%;
    height: auto;
    content-align: left middle;
    text-align: left;
    padding: 1 0;
    border-bottom: solid #333333 1;
    margin-bottom: 2;
}

.form-label {
    width: 100%;
    padding: 1 0;
    color: #E8E8E8;
}

.form-input {
    width: 100%;
    background: #0C0C0C;
    border: solid #333333 1;
    height: 3;
    margin-bottom: 2;
    padding: 1;
    color: #E8E8E8;
}

.form-input:focus {
    border: solid #33FF33 1;
    outline: none;
}

.button-container {
    width: 100%;
    height: auto;
    align: right middle;
    padding-top: 2;
}

.button {
    background: transparent;
    color: #E8E8E8;
    min-width: 8;
    margin-left: 1;
    border: solid #333333 1;
    padding: 1 2;
}

.button:hover {
    background: #1A1A1A;
    border: solid #33FF33 1;
}

.button.cancel {
    border: solid #FF4444 1;
}

.button.cancel:hover {
    border: solid #FF4444 1;
    background: #1A1A1A;
}

/* Tags - Minimal and functional */
.tag {
    background: transparent;
    color: #E8E8E8;
    padding: 0 1;
    margin: 0 1 0 0;
    border: solid #333333 1;
}

/* Timestamp styling */
.timestamp {
    color: #666666;
    font-size: 0.9;
}

/* Focus indicators - Consistent throughout */
*:focus {
    outline: none;
    border-color: #33FF33 !important;
}

/* Scrollbars - Minimal styling */
::-webkit-scrollbar {
    width: 8px;
}

::-webkit-scrollbar-track {
    background: #0C0C0C;
}

::-webkit-scrollbar-thumb {
    background: #333333;
    border-radius: 0;
}

::-webkit-scrollbar-thumb:hover {
    background: #666666;
}
"""
