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
    
    #browser-title {
        width: 100%;
        height: 1;
        content-align: center middle;
        text-align: center;
        color: $text;
        background: $primary-darken-2;
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
        # Title
        yield Static("Ollama Model Browser", id="browser-title")
        
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
            with Container(id="local-models", classes="active"):
                yield DataTable(id="local-models-table")
                with Container(id="model-actions"):
                    with Horizontal(id="action-buttons"):
                        yield Button("Pull Model", id="pull-button", variant="primary")
                        yield Button("Delete Model", id="delete-button", variant="error")
                        yield Button("View Details", id="details-button", variant="default")
            
            # Available models tab
            with Container(id="available-models"):
                yield DataTable(id="available-models-table")
                with Container(id="model-actions"):
                    with Horizontal(id="action-buttons"):
                        yield Button("Pull Model", id="pull-available-button", variant="primary")
                        yield Button("View Details", id="details-available-button", variant="default")
        
        # Model details area (hidden by default)
        with Container(id="model-details"):
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
        
        # Load models
        await self.load_local_models()
        
        # Focus search input
        self.query_one("#model-search").focus()
    
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
                    size = self._format_size(details.get("size", 0))
                    family = details.get("modelfile", {}).get("parameter_size", "Unknown")
                    modified = details.get("modified_at", "Unknown")
                except Exception:
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
            
            # Load models from registry
            try:
                # First try the API-based registry
                self.available_models = await self.ollama_client.list_available_models_from_registry(query)
                if not self.available_models:
                    # If no models found, use the curated list
                    self.available_models = await self.ollama_client.get_registry_models()
            except Exception as e:
                self.notify(f"Error from registry API: {str(e)}", severity="warning")
                # Fallback to curated list
                self.available_models = await self.ollama_client.get_registry_models()
            
            # Clear and populate table
            available_table = self.query_one("#available-models-table", DataTable)
            available_table.clear()
            
            for model in self.available_models:
                name = model.get("name", "Unknown")
                size = self._format_size(model.get("size", 0))
                family = model.get("model_family", "Unknown")
                description = model.get("description", "No description available")
                
                available_table.add_row(name, size, family, description)
            
            self.notify(f"Loaded {len(self.available_models)} available models", severity="information")
            
        except Exception as e:
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
        
        if button_id == "local-tab":
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
        elif button_id in ["pull-button", "pull-available-button"]:
            # Start model pull
            self._pull_selected_model()
        elif button_id == "delete-button":
            # Delete selected model
            self._delete_selected_model()
        elif button_id in ["details-button", "details-available-button"]:
            # Show model details
            self._show_model_details()
    
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
        local_container = self.query_one("#local-models", Container)
        available_container = self.query_one("#available-models", Container)
        
        if tab == "local":
            local_container.add_class("active")
            available_container.remove_class("active")
        else:
            local_container.remove_class("active")
            available_container.add_class("active")
    
    async def _pull_selected_model(self) -> None:
        """Pull the selected model from Ollama registry"""
        # Get selected model based on current tab
        model_id = self._get_selected_model_id()
        
        if not model_id:
            self.notify("No model selected", severity="warning")
            return
        
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
                await self.app.sleep(3)
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
            self.notify("No model selected", severity="warning")
            return
        
        # Get model details container
        details_container = self.query_one("#model-details")
        details_content = self.query_one("#details-content", Static)
        
        try:
            # Get model details from Ollama
            details = await self.ollama_client.get_model_details(model_id)
            
            # Format details
            formatted_details = f"Model: {model_id}\n"
            formatted_details += f"Size: {self._format_size(details.get('size', 0))}\n"
            
            if "modelfile" in details:
                modelfile = details["modelfile"]
                formatted_details += f"Family: {modelfile.get('parameter_size', 'Unknown')}\n"
                formatted_details += f"Template: {modelfile.get('template', 'Unknown')}\n"
                formatted_details += f"License: {modelfile.get('license', 'Unknown')}\n"
                
                if "system" in modelfile:
                    formatted_details += f"\nSystem Prompt:\n{modelfile['system']}\n"
            
            # Update and show details
            details_content.update(formatted_details)
            details_container.add_class("visible")
            
        except Exception as e:
            self.notify(f"Error getting model details: {str(e)}", severity="error")
            details_content.update(f"Error loading details: {str(e)}")
            details_container.add_class("visible")
    
    def _get_selected_model_id(self) -> str:
        """Get the ID of the currently selected model"""
        if self.current_tab == "local":
            table = self.query_one("#local-models-table", DataTable)
            if table.cursor_row is not None:
                row = table.get_row_at(table.cursor_row)
                # Get model ID from local models list
                for model in self.local_models:
                    if model["name"] == row[0]:
                        return model["id"]
        else:
            table = self.query_one("#available-models-table", DataTable)
            if table.cursor_row is not None:
                row = table.get_row_at(table.cursor_row)
                # Return the model name as ID
                return row[0]
        
        return ""
    
    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in data tables"""
        # Set selected model ID based on the selected row
        if event.data_table.id == "local-models-table":
            row = event.data_table.get_row_at(event.cursor_row)
            # Find the model ID from the display name
            for model in self.local_models:
                if model["name"] == row[0]:
                    self.selected_model_id = model["id"]
                    break
        elif event.data_table.id == "available-models-table":
            row = event.data_table.get_row_at(event.cursor_row)
            self.selected_model_id = row[0]  # Model name is used as ID
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission (Enter key in search input)"""
        if event.input.id == "model-search":
            # Trigger search
            if self.current_tab == "local":
                self.app.call_later(self.load_local_models)
            else:
                self.app.call_later(self.load_available_models)