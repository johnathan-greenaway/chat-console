from typing import Dict, List, Any, Optional
from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Select, Label, Input
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
        padding: 0;
        background: $surface-darken-1;
    }
    
    #selector-container {
        width: 100%;
        layout: horizontal;
        height: 3;
        padding: 0;
    }
    
    #provider-select {
        width: 30%;
        height: 3;
        margin-right: 1;
    }
    
    #model-select, #custom-model-input {
        width: 1fr;
        height: 3;
    }

    #custom-model-input {
        display: none;
    }

    #custom-model-input.show {
        display: block;
    }

    #model-select.hide {
        display: none;
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
        # Handle custom models not in CONFIG
        if self.selected_model in CONFIG["available_models"]:
            self.selected_provider = CONFIG["available_models"][self.selected_model]["provider"]
        else:
            # Default to OpenAI for custom models
            self.selected_provider = "openai"
        
    async def compose(self) -> ComposeResult:
        """Set up the model selector"""
        with Container(id="selector-container"):
            # Provider options including Ollama
            provider_options = [
                ("OpenAI", "openai"),
                ("Anthropic", "anthropic"),
                ("Ollama", "ollama")
            ]
            
            # Provider selector
            yield Select(
                provider_options,
                id="provider-select",
                value=self.selected_provider,
                allow_blank=False
            )
            
            # Model selector and custom input
            is_custom = self.selected_model not in CONFIG["available_models"]
            model_options = await self._get_model_options(self.selected_provider)
            yield Select(
                model_options + [("Custom Model...", "custom")],
                id="model-select",
                value="custom" if is_custom else self.selected_model,
                classes="hide" if is_custom else "",
                allow_blank=False
            )
            yield Input(
                value=self.selected_model if is_custom else "",
                placeholder="Enter custom model name",
                id="custom-model-input",
                classes="" if is_custom else "hide"
            )
            
    async def _get_model_options(self, provider: str) -> List[tuple]:
        """Get model options for a specific provider"""
        options = [
            (model_info["display_name"], model_id)
            for model_id, model_info in CONFIG["available_models"].items()
            if model_info["provider"] == provider
        ]
        
        # Add available Ollama models
        if provider == "ollama":
            try:
                from app.api.ollama import OllamaClient
                ollama = OllamaClient()
                ollama_models = await ollama.get_available_models()
                for model in ollama_models:
                    if model["id"] not in CONFIG["available_models"]:
                        options.append((model["name"], model["id"]))
            except:
                pass
                
        options.append(("Custom Model...", "custom"))
        return options
        
    async def on_select_changed(self, event: Select.Changed) -> None:
        """Handle select changes"""
        if event.select.id == "provider-select":
            self.selected_provider = event.value
            # Update model options
            model_select = self.query_one("#model-select", Select)
            model_options = await self._get_model_options(self.selected_provider)
            model_select.set_options(model_options)
            # Select first model of new provider
            if model_options:
                self.selected_model = model_options[0][1]
                model_select.value = self.selected_model
                self.post_message(self.ModelSelected(self.selected_model))
                
        elif event.select.id == "model-select":
            if event.value == "custom":
                # Show custom input
                model_select = self.query_one("#model-select")
                custom_input = self.query_one("#custom-model-input")
                model_select.add_class("hide")
                custom_input.remove_class("hide")
                custom_input.focus()
            else:
                # Hide custom input
                model_select = self.query_one("#model-select")
                custom_input = self.query_one("#custom-model-input")
                model_select.remove_class("hide")
                custom_input.add_class("hide")
                self.selected_model = event.value
                self.post_message(self.ModelSelected(event.value))

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle custom model input changes"""
        if event.input.id == "custom-model-input":
            value = event.value.strip()
            if value:  # Only update if there's actual content
                self.selected_model = value
                self.post_message(self.ModelSelected(value))
            
            
    def get_selected_model(self) -> str:
        """Get the current selected model ID"""
        return self.selected_model
    
    def set_selected_model(self, model_id: str) -> None:
        """Set the selected model"""
        self.selected_model = model_id
        if model_id in CONFIG["available_models"]:
            select = self.query_one("#model-select", Select)
            custom_input = self.query_one("#custom-model-input")
            select.value = model_id
            select.remove_class("hide")
            custom_input.add_class("hide")
        else:
            select = self.query_one("#model-select", Select)
            custom_input = self.query_one("#custom-model-input")
            select.value = "custom"
            select.add_class("hide")
            custom_input.value = model_id
            custom_input.remove_class("hide")

class StyleSelector(Container):
    """Widget for selecting the AI response style"""
    
    DEFAULT_CSS = """
    StyleSelector {
        width: 100%;
        height: auto;
        padding: 0;
        background: $surface-darken-1;
    }
    
    #selector-container {
        width: 100%;
        layout: horizontal;
        height: 3;
        padding: 0;
    }
    
    #style-label {
        width: 30%;
        height: 3;
        content-align: left middle;
        padding-right: 1;
    }
    
    #style-select {
        width: 1fr;
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
        with Container(id="selector-container"):
            yield Label("Style:", id="style-label")
            
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
            
    def get_selected_style(self) -> str:
        """Get the current selected style ID"""
        return self.selected_style
    
    def set_selected_style(self, style_id: str) -> None:
        """Set the selected style"""
        if style_id in CONFIG["user_styles"]:
            self.selected_style = style_id
            select = self.query_one("#style-select", Select)
            select.value = style_id
