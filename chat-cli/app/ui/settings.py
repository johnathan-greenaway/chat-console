"""Settings UI for configuring API providers and other preferences"""

import logging
from typing import Dict, Any, Optional
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import Label, Input, Button, Switch, Select, Static
from textual.screen import ModalScreen
from textual.message import Message
import asyncio
import json
from pathlib import Path

from ..config import CONFIG, CONFIG_PATH, save_config, CUSTOM_PROVIDERS
from ..api.custom_openai import CustomOpenAIClient

logger = logging.getLogger(__name__)

class SettingsScreen(ModalScreen):
    """Modal settings screen for configuring the application"""
    
    CSS = """
    SettingsScreen {
        align: center middle;
    }
    
    #settings-container {
        width: 80;
        height: 40;
        background: $surface;
        border: solid $primary;
        padding: 1;
    }
    
    #settings-title {
        text-align: center;
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }
    
    .settings-section {
        margin-bottom: 2;
        padding: 1;
        border: solid $surface-lighten-1;
    }
    
    .section-title {
        text-style: bold;
        color: $secondary;
        margin-bottom: 1;
    }
    
    .settings-row {
        layout: horizontal;
        height: 3;
        margin-bottom: 1;
    }
    
    .settings-label {
        width: 30%;
        content-align: left middle;
    }
    
    .settings-input {
        width: 70%;
    }
    
    .settings-switch {
        width: auto;
    }
    
    #button-container {
        layout: horizontal;
        height: 3;
        align: center middle;
        margin-top: 2;
    }
    
    #save-button {
        margin-right: 2;
    }
    
    #test-button {
        margin-right: 2;
    }
    
    #status-message {
        text-align: center;
        margin-top: 1;
        height: 2;
    }
    
    .success {
        color: $success;
    }
    
    .error {
        color: $error;
    }
    
    .info {
        color: $primary;
    }
    """
    
    class SettingsUpdated(Message):
        """Message sent when settings are saved"""
        def __init__(self, settings: Dict[str, Any]):
            self.settings = settings
            super().__init__()
    
    def compose(self) -> ComposeResult:
        """Compose the settings UI"""
        with Container(id="settings-container"):
            yield Label("⚙️  Settings", id="settings-title")
            
            with ScrollableContainer():
                # Custom API Provider Section
                with Container(classes="settings-section"):
                    yield Label("🔌 Custom API Provider", classes="section-title")
                    
                    # Enable/Disable switch
                    with Horizontal(classes="settings-row"):
                        yield Label("Enable Custom API:", classes="settings-label")
                        yield Switch(
                            value=CONFIG.get("custom_api_enabled", True),
                            id="custom-api-enabled",
                            classes="settings-switch"
                        )
                    
                    # API Base URL
                    with Horizontal(classes="settings-row"):
                        yield Label("API Base URL:", classes="settings-label")
                        yield Input(
                            value=CONFIG.get("custom_api_base_url", CUSTOM_PROVIDERS.get("openai-compatible", {}).get("base_url", "")),
                            placeholder="https://api.example.com/v1",
                            id="custom-api-url",
                            classes="settings-input"
                        )
                    
                    # API Key
                    with Horizontal(classes="settings-row"):
                        yield Label("API Key:", classes="settings-label")
                        yield Input(
                            value=CONFIG.get("custom_api_key", CUSTOM_PROVIDERS.get("openai-compatible", {}).get("api_key", "")),
                            placeholder="your-api-key-here",
                            password=True,
                            id="custom-api-key",
                            classes="settings-input"
                        )
                    
                    # Display Name
                    with Horizontal(classes="settings-row"):
                        yield Label("Display Name:", classes="settings-label")
                        yield Input(
                            value=CONFIG.get("custom_api_display_name", "Custom API"),
                            placeholder="Custom API",
                            id="custom-api-display-name",
                            classes="settings-input"
                        )
                
                # Other Settings Section
                with Container(classes="settings-section"):
                    yield Label("🎨 Display Settings", classes="section-title")
                    
                    # Dynamic Titles
                    with Horizontal(classes="settings-row"):
                        yield Label("Generate Dynamic Titles:", classes="settings-label")
                        yield Switch(
                            value=CONFIG.get("generate_dynamic_titles", True),
                            id="dynamic-titles",
                            classes="settings-switch"
                        )
                    
                    # Code Highlighting
                    with Horizontal(classes="settings-row"):
                        yield Label("Highlight Code:", classes="settings-label")
                        yield Switch(
                            value=CONFIG.get("highlight_code", True),
                            id="highlight-code",
                            classes="settings-switch"
                        )
                    
                    # Max History Items
                    with Horizontal(classes="settings-row"):
                        yield Label("Max History Items:", classes="settings-label")
                        yield Input(
                            value=str(CONFIG.get("max_history_items", 100)),
                            placeholder="100",
                            id="max-history",
                            classes="settings-input"
                        )
            
            # Buttons
            with Horizontal(id="button-container"):
                yield Button("Test Connection", variant="primary", id="test-button")
                yield Button("Save", variant="success", id="save-button")
                yield Button("Cancel", variant="default", id="cancel-button")
            
            # Status message
            yield Static("", id="status-message")
    
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        if event.button.id == "cancel-button":
            self.dismiss()
        elif event.button.id == "save-button":
            await self.save_settings()
        elif event.button.id == "test-button":
            await self.test_connection()
    
    async def test_connection(self) -> None:
        """Test the custom API connection"""
        status = self.query_one("#status-message", Static)
        status.update("🔄 Testing connection...")
        status.add_class("info")
        status.remove_class("success", "error")
        
        # Get current form values
        enabled = self.query_one("#custom-api-enabled", Switch).value
        base_url = self.query_one("#custom-api-url", Input).value
        api_key = self.query_one("#custom-api-key", Input).value
        
        if not enabled:
            status.update("ℹ️ Custom API is disabled")
            return
        
        if not base_url or not api_key:
            status.update("❌ Please provide both URL and API key")
            status.remove_class("info", "success")
            status.add_class("error")
            return
        
        try:
            # Create a temporary client with the test settings
            import os
            # Temporarily set the environment variables
            old_url = os.environ.get("CUSTOM_API_BASE_URL")
            old_key = os.environ.get("CUSTOM_API_KEY")
            
            os.environ["CUSTOM_API_BASE_URL"] = base_url
            os.environ["CUSTOM_API_KEY"] = api_key
            
            # Update CUSTOM_PROVIDERS temporarily
            old_provider = CUSTOM_PROVIDERS.get("openai-compatible", {}).copy()
            CUSTOM_PROVIDERS["openai-compatible"] = {
                "base_url": base_url,
                "api_key": api_key,
                "type": "openai_compatible",
                "display_name": self.query_one("#custom-api-display-name", Input).value or "Custom API"
            }
            
            # Test the connection
            client = await CustomOpenAIClient.create("openai-compatible")
            models = await client.list_models()
            
            # Restore old values
            if old_url is not None:
                os.environ["CUSTOM_API_BASE_URL"] = old_url
            elif "CUSTOM_API_BASE_URL" in os.environ:
                del os.environ["CUSTOM_API_BASE_URL"]
                
            if old_key is not None:
                os.environ["CUSTOM_API_KEY"] = old_key
            elif "CUSTOM_API_KEY" in os.environ:
                del os.environ["CUSTOM_API_KEY"]
                
            CUSTOM_PROVIDERS["openai-compatible"] = old_provider
            
            status.update(f"✅ Connected! Found {len(models)} models")
            status.remove_class("info", "error")
            status.add_class("success")
            
        except Exception as e:
            # Restore old values on error
            if 'old_url' in locals():
                if old_url is not None:
                    os.environ["CUSTOM_API_BASE_URL"] = old_url
                elif "CUSTOM_API_BASE_URL" in os.environ:
                    del os.environ["CUSTOM_API_BASE_URL"]
                    
            if 'old_key' in locals():
                if old_key is not None:
                    os.environ["CUSTOM_API_KEY"] = old_key
                elif "CUSTOM_API_KEY" in os.environ:
                    del os.environ["CUSTOM_API_KEY"]
                    
            if 'old_provider' in locals():
                CUSTOM_PROVIDERS["openai-compatible"] = old_provider
            
            status.update(f"❌ Connection failed: {str(e)[:50]}")
            status.remove_class("info", "success")
            status.add_class("error")
    
    async def save_settings(self) -> None:
        """Save the settings to config"""
        status = self.query_one("#status-message", Static)
        
        try:
            # Get all form values
            custom_api_enabled = self.query_one("#custom-api-enabled", Switch).value
            custom_api_url = self.query_one("#custom-api-url", Input).value
            custom_api_key = self.query_one("#custom-api-key", Input).value
            custom_api_display_name = self.query_one("#custom-api-display-name", Input).value
            
            dynamic_titles = self.query_one("#dynamic-titles", Switch).value
            highlight_code = self.query_one("#highlight-code", Switch).value
            max_history = self.query_one("#max-history", Input).value
            
            # Update CONFIG
            CONFIG["custom_api_enabled"] = custom_api_enabled
            CONFIG["custom_api_base_url"] = custom_api_url
            CONFIG["custom_api_key"] = custom_api_key
            CONFIG["custom_api_display_name"] = custom_api_display_name or "Custom API"
            
            CONFIG["generate_dynamic_titles"] = dynamic_titles
            CONFIG["highlight_code"] = highlight_code
            try:
                CONFIG["max_history_items"] = int(max_history)
            except ValueError:
                CONFIG["max_history_items"] = 100
            
            # Update CUSTOM_PROVIDERS
            if custom_api_enabled and custom_api_url and custom_api_key:
                CUSTOM_PROVIDERS["openai-compatible"] = {
                    "base_url": custom_api_url,
                    "api_key": custom_api_key,
                    "type": "openai_compatible",
                    "display_name": custom_api_display_name or "Custom API"
                }
                
                # Update environment variables for immediate effect
                import os
                os.environ["CUSTOM_API_BASE_URL"] = custom_api_url
                os.environ["CUSTOM_API_KEY"] = custom_api_key
            
            # Save to disk
            save_config(CONFIG)
            
            status.update("✅ Settings saved successfully!")
            status.remove_class("info", "error")
            status.add_class("success")
            
            # Post message to update the app
            self.post_message(self.SettingsUpdated(CONFIG))
            
            # Dismiss after a short delay
            await asyncio.sleep(1.5)
            self.dismiss()
            
        except Exception as e:
            status.update(f"❌ Error saving settings: {str(e)}")
            status.remove_class("info", "success")
            status.add_class("error")
            logger.error(f"Error saving settings: {e}")