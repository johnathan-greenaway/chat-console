from typing import List, Dict, Any, Optional, Callable
import time

from textual.app import ComposeResult
from textual.containers import Container, ScrollableContainer
from textual.reactive import reactive
from textual.widgets import Button, Input, Label, Static
from textual.widget import Widget
from textual.message import Message
from textual.timer import Timer

from ..models import Conversation
from ..database import ChatDatabase
from ..config import CONFIG

class SearchResult(Static):
    """Widget to display a single search result"""
    
    DEFAULT_CSS = """
    SearchResult {
        width: 100%;
        height: auto;
        min-height: 3;
        padding: 1;
        border-bottom: solid $primary-darken-3;
    }
    
    SearchResult:hover {
        background: $primary-darken-2;
    }
    
    .result-title {
        width: 100%;
        content-align: center middle;
        text-align: left;
        text-style: bold;
    }
    
    .result-preview {
        width: 100%;
        color: $text-muted;
        margin-top: 1;
        text-align: left;
    }
    
    .result-date {
        width: 100%;
        color: $text-muted;
        text-align: right;
        text-style: italic;
    }
    """
    
    class ResultSelected(Message):
        """Event sent when a search result is selected"""
        def __init__(self, conversation_id: int):
            self.conversation_id = conversation_id
            super().__init__()
    
    def __init__(
        self, 
        conversation: Conversation,
        name: Optional[str] = None
    ):
        super().__init__(name=name)
        self.conversation = conversation
        
    def compose(self) -> ComposeResult:
        """Set up the search result"""
        yield Label(self.conversation.title, classes="result-title")
        
        # Preview text (truncate if too long)
        preview = getattr(self.conversation, 'preview', '')
        if preview and len(preview) > 100:
            preview = preview[:100] + "..."
        
        yield Label(preview, classes="result-preview")
        
        # Format date
        updated_at = self.conversation.updated_at
        if updated_at:
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(updated_at)
                formatted_date = dt.strftime("%Y-%m-%d %H:%M")
            except:
                formatted_date = updated_at
        else:
            formatted_date = "Unknown"
            
        yield Label(formatted_date, classes="result-date")
        
    def on_click(self) -> None:
        """Handle click events"""
        self.post_message(self.ResultSelected(self.conversation.id))

class SearchBar(Container):
    """Widget for searching conversations"""
    
    DEFAULT_CSS = """
    SearchBar {
        width: 100%;
        height: auto;
        padding: 1;
        background: $surface-darken-1;
    }
    
    #search-input {
        width: 100%;
        height: 3;
        margin-bottom: 1;
    }
    
    #search-results-container {
        width: 100%;
        height: auto;
        max-height: 15;
        background: $surface;
        display: none;
    }
    
    #search-results-count {
        width: 100%;
        height: 2;
        background: $primary-darken-1;
        color: $text;
        content-align: center middle;
        text-align: center;
    }
    
    #loading-indicator {
        width: 100%;
        height: 1;
        background: $primary-darken-1;
        color: $text;
        display: none;
    }
    
    #no-results {
        width: 100%;
        height: 3;
        color: $text-muted;
        content-align: center middle;
        text-align: center;
        display: none;
    }
    """
    
    is_searching = reactive(False)
    search_results = reactive([])
    search_timer: Optional[Timer] = None
    
    class SearchResultSelected(Message):
        """Event sent when a search result is selected"""
        def __init__(self, conversation_id: int):
            self.conversation_id = conversation_id
            super().__init__()
    
    def __init__(
        self,
        db: ChatDatabase,
        name: Optional[str] = None,
        id: Optional[str] = None
    ):
        super().__init__(name=name, id=id)
        self.db = db
        
    def compose(self) -> ComposeResult:
        """Set up the search bar"""
        yield Input(placeholder="Search conversations...", id="search-input")
        
        with Container(id="loading-indicator"):
            yield Label("Searching...", id="loading-text")
            
        with Container(id="search-results-container"):
            yield Label("Search Results", id="search-results-count")
            
            with ScrollableContainer(id="results-scroll"):
                yield Label("No results found.", id="no-results")
        
    def on_unmount(self) -> None:
        """Clean up when unmounting"""
        if self.search_timer:
            self.search_timer.stop()
            self.search_timer = None

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input changes"""
        if event.input.id == "search-input":
            query = event.value.strip()
            
            # Cancel existing timer if any
            if self.search_timer:
                self.search_timer.stop()
                self.search_timer = None
                
            if not query:
                # Hide results when search is cleared
                self.clear_results()
                try:
                    results_container = self.query_one("#search-results-container")
                    if results_container:
                        results_container.display = False
                except Exception:
                    pass
                # Return focus to chat input
                self._return_focus_to_chat()
                return
                
            # Start a new timer (debounce)
            try:
                self.search_timer = self.set_timer(0.3, self.perform_search, query)
            except Exception:
                # If timer creation fails, perform search immediately
                self.perform_search(query)
                
    def _return_focus_to_chat(self) -> None:
        """Helper to return focus to chat input"""
        try:
            from .chat_interface import ChatInterface
            chat_interface = self.app.query_one("#chat-interface", expect_type=ChatInterface)
            if chat_interface:
                input_field = chat_interface.query_one("#message-input")
                if input_field:
                    self.app.set_focus(input_field)
        except Exception:
            pass
            
    def perform_search(self, query: str) -> None:
        """Perform the search after debounce"""
        if not self.is_mounted:
            return
            
        self.is_searching = True
        
        try:
            search_results = self.db.search_conversations(query)
            self.search_results = [Conversation.from_dict(c) for c in search_results]
            
            if self.is_mounted:  # Check if still mounted before updating UI
                try:
                    results_container = self.query_one("#search-results-container")
                    if results_container:
                        results_container.display = True
                    self._update_results_ui()
                except Exception:
                    pass
        except Exception:
            # Handle search errors gracefully
            self.search_results = []
            if self.is_mounted:
                try:
                    self._update_results_ui()
                except Exception:
                    pass
        finally:
            self.is_searching = False
            if self.search_timer:
                self.search_timer.stop()
                self.search_timer = None
            
    def _update_results_ui(self) -> None:
        """Update the UI with current search results"""
        results_count = self.query_one("#search-results-count")
        results_count.update(f"Found {len(self.search_results)} results")
        
        scroll_container = self.query_one("#results-scroll")
        
        # Clear previous results
        for child in scroll_container.children:
            if not child.id == "no-results":
                child.remove()
                
        no_results = self.query_one("#no-results")
                
        if not self.search_results:
            no_results.display = True
            return
        else:
            no_results.display = False
            
        # Mount results directly without using batch_update
        for result in self.search_results:
            scroll_container.mount(SearchResult(result))
                
    def on_search_result_result_selected(self, event: SearchResult.ResultSelected) -> None:
        """Handle search result selection"""
        self.post_message(self.SearchResultSelected(event.conversation_id))
        
        # Clear search and hide results
        input_widget = self.query_one("#search-input", Input)
        input_widget.value = ""
        
        results_container = self.query_one("#search-results-container")
        results_container.display = False
        
        # Return focus to chat input
        self._return_focus_to_chat()
        
    def clear_results(self) -> None:
        """Clear search results"""
        self.search_results = []
        self._update_results_ui()
        
    def watch_is_searching(self, is_searching: bool) -> None:
        """Watch the is_searching property"""
        loading = self.query_one("#loading-indicator")
        loading.display = True if is_searching else False
