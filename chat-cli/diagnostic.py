#!/usr/bin/env python3
"""
Diagnostic version of Terminal Chat to isolate UI interactivity issues
"""
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Input, Label, Header, Footer, Static

class DiagnosticApp(App):
    """Simplified Terminal Chat app to diagnose UI interactivity issues"""
    
    TITLE = "Terminal Chat Diagnostic"
    SUB_TITLE = "Testing UI interactivity"
    
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("escape", "quit", "Quit"),
        ("ctrl+c", "quit", "Quit"),
    ]
    
    def compose(self) -> ComposeResult:
        """Create a simple test UI layout"""
        yield Header()
        
        with Vertical():
            yield Label("This is a diagnostic version to test UI interactivity")
            yield Label("Please try interacting with the buttons and input field below:")
            
            with Container(id="message-container"):
                yield Static("Messages will appear here", id="message-display")
            
            with Horizontal():
                yield Input(placeholder="Type here to test input...", id="test-input")
                yield Button("Send", id="send-button", variant="primary")
                yield Button("Clear", id="clear-button", variant="warning")
        
        yield Footer()
    
    def on_mount(self) -> None:
        """Set focus to input on start"""
        self.query_one("#test-input").focus()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        if event.button.id == "send-button":
            self.send_message()
        elif event.button.id == "clear-button":
            self.clear_messages()
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission"""
        self.send_message()
    
    def send_message(self) -> None:
        """Add the input text to the message display"""
        input_widget = self.query_one("#test-input", Input)
        message = input_widget.value.strip()
        
        if message:
            # Get current content
            display = self.query_one("#message-display", Static)
            current_content = display.renderable
            
            # Add new message
            new_content = f"{current_content}\n• {message}"
            display.update(new_content)
            
            # Clear input
            input_widget.value = ""
            input_widget.focus()
    
    def clear_messages(self) -> None:
        """Clear message display"""
        display = self.query_one("#message-display", Static)
        display.update("Messages will appear here")
        
        # Return focus to input
        self.query_one("#test-input").focus()

if __name__ == "__main__":
    app = DiagnosticApp()
    app.run()
