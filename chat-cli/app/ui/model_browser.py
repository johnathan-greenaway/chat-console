import asyncio
import logging
from typing import Dict, List, Any, Optional
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import Button, Input, Label, Static, DataTable, LoadingIndicator, ProgressBar
from textual.widget import Widget
from textual.message import Message
from textual.reactive import reactive

from ..api.ollama import OllamaClient
from ..config import CONFIG

# Set up logging
logger = logging.getLogger(__name__)

class ModelBrowser(Container):
    """Widget for browsing and downloading Ollama models"""
    
    DEFAULT_CSS = """
    ModelBrowser {
        width: 100%;
        height: 100%;
        background: $surface;
        padding: 1;
    }
    
    #browser-header {
        width: 100%;
        height: 3;
        layout: horizontal;
        margin-bottom: 1;
    }
    
    #browser-title {
        width: 1fr;
        height: 3;
        content-align: center middle;
        text-align: center;
        color: $text;
        background: $primary-darken-2;
    }
    
    #close-button {
        width: 10;
        height: 3;
        margin-left: 1;
    }
    
    #search-container {
        width: 100%;
        height: 3;
        layout: horizontal;
        margin-bottom: 1;
    }
    
    #model-search {
        width: 1fr;
        height: 3;
    }
    
    #search-button {
        width: 10;
        height: 3;
        margin-left: 1;
    }
    
    #refresh-button {
        width: 10;
        height: 3;
        margin-left: 1;
    }
    
    #tabs-container {
        width: 100%;
        height: 3;
        layout: horizontal;
        margin-bottom: 1;
    }
    
    .tab-button {
        height: 3;
        min-width: 15;
        background: $primary-darken-3;
    }
    
    .tab-button.active {
        background: $primary;
    }
    
    #models-container {
        width: 100%;
        height: 1fr;
    }
    
    #local-models, #available-models {
        width: 100%;
        height: 100%;
        display: none;
    }
    
    #local-models.active, #available-models.active {
        display: block;
    }
    
    DataTable {
        width: 100%;
        height: 1fr;
        min-height: 10;
    }
    
    #model-actions {
        width: 100%;
        height: auto;
        margin-top: 1;
    }
    
    #model-details {
        width: 100%;
        height: auto;
        display: none;
        border: solid $primary;
        padding: 1;
        margin-top: 1;
    }
    
    #model-details.visible {
        display: block;
    }
    
    #progress-area {
        width: 100%;
        height: auto;
        display: none;
        margin-top: 1;
        border: solid $primary;
        padding: 1;
    }
    
    #progress-area.visible {
        display: block;
    }
    
    #progress-bar {
        width: 100%;
        height: 1;
    }
    
    #progress-label {
        width: 100%;
        height: 1;
        content-align: center middle;
        text-align: center;
    }
    
    #status-label {
        width: 100%;
        height: 2;
        content-align: center middle;
        text-align: center;
    }
    
    #action-buttons {
        layout: horizontal;
        width: 100%;
        height: auto;
        align: center middle;
    }
    
    #action-buttons Button {
        margin: 0 1;
    }
    
    LoadingIndicator {
        width: 100%;
        height: 1fr;
    }
    """
    
    # Reactive variables to track state
    selected_model_id = reactive("")
    current_tab = reactive("local")  # "local" or "available"
    is_loading = reactive(False)
    is_pulling = reactive(False)
    pull_progress = reactive(0.0)
    pull_status = reactive("")
    
    def __init__(
        self, 
        name: Optional[str] = None,
        id: Optional[str] = None
    ):
        super().__init__(name=name, id=id)
        self.ollama_client = OllamaClient()
        self.local_models = []
        self.available_models = []
    
    def compose(self) -> ComposeResult:
        """Set up the model browser"""
        # Title and close button
        with Container(id="browser-header"):
            yield Static("Ollama Model Browser", id="browser-title")
            yield Button("Close", id="close-button", variant="error")
        
        # Search bar
        with Container(id="search-container"):
            yield Input(placeholder="Search models...", id="model-search")
            yield Button("Search", id="search-button")
            yield Button("Refresh", id="refresh-button")
        
        # Tabs
        with Container(id="tabs-container"):
            yield Button("Local Models", id="local-tab", classes="tab-button active")
            yield Button("Available Models", id="available-tab", classes="tab-button")
        
        # Models container (will hold both tabs)
        with Container(id="models-container"):
            # Local models tab
            with ScrollableContainer(id="local-models", classes="active"):
                yield DataTable(id="local-models-table")
                with Container(id="model-actions"):
                    with Horizontal(id="action-buttons"):
                        yield Button("Run Model", id="run-button", variant="success")
                        yield Button("Delete Model", id="delete-button", variant="error")
                        yield Button("View Details", id="details-button", variant="default")
            
            # Available models tab
            with ScrollableContainer(id="available-models"):
                yield DataTable(id="available-models-table")
                with Container(id="model-actions"):
                    with Horizontal(id="action-buttons"):
                        yield Button("Pull Model", id="pull-available-button", variant="primary")
                        yield Button("View Details", id="details-available-button", variant="default")
        
        # Model details area (hidden by default)
        with ScrollableContainer(id="model-details"):
            yield Static("No model selected", id="details-content")
        
        # Progress area for model downloads (hidden by default)
        with Container(id="progress-area"):
            yield Static("Downloading model...", id="status-label")
            yield ProgressBar(id="progress-bar", total=100)
            yield Static("0%", id="progress-label")
    
    async def on_mount(self) -> None:
        """Initialize model tables after mount"""
        # Set up local models table
        local_table = self.query_one("#local-models-table", DataTable)
        local_table.add_columns("Model", "Size", "Family", "Modified")
        local_table.cursor_type = "row"
        
        # Set up available models table
        available_table = self.query_one("#available-models-table", DataTable)
        available_table.add_columns("Model", "Size", "Family", "Description")
        available_table.cursor_type = "row"
        
        # Show notification about model loading
        self.notify("Initializing model browser, this might take a moment on first run...", 
                   severity="information", timeout=5)
        
        # Load models
        await self.load_local_models()
        
        # Start loading available models in the background
        asyncio.create_task(self.preload_available_models())
        
        # Focus search input
        self.query_one("#model-search").focus()
        
    async def preload_available_models(self) -> None:
        """Preload available models in the background"""
        # Load the available models list in the background to make it faster when
        # the user switches to the Available Models tab
        try:
            # This will trigger cache creation if needed, making tab switching faster
            models = await self.ollama_client.list_available_models_from_registry()
            if models:
                logger.info(f"Preloaded {len(models)} available models")
        except Exception as e:
            logger.error(f"Error preloading available models: {str(e)}")
    
    async def load_local_models(self) -> None:
        """Load locally installed Ollama models"""
        self.is_loading = True
        
        try:
            self.local_models = await self.ollama_client.get_available_models()
            
            # Clear and populate table
            local_table = self.query_one("#local-models-table", DataTable)
            local_table.clear()
            
            for model in self.local_models:
                # Try to get additional details
                try:
                    details = await self.ollama_client.get_model_details(model["id"])
                    
                    # Extract parameter size info (in billions)
                    size = "Unknown"
                    
                    # First try to get parameter size from modelfile if available
                    if "modelfile" in details and details["modelfile"] is not None:
                        modelfile = details["modelfile"]
                        if "parameter_size" in modelfile and modelfile["parameter_size"]:
                            size = str(modelfile["parameter_size"])
                            # Make sure it ends with B for billions if it doesn't already
                            if not size.upper().endswith("B"):
                                size += "B"
                    
                    # If not found in modelfile, try to extract from name
                    if size == "Unknown":
                        name = model["name"].lower()
                        if "70b" in name:
                            size = "70B"
                        elif "405b" in name or "400b" in name:
                            size = "405B"
                        elif "34b" in name or "35b" in name:
                            size = "34B"
                        elif "27b" in name or "28b" in name:
                            size = "27B"
                        elif "13b" in name or "14b" in name:
                            size = "13B"
                        elif "8b" in name:
                            size = "8B"
                        elif "7b" in name:
                            size = "7B"
                        elif "6b" in name:
                            size = "6B"
                        elif "3b" in name:
                            size = "3B"
                        elif "2b" in name:
                            size = "2B"
                        elif "1b" in name:
                            size = "1B"
                        elif "mini" in name:
                            size = "3B"
                        elif "small" in name:
                            size = "7B"
                        elif "medium" in name:
                            size = "13B"
                        elif "large" in name:
                            size = "34B"
                        
                        # Special handling for base models with no size indicator
                        if size == "Unknown":
                            # Remove tag part if present to get base model
                            base_name = name.split(":")[0]
                            
                            # Check if we have default parameter sizes for known models
                            model_defaults = {
                                "llama3": "8B",
                                "llama2": "7B",
                                "mistral": "7B",
                                "gemma": "7B",
                                "gemma2": "9B",
                                "phi": "3B",
                                "phi2": "3B",
                                "phi3": "3B",
                                "orca-mini": "7B",
                                "llava": "7B",
                                "codellama": "7B",
                                "neural-chat": "7B",
                                "wizard-math": "7B",
                                "yi": "6B",
                                "deepseek": "7B",
                                "deepseek-coder": "7B",
                                "qwen": "7B",
                                "falcon": "7B",
                                "stable-code": "3B"
                            }
                            
                            # Try to find a match in default sizes
                            for model_name, default_size in model_defaults.items():
                                if model_name in base_name:
                                    size = default_size
                                    break
                    
                    # Extract family info - check multiple possible locations
                    family = "Unknown"
                    if "modelfile" in details and details["modelfile"] is not None:
                        # First check for family field
                        if "family" in details["modelfile"] and details["modelfile"]["family"]:
                            family = details["modelfile"]["family"]
                        # Try to infer from model name if not available
                        else:
                            name = model["name"].lower()
                            if "llama" in name:
                                family = "Llama"
                            elif "mistral" in name:
                                family = "Mistral"
                            elif "phi" in name:
                                family = "Phi"
                            elif "gemma" in name:
                                family = "Gemma"
                            elif "yi" in name:
                                family = "Yi"
                            elif "orca" in name:
                                family = "Orca"
                            elif "wizard" in name:
                                family = "Wizard"
                            elif "neural" in name:
                                family = "Neural Chat"
                            elif "qwen" in name:
                                family = "Qwen"
                            elif "deepseek" in name:
                                family = "DeepSeek"
                            elif "falcon" in name:
                                family = "Falcon"
                            elif "stable" in name:
                                family = "Stable"
                            elif "codellama" in name:
                                family = "CodeLlama"
                            elif "llava" in name:
                                family = "LLaVA"
                    
                    # Extract modified date
                    modified = details.get("modified_at", "Unknown")
                    if modified == "Unknown" and "created_at" in details:
                        modified = details["created_at"]
                        
                except Exception as detail_error:
                    self.notify(f"Error getting details for {model['name']}: {str(detail_error)}", severity="warning")
                    size = "Unknown"
                    family = "Unknown"
                    modified = "Unknown"
                
                local_table.add_row(model["name"], size, family, modified)
            
            self.notify(f"Loaded {len(self.local_models)} local models", severity="information")
            
        except Exception as e:
            self.notify(f"Error loading local models: {str(e)}", severity="error")
        finally:
            self.is_loading = False
    
    async def load_available_models(self) -> None:
        """Load available models from Ollama registry"""
        self.is_loading = True
        
        try:
            # Get search query if any
            search_input = self.query_one("#model-search", Input)
            query = search_input.value.strip()
            
            # Debug to track model loading
            logger.info(f"Loading available models, query: '{query}'")
            
            # Load models from registry - don't apply the query here, get ALL models
            try:
                # First try the API-based registry
                self.available_models = await self.ollama_client.list_available_models_from_registry("")
                logger.info(f"Got {len(self.available_models)} models from registry")
                
                # If no models found, use the curated list
                if not self.available_models:
                    self.available_models = await self.ollama_client.get_registry_models("")
                    logger.info(f"Got {len(self.available_models)} models from curated list")
            except Exception as e:
                logger.error(f"Error from registry API: {str(e)}")
                # Fallback to curated list
                self.available_models = await self.ollama_client.get_registry_models("")
                logger.info(f"Fallback: Got {len(self.available_models)} models from curated list")
            
            # Clear and populate table
            available_table = self.query_one("#available-models-table", DataTable)
            available_table.clear()
            
            # Get number of models loaded (but don't notify to avoid notification spam)
            model_count = len(self.available_models)
            logger.info(f"Found {model_count} models to display")
            
            # Filter models by search query if provided
            filtered_models = self.available_models
            if query:
                query = query.lower()
                filtered_models = []
                for model in self.available_models:
                    # Check if query matches name, description or family
                    name = str(model.get("name", "")).lower()
                    desc = str(model.get("description", "")).lower()
                    family = str(model.get("model_family", "")).lower()
                    
                    # Also check variants if available
                    variants_match = False
                    if "variants" in model and model["variants"]:
                        variants_text = " ".join([str(v).lower() for v in model["variants"]])
                        if query in variants_text:
                            variants_match = True
                    
                    if query in name or query in desc or query in family or variants_match:
                        filtered_models.append(model)
                
                logger.info(f"Filtered to {len(filtered_models)} models matching '{query}'")
            
            # Add all filtered models to the table - no pagination limit
            for model in filtered_models:
                name = model.get("name", "Unknown")
                
                # Extract parameter size info (in billions)
                size = "Unknown"
                
                # Check if parameter_size is available in the model metadata
                if "parameter_size" in model and model["parameter_size"]:
                    size = str(model["parameter_size"])
                    # Make sure it ends with B for billions if it doesn't already
                    if not size.upper().endswith("B"):
                        size += "B"
                # Check if we can extract from variants
                elif "variants" in model and model["variants"]:
                    for variant in model["variants"]:
                        if any(char.isdigit() for char in str(variant)):
                            # This looks like a size variant (e.g., "7b", "70b")
                            variant_str = str(variant).lower()
                            if variant_str.endswith('b'):
                                size = str(variant).upper()
                            else:
                                size = f"{variant}B"
                            break
                else:
                    # Extract from name if not available
                    model_name = str(name).lower()
                    if "70b" in model_name:
                        size = "70B"
                    elif "405b" in model_name or "400b" in model_name:
                        size = "405B"
                    elif "34b" in model_name or "35b" in model_name:
                        size = "34B"
                    elif "27b" in model_name or "28b" in model_name:
                        size = "27B"
                    elif "13b" in model_name or "14b" in model_name:
                        size = "13B"
                    elif "8b" in model_name:
                        size = "8B"
                    elif "7b" in model_name:
                        size = "7B"
                    elif "6b" in model_name:
                        size = "6B"
                    elif "3b" in model_name:
                        size = "3B"
                    elif "2b" in model_name:
                        size = "2B"
                    elif "1b" in model_name:
                        size = "1B"
                    elif "mini" in model_name:
                        size = "3B"
                    elif "small" in model_name:
                        size = "7B"
                    elif "medium" in model_name:
                        size = "13B"
                    elif "large" in model_name:
                        size = "34B"
                        
                    # Special handling for base models with no size indicator
                    if size == "Unknown":
                        # Remove tag part if present to get base model
                        base_name = model_name.split(":")[0]
                        
                        # Check if we have default parameter sizes for known models
                        model_defaults = {
                            "llama3": "8B",
                            "llama2": "7B",
                            "mistral": "7B",
                            "gemma": "7B",
                            "gemma2": "9B",
                            "phi": "3B",
                            "phi2": "3B",
                            "phi3": "3B",
                            "phi4": "7B",
                            "orca-mini": "7B",
                            "llava": "7B",
                            "codellama": "7B",
                            "neural-chat": "7B",
                            "wizard-math": "7B",
                            "yi": "6B",
                            "deepseek": "7B",
                            "deepseek-coder": "7B",
                            "qwen": "7B",
                            "falcon": "7B",
                            "stable-code": "3B"
                        }
                        
                        # Try to find a match in default sizes
                        for model_prefix, default_size in model_defaults.items():
                            if model_prefix in base_name:
                                size = default_size
                                break
                
                family = model.get("model_family", "Unknown")
                description = model.get("description", "No description available")
                
                # Keep this for debugging
                # logger.info(f"Adding model to table: {name} - {size} - {family}")
                
                available_table.add_row(name, size, family, description)
            
            actual_displayed = available_table.row_count
            logger.info(f"Loaded {actual_displayed} available models")
            
        except Exception as e:
            logger.error(f"Error loading available models: {str(e)}")
            self.notify(f"Error loading available models: {str(e)}", severity="error")
        finally:
            self.is_loading = False
    
    def _format_size(self, size_bytes: int) -> str:
        """Format size in bytes to human-readable format"""
        if size_bytes == 0:
            return "Unknown"
        
        suffixes = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        while size_bytes >= 1024 and i < len(suffixes) - 1:
            size_bytes /= 1024
            i += 1
        
        return f"{size_bytes:.2f} {suffixes[i]}"
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        button_id = event.button.id
        
        if button_id == "close-button":
            # Close the model browser by popping the screen
            if hasattr(self.app, "pop_screen"):
                self.app.pop_screen()
            return
        elif button_id == "local-tab":
            self._switch_tab("local")
        elif button_id == "available-tab":
            self._switch_tab("available")
            # Load available models if they haven't been loaded yet
            if not self.available_models:
                self.app.call_later(self.load_available_models)
        elif button_id == "search-button":
            # Search in the current tab
            if self.current_tab == "local":
                self.app.call_later(self.load_local_models)
            else:
                self.app.call_later(self.load_available_models)
        elif button_id == "refresh-button":
            # Refresh current tab
            if self.current_tab == "local":
                self.app.call_later(self.load_local_models)
            else:
                self.app.call_later(self.load_available_models)
        elif button_id == "run-button":
            # Set model in the main app
            self.app.call_later(self._run_selected_model)
        elif button_id == "pull-available-button":
            # Start model pull
            self.app.call_later(self._pull_selected_model)
        elif button_id == "delete-button":
            # Delete selected model
            self.app.call_later(self._delete_selected_model)
        elif button_id in ["details-button", "details-available-button"]:
            # Show model details
            self.app.call_later(self._show_model_details)
    
    def _switch_tab(self, tab: str) -> None:
        """Switch between local and available tabs"""
        self.current_tab = tab
        
        # Update tab buttons
        local_tab = self.query_one("#local-tab", Button)
        available_tab = self.query_one("#available-tab", Button)
        
        if tab == "local":
            local_tab.add_class("active")
            available_tab.remove_class("active")
        else:
            local_tab.remove_class("active")
            available_tab.add_class("active")
        
        # Update containers
        local_container = self.query_one("#local-models", ScrollableContainer)
        available_container = self.query_one("#available-models", ScrollableContainer)
        
        if tab == "local":
            local_container.add_class("active")
            available_container.remove_class("active")
        else:
            local_container.remove_class("active")
            available_container.add_class("active")
    
    async def _run_selected_model(self) -> None:
        """Set the selected model as the active model in the main app"""
        # Get selected model based on current tab
        model_id = self._get_selected_model_id()
        
        if not model_id:
            self.notify("No model selected", severity="warning")
            return
            
        try:
            # Set the model in the app
            if hasattr(self.app, "selected_model"):
                self.app.selected_model = model_id
                self.app.update_app_info()  # Update app info to show new model
                self.notify(f"Model set to: {model_id}", severity="success")
                self.app.pop_screen()  # Close the model browser screen
            else:
                self.notify("Cannot set model: app interface not available", severity="error")
        except Exception as e:
            self.notify(f"Error setting model: {str(e)}", severity="error")
            
    async def _pull_selected_model(self) -> None:
        """Pull the selected model from Ollama registry"""
        # Get selected model based on current tab
        model_id = self._get_selected_model_id()
        
        if not model_id:
            self.notify("No model selected", severity="warning")
            return
        
        # Show confirmation dialog - use a simple notification instead of modal
        msg = f"Downloading model '{model_id}'. This may take several minutes depending on model size."
        self.notify(msg, severity="information", timeout=5)
        
        # No confirmation needed now, since we're just proceeding with notification
        
        if self.is_pulling:
            self.notify("Already pulling a model", severity="warning")
            return
        
        self.is_pulling = True
        self.pull_progress = 0.0
        self.pull_status = f"Starting download of {model_id}..."
        
        # Show progress area
        progress_area = self.query_one("#progress-area")
        progress_area.add_class("visible")
        
        # Update progress UI
        progress_bar = self.query_one("#progress-bar", ProgressBar)
        progress_bar.update(progress=0)
        status_label = self.query_one("#status-label", Static)
        status_label.update(f"Downloading {model_id}...")
        progress_label = self.query_one("#progress-label", Static)
        progress_label.update("0%")
        
        try:
            # Start pulling model with progress updates
            async for progress_data in self.ollama_client.pull_model(model_id):
                # Update progress
                if "status" in progress_data:
                    self.pull_status = progress_data["status"]
                    status_label.update(self.pull_status)
                
                if "completed" in progress_data and "total" in progress_data:
                    completed = progress_data["completed"]
                    total = progress_data["total"]
                    if total > 0:
                        percentage = (completed / total) * 100
                        self.pull_progress = percentage
                        progress_bar.update(progress=int(percentage))
                        progress_label.update(f"{percentage:.1f}%")
            
            # Download complete
            self.pull_status = f"Download of {model_id} complete!"
            status_label.update(self.pull_status)
            progress_bar.update(progress=100)
            progress_label.update("100%")
            
            self.notify(f"Model {model_id} downloaded successfully", severity="success")
            
            # Refresh local models
            await self.load_local_models()
            
        except Exception as e:
            self.notify(f"Error pulling model: {str(e)}", severity="error")
            status_label.update(f"Error: {str(e)}")
        finally:
            self.is_pulling = False
            # Hide progress area after a delay
            async def hide_progress():
                # Use asyncio.sleep instead of app.sleep
                import asyncio
                await asyncio.sleep(3)
                progress_area.remove_class("visible")
            self.app.call_later(hide_progress)
    
    async def _delete_selected_model(self) -> None:
        """Delete the selected model from local storage"""
        # Only works on local tab
        if self.current_tab != "local":
            self.notify("Can only delete local models", severity="warning")
            return
        
        model_id = self._get_selected_model_id()
        
        if not model_id:
            self.notify("No model selected", severity="warning")
            return
        
        # Confirm deletion
        if not await self.app.run_modal("confirm_dialog", f"Are you sure you want to delete {model_id}?"):
            return
        
        try:
            await self.ollama_client.delete_model(model_id)
            self.notify(f"Model {model_id} deleted successfully", severity="success")
            
            # Refresh local models
            await self.load_local_models()
            
        except Exception as e:
            self.notify(f"Error deleting model: {str(e)}", severity="error")
    
    async def _show_model_details(self) -> None:
        """Show details for the selected model"""
        model_id = self._get_selected_model_id()
        
        if not model_id:
            # Try to select the first model in the table
            if self.current_tab == "local" and self.local_models:
                model_id = self.local_models[0]["id"]
            elif self.current_tab == "available" and self.available_models:
                model_id = self.available_models[0]["name"]
                
            # If we still don't have a model ID, show warning and return
            if not model_id:
                self.notify("No model selected", severity="warning")
                return
        
        # Get model details container
        details_container = self.query_one("#model-details")
        details_content = self.query_one("#details-content", Static)
        
        # Check if we're in "available" tab or "local" tab
        if self.current_tab == "available":
            # For available models, use cached info instead of making API calls
            try:
                # Find the model in our available_models list
                model_info = None
                for model in self.available_models:
                    if model.get("name") == model_id:
                        model_info = model
                        break
                
                if not model_info:
                    details_content.update(f"No details found for model: {model_id}")
                    details_container.add_class("visible")
                    return
                
                # Format the details from the cached info
                formatted_details = f"Model: {model_id}\n"
                
                # Add parameters info
                param_size = model_info.get("parameter_size", "Unknown")
                if param_size and not str(param_size).upper().endswith("B"):
                    param_size = f"{param_size}B"
                formatted_details += f"Parameters: {param_size}\n"
                
                # Add family info
                family = model_info.get("model_family", "Unknown")
                formatted_details += f"Family: {family}\n"
                
                # Add description
                description = model_info.get("description", "No description available.")
                formatted_details += f"\nDescription:\n{description}\n"
                
                # Add variants if available
                if "variants" in model_info and model_info["variants"]:
                    formatted_details += f"\nVariants: {', '.join(model_info['variants'])}\n"
                
                # Add stats if available
                if "stats" in model_info and model_info["stats"]:
                    stats = model_info["stats"]
                    formatted_details += f"\nStats:\n"
                    if "pulls" in stats:
                        formatted_details += f"Pulls: {stats['pulls']}\n"
                    if "tags" in stats:
                        formatted_details += f"Tags: {stats['tags']}\n"
                    if "last_updated" in stats:
                        formatted_details += f"Last Updated: {stats['last_updated']}\n"
                
                # Update and show details
                details_content.update(formatted_details)
                details_container.add_class("visible")
            except Exception as e:
                logger.error(f"Error showing available model details: {str(e)}")
                details_content.update(f"Error loading details: {str(e)}")
                details_container.add_class("visible")
        else:
            # For local models, we still need to get details from API
            try:
                # Get model details from Ollama
                details = await self.ollama_client.get_model_details(model_id)
                
                # Check for error in response
                if "error" in details:
                    error_msg = f"Error: {details['error']}"
                    details_content.update(error_msg)
                    details_container.add_class("visible")
                    return
                
                formatted_details = f"Model: {model_id}\n"
                
                # Extract parameter size info
                param_size = "Unknown"
                
                # First try to get parameter size from modelfile if available
                if "modelfile" in details and details["modelfile"] is not None:
                    modelfile = details["modelfile"]
                    if "parameter_size" in modelfile and modelfile["parameter_size"]:
                        param_size = str(modelfile["parameter_size"])
                        # Make sure it ends with B for billions if it doesn't already
                        if not param_size.upper().endswith("B"):
                            param_size += "B"
                
                # If not found in modelfile, try to extract from name
                if param_size == "Unknown":
                    model_name = str(model_id).lower()
                    if "70b" in model_name:
                        param_size = "70B"
                    elif "405b" in model_name or "400b" in model_name:
                        param_size = "405B"
                    elif "34b" in model_name or "35b" in model_name:
                        param_size = "34B"
                    elif "27b" in model_name or "28b" in model_name:
                        param_size = "27B"
                    elif "13b" in model_name or "14b" in model_name:
                        param_size = "13B"
                    elif "8b" in model_name:
                        param_size = "8B"
                    elif "7b" in model_name:
                        param_size = "7B"
                    elif "6b" in model_name:
                        param_size = "6B"
                    elif "3b" in model_name:
                        param_size = "3B"
                    elif "2b" in model_name:
                        param_size = "2B"
                    elif "1b" in model_name:
                        param_size = "1B"
                    elif "mini" in model_name:
                        param_size = "3B"
                    elif "small" in model_name:
                        param_size = "7B"
                    elif "medium" in model_name:
                        param_size = "13B"
                    elif "large" in model_name:
                        param_size = "34B"
                    
                    # Special handling for base models with no size indicator
                    if param_size == "Unknown":
                        # Remove tag part if present to get base model
                        base_name = model_name.split(":")[0]
                        
                        # Check if we have default parameter sizes for known models
                        model_defaults = {
                            "llama3": "8B",
                            "llama2": "7B",
                            "mistral": "7B",
                            "gemma": "7B",
                            "gemma2": "9B",
                            "phi": "3B",
                            "phi2": "3B",
                            "phi3": "3B",
                            "phi4": "7B",
                            "orca-mini": "7B",
                            "llava": "7B",
                            "codellama": "7B",
                            "neural-chat": "7B",
                            "wizard-math": "7B",
                            "yi": "6B",
                            "deepseek": "7B",
                            "deepseek-coder": "7B",
                            "qwen": "7B",
                            "falcon": "7B",
                            "stable-code": "3B"
                        }
                        
                        # Try to find a match in default sizes
                        for model_name, default_size in model_defaults.items():
                            if model_name in base_name:
                                param_size = default_size
                                break
                    
                # Show both parameter size and disk size
                formatted_details += f"Parameters: {param_size}\n"
                formatted_details += f"Disk Size: {self._format_size(details.get('size', 0))}\n"
                
                # Extract family info - check multiple possible locations
                family = "Unknown"
                template = "Unknown"
                license_info = "Unknown"
                system_prompt = ""
                
                if "modelfile" in details and details["modelfile"] is not None:
                    modelfile = details["modelfile"]

                    # Ensure modelfile is a dictionary before accessing keys
                    if isinstance(modelfile, dict):
                        # Extract family/parameter size
                        if "parameter_size" in modelfile:
                            family = modelfile.get("parameter_size")
                        elif "family" in modelfile:
                            family = modelfile.get("family")
                        else:
                            # Try to infer from model name if not explicitly set
                            try:
                                name = str(model_id).lower() if model_id is not None else ""
                                if "llama" in name:
                                    family = "Llama"
                                elif "mistral" in name:
                                    family = "Mistral"
                                elif "phi" in name:
                                    family = "Phi"
                                elif "gemma" in name:
                                    family = "Gemma"
                                else:
                                    family = "Unknown"
                            except (TypeError, ValueError) as e:
                                logger.error(f"Error inferring model family: {str(e)}")
                                family = "Unknown"

                        # Get template
                        template = modelfile.get("template", "Unknown")

                        # Get license
                        license_info = modelfile.get("license", "Unknown")

                        # Get system prompt if available
                        if "system" in modelfile:
                            system_prompt = modelfile.get("system", "") # Use get for safety
                    else:
                        # If modelfile is not a dict (e.g., a string), set defaults
                        logger.warning(f"Modelfile for {model_id} is not a dictionary. Type: {type(modelfile)}")
                        # Keep existing defaults or try to infer family from name again
                        if family == "Unknown":
                             try:
                                name = str(model_id).lower() if model_id is not None else ""
                                if "llama" in name: family = "Llama"
                                elif "mistral" in name: family = "Mistral"
                                elif "phi" in name: family = "Phi"
                                elif "gemma" in name: family = "Gemma"
                             except (TypeError, ValueError): pass # Ignore errors here
                        # template, license_info, system_prompt remain "Unknown" or empty
                
                formatted_details += f"Family: {family}\n"
                formatted_details += f"Template: {template}\n"
                formatted_details += f"License: {license_info}\n"
                
                # Add timestamps if available
                if "modified_at" in details and details["modified_at"]:
                    formatted_details += f"Modified: {details['modified_at']}\n"
                elif "created_at" in details and details["created_at"]:
                    formatted_details += f"Created: {details['created_at']}\n"
                    
                # Add system prompt if available
                if system_prompt:
                    formatted_details += f"\nSystem Prompt:\n{system_prompt}\n"
                
                # Update and show details
                details_content.update(formatted_details)
                details_container.add_class("visible")
                
            except Exception as e:
                self.notify(f"Error getting model details: {str(e)}", severity="error")
                details_content.update(f"Error loading details: {str(e)}")
                details_container.add_class("visible")
    
    def _get_selected_model_id(self) -> str:
        """Get the ID of the currently selected model"""
        try:
            if self.current_tab == "local":
                table = self.query_one("#local-models-table", DataTable)
                if table.cursor_row is not None:
                    row = table.get_row_at(table.cursor_row)
                    # Get model ID from local models list
                    try:
                        if row and len(row) > 0:
                            row_name = str(row[0]) if row[0] is not None else ""
                            for model in self.local_models:
                                if model["name"] == row_name:
                                    return model["id"]
                    except (IndexError, TypeError) as e:
                        logger.error(f"Error processing row data: {str(e)}")
            else:
                table = self.query_one("#available-models-table", DataTable)
                if table.cursor_row is not None:
                    try:
                        row = table.get_row_at(table.cursor_row)
                        # Return the model name as ID
                        if row and len(row) > 0:
                            return str(row[0]) if row[0] is not None else ""
                    except Exception as e:
                        logger.error(f"Error getting row at cursor: {str(e)}")
                
                # If we couldn't get a valid row, check if there are any rows and select the first one
                if table.row_count > 0:
                    try:
                        # Select the first row and get its ID
                        table.cursor_row = 0
                        row = table.get_row_at(0)
                        if row and len(row) > 0:
                            return str(row[0]) if row[0] is not None else ""
                    except Exception as e:
                        logger.error(f"Error selecting first row: {str(e)}")
        except Exception as e:
            logger.error(f"Error in _get_selected_model_id: {str(e)}")
        
        return ""
    
    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in data tables"""
        # Set selected model ID based on the selected row
        if event.data_table.id == "local-models-table":
            row = event.data_table.get_row_at(event.cursor_row)
            # Find the model ID from the display name
            try:
                if row and len(row) > 0:
                    row_name = str(row[0]) if row[0] is not None else ""
                    for model in self.local_models:
                        if model["name"] == row_name:
                            self.selected_model_id = model["id"]
                            break
            except (IndexError, TypeError) as e:
                logger.error(f"Error processing row data: {str(e)}")
        elif event.data_table.id == "available-models-table":
            row = event.data_table.get_row_at(event.cursor_row)
            # Model name is used as ID
            try:
                if row and len(row) > 0:
                    self.selected_model_id = str(row[0]) if row[0] is not None else ""
                else:
                    self.selected_model_id = ""
            except (IndexError, TypeError) as e:
                logger.error(f"Error getting model ID from row: {str(e)}")
                self.selected_model_id = ""
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission (Enter key in search input)"""
        if event.input.id == "model-search":
            # Trigger search
            if self.current_tab == "local":
                self.app.call_later(self.load_local_models)
            else:
                self.app.call_later(self.load_available_models)
                
    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input changes for live search"""
        if event.input.id == "model-search" and self.current_tab == "available":
            # Auto-search as user types in the available models tab
            self.app.call_later(self.load_available_models)
