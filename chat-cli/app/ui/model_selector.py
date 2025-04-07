import logging
from typing import Dict, List, Any, Optional
from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Select, Label, Input
from textual.widget import Widget
from textual.message import Message

from ..config import CONFIG
from ..utils import resolve_model_id  # Import the resolve_model_id function
from ..api.ollama import OllamaClient
from .chat_interface import ChatInterface

# Set up logging
logger = logging.getLogger(__name__)

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
            # Always resolve the model ID before sending it to the main app
            # This ensures short names like "claude-3.7-sonnet" are converted to full IDs
            self.model_id = resolve_model_id(model_id)
            logger.info(f"ModelSelected: Original ID '{model_id}' resolved to '{self.model_id}'")
            super().__init__()
    
    def __init__(
        self, 
        selected_model: str = None,
        name: Optional[str] = None,
        id: Optional[str] = None
    ):
        super().__init__(name=name, id=id)
        # Resolve the model ID during initialization
        original_id = selected_model or CONFIG["default_model"]
        self.selected_model = resolve_model_id(original_id)
        logger.info(f"ModelSelector.__init__: Original ID '{original_id}' resolved to '{self.selected_model}'")
        # Handle custom models not in CONFIG
        if self.selected_model in CONFIG["available_models"]:
            self.selected_provider = CONFIG["available_models"][self.selected_model]["provider"]
        else:
            # Default to Ollama for unknown models since it's more flexible
            self.selected_provider = "ollama"
        
    def compose(self) -> ComposeResult:
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
            
            # Get initial model options synchronously
            initial_options = []
            for model_id, model_info in CONFIG["available_models"].items():
                if model_info["provider"] == self.selected_provider:
                    initial_options.append((model_info["display_name"], model_id))
            
            # Ensure we have at least the custom option
            if not initial_options or self.selected_model not in [opt[1] for opt in initial_options]:
                initial_options.append(("Custom Model...", "custom"))
                is_custom = True
                initial_value = "custom"
            else:
                is_custom = False
                initial_value = self.selected_model
            
            # Model selector and custom input
            yield Select(
                initial_options,
                id="model-select",
                value=initial_value,
                classes="hide" if is_custom else "",
                allow_blank=False
            )
            yield Input(
                value=self.selected_model if is_custom else "",
                placeholder="Enter custom model name",
                id="custom-model-input",
                classes="" if is_custom else "hide"
            )

    async def on_mount(self) -> None:
        """Initialize model options after mount"""
        # Always update model options to ensure we have the latest
        model_select = self.query_one("#model-select", Select)
        model_options = await self._get_model_options(self.selected_provider)
        model_select.set_options(model_options)
        
        # Handle model selection
        if self.selected_model in [opt[1] for opt in model_options]:
            model_select.value = self.selected_model
            model_select.remove_class("hide")
            self.query_one("#custom-model-input").add_class("hide")
        else:
            model_select.value = "custom"
            model_select.add_class("hide")
            custom_input = self.query_one("#custom-model-input")
            custom_input.value = self.selected_model
            custom_input.remove_class("hide")

        # Set initial focus on the provider selector after mount completes
        def _focus_provider():
            try:
                self.query_one("#provider-select", Select).focus()
            except Exception as e:
                logger.error(f"Error setting focus in ModelSelector: {e}")
        self.call_later(_focus_provider)
            
    async def _get_model_options(self, provider: str) -> List[tuple]:
        """Get model options for a specific provider"""
        logger = logging.getLogger(__name__)
        logger.info(f"Getting model options for provider: {provider}")
        
        options = [
            (model_info["display_name"], model_id)
            for model_id, model_info in CONFIG["available_models"].items()
            if model_info["provider"] == provider
        ]
        logger.info(f"Found {len(options)} models in config for {provider}")
        
        # Add available Ollama models
        if provider == "ollama":
            try:
                logger.info("Initializing Ollama client...")
                ollama = OllamaClient()
                logger.info("Getting available Ollama models...")
                try:
                    models = await ollama.get_available_models()
                    logger.info(f"Found {len(models)} models from Ollama API")
                    
                    # Store models in config for later use
                    CONFIG["ollama_models"] = models
                    from ..config import save_config
                    save_config(CONFIG)
                    logger.info("Saved Ollama models to config")
                    
                    for model in models:
                        if model["id"] not in CONFIG["available_models"]:
                            logger.info(f"Adding new Ollama model: {model['name']}")
                            options.append((model["name"], model["id"]))
                except AttributeError:
                    # Fallback for sync method
                    models = ollama.get_available_models()
                    logger.info(f"Found {len(models)} models from Ollama API (sync)")
                    CONFIG["ollama_models"] = models
                    from ..config import save_config
                    save_config(CONFIG)
                    logger.info("Saved Ollama models to config (sync)")
                    
                    for model in models:
                        if model["id"] not in CONFIG["available_models"]:
                            logger.info(f"Adding new Ollama model: {model['name']}")
                            options.append((model["name"], model["id"]))
            except Exception as e:
                logger.error(f"Error getting Ollama models: {str(e)}")
                # Add default Ollama models if API fails
                default_models = [
                    ("Llama 2", "llama2"),
                    ("Mistral", "mistral"),
                    ("Code Llama", "codellama"),
                    ("Gemma", "gemma")
                ]
                logger.info("Adding default Ollama models as fallback")
                options.extend(default_models)
                
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
            if model_options and len(model_options) > 0:
                # Check if model_options is properly structured as a list of tuples
                try:
                    # Get the first non-custom model if available
                    first_model = None
                    for model_option in model_options:
                        if isinstance(model_option, tuple) and len(model_option) >= 2 and model_option[1] != "custom":
                            first_model = model_option
                            break
                    
                    # If no non-custom models, use the first model
                    if not first_model and isinstance(model_options[0], tuple) and len(model_options[0]) >= 2:
                        first_model = model_options[0]
                        
                    # Set the model if we found one
                    if first_model and len(first_model) >= 2:
                        # Resolve the model ID before storing and sending
                        original_id = first_model[1]
                        resolved_id = resolve_model_id(original_id)
                        logger.info(f"on_select_changed (provider): Original ID '{original_id}' resolved to '{resolved_id}'")
                        self.selected_model = resolved_id
                        model_select.value = resolved_id
                        model_select.remove_class("hide")
                        self.query_one("#custom-model-input").add_class("hide")
                        self.post_message(self.ModelSelected(resolved_id))
                    else:
                        # Fall back to custom if no valid model found
                        self.selected_model = "custom"
                        model_select.value = "custom"
                        model_select.add_class("hide")
                        custom_input = self.query_one("#custom-model-input")
                        custom_input.remove_class("hide")
                        custom_input.focus()
                except (IndexError, TypeError) as e:
                    logger.error(f"Error selecting first model: {e}")
                    # Fall back to custom
                    self.selected_model = "custom"
                    model_select.value = "custom"
                    model_select.add_class("hide")
                    custom_input = self.query_one("#custom-model-input")
                    custom_input.remove_class("hide")
                    custom_input.focus()
                
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
                # Resolve the model ID before storing and sending
                resolved_id = resolve_model_id(event.value)
                logger.info(f"on_select_changed: Original ID '{event.value}' resolved to '{resolved_id}'")
                self.selected_model = resolved_id
                self.post_message(self.ModelSelected(resolved_id))

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle custom model input changes"""
        if event.input.id == "custom-model-input":
            value = event.value.strip()
            if value:  # Only update if there's actual content
                # Resolve the model ID before storing and sending
                resolved_id = resolve_model_id(value)
                logger.info(f"on_input_changed: Original ID '{value}' resolved to '{resolved_id}'")
                self.selected_model = resolved_id
                self.post_message(self.ModelSelected(resolved_id))
            
    def get_selected_model(self) -> str:
        """Get the current selected model ID, ensuring it's properly resolved"""
        resolved_id = resolve_model_id(self.selected_model)
        logger.info(f"get_selected_model: Original ID '{self.selected_model}' resolved to '{resolved_id}'")
        return resolved_id
    
    def set_selected_model(self, model_id: str) -> None:
        """Set the selected model, ensuring it's properly resolved"""
        # First resolve the model ID to ensure we're using the full ID
        resolved_id = resolve_model_id(model_id)
        logger.info(f"set_selected_model: Original ID '{model_id}' resolved to '{resolved_id}'")
        
        # Store the resolved ID
        self.selected_model = resolved_id
        
        # Update the UI based on whether this is a known model or custom
        if resolved_id in CONFIG["available_models"]:
            select = self.query_one("#model-select", Select)
            custom_input = self.query_one("#custom-model-input")
            select.value = resolved_id
            select.remove_class("hide")
            custom_input.add_class("hide")
        else:
            select = self.query_one("#model-select", Select)
            custom_input = self.query_one("#custom-model-input")
            select.value = "custom"
            select.add_class("hide")
            custom_input.value = resolved_id
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
