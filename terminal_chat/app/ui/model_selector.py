from typing import Dict, List, Any, Optional
from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Select, Label
from textual.widget import Widget
from textual.message import Message

from ..config import CONFIG
from .chat_interface import ChatInterface

class ModelSelector(Container):
    """Widget for selecting the AI model to use"""
    
    DEFAULT_CSS = """
    ModelSelector {
        width: 100%;
        height: auto;
        padding: 1;
        background: $surface-darken-1;
    }
    
    #model-label {
        width: 100%;
        text-align: left;
        padding-bottom: 1;
    }
    
    #model-select {
        width: 100%;
        height: 3;
    }
    """
    
    class ModelSelected(Message):
        """Event sent when a model is selected"""
        def __init__(self, model_id: str):
            self.model_id = model_id
            super().__init__()
    
    def __init__(
        self, 
        selected_model: str = None,
        name: Optional[str] = None,
        id: Optional[str] = None
    ):
        super().__init__(name=name, id=id)
        self.selected_model = selected_model or CONFIG["default_model"]
        
    def compose(self) -> ComposeResult:
        """Set up the model selector"""
        yield Label("Model:", id="model-label")
        
        # Get model options
        options = []
        for model_id, model_info in CONFIG["available_models"].items():
            options.append((model_info["display_name"], model_id))
            
        yield Select(
            options, 
            id="model-select", 
            value=self.selected_model, 
            allow_blank=False
        )
        
    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle select changes"""
        if event.select.id == "model-select":
            self.selected_model = event.value
            self.post_message(self.ModelSelected(event.value))
            # Return focus to chat input
            chat_interface = self.app.query_one("#chat-interface", expect_type=ChatInterface)
            if chat_interface:
                input_field = chat_interface.query_one("#message-input")
                if input_field:
                    self.app.set_focus(input_field)
            
    def get_selected_model(self) -> str:
        """Get the current selected model ID"""
        return self.selected_model
    
    def set_selected_model(self, model_id: str) -> None:
        """Set the selected model"""
        if model_id in CONFIG["available_models"]:
            self.selected_model = model_id
            select = self.query_one("#model-select", Select)
            select.value = model_id

class StyleSelector(Container):
    """Widget for selecting the AI response style"""
    
    DEFAULT_CSS = """
    StyleSelector {
        width: 100%;
        height: auto;
        padding: 1;
        background: $surface-darken-1;
    }
    
    #style-label {
        width: 100%;
        text-align: left;
        padding-bottom: 1;
    }
    
    #style-select {
        width: 100%;
        height: 3;
    }
    """
    
    class StyleSelected(Message):
        """Event sent when a style is selected"""
        def __init__(self, style_id: str):
            self.style_id = style_id
            super().__init__()
    
    def __init__(
        self, 
        selected_style: str = None,
        name: Optional[str] = None,
        id: Optional[str] = None
    ):
        super().__init__(name=name, id=id)
        self.selected_style = selected_style or CONFIG["default_style"]
        
    def compose(self) -> ComposeResult:
        """Set up the style selector"""
        yield Label("Response Style:", id="style-label")
        
        # Get style options
        options = []
        for style_id, style_info in CONFIG["user_styles"].items():
            options.append((style_info["name"], style_id))
            
        yield Select(
            options, 
            id="style-select", 
            value=self.selected_style, 
            allow_blank=False
        )
        
    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle select changes"""
        if event.select.id == "style-select":
            self.selected_style = event.value
            self.post_message(self.StyleSelected(event.value))
            # Return focus to chat input
            chat_interface = self.app.query_one("#chat-interface", expect_type=ChatInterface)
            if chat_interface:
                input_field = chat_interface.query_one("#message-input")
                if input_field:
                    self.app.set_focus(input_field)
            
    def get_selected_style(self) -> str:
        """Get the current selected style ID"""
        return self.selected_style
    
    def set_selected_style(self, style_id: str) -> None:
        """Set the selected style"""
        if style_id in CONFIG["user_styles"]:
            self.selected_style = style_id
            select = self.query_one("#style-select", Select)
            select.value = style_id
