#!/usr/bin/env python3
"""
Pure Console Chat Interface - No Textual Dependencies
A true terminal interface following Dieter Rams principles
"""

# Pre-import logging suppression to prevent any output during imports
import logging
logging.getLogger().setLevel(logging.CRITICAL)
logging.basicConfig(level=logging.CRITICAL, handlers=[logging.NullHandler()])

import os
import sys
import asyncio
import signal
import time
from datetime import datetime
from typing import List, Optional, Dict
import shutil

from .models import Message, Conversation
from .database import ChatDatabase
from .config import CONFIG, save_config, update_last_used_model, check_provider_availability, OLLAMA_BASE_URL
from .config import OPENAI_API_KEY, ANTHROPIC_API_KEY, CUSTOM_PROVIDERS
from .utils import resolve_model_id, generate_conversation_title
from .console_utils import console_streaming_response, apply_style_prefix
from .api.base import BaseModelClient
from .model_manager import model_manager

class ConsoleUI:
    """Pure console UI following Rams design principles with Gemini-inspired enhancements"""
    
    def __init__(self):
        self._update_terminal_size()
        self.db = ChatDatabase()
        self.current_conversation: Optional[Conversation] = None
        self.messages: List[Message] = []
        self.selected_model = resolve_model_id(CONFIG["default_model"])
        self.selected_style = CONFIG["default_style"]
        # Update last used model on startup
        update_last_used_model(self.selected_model)
        self.running = True
        self._exit_to_chat = False
        self.generating = False
        self.input_mode = "text"  # "text" or "menu"
        self.multi_line_input = []
        self.input_history = []
        self.history_index = 0
        self.theme = self._load_theme()
        self.loading_phrases = [
            "Thinking deeply", "Crafting response", "Processing context",
            "Analyzing request", "Generating ideas", "Considering options",
            "Formulating answer", "Connecting concepts", "Refining thoughts"
        ]
        self.loading_phase_index = 0
        self.start_time = time.time()
        
        # Scrolling support
        self.scroll_offset = 0  # How many messages to skip from the bottom
        self.messages_per_page = 10  # Default messages per page
        self.scroll_mode = False  # Whether we're in scroll mode
        
        # Message rendering cache and state
        self.formatted_messages_cache = []  # Cache of formatted message lines
        self.message_buffer = []  # Current visible message lines
        self.last_message_count = 0  # Track when to refresh cache
        self.screen_regions = {
            'header': [],
            'messages': [],
            'input': [],
            'footer': []
        }
        
        # Suppress verbose logging for console mode
        self._setup_console_logging()
        
        # Resize handling
        self._resize_flag = False
        self._setup_resize_handler()
    
    def _load_theme(self) -> Dict[str, str]:
        """Load color theme configuration"""
        try:
            # Try to import colorama for colors
            from colorama import Fore, Style, init
            init(autoreset=True)
            
            # Default theme inspired by gemini-code-assist
            return {
                'primary': Fore.CYAN,
                'secondary': Fore.BLUE,
                'accent': Fore.MAGENTA,
                'success': Fore.GREEN,
                'warning': Fore.YELLOW,
                'error': Fore.RED,
                'muted': Fore.LIGHTBLACK_EX,
                'text': Fore.WHITE,
                'reset': Style.RESET_ALL,
                'bold': Style.BRIGHT,
                'dim': Style.DIM
            }
        except ImportError:
            # Fallback to no colors if colorama not available
            return {key: '' for key in [
                'primary', 'secondary', 'accent', 'success', 'warning', 
                'error', 'muted', 'text', 'reset', 'bold', 'dim'
            ]}
    
    def _update_terminal_size(self):
        """Update terminal dimensions with responsive bounds checking"""
        size = shutil.get_terminal_size()
        # More forgiving minimum width for better mobile/narrow terminal support
        self.width = min(max(size.columns, 20), 200)  # Minimum 20, cap at 200 for readability
        self.height = max(size.lines, 8)  # Minimum 8 lines for basic functionality
        
        # Define responsive breakpoints
        self.is_minimal = self.width < 30  # Very narrow - minimal mode
        self.is_narrow = 30 <= self.width < 50  # Narrow but functional
        self.is_medium = 50 <= self.width < 80  # Medium sized
        self.is_wide = self.width >= 80  # Full featured
    
    def responsive_text_wrap(self, text: str, max_width: int = None) -> List[str]:
        """Wrap text responsively based on terminal width"""
        if max_width is None:
            max_width = max(10, self.width - 4)  # Leave room for borders
        
        # Handle empty or very short text
        if not text or len(text) <= max_width:
            return [text]
        
        # Simple word wrapping that respects word boundaries
        words = text.split()
        lines = []
        current_line = ""
        
        for word in words:
            # If single word is longer than max_width, break it
            if len(word) > max_width:
                if current_line:
                    lines.append(current_line.strip())
                    current_line = ""
                # Break long word
                while word:
                    lines.append(word[:max_width])
                    word = word[max_width:]
                continue
            
            # Check if adding word would exceed width
            test_line = current_line + (" " if current_line else "") + word
            if len(test_line) <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line.strip())
                current_line = word
        
        if current_line:
            lines.append(current_line.strip())
        
        return lines if lines else [""]
    
    def responsive_center(self, text: str, width: int = None) -> str:
        """Center text responsively, truncating if too long"""
        if width is None:
            width = self.width
        
        # Remove ANSI color codes for length calculation
        clean_text = re.sub(r'\x1b\[[0-9;]*m', '', text)
        
        if len(clean_text) > width - 2:
            # Truncate and add ellipsis
            available = max(3, width - 5)  # Leave room for "..."
            clean_truncated = clean_text[:available] + "..."
            # Reapply colors if they existed (simplified approach)
            if len(text) > len(clean_text):
                return f"{self.theme.get('primary', '')}{clean_truncated}{self.theme.get('reset', '')}"
            return clean_truncated
        
        return text.center(width)
    
    def _setup_resize_handler(self):
        """Setup terminal resize signal handler"""
        if hasattr(signal, 'SIGWINCH'):
            signal.signal(signal.SIGWINCH, self._handle_resize)
    
    def _handle_resize(self, signum=None, frame=None):
        """Handle terminal resize signal"""
        self._resize_flag = True
        self._update_terminal_size()
    
    def _setup_console_logging(self):
        """Completely disable all logging and debug output"""
        import sys
        import os
        
        # Completely disable logging system
        logging.disable(logging.CRITICAL)
        
        # Clear all existing handlers and disable root logger
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        root_logger.disabled = True
        
        # Redirect stderr to devnull to suppress any remaining debug output
        try:
            devnull_fd = os.open(os.devnull, os.O_WRONLY)
            os.dup2(devnull_fd, 2)  # Redirect stderr (fd 2) to /dev/null
            os.close(devnull_fd)
        except (OSError, IOError):
            pass  # If redirection fails, continue anyway
        
        # Disable all known loggers completely
        noisy_loggers = [
            'app', 'app.api', 'app.api.base', 'app.api.ollama', 'app.api.openai',
            'app.api.anthropic', 'app.utils', 'app.console_utils', 'aiohttp', 'urllib3', 
            'httpx', 'asyncio', 'root', 'httpcore', 'httpx._client', 'hpack', 'h11'
        ]
        
        for logger_name in noisy_loggers:
            logger = logging.getLogger(logger_name)
            logger.disabled = True
            logger.handlers.clear()
            logger.propagate = False
        
    def _suppress_output(self):
        """Context manager to suppress all output during sensitive operations"""
        import contextlib
        
        @contextlib.contextmanager
        def suppress():
            with open(os.devnull, "w") as devnull:
                old_stdout = sys.stdout
                old_stderr = sys.stderr
                try:
                    sys.stdout = devnull
                    sys.stderr = devnull
                    yield
                finally:
                    sys.stdout = old_stdout
                    sys.stderr = old_stderr
        
        return suppress()
        
    def clear_screen(self):
        """Clear the terminal screen using ANSI escape sequences for smoother operation"""
        # Use ANSI escape sequences instead of os.system for smoother clearing
        # This prevents the bouncing/scrolling effect on Windows terminals
        if os.name == 'nt':
            # Windows-specific: Use more compatible ANSI sequences
            print('\033[2J\033[1;1H', end='', flush=True)
        else:
            print('\033[2J\033[H', end='', flush=True)
    
    def soft_clear(self):
        """Soft clear that just moves cursor to top without full screen clear"""
        # Move cursor to top-left without clearing (reduces flicker)
        if os.name == 'nt':
            # Windows-specific positioning
            print('\033[1;1H', end='', flush=True)
        else:
            print('\033[H', end='', flush=True)
    
    def _rebuild_message_cache(self):
        """Rebuild the formatted message cache when messages change"""
        # Always rebuild during streaming to show updated content
        if not self.generating and len(self.messages) == self.last_message_count:
            return  # No change needed when not streaming
            
        self.formatted_messages_cache = []
        
        for i, message in enumerate(self.messages):
            is_streaming = (i == len(self.messages) - 1 and 
                          message.role == "assistant" and 
                          self.generating and 
                          self.scroll_offset == 0)
            formatted_lines = self.format_message(message, streaming=is_streaming)
            self.formatted_messages_cache.extend(formatted_lines)
            
        self.last_message_count = len(self.messages)
    
    def _update_message_buffer(self):
        """Update the message buffer based on current scroll state"""
        self._rebuild_message_cache()
        
        total_lines = len(self.formatted_messages_cache)
        if total_lines == 0:
            self.message_buffer = self._get_empty_state_messages()
            return
            
        # Calculate available space for messages
        header_lines = len(self.screen_regions['header'])
        footer_lines = len(self.screen_regions['footer']) 
        input_lines = len(self.screen_regions['input'])
        used_lines = header_lines + footer_lines + input_lines
        available_lines = self.height - used_lines - 2
        
        # Calculate scroll position in terms of lines, not messages
        if self.scroll_offset == 0:
            # Show most recent lines
            start_line = max(0, total_lines - available_lines)
            end_line = total_lines
        else:
            # Convert message offset to line offset
            # This is approximate - we'll improve this later
            lines_per_message = max(1, total_lines // max(1, len(self.messages)))
            line_offset = self.scroll_offset * lines_per_message
            end_line = max(available_lines, total_lines - line_offset)
            start_line = max(0, end_line - available_lines)
            
        self.message_buffer = self.formatted_messages_cache[start_line:end_line]
        
        # Add scroll indicators if needed
        if self.scroll_mode or self.scroll_offset > 0:
            self._add_scroll_indicators()
    
    def _get_empty_state_messages(self):
        """Get the empty state welcome messages"""
        chars = self.get_border_chars()
        lines = []
        
        # Enhanced empty state with tips
        empty_line = chars['vertical'] + " " * (self.width - 2) + chars['vertical']
        lines.extend([empty_line] * 2)
        
        # Welcome message with colors
        welcome_text = f"{self.theme['primary']}✨ Start a conversation by typing a message below ✨{self.theme['reset']}"
        clean_welcome = " Start a conversation by typing a message below "
        color_padding = len(welcome_text) - len(clean_welcome)
        centered_line = chars['vertical'] + welcome_text.center(self.width - 2 + color_padding) + chars['vertical']
        lines.append(centered_line)
        
        lines.append(empty_line)
        
        # Tips with colors
        tips = [
            f"{self.theme['muted']}• Use {self.theme['accent']}Shift+Enter{self.theme['muted']} for multi-line input{self.theme['reset']}",
            f"{self.theme['muted']}• Press {self.theme['accent']}Tab{self.theme['muted']} to access menu mode{self.theme['reset']}",
            f"{self.theme['muted']}• Use {self.theme['accent']}Ctrl+B{self.theme['muted']} to enable scrolling{self.theme['reset']}"
        ]
        
        for tip in tips:
            clean_tip = tip.replace(self.theme['muted'], '').replace(self.theme['accent'], '').replace(self.theme['reset'], '')
            color_padding = len(tip) - len(clean_tip)
            tip_line = chars['vertical'] + f" {tip}".ljust(self.width - 2 + color_padding) + chars['vertical']
            lines.append(tip_line)
        
        lines.extend([empty_line] * 2)
        return lines
    
    def _add_scroll_indicators(self):
        """Add scroll indicators to the message buffer"""
        if not (self.scroll_mode or self.scroll_offset > 0):
            return
            
        chars = self.get_border_chars()
        empty_line = chars['vertical'] + " " * (self.width - 2) + chars['vertical']
        
        indicators = []
        
        # Top indicator - show if we can scroll up (more messages above)
        if self.scroll_offset < len(self.messages) - 1:
            more_above = f"{self.theme['accent']}↑ More messages above (offset: {self.scroll_offset}) ↑{self.theme['reset']}"
            clean_above = f"↑ More messages above (offset: {self.scroll_offset}) ↑"
            color_padding = len(more_above) - len(clean_above)
            above_line = chars['vertical'] + more_above.center(self.width - 2 + color_padding) + chars['vertical']
            indicators.extend([above_line, empty_line])
        
        # Bottom indicator - show if we can scroll down (more messages below)  
        if self.scroll_offset > 0:
            more_below = f"{self.theme['accent']}↓ More messages below (use j or Ctrl+D) ↓{self.theme['reset']}"
            clean_below = f"↓ More messages below (use j or Ctrl+D) ↓"
            color_padding = len(more_below) - len(clean_below)
            below_line = chars['vertical'] + more_below.center(self.width - 2 + color_padding) + chars['vertical']
            indicators.extend([empty_line, below_line])
        
        # Add indicators to message buffer
        if indicators:
            self.message_buffer = indicators + self.message_buffer
    
    def get_border_chars(self):
        """Get clean ASCII border characters"""
        return {
            'horizontal': '─',
            'vertical': '│',
            'top_left': '┌',
            'top_right': '┐',
            'bottom_left': '└',
            'bottom_right': '┘',
            'tee_down': '┬',
            'tee_up': '┴',
            'tee_right': '├',
            'tee_left': '┤'
        }
    
    def draw_border_line(self, width: int, position: str = 'top') -> str:
        """Draw a clean border line"""
        chars = self.get_border_chars()
        
        if position == 'top':
            return chars['top_left'] + chars['horizontal'] * (width - 2) + chars['top_right']
        elif position == 'bottom':
            return chars['bottom_left'] + chars['horizontal'] * (width - 2) + chars['bottom_right']
        elif position == 'middle':
            return chars['tee_right'] + chars['horizontal'] * (width - 2) + chars['tee_left']
        else:
            return chars['horizontal'] * width
    
    def draw_ascii_welcome(self) -> List[str]:
        """Draw beautiful ASCII art welcome inspired by gemini-code-assist"""
        if not hasattr(self, '_welcome_shown'):
            self._welcome_shown = True
            
            from . import __version__
            
            ascii_art = [
                "    ███████╗██╗  ██╗ █████╗ ████████╗      ██████╗ ██████╗ ███╗   ██╗███████╗ ██████╗ ██╗     ███████╗",
                "    ██╔════╝██║  ██║██╔══██╗╚══██╔══╝     ██╔════╝██╔═══██╗████╗  ██║██╔════╝██╔═══██╗██║     ██╔════╝",
                "    ██║     ███████║███████║   ██║        ██║     ██║   ██║██╔██╗ ██║███████╗██║   ██║██║     █████╗  ",
                "    ██║     ██╔══██║██╔══██║   ██║        ██║     ██║   ██║██║╚██╗██║╚════██║██║   ██║██║     ██╔══╝  ",
                "    ╚██████╗██║  ██║██║  ██║   ██║        ╚██████╗╚██████╔╝██║ ╚████║███████║╚██████╔╝███████╗███████╗",
                "     ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝         ╚═════╝ ╚═════╝ ╚═╝  ╚═══╝╚══════╝ ╚═════╝ ╚══════╝╚══════╝"
            ]
            
            # Responsive ASCII art scaling
            if self.is_minimal:  # < 30 columns - ultra minimal
                ascii_art = [
                    "CHAT"
                ]
            elif self.is_narrow:  # 30-50 columns
                ascii_art = [
                    "░▒▓ CHAT ▓▒░"
                ]
            elif self.is_medium:  # 50-80 columns  
                ascii_art = [
                    "  ╔═══╗╦ ╦╔═══╗╔════╗",
                    "  ║   ║║ ║║   ║║    ║",
                    "  ║   ║███║███████║  ║", 
                    "  ║   ║║ ║║   ║║    ║",
                    "  ╚═══╝╩ ╩╩   ╩╚════╝"
                ]
            elif self.width < 100:  # 80-100 columns
                ascii_art = [
                    "  ██████╗██╗  ██╗ █████╗ ████████╗",
                    "  ██╔════╝██║  ██║██╔══██╗╚══██╔══╝",
                    "  ██║     ███████║███████║   ██║   ",
                    "  ██║     ██╔══██║██╔══██║   ██║   ",
                    "  ╚██████╗██║  ██║██║  ██║   ██║   ",
                    "   ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝   "
                ]
            
            welcome_lines = []
            for line in ascii_art:
                colored_line = f"{self.theme['accent']}{line.center(self.width)}{self.theme['reset']}"
                welcome_lines.append(colored_line)
                
            # Add version number subtly
            welcome_lines.append("")
            version_text = f"{self.theme['muted']}v{__version__}{self.theme['reset']}"
            welcome_lines.append(version_text.center(self.width))
            
            # Add welcome message
            welcome_lines.append("")
            welcome_text = f"{self.theme['primary']}✨ Welcome to Chat Console - Pure Terminal AI Experience ✨{self.theme['reset']}"
            welcome_lines.append(welcome_text.center(self.width))
            
            tips_text = f"{self.theme['muted']}Press Tab for menu mode • Shift+Enter for multi-line input{self.theme['reset']}"
            welcome_lines.append(tips_text.center(self.width))
            welcome_lines.append("")
            
            return welcome_lines
        return []
    
    def draw_header(self) -> List[str]:
        """Draw the enhanced application header with colors"""
        from . import __version__
        chars = self.get_border_chars()
        
        lines = []
        
        # Top border with title and model info
        title = f" {self.theme['bold']}Chat Console v{__version__}{self.theme['reset']} "
        
        # Responsive model name display
        if self.is_narrow:
            # Very abbreviated for narrow terminals
            model_display = self.selected_model.split('/')[-1]  # Remove provider prefix
            if len(model_display) > 10:
                model_display = model_display[:7] + "..."
            model_info = f" {self.theme['primary']}{model_display}{self.theme['reset']} "
        elif self.is_medium:
            # Moderate truncation for medium terminals
            max_model_len = max(15, self.width - 30)
            model_display = self.selected_model
            if len(model_display) > max_model_len:
                model_display = model_display[:max_model_len-3] + "..."
            model_info = f" {self.theme['primary']}M: {model_display}{self.theme['reset']} "
        else:
            # Full display for wide terminals
            max_model_len = max(20, self.width - 40)
            model_display = self.selected_model
            if len(model_display) > max_model_len:
                model_display = model_display[:max_model_len-3] + "..."
            model_info = f" {self.theme['primary']}Model: {model_display}{self.theme['reset']} "
        
        # Add scroll indicator if in scroll mode
        if self.scroll_mode or self.scroll_offset > 0:
            scroll_info = f" {self.theme['warning']}[SCROLL MODE]{self.theme['reset']} "
        else:
            scroll_info = ""
        
        # Calculate spacing (account for color codes)
        clean_title = f" Chat Console v{__version__} "
        clean_model = f" Model: {model_display} "
        clean_scroll = " [SCROLL MODE] " if (self.scroll_mode or self.scroll_offset > 0) else ""
        used_space = len(clean_title) + len(clean_model) + len(clean_scroll)
        remaining = self.width - used_space - 2
        spacing = chars['horizontal'] * max(0, remaining)
        
        header_line = chars['top_left'] + title + spacing + scroll_info + model_info + chars['top_right']
        lines.append(header_line)
        
        # Responsive conversation title display
        conv_title = self.current_conversation.title if self.current_conversation else "New Conversation"
        
        if self.is_narrow:
            # Very short titles for narrow terminals
            max_title_len = max(8, self.width - 8)
            if len(conv_title) > max_title_len:
                conv_title = conv_title[:max_title_len-3] + "..."
        elif self.is_medium:
            # Moderate length for medium terminals
            max_title_len = max(15, self.width - 6)
            if len(conv_title) > max_title_len:
                conv_title = conv_title[:max_title_len-3] + "..."
        else:
            # Full length for wide terminals
            max_title_len = max(20, self.width - 4)
            if len(conv_title) > max_title_len:
                conv_title = conv_title[:max_title_len-3] + "..."
        
        colored_title = f" {self.theme['secondary']}{conv_title}{self.theme['reset']} "
        title_line = chars['vertical'] + colored_title.ljust(self.width - 2 + len(self.theme['secondary']) + len(self.theme['reset'])) + chars['vertical']
        lines.append(title_line)
        
        # Separator
        lines.append(self.draw_border_line(self.width, 'middle'))
        
        return lines
    
    def draw_footer(self) -> List[str]:
        """Draw the enhanced footer with colorized controls"""
        chars = self.get_border_chars()
        
        # Show different controls based on mode and terminal width
        if self.scroll_mode or self.scroll_offset > 0:
            # Scroll mode controls - adapt to terminal width
            if self.is_wide:
                controls = (
                    f"{self.theme['muted']}[{self.theme['accent']}j/i{self.theme['muted']}] Line ↓/↑  "
                    f"[{self.theme['accent']}Ctrl+U/D{self.theme['muted']}] Page ↑/↓  "
                    f"[{self.theme['accent']}Ctrl+G{self.theme['muted']}] Top  "
                    f"[{self.theme['accent']}Ctrl+E{self.theme['muted']}] End  "
                    f"[{self.theme['accent']}Esc{self.theme['muted']}] Exit{self.theme['reset']}"
                )
                clean_controls = "[j/i] Line ↓/↑  [Ctrl+U/D] Page ↑/↓  [Ctrl+G] Top  [Ctrl+E] End  [Esc] Exit"
            elif self.is_medium:
                controls = (
                    f"{self.theme['muted']}[{self.theme['accent']}j/i{self.theme['muted']}] ↓/↑  "
                    f"[{self.theme['accent']}U/D{self.theme['muted']}] Page  "
                    f"[{self.theme['accent']}Esc{self.theme['muted']}] Exit{self.theme['reset']}"
                )
                clean_controls = "[j/i] ↓/↑  [U/D] Page  [Esc] Exit"
            elif self.is_narrow:
                controls = (
                    f"{self.theme['muted']}[{self.theme['accent']}j/i{self.theme['muted']}]↓↑ "
                    f"[{self.theme['accent']}Esc{self.theme['muted']}]Exit{self.theme['reset']}"
                )
                clean_controls = "[j/i]↓↑ [Esc]Exit"
            else:  # minimal
                controls = f"{self.theme['muted']}j/i ↓↑{self.theme['reset']}"
                clean_controls = "j/i ↓↑"
        else:
            # Normal controls - adapt to terminal width
            if self.is_wide:
                controls = (
                    f"{self.theme['muted']}[{self.theme['accent']}Tab{self.theme['muted']}] Menu  "
                    f"[{self.theme['accent']}Ctrl+B{self.theme['muted']}] Scroll  "
                    f"[{self.theme['accent']}q{self.theme['muted']}] Quit  "
                    f"[{self.theme['accent']}n{self.theme['muted']}] New  "
                    f"[{self.theme['accent']}h{self.theme['muted']}] History  "
                    f"[{self.theme['accent']}s{self.theme['muted']}] Settings{self.theme['reset']}"
                )
                clean_controls = "[Tab] Menu  [Ctrl+B] Scroll  [q] Quit  [n] New  [h] History  [s] Settings"
            elif self.is_medium:
                controls = (
                    f"{self.theme['muted']}[{self.theme['accent']}Tab{self.theme['muted']}] Menu  "
                    f"[{self.theme['accent']}q{self.theme['muted']}] Quit  "
                    f"[{self.theme['accent']}n{self.theme['muted']}] New  "
                    f"[{self.theme['accent']}h{self.theme['muted']}] History{self.theme['reset']}"
                )
                clean_controls = "[Tab] Menu  [q] Quit  [n] New  [h] History"
            elif self.is_narrow:
                controls = (
                    f"{self.theme['muted']}[{self.theme['accent']}q{self.theme['muted']}]Quit "
                    f"[{self.theme['accent']}n{self.theme['muted']}]New{self.theme['reset']}"
                )
                clean_controls = "[q]Quit [n]New"
            else:  # minimal
                controls = f"{self.theme['muted']}q=quit{self.theme['reset']}"
                clean_controls = "q=quit"
        
        # Calculate clean length for padding
        color_padding = len(controls) - len(clean_controls)
        footer_line = chars['vertical'] + f" {controls} ".ljust(self.width - 2 + color_padding) + chars['vertical']
        
        return [
            self.draw_border_line(self.width, 'middle'),
            footer_line,
            self.draw_border_line(self.width, 'bottom')
        ]
    
    def _detect_and_highlight_code(self, content: str) -> str:
        """Detect and highlight code blocks in content"""
        if not CONFIG.get("highlight_code", True):
            return content
            
        try:
            # Try to import colorama for terminal colors
            from colorama import Fore, Style, init
            init()  # Initialize colorama
            
            lines = content.split('\n')
            result_lines = []
            in_code_block = False
            
            for line in lines:
                # Detect code block markers
                if line.strip().startswith('```'):
                    in_code_block = not in_code_block
                    if in_code_block:
                        result_lines.append(f"{Fore.CYAN}{line}{Style.RESET_ALL}")
                    else:
                        result_lines.append(f"{Fore.CYAN}{line}{Style.RESET_ALL}")
                elif in_code_block:
                    # Highlight code content
                    result_lines.append(f"{Fore.GREEN}{line}{Style.RESET_ALL}")
                elif '`' in line and line.count('`') >= 2:
                    # Inline code highlighting
                    import re
                    highlighted = re.sub(
                        r'`([^`]+)`', 
                        f'{Fore.GREEN}`\\1`{Style.RESET_ALL}', 
                        line
                    )
                    result_lines.append(highlighted)
                else:
                    result_lines.append(line)
            
            return '\n'.join(result_lines)
            
        except ImportError:
            # Colorama not available, return content as-is
            return content
        except Exception:
            # Any other error, return content as-is
            return content
    
    def _improved_word_wrap(self, text: str, width: int) -> List[str]:
        """Improved word wrapping that preserves code blocks and handles long lines"""
        lines = text.split('\n')
        wrapped_lines = []
        
        for line in lines:
            # Handle very long lines (like URLs or code)
            if len(line) > width:
                # If it looks like code or a URL, don't break it aggressively
                if (line.strip().startswith(('http', 'https', 'www', '  ', '\t')) or 
                    '```' in line or line.count('`') >= 2):
                    # Add as-is but truncate if necessary
                    if len(line) > width:
                        wrapped_lines.append(line[:width-3] + "...")
                    else:
                        wrapped_lines.append(line)
                else:
                    # Normal word wrapping
                    words = line.split()
                    current_line = ""
                    
                    for word in words:
                        if len(current_line) + len(word) + 1 <= width:
                            if current_line:
                                current_line += " "
                            current_line += word
                        else:
                            if current_line:
                                wrapped_lines.append(current_line)
                            current_line = word
                    
                    if current_line:
                        wrapped_lines.append(current_line)
            else:
                # Line fits, add as-is
                wrapped_lines.append(line)
        
        return wrapped_lines or [""]
    
    def format_message(self, message: Message, streaming: bool = False) -> List[str]:
        """Enhanced message formatting with colors, streaming indicators, and better wrapping"""
        timestamp = datetime.now().strftime("%H:%M")
        chars = self.get_border_chars()
        
        # Calculate available width for content with responsive padding
        if self.is_minimal:
            content_width = max(10, self.width - 4)  # Minimal padding for very narrow
        elif self.is_narrow:
            content_width = max(15, self.width - 8)  # Less padding for narrow
        else:
            content_width = self.width - 12  # Full padding for normal width
        
        # Apply code highlighting if enabled
        highlighted_content = self._detect_and_highlight_code(message.content)
        
        # Add streaming cursor if actively streaming
        if streaming and message.content:
            highlighted_content += f"{self.theme['accent']}▎{self.theme['reset']}"
        
        # If no content yet, show placeholder for streaming
        if streaming and not message.content:
            highlighted_content = f"{self.theme['muted']}[Generating response...]{self.theme['reset']}"
        
        # Use improved word wrapping
        lines = self._improved_word_wrap(highlighted_content, content_width)
        
        # Format lines with proper spacing and colors
        formatted_lines = []
        for i, line in enumerate(lines):
            if i == 0:
                # First line with timestamp and role indicator
                if message.role == "user":
                    role_indicator = f"{self.theme['primary']}👤{self.theme['reset']}"
                    role_color = self.theme['primary']
                else:
                    role_indicator = f"{self.theme['success']}🤖{self.theme['reset']}"
                    role_color = self.theme['success']
                    if streaming:
                        # More obvious streaming indicator with blinking effect
                        role_indicator = f"{self.theme['accent']}✨{self.theme['reset']}"
                        role_color = self.theme['accent']
                
                timestamp_colored = f"{self.theme['muted']}{timestamp}{self.theme['reset']}"
                prefix = f" {role_indicator} {timestamp_colored} "
                
                # Apply role color to content
                colored_line = f"{role_color}{line}{self.theme['reset']}"
                
                # Create line and pad to exact width
                content = prefix + colored_line
                # Remove color codes to calculate visual width
                import re
                visual_content = re.sub(r'\x1b\[[0-9;]*m', '', content)
                current_width = len(visual_content)
                padding_needed = self.width - 2 - current_width  # -2 for border chars
                formatted_line = (chars['vertical'] + content + 
                                " " * max(0, padding_needed) + chars['vertical'])
            else:
                # Continuation lines with proper indentation and color
                prefix = "        "  # Align with content
                role_color = self.theme['primary'] if message.role == "user" else self.theme['text']
                colored_line = f"{role_color}{line}{self.theme['reset']}"
                
                # Create line and pad to exact width
                content = prefix + colored_line
                # Remove color codes to calculate visual width
                visual_content = re.sub(r'\x1b\[[0-9;]*m', '', content)
                current_width = len(visual_content)
                padding_needed = self.width - 2 - current_width  # -2 for border chars
                formatted_line = (chars['vertical'] + content + 
                                " " * max(0, padding_needed) + chars['vertical'])
            formatted_lines.append(formatted_line)
        
        # Add empty line for spacing
        empty_line = chars['vertical'] + " " * (self.width - 2) + chars['vertical']
        formatted_lines.append(empty_line)
        
        return formatted_lines
    
    def draw_messages(self) -> List[str]:
        """Draw all messages - now uses the new buffer system"""
        # Use the new message buffer system
        self._update_message_buffer()
        return self.message_buffer.copy()
    
    def draw_input_area(self, current_input: str = "", prompt: str = "Type your message") -> List[str]:
        """Draw the enhanced input area with multi-line support and dynamic indicators"""
        chars = self.get_border_chars()
        lines = []
        
        # Add top border for input area
        lines.append(self.draw_border_line(self.width, 'middle'))
        
        # Input prompt with enhanced mode indicator
        if self.input_mode == "text":
            if len(self.multi_line_input) > 0:
                mode_indicator = f"{self.theme['accent']}📋{self.theme['reset']}"  # Multi-line
                mode_text = f"{self.theme['accent']}MULTI-LINE{self.theme['reset']}"
                extra_hint = f"{self.theme['muted']} (Enter to add line, Ctrl+D to send){self.theme['reset']}"
            else:
                mode_indicator = f"{self.theme['primary']}📝{self.theme['reset']}"  # Single line
                mode_text = f"{self.theme['primary']}TEXT{self.theme['reset']}"
                extra_hint = f"{self.theme['muted']} (Shift+Enter for multi-line){self.theme['reset']}"
        else:
            mode_indicator = f"{self.theme['warning']}⚡{self.theme['reset']}"
            mode_text = f"{self.theme['warning']}MENU{self.theme['reset']}"
            extra_hint = f"{self.theme['muted']} (Tab to switch){self.theme['reset']}"
        
        prompt_with_mode = f"{mode_indicator} {prompt} ({mode_text} mode{extra_hint})"
        # Calculate clean length for padding
        clean_prompt = f" {prompt} (TEXT mode (Tab to switch))"
        color_padding = len(prompt_with_mode) - len(clean_prompt)
        prompt_line = chars['vertical'] + f" {prompt_with_mode}: ".ljust(self.width - 2 + color_padding) + chars['vertical']
        lines.append(prompt_line)
        
        # Multi-line input display
        if self.multi_line_input:
            for i, line in enumerate(self.multi_line_input[-3:]):  # Show last 3 lines
                line_num = f"{self.theme['muted']}{i+1:2d}|{self.theme['reset']}"
                content = line[:self.width-8] if len(line) > self.width-8 else line
                input_line = chars['vertical'] + f" {line_num} {content}".ljust(self.width - 2 + len(line_num) - 4) + chars['vertical']
                lines.append(input_line)
            
            if len(self.multi_line_input) > 3:
                more_lines = chars['vertical'] + f" {self.theme['muted']}... {len(self.multi_line_input)-3} more lines{self.theme['reset']}".ljust(self.width - 2 + 20) + chars['vertical']
                lines.append(more_lines)
        
        # Current input field
        if self.input_mode == "text":
            input_content = current_input
            if len(input_content) > self.width - 6:
                input_content = input_content[-(self.width - 9):] + "..."
            cursor_indicator = f"{self.theme['accent']}▎{self.theme['reset']}"  # Cursor block
            input_line = chars['vertical'] + f" > {input_content}{cursor_indicator}".ljust(self.width - 2 + len(cursor_indicator) - 1) + chars['vertical']
        else:
            # Menu mode - show colorized hotkeys
            menu_help = (
                f"{self.theme['accent']}n{self.theme['muted']})ew  "
                f"{self.theme['accent']}h{self.theme['muted']})istory  "
                f"{self.theme['accent']}s{self.theme['muted']})ettings  "
                f"{self.theme['accent']}m{self.theme['muted']})odels  "
                f"{self.theme['accent']}q{self.theme['muted']})uit{self.theme['reset']}"
            )
            clean_menu = "n)ew  h)istory  s)ettings  m)odels  q)uit"
            color_padding = len(menu_help) - len(clean_menu)
            input_line = chars['vertical'] + f" {menu_help}".ljust(self.width - 2 + color_padding) + chars['vertical']
        
        lines.append(input_line)
        
        # Enhanced generating indicator with cycling phrases
        if self.generating:
            elapsed = int(time.time() - self.start_time)
            current_phrase = self.loading_phrases[self.loading_phase_index % len(self.loading_phrases)]
            
            # Cycle through loading phrases every 2 seconds
            if elapsed % 2 == 0 and elapsed > 0:
                self.loading_phase_index = (self.loading_phase_index + 1) % len(self.loading_phrases)
            
            # Animated dots
            dots = "." * ((elapsed % 3) + 1)
            status_text = f"{self.theme['accent']}✨ {current_phrase}{dots}{self.theme['reset']} {self.theme['muted']}({elapsed}s){self.theme['reset']}"
            clean_status = f" {current_phrase}{dots} ({elapsed}s)"
            color_padding = len(status_text) - len(clean_status)
            status_line = chars['vertical'] + f" {status_text}".ljust(self.width - 2 + color_padding) + chars['vertical']
            lines.append(status_line)
        
        return lines
    
    def _render_regions(self, current_input: str = "", input_prompt: str = "Type your message"):
        """Render all screen regions into buffers"""
        # Update all regions
        self.screen_regions['header'] = self.draw_header()
        self.screen_regions['footer'] = self.draw_footer()
        self.screen_regions['input'] = self.draw_input_area(current_input, input_prompt)
        
        # Update message buffer using the new system
        self._update_message_buffer()
        self.screen_regions['messages'] = self.message_buffer.copy()
        
        # Ensure message area fits available space
        header_lines = len(self.screen_regions['header'])
        footer_lines = len(self.screen_regions['footer'])
        input_lines = len(self.screen_regions['input'])
        used_lines = header_lines + footer_lines + input_lines
        available_lines = self.height - used_lines - 2
        
        # Pad or truncate message area
        chars = self.get_border_chars()
        empty_line = chars['vertical'] + " " * (self.width - 2) + chars['vertical']
        
        if len(self.screen_regions['messages']) < available_lines:
            # Pad with empty lines
            padding_needed = available_lines - len(self.screen_regions['messages'])
            self.screen_regions['messages'].extend([empty_line] * padding_needed)
        else:
            # Truncate to fit
            self.screen_regions['messages'] = self.screen_regions['messages'][:available_lines]
    
    def _update_region(self, region_name: str, new_content: List[str]):
        """Update a specific screen region without full redraw"""
        # Store old content for comparison
        old_content = self.screen_regions.get(region_name, [])
        
        # Update the region
        self.screen_regions[region_name] = new_content.copy()
        
        # For now, we'll still do full redraws but this sets up the structure
        # for targeted updates later
        return old_content != new_content
    
    def draw_screen(self, current_input: str = "", input_prompt: str = "Type your message", show_welcome: bool = False, force_redraw: bool = False):
        """Draw the complete enhanced screen with smart updates"""
        
        # Check for terminal resize
        if self._resize_flag:
            self._resize_flag = False
            self._update_terminal_size()
            force_redraw = True
        
        # Show welcome message on first run
        if show_welcome:
            self.clear_screen()
            welcome_lines = self.draw_ascii_welcome()
            for line in welcome_lines:
                print(line)
            print("\n" * 2)
            time.sleep(2.5)  # Pause to let user see welcome screen properly
            # After welcome, force a full redraw
            force_redraw = True
        
        # Render all regions
        self._render_regions(current_input, input_prompt)
        
        # Smart clearing strategy to reduce bouncing on Windows
        if force_redraw or not hasattr(self, '_screen_initialized'):
            if show_welcome or not hasattr(self, '_screen_initialized'):
                # Only do full clear for welcome screen or initial setup
                self.clear_screen()
            else:
                # Use soft clear for regular updates to reduce flicker
                self.soft_clear()
            self._screen_initialized = True
        
        # Draw all regions with seamless borders
        # Draw header (includes bottom separator)
        for line in self.screen_regions['header']:
            print(line)
        
        # Draw messages
        for line in self.screen_regions['messages']:
            print(line)
        
        # Draw input
        for line in self.screen_regions['input']:
            print(line)
        
        # Draw footer (includes top and bottom borders)
        for line in self.screen_regions['footer']:
            print(line)
        
        # Simple output flush without cursor positioning to avoid duplication
        sys.stdout.flush()
    
    def _suppress_all_output(self):
        """Temporarily suppress all stdout/stderr to prevent interference"""
        import sys
        import os
        
        class DevNull:
            def write(self, _): pass
            def flush(self): pass
        
        self._old_stdout = sys.stdout
        self._old_stderr = sys.stderr
        devnull = DevNull()
        sys.stdout = devnull
        sys.stderr = devnull
    
    def _restore_output(self):
        """Restore stdout/stderr"""
        import sys
        if hasattr(self, '_old_stdout'):
            sys.stdout = self._old_stdout
        if hasattr(self, '_old_stderr'):
            sys.stderr = self._old_stderr

    def update_messages_only(self):
        """Update messages during scroll - use full redraw to avoid issues"""
        # Just use the regular draw_screen method but force a redraw
        # This is the safest approach to avoid any stray output
        pass  # This method will be replaced by direct draw_screen calls
    
    def get_input(self, prompt: str = "Type your message") -> str:
        """Enhanced input with multi-line support, history navigation, and improved UX"""
        current_input = ""
        show_welcome = not hasattr(self, '_welcome_shown')
        
        while True:
            # Only redraw screen if not currently generating to avoid interference
            # Also avoid redraw if we're in scroll mode and just did a scroll operation
            if not self.generating and not getattr(self, '_skip_redraw', False):
                self.draw_screen(current_input, prompt, show_welcome)
                show_welcome = False  # Only show once
            
            # Reset skip redraw flag
            self._skip_redraw = False
            
            # Get single character with better handling
            if os.name == 'nt':
                import msvcrt
                char = msvcrt.getch().decode('utf-8', errors='ignore')
            else:
                import termios, tty
                fd = sys.stdin.fileno()
                old_settings = termios.tcgetattr(fd)
                try:
                    tty.setraw(sys.stdin.fileno())
                    char = sys.stdin.read(1)
                    
                    # Handle escape sequences (arrow keys, etc.)
                    if char == '\x1b':  # ESC sequence start
                        try:
                            tty.setraw(sys.stdin.fileno())
                            next_char = sys.stdin.read(1)
                            if next_char == '[':
                                arrow_char = sys.stdin.read(1)
                                if arrow_char == 'A':  # Up arrow
                                    char = '\x1b[A'
                                elif arrow_char == 'B':  # Down arrow
                                    char = '\x1b[B'
                                else:
                                    char = '\x1b'  # Just escape
                            else:
                                char = '\x1b'  # Just escape
                        except (OSError, IOError, ValueError):
                            char = '\x1b'
                finally:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            
            # Handle special keys first
            if char == '\t':
                # Tab - switch between text and menu mode
                self.input_mode = "menu" if self.input_mode == "text" else "text"
                current_input = ""  # Clear input when switching modes
                continue
            
            elif char == '\r' or char == '\n':
                # Enter behavior
                if self.input_mode == "text":
                    if len(self.multi_line_input) > 0:
                        # In multi-line mode, add current line
                        if current_input.strip():
                            self.multi_line_input.append(current_input)
                        current_input = ""
                        continue
                    else:
                        # Single line mode - submit if not empty
                        if current_input.strip():
                            result = current_input.strip()
                            # Add to history
                            if result not in self.input_history:
                                self.input_history.append(result)
                            self.history_index = len(self.input_history)
                            return result
                        # Don't automatically switch to menu mode on empty input
                        # User must explicitly press Tab to switch to menu mode
                        continue
                else:
                    # In menu mode, Enter does nothing
                    continue
            
            
            elif char == '\x03':  # Ctrl+C
                if self.generating:
                    self.generating = False
                    return ""
                elif self.multi_line_input:
                    # Cancel multi-line input
                    self.multi_line_input = []
                    current_input = ""
                    continue
                else:
                    raise KeyboardInterrupt
            
            elif char == '\x1b[A':  # Up arrow - history navigation
                if self.input_mode == "text" and self.input_history:
                    if self.history_index > 0:
                        self.history_index -= 1
                        current_input = self.input_history[self.history_index]
                continue
            
            elif char == '\x1b[B':  # Down arrow - history navigation
                if self.input_mode == "text" and self.input_history:
                    if self.history_index < len(self.input_history) - 1:
                        self.history_index += 1
                        current_input = self.input_history[self.history_index]
                    else:
                        self.history_index = len(self.input_history)
                        current_input = ""
                continue
            
            elif char == '\x1b':  # Escape
                if self.multi_line_input:
                    # Exit multi-line mode
                    self.multi_line_input = []
                    current_input = ""
                elif self.input_mode == "menu":
                    # Switch back to text mode
                    self.input_mode = "text"
                elif self.scroll_mode:
                    # Exit scroll mode and return to bottom
                    self.scroll_mode = False
                    self.scroll_offset = 0
                continue
            
            # Scroll controls
            elif char == '\x02':  # Ctrl+B - Toggle scroll mode
                self.scroll_mode = not self.scroll_mode
                if not self.scroll_mode:
                    # When exiting scroll mode, return to bottom
                    self.scroll_offset = 0
                # Use regular draw_screen to avoid stray output
                self.draw_screen(current_input, prompt, force_redraw=True)
                self._skip_redraw = True
                continue
            
            elif char == '\x15':  # Ctrl+U - Page up
                # First ensure we have enough messages to scroll
                if len(self.messages) > 1:  # Need at least 2 messages to scroll
                    # Page up means show older messages (increase offset)
                    page_size = max(1, self.messages_per_page // 2)  # Half page for smoother scrolling
                    max_offset = len(self.messages) - 1
                    self.scroll_offset = min(self.scroll_offset + page_size, max_offset)
                    self.scroll_mode = True
                    # Use regular draw_screen to avoid stray output
                    self.draw_screen(current_input, prompt, force_redraw=True)
                    self._skip_redraw = True
                continue
            
            elif char == '\x04':  # Ctrl+D - Page down (when not in multi-line mode)
                if not self.multi_line_input and self.scroll_offset > 0:
                    page_size = max(1, self.messages_per_page // 2)
                    self.scroll_offset = max(0, self.scroll_offset - page_size)
                    if self.scroll_offset == 0:
                        self.scroll_mode = False
                    # Use regular draw_screen to avoid stray output
                    self.draw_screen(current_input, prompt, force_redraw=True)
                    self._skip_redraw = True
                    continue
                elif self.multi_line_input:
                    # Original Ctrl+D behavior for multi-line input
                    if current_input.strip():
                        self.multi_line_input.append(current_input)
                    result = "\n".join(self.multi_line_input)
                    self.multi_line_input = []  # Clear multi-line buffer
                    # Add to history
                    if result not in self.input_history:
                        self.input_history.append(result)
                    self.history_index = len(self.input_history)
                    # Reset scroll when sending a message
                    self.scroll_offset = 0
                    self.scroll_mode = False
                    return result
                continue
            
            elif char == '\x07':  # Ctrl+G - Go to top
                if len(self.messages) > 1:
                    # Go to the very beginning (show oldest messages)
                    self.scroll_offset = max(0, len(self.messages) - 1)
                    self.scroll_mode = True
                    # Use regular draw_screen to avoid stray output
                    self.draw_screen(current_input, prompt, force_redraw=True)
                    self._skip_redraw = True
                continue
            
            elif char == '\x05':  # Ctrl+E - Go to end (bottom)
                self.scroll_offset = 0
                self.scroll_mode = False
                # Use regular draw_screen to avoid stray output
                self.draw_screen(current_input, prompt, force_redraw=True)
                self._skip_redraw = True
                continue
            
            # Mode-specific handling
            if self.input_mode == "text":
                # Check if we're in scroll mode for vim-style navigation
                if self.scroll_mode:
                    if char.lower() == 'j':  # Down one line (toward newer messages)
                        if self.scroll_offset > 0:
                            self.scroll_offset = max(0, self.scroll_offset - 1)
                            if self.scroll_offset == 0:
                                self.scroll_mode = False
                            self.draw_screen(current_input, prompt, force_redraw=True)
                            self._skip_redraw = True
                        continue
                    elif char.lower() == 'i':  # Up one line (toward older messages)
                        if len(self.messages) > 1:
                            max_offset = len(self.messages) - 1
                            self.scroll_offset = min(self.scroll_offset + 1, max_offset)
                            self.draw_screen(current_input, prompt, force_redraw=True)
                            self._skip_redraw = True
                        continue
                
                # Normal text input mode
                if char == '\x7f' or char == '\x08':  # Backspace
                    current_input = current_input[:-1]
                elif char == '\x0a':  # Shift+Enter for multi-line (simplified detection)
                    # Start multi-line mode
                    if current_input.strip():
                        self.multi_line_input.append(current_input)
                    current_input = ""
                    continue
                elif ord(char) >= 32:  # Printable character
                    current_input += char
            else:
                # Menu mode - handle colorized hotkeys
                if char.lower() == 'q':
                    return "##QUIT##"
                elif char.lower() == 'n':
                    return "##NEW##"
                elif char.lower() == 'h':
                    return "##HISTORY##"
                elif char.lower() == 's':
                    return "##SETTINGS##"
                elif char.lower() == 'm':
                    return "##MODELS##"
    
    async def create_new_conversation(self):
        """Create a new conversation"""
        title = "New Conversation"
        conversation_id = self.db.create_conversation(title, self.selected_model, self.selected_style)
        conversation_data = self.db.get_conversation(conversation_id)
        self.current_conversation = Conversation.from_dict(conversation_data)
        self.messages = []
        
    async def add_message(self, role: str, content: str):
        """Add a message to the current conversation"""
        message = Message(role=role, content=content)
        self.messages.append(message)
        
        if self.current_conversation:
            self.db.add_message(self.current_conversation.id, role, content)
    
    async def _generate_title_background(self, first_message: str):
        """Generate conversation title in background after first user message"""
        if not CONFIG.get("generate_dynamic_titles", True) or not self.current_conversation:
            return
            
        # Ensure message is long enough to generate a meaningful title
        if len(first_message) < 3:
            return
            
        try:
            # Use sophisticated model prioritization like the legacy version
            title_client = None
            title_model = None
            
            # Import needed components
            
            # Prioritize faster, cheaper models for title generation
            if OPENAI_API_KEY:
                # OpenAI is most reliable for title generation
                from .api.openai import OpenAIClient
                title_client = await OpenAIClient.create()
                title_model = "gpt-3.5-turbo"
            elif ANTHROPIC_API_KEY:
                # Anthropic is second choice
                from .api.anthropic import AnthropicClient
                title_client = await AnthropicClient.create()
                title_model = "claude-3-haiku-20240307"
            else:
                # Fallback to current model - keep same model to preserve warming
                selected_model_resolved = resolve_model_id(self.selected_model)
                client_type = BaseModelClient.get_client_type_for_model(selected_model_resolved)
                
                # For Ollama models, use the SAME model the user selected
                if client_type and client_type.__name__ == "OllamaClient":
                    try:
                        from .api.ollama import OllamaClient
                        title_client = await OllamaClient.create()
                        title_model = selected_model_resolved  # Use same model
                        
                    except Exception:
                        # Fallback to standard approach
                        title_client = await BaseModelClient.get_client_for_model(selected_model_resolved)
                        title_model = selected_model_resolved
                else:
                    # For other providers, use the current model
                    title_client = await BaseModelClient.get_client_for_model(selected_model_resolved)
                    title_model = selected_model_resolved
            
            if not title_client or not title_model:
                return
            
            # Generate title with timeout handling and fallback for Ollama
            new_title = None
            
            try:
                # For Ollama models, generate title directly to preserve warming
                if client_type and client_type.__name__ == "OllamaClient":
                    title_generation_task = asyncio.create_task(
                        self._generate_title_directly(first_message, title_model, title_client)
                    )
                else:
                    # For other providers, use the utils function
                    title_generation_task = asyncio.create_task(
                        generate_conversation_title(first_message, title_model, title_client)
                    )
                
                # Wait for completion with 30-second timeout
                new_title = await asyncio.wait_for(title_generation_task, timeout=30)
                
            except (asyncio.TimeoutError, Exception) as e:
                # Cancel the task if it's still running
                if 'title_generation_task' in locals() and not title_generation_task.done():
                    title_generation_task.cancel()
                
                # For Ollama models, try fallback to small model if main model failed
                if (client_type and client_type.__name__ == "OllamaClient" and 
                    not isinstance(e, asyncio.TimeoutError)):
                    try:
                        # Try with a small model as fallback
                        from .api.ollama import OllamaClient
                        fallback_client = await OllamaClient.create()
                        available_models = await fallback_client.get_available_models()
                        
                        # Find a small model for fallback
                        small_fallback_models = ["smollm2:latest", "tinyllama", "gemma:2b"]
                        fallback_model = None
                        
                        for small_model in small_fallback_models:
                            if any(model.get("id", "") == small_model for model in available_models):
                                fallback_model = small_model
                                break
                        
                        if fallback_model:
                            fallback_task = asyncio.create_task(
                                generate_conversation_title(first_message, fallback_model, fallback_client)
                            )
                            new_title = await asyncio.wait_for(fallback_task, timeout=15)
                            
                    except Exception:
                        # If fallback also fails, use default title
                        new_title = f"Conversation ({datetime.now().strftime('%Y-%m-%d %H:%M')})"
                else:
                    # For timeouts or non-Ollama models, use default title
                    new_title = f"Conversation ({datetime.now().strftime('%Y-%m-%d %H:%M')})"
            
            # Update conversation title if valid
            if (new_title and 
                new_title != "New Conversation" and 
                not new_title.startswith("Conversation (") and
                self.current_conversation):
                
                # Verify conversation still exists and is current
                current_conv_id = self.current_conversation.id
                if self.db.get_conversation(current_conv_id):
                    # Update database
                    self.db.update_conversation(current_conv_id, title=new_title)
                    
                    # Update local conversation object if still current
                    if self.current_conversation and self.current_conversation.id == current_conv_id:
                        self.current_conversation.title = new_title
                        
        except Exception:
            # Silently fail - title generation is not critical
            pass
    
    async def _generate_title_directly(self, message: str, model: str, client) -> str:
        """Generate title directly using the passed client to preserve model warming"""
        try:
            # Create a special prompt for title generation
            title_prompt = [
                {
                    "role": "system", 
                    "content": "Generate a brief, descriptive title (maximum 40 characters) for a conversation that starts with the following message. ONLY output the title text. DO NOT include phrases like 'Sure, here's a title' or any additional formatting, explanation, or quotes."
                },
                {
                    "role": "user",
                    "content": message
                }
            ]
            
            # Generate title using the existing client (preserves warming)
            title = await client.generate_completion(
                messages=title_prompt,
                model=model,
                temperature=0.7,
                max_tokens=60
            )
            
            # Sanitize the title - remove quotes, extra spaces and unwanted prefixes
            if title:
                title = title.strip().strip('"').strip("'")
                # Remove common prefixes that models sometimes add
                prefixes_to_remove = [
                    "Title: ", "title: ", "Here's a title: ", "A good title would be: ",
                    "Conversation about ", "Discussion on ", "Chat about "
                ]
                for prefix in prefixes_to_remove:
                    if title.startswith(prefix):
                        title = title[len(prefix):].strip()
                
                # Ensure reasonable length
                if len(title) > 60:
                    title = title[:57] + "..."
                elif len(title) < 3:
                    title = "New Conversation"
                    
                return title
            
            return "New Conversation"
            
        except Exception:
            return "New Conversation"
    
    def _get_context_aware_loading_phrases(self, user_message: str) -> List[str]:
        """Generate context-aware loading phrases based on user input"""
        message_lower = user_message.lower()
        
        # Code-related keywords
        if any(keyword in message_lower for keyword in [
            'code', 'function', 'debug', 'error', 'bug', 'script', 'program', 
            'algorithm', 'python', 'javascript', 'java', 'c++', 'html', 'css',
            'sql', 'git', 'api', 'database', 'framework', 'library'
        ]):
            return [
                "Analyzing your code", "Reviewing logic", "Debugging the issue",
                "Examining patterns", "Processing syntax", "Evaluating approach",
                "Formulating solution", "Optimizing structure"
            ]
        
        # Writing/creative keywords  
        elif any(keyword in message_lower for keyword in [
            'write', 'essay', 'story', 'article', 'blog', 'creative', 'poem',
            'letter', 'email', 'content', 'draft', 'narrative', 'description'
        ]):
            return [
                "Crafting your text", "Shaping ideas", "Weaving words",
                "Building narrative", "Polishing prose", "Structuring content",
                "Refining language", "Creating flow"
            ]
        
        # Analysis/research keywords
        elif any(keyword in message_lower for keyword in [
            'analyze', 'research', 'study', 'explain', 'compare', 'evaluate',
            'assess', 'investigate', 'examine', 'understand', 'interpret'
        ]):
            return [
                "Analyzing information", "Processing data", "Examining details",
                "Connecting insights", "Evaluating evidence", "Synthesizing findings",
                "Drawing conclusions", "Structuring analysis"
            ]
        
        # Math/calculation keywords
        elif any(keyword in message_lower for keyword in [
            'calculate', 'math', 'solve', 'equation', 'formula', 'statistics',
            'probability', 'geometry', 'algebra', 'number', 'compute'
        ]):
            return [
                "Calculating result", "Processing numbers", "Solving equation",
                "Working through math", "Computing values", "Analyzing formula",
                "Checking calculations", "Verifying solution"
            ]
        
        # Question/help keywords
        elif any(keyword in message_lower for keyword in [
            'how', 'what', 'why', 'when', 'where', 'help', 'assist', 'guide',
            'explain', 'show', 'teach', 'learn', 'understand'
        ]):
            return [
                "Processing your question", "Gathering information", "Organizing thoughts",
                "Preparing explanation", "Structuring response", "Connecting concepts",
                "Clarifying details", "Formulating answer"
            ]
        
        # Default generic phrases
        else:
            return self.loading_phrases
    
    def _get_dynamic_loading_phrase(self, user_message: str = "") -> str:
        """Get current loading phrase with context-awareness and cycling"""
        elapsed = time.time() - self.start_time
        
        # Get context-aware phrases if user message provided
        if user_message and hasattr(self, '_current_context_phrases'):
            phrases = self._current_context_phrases
        elif user_message:
            phrases = self._get_context_aware_loading_phrases(user_message)
            self._current_context_phrases = phrases  # Cache for this generation
        else:
            phrases = self.loading_phrases
        
        # Change phrase every 2 seconds
        phrase_index = int(elapsed // 2) % len(phrases)
        return phrases[phrase_index]
    
    def _update_screen_buffered(self, status_message: str):
        """Update screen using double buffering to prevent flashing"""
        # Move cursor to home position instead of clearing
        print("\033[H", end='')  # Move cursor to top-left
        
        # Draw the complete screen content
        header_lines = self.draw_header()
        footer_lines = self.draw_footer()
        input_lines = self._draw_streaming_input_area(status_message)
        message_lines = self.draw_messages()
        
        # Build all screen lines with proper clearing
        all_lines = header_lines + message_lines + input_lines + footer_lines
        
        # Output each line with clearing to end of line to prevent artifacts
        for i, line in enumerate(all_lines):
            # Clear to end of line to overwrite any previous content
            print(f"\033[{i+1};1H{line}\033[K", end='')
        
        # Clear any remaining lines below our content
        total_content_lines = len(all_lines)
        if total_content_lines < self.height:
            for i in range(total_content_lines + 1, self.height + 1):
                print(f"\033[{i};1H\033[K", end='')
        
        # Position cursor at bottom for any future output
        print(f"\033[{self.height};1H", end='', flush=True)
    
    def _update_streaming_display(self, content: str):
        """Update display with real-time streaming content and context-aware status"""
        if not self.generating:
            return
            
        # Rate limit updates to avoid flickering, but allow faster updates for better streaming effect
        current_time = time.time()
        if hasattr(self, '_last_display_update'):
            # Increased minimum time between updates to reduce flashing (from 0.02 to 0.05)
            # This gives ~20 updates per second instead of 50, which is still smooth but less flashy
            if current_time - self._last_display_update < 0.05:  # Max 20 updates per second
                return
        self._last_display_update = current_time
        
        # Update the last assistant message with current content
        if self.messages and self.messages[-1].role == "assistant":
            self.messages[-1].content = content
        
        # Show dynamic loading indicator with cycling phrases
        elapsed = int(time.time() - self.start_time)
        user_message = getattr(self, '_current_user_message', "")
        phrase = self._get_dynamic_loading_phrase(user_message)
        
        # Create streaming status with animated indicators
        dots = "." * ((elapsed % 3) + 1)
        activity_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        activity_indicator = activity_chars[elapsed % len(activity_chars)]
        streaming_status = f"{activity_indicator} {phrase}{dots} ({elapsed}s) - {len(content)} chars"
        
        # Use buffered screen update instead of clearing
        self._update_screen_buffered(streaming_status)
        
        # Ensure output is flushed
        sys.stdout.flush()
    
    def _draw_streaming_screen(self, status_message: str):
        """Draw the screen optimized for streaming updates"""
        # Calculate layout
        header_lines = self.draw_header()
        footer_lines = self.draw_footer()
        
        # Modified input area for streaming
        input_lines = self._draw_streaming_input_area(status_message)
        
        # Calculate available space for messages
        used_lines = len(header_lines) + len(footer_lines) + len(input_lines)
        available_lines = self.height - used_lines - 2
        
        # Draw header
        for line in header_lines:
            print(line)
        
        # Draw messages
        message_lines = self.draw_messages()
        chars = self.get_border_chars()
        
        # Pad or truncate message area
        if len(message_lines) < available_lines:
            # Pad with empty lines
            empty_line = chars['vertical'] + " " * (self.width - 2) + chars['vertical']
            message_lines.extend([empty_line] * (available_lines - len(message_lines)))
        else:
            # Truncate to fit
            message_lines = message_lines[-available_lines:]
        
        for line in message_lines:
            print(line)
        
        # Draw streaming input area
        for line in input_lines:
            print(line)
        
        # Draw footer
        for line in footer_lines:
            print(line)
    
    def _draw_streaming_input_area(self, status_message: str) -> List[str]:
        """Draw input area optimized for streaming with status"""
        chars = self.get_border_chars()
        lines = []
        
        # Show streaming status
        status_text = f"{self.theme['accent']}✨ {status_message}{self.theme['reset']}"
        clean_status = f" {status_message}"
        color_padding = len(status_text) - len(clean_status)
        status_line = chars['vertical'] + f" {status_text}".ljust(self.width - 2 + color_padding) + chars['vertical']
        lines.append(status_line)
        
        # Show cancellation hint
        cancel_hint = f"{self.theme['muted']}Press Ctrl+C to cancel generation{self.theme['reset']}"
        clean_hint = "Press Ctrl+C to cancel generation"
        hint_padding = len(cancel_hint) - len(clean_hint)
        hint_line = chars['vertical'] + f" {cancel_hint}".ljust(self.width - 2 + hint_padding) + chars['vertical']
        lines.append(hint_line)
        
        return lines
    
    def _show_initial_loading_screen(self):
        """Show initial loading screen immediately when generation starts"""
        # Clear screen and show loading state
        self.clear_screen()
        
        # Get initial loading phrase
        phrase = self._get_dynamic_loading_phrase(self._current_user_message)
        dots = "."
        activity_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        activity_indicator = activity_chars[0]  # Start with first spinner
        initial_status = f"{activity_indicator} {phrase}{dots} (0s) - preparing..."
        
        # Draw the screen with initial loading state
        self._draw_streaming_screen(initial_status)
        
        # Ensure output is flushed
        sys.stdout.flush()
    
    async def _animate_loading_screen(self):
        """Continuously animate the loading screen while generating"""
        activity_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        dot_patterns = ["   ", ".  ", ".. ", "..."]
        
        while self.generating and not hasattr(self, '_streaming_started'):
            try:
                elapsed = int(time.time() - self.start_time)
                
                # Get current loading phrase
                phrase = self._get_dynamic_loading_phrase(self._current_user_message)
                
                # Cycle through spinner characters
                spinner_index = elapsed % len(activity_chars)
                activity_indicator = activity_chars[spinner_index]
                
                # Cycle through dot patterns
                dot_index = (elapsed // 2) % len(dot_patterns)
                dots = dot_patterns[dot_index]
                
                # Create animated status
                status = f"{activity_indicator} {phrase}{dots} ({elapsed}s) - preparing..."
                
                # Redraw screen with updated animation
                self.clear_screen()
                self._draw_streaming_screen(status)
                sys.stdout.flush()
                
                # Update every 0.5 seconds for smooth animation
                await asyncio.sleep(0.5)
                
            except Exception:
                # If animation fails, break gracefully
                break
    
    async def generate_response(self, user_message: str):
        """Generate AI response with enhanced streaming and visual feedback"""
        self.generating = True
        self.start_time = time.time()
        self.loading_phase_index = 0
        self._current_user_message = user_message  # Store for context-aware loading
        assistant_message = None
        animation_task = None
        
        # Reset scroll position when generating new response
        self.scroll_offset = 0
        self.scroll_mode = False
        
        # Clear any cached context phrases for new generation
        if hasattr(self, '_current_context_phrases'):
            delattr(self, '_current_context_phrases')
        
        try:
            # Add user message
            await self.add_message("user", user_message)
            
            # Show loading animation immediately after user message is added
            self._show_initial_loading_screen()
            
            # Start animated loading screen in background
            animation_task = asyncio.create_task(self._animate_loading_screen())
            
            # Generate title for first user message if this is a new conversation
            if (self.current_conversation and 
                self.current_conversation.title == "New Conversation" and 
                len([msg for msg in self.messages if msg.role == "user"]) == 1):
                # Generate title in background (non-blocking)
                asyncio.create_task(self._generate_title_background(user_message))
            
            # Prepare messages for API
            api_messages = []
            for msg in self.messages:
                api_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
            
            # Get client
            client = await BaseModelClient.get_client_for_model(self.selected_model)
            
            # Add assistant message with streaming indicator
            assistant_message = Message(role="assistant", content="")
            self.messages.append(assistant_message)
            
            # Enhanced streaming with real-time updates
            full_response = ""
            cancelled = False
            
            def update_callback(content: str):
                nonlocal full_response
                if not self.generating:
                    return
                    
                # Signal that streaming has started (stops animation)
                self._streaming_started = True
                
                full_response = content
                assistant_message.content = content
                
                # Use our new streaming display method
                self._update_streaming_display(content)
            
            # Apply style to messages
            styled_messages = apply_style_prefix(api_messages, self.selected_style)
            
            # Generate streaming response with enhanced visual feedback
            try:
                async for chunk in console_streaming_response(
                    styled_messages, self.selected_model, self.selected_style, client, update_callback
                ):
                    if not self.generating:
                        cancelled = True
                        break
                    # Note: content is already handled in update_callback
                        
            except asyncio.CancelledError:
                cancelled = True
                raise
            
            # Handle cancellation cleanup
            if cancelled or not self.generating:
                if assistant_message and assistant_message in self.messages:
                    # Remove incomplete assistant message
                    self.messages.remove(assistant_message)
                self.draw_screen("", "Generation cancelled")
                return
            
            # Update final message content
            assistant_message.content = full_response
            
            # Save final response only if complete
            if self.current_conversation and full_response and not cancelled:
                self.db.add_message(self.current_conversation.id, "assistant", full_response)
            
            # Show final screen with complete response
            if not cancelled and full_response:
                self.draw_screen("", "Type your message")
                
        except KeyboardInterrupt:
            # Handle direct keyboard interrupt
            if assistant_message and assistant_message in self.messages:
                self.messages.remove(assistant_message)
            self.draw_screen("", "Generation cancelled")
            
        except Exception as e:
            # Handle other errors
            error_msg = f"Error: {str(e)}"
            if assistant_message:
                assistant_message.content = error_msg
            else:
                await self.add_message("assistant", error_msg)
        finally:
            self.generating = False
            # Clean up animation task and reset streaming flag
            if hasattr(self, '_streaming_started'):
                delattr(self, '_streaming_started')
            # Cancel animation task if it's still running
            try:
                if animation_task and not animation_task.done():
                    animation_task.cancel()
            except (asyncio.CancelledError, RuntimeError):
                pass
    
    def show_history(self):
        """Show conversation history"""
        conversations = self.db.get_all_conversations(limit=20)
        if not conversations:
            input("No conversations found. Press Enter to continue...")
            return
        
        self.clear_screen()
        print("=" * self.width)
        print("CONVERSATION HISTORY".center(self.width))
        print("=" * self.width)
        
        for i, conv in enumerate(conversations):
            print(f"{i+1:2d}. {conv['title'][:60]} ({conv['model']})")
        
        print("\nEnter conversation number to load (or press Enter to cancel):")
        
        try:
            choice = input("> ").strip()
            if choice and choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(conversations):
                    # Load conversation
                    conv_data = self.db.get_conversation(conversations[idx]['id'])
                    self.current_conversation = Conversation.from_dict(conv_data)
                    self.messages = [Message(**msg) for msg in self.current_conversation.messages]
        except (ValueError, KeyboardInterrupt):
            pass
    
    def _show_help(self):
        """Display help information about available commands"""
        self.clear_screen()
        print("=" * self.width)
        print("HELP - Available Commands".center(self.width))
        print("=" * self.width)
        print()
        
        commands = [
            ("Slash Commands:", ""),
            ("/help", "Show this help message"),
            ("/settings", "Open settings menu"),
            ("/models", "Browse and select models"),
            ("/history", "View conversation history"),
            ("/new", "Start a new conversation"),
            ("/quit or /exit", "Exit the application"),
            ("", ""),
            ("Keyboard Shortcuts:", ""),
            ("Tab", "Access menu mode"),
            ("Ctrl+B", "Toggle scroll mode"),
            ("Shift+Enter", "Multi-line input"),
            ("q", "Quick quit"),
            ("n", "Quick new conversation"),
            ("h", "Quick history"),
            ("s", "Quick settings"),
        ]
        
        for cmd, desc in commands:
            if not cmd and not desc:
                print()
            elif not desc:
                print(f"{self.theme['accent']}{cmd}{self.theme['reset']}")
            else:
                print(f"  {self.theme['primary']}{cmd:<20}{self.theme['reset']} {desc}")
        
        print()
        print(f"{self.theme['muted']}Press Enter to continue...{self.theme['reset']}")
        input()
    
    async def show_settings(self):
        """Show streamlined provider-first settings menu"""
        while True:
            self.soft_clear()
            print("=" * self.width)
            print("SETTINGS".center(self.width))
            print("=" * self.width)
            
            # Get current model display name with fallback
            try:
                current_model_info = CONFIG['available_models'][self.selected_model]
                current_model_name = current_model_info['display_name']
                current_provider = current_model_info.get('provider', 'unknown')
            except KeyError:
                current_model_name = f"{self.selected_model} (Ollama)"
                current_provider = 'ollama'
            
            # Get current style name with fallback
            try:
                current_style_name = CONFIG['user_styles'][self.selected_style]['name']
            except KeyError:
                current_style_name = self.selected_style
                
            print(f"Current Provider: {current_provider.title()}")
            print(f"Current Model: {current_model_name}")
            print(f"Current Style: {current_style_name}")
            print()
            print("Settings Menu:")
            print("1. Select Provider & Model")
            print("2. Configure API Keys")
            print("3. Response Style")
            print("4. Advanced Settings")
            print("5. Save & Exit")
            print("0. Back to Chat")
            
            try:
                choice = input("\n> ").strip()
                
                if choice == "1":
                    # Provider and model selection in one flow
                    await self._select_provider_and_model()
                elif choice == "2":
                    # API Key configuration
                    await self._configure_api_keys()
                elif choice == "3":
                    # Style selection
                    self._select_style()
                elif choice == "4":
                    # Advanced settings
                    await self._show_advanced_settings()
                elif choice == "5":
                    # Save settings
                    self._save_settings()
                    break
                elif choice == "0" or choice == "":
                    break
                    
            except (ValueError, KeyboardInterrupt):
                break
    
    def _process_fetched_models(self, dynamic_models, force_refresh=False):
        """Process fetched models and update configuration
        
        Args:
            dynamic_models: Formatted models for config
            force_refresh: Whether to save config immediately
            
        Returns:
            dict: Available models dictionary
        """
        providers_to_refresh = ['openai', 'anthropic']
        
        # Merge with existing static models (like Ollama)
        available_models = CONFIG["available_models"].copy()
        
        # Remove old dynamic models and add fresh ones
        for model_id in list(available_models.keys()):
            if available_models[model_id].get('provider') in providers_to_refresh:
                del available_models[model_id]
        
        # Add fetched models
        available_models.update(dynamic_models)
        
        # Update global config
        CONFIG["available_models"] = available_models
        
        if force_refresh:
            save_config(CONFIG)
        
        return available_models
    
    async def _fetch_and_update_models_async(self, force_refresh=False):
        """Async version - Fetch and update models from APIs
        
        Returns:
            dict: Available models dictionary
        """
        try:
            all_models = await model_manager.get_all_models(force_refresh)
            dynamic_models = model_manager.format_models_for_config(all_models)
            return self._process_fetched_models(dynamic_models, force_refresh)
            
        except Exception as e:
            print(f"{self.theme['error']}Failed to fetch models: {e}{self.theme['reset']}")
            print(f"{self.theme['muted']}Using cached models...{self.theme['reset']}")
            return CONFIG["available_models"]
    
    def _fetch_and_update_models(self, force_refresh=False):
        """Sync wrapper - Fetch and update models from APIs
        
        Returns:
            dict: Available models dictionary
        """
        try:
            # Use asyncio.run for synchronous contexts
            all_models = asyncio.run(model_manager.get_all_models(force_refresh))
            dynamic_models = model_manager.format_models_for_config(all_models)
            return self._process_fetched_models(dynamic_models, force_refresh)
            
        except Exception as e:
            print(f"{self.theme['error']}Failed to fetch models: {e}{self.theme['reset']}")
            print(f"{self.theme['muted']}Using cached models...{self.theme['reset']}")
            return CONFIG["available_models"]
    
    def _display_provider_models(self, provider, models, model_list):
        """Display models for a specific provider
        
        Args:
            provider: Provider name
            models: List of (model_id, info) tuples
            model_list: List to append model IDs to
        """
        print(f"\n{self.theme['primary']}{provider.upper()}{self.theme['reset']}")
        for model_id, info in models:
            model_list.append(model_id)
            idx = len(model_list)
            marker = f"{self.theme['accent']}►{self.theme['reset']}" if model_id == self.selected_model else " "
            display_name = info.get("display_name", model_id)
            print(f"{marker} {idx:2d}. {display_name}")
    
    async def _select_model(self):
        """Enhanced model selection submenu with dynamic model fetching"""
        
        while True:  # Use loop instead of recursion
            self.clear_screen()
            print("=" * self.width)
            print("MODEL SELECTION".center(self.width))
            print("=" * self.width)
            
            print(f"{self.theme['muted']}Fetching latest models...{self.theme['reset']}")
            
            # Fetch latest models using async helper method
            available_models = await self._fetch_and_update_models_async()
            
            self.clear_screen()
            print("=" * self.width)
            print("MODEL SELECTION".center(self.width))
            print("=" * self.width)
            
            # Group models by provider
            models_by_provider = {}
            for model_id, info in available_models.items():
                provider = info.get('provider', 'unknown')
                if provider not in models_by_provider:
                    models_by_provider[provider] = []
                models_by_provider[provider].append((model_id, info))
            
            # Sort models within each provider by creation date and name
            for provider in models_by_provider:
                models_by_provider[provider].sort(
                    key=lambda x: (-x[1].get('created', 0), x[1].get('display_name', x[0]))
                )
            
            # Display models grouped by provider using helper method
            model_list = []
            
            # Show preferred providers first
            for provider in ['openai', 'anthropic', 'ollama']:
                if provider in models_by_provider:
                    self._display_provider_models(provider, models_by_provider[provider], model_list)
            
            # Show models from other providers
            for provider, models in models_by_provider.items():
                if provider not in ['openai', 'anthropic', 'ollama']:
                    self._display_provider_models(provider, models, model_list)
            
            print(f"\n{self.theme['muted']}Enter model number to select (r to refresh, Enter to cancel):{self.theme['reset']}")
            
            try:
                choice = input("> ").strip()
                if choice.lower() == 'r':
                    # Force refresh models using async helper method
                    print(f"{self.theme['muted']}Refreshing models from APIs...{self.theme['reset']}")
                    try:
                        await self._fetch_and_update_models_async(force_refresh=True)
                        print(f"{self.theme['success']}Models refreshed successfully!{self.theme['reset']}")
                    except Exception as e:
                        print(f"{self.theme['error']}Failed to refresh models: {e}{self.theme['reset']}")
                    input("Press Enter to continue...")
                    continue  # Loop back to show refreshed models
                
                elif choice and choice.isdigit():
                    idx = int(choice) - 1
                    if 0 <= idx < len(model_list):
                        self.selected_model = model_list[idx]
                        update_last_used_model(self.selected_model)
                        
                        # Save updated config
                        save_config(CONFIG)
                        
                        display_name = CONFIG["available_models"][self.selected_model]["display_name"]
                        print(f"{self.theme['success']}Model changed to: {display_name}{self.theme['reset']}")
                        input("Press Enter to continue...")
                        break  # Exit the loop after successful selection
                else:
                    # User pressed Enter or invalid option - exit
                    break
                    
            except (ValueError, KeyboardInterrupt):
                break  # Exit on error or interrupt
    
    def _select_style(self):
        """Style selection submenu"""
        self.clear_screen()
        print("=" * self.width)
        print("RESPONSE STYLE SELECTION".center(self.width))
        print("=" * self.width)
        
        styles = list(CONFIG["user_styles"].keys())
        for i, style in enumerate(styles):
            marker = "►" if style == self.selected_style else " "
            name = CONFIG["user_styles"][style]["name"]
            description = CONFIG["user_styles"][style]["description"]
            print(f"{marker} {i+1:2d}. {name}")
            print(f"     {description}")
            print()
        
        print("Enter style number to select (or press Enter to cancel):")
        
        try:
            choice = input("> ").strip()
            if choice and choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(styles):
                    old_style = self.selected_style
                    self.selected_style = styles[idx]
                    print(f"Style changed from {old_style} to {self.selected_style}")
                    input("Press Enter to continue...")
        except (ValueError, KeyboardInterrupt):
            pass
    
    def _save_settings(self):
        """Save current settings to config file"""
        try:
            CONFIG["default_model"] = self.selected_model
            CONFIG["default_style"] = self.selected_style
            save_config(CONFIG)
            print("Settings saved successfully!")
        except Exception as e:
            print(f"Error saving settings: {e}")
        input("Press Enter to continue...")

    async def _select_provider_and_model(self):
        """Unified provider and model selection in one flow"""
        while True:
            self.soft_clear()
            print("=" * self.width)
            print("SELECT PROVIDER & MODEL".center(self.width))
            print("=" * self.width)
            
            # Check available providers
            available_providers = check_provider_availability()
            providers = []
            
            if available_providers.get("openai"):
                providers.append(("openai", "OpenAI (GPT Models)"))
            if available_providers.get("anthropic"):
                providers.append(("anthropic", "Anthropic (Claude Models)"))
            if available_providers.get("ollama"):
                providers.append(("ollama", "Ollama (Local Models)"))
            
            # Add custom providers
            for provider_name, config in CUSTOM_PROVIDERS.items():
                if config.get("api_key"):
                    display_name = config.get("display_name", provider_name)
                    providers.append((provider_name, f"{display_name} (Custom API)"))
            
            if not providers:
                print("No providers available. Please configure API keys first.")
                input("Press Enter to continue...")
                return
            
            print("Available Providers:")
            for i, (provider_id, display_name) in enumerate(providers, 1):
                print(f"{i}. {display_name}")
            print("0. Back to Settings")
            
            try:
                choice = input("\n> ").strip()
                if choice == "0" or choice == "":
                    return
                
                choice_num = int(choice)
                if 1 <= choice_num <= len(providers):
                    provider_id, _ = providers[choice_num - 1]
                    # Now show models for this provider
                    if await self._select_model_for_provider(provider_id):
                        return  # Exit if model was selected
                else:
                    print("Invalid choice. Please try again.")
                    input("Press Enter to continue...")
                    
            except (ValueError, KeyboardInterrupt):
                return

    async def _select_model_for_provider(self, provider_id):
        """Select a model from a specific provider"""
        self.soft_clear()
        print("=" * self.width)
        print(f"MODELS FOR {provider_id.upper()}".center(self.width))
        print("=" * self.width)
        
        print(f"{self.theme['muted']}Fetching latest models...{self.theme['reset']}")
        
        try:
            # Fetch models for this specific provider
            if provider_id == "ollama":
                # Use existing Ollama logic
                await self.show_model_browser()
                return True
            else:
                # Fetch models from API providers
                available_models = await self._fetch_and_update_models_async()
                provider_models = [(model_id, info) for model_id, info in available_models.items() 
                                 if info.get('provider') == provider_id]
                
                if not provider_models:
                    print(f"No models available for {provider_id}")
                    input("Press Enter to continue...")
                    return False
                
                self.clear_screen()
                print("=" * self.width)
                print(f"MODELS FOR {provider_id.upper()} ({len(provider_models)} available)".center(self.width))
                print("=" * self.width)
                
                for i, (model_id, info) in enumerate(provider_models, 1):
                    display_name = info.get('display_name', model_id)
                    print(f"{i}. {display_name}")
                
                print("0. Back to Provider Selection")
                
                choice = input("\n> ").strip()
                if choice == "0" or choice == "":
                    return False
                
                try:
                    choice_num = int(choice)
                    if 1 <= choice_num <= len(provider_models):
                        model_id, _ = provider_models[choice_num - 1]
                        self.selected_model = model_id
                        # Save the selection to config immediately
                        CONFIG["default_model"] = model_id
                        save_config(CONFIG)
                        update_last_used_model(model_id)
                        print(f"Selected model: {model_id}")
                        print("Settings saved successfully!")
                        input("Press Enter to continue...")
                        return True
                    else:
                        print("Invalid choice.")
                        input("Press Enter to continue...")
                        return False
                except ValueError:
                    print("Invalid input.")
                    input("Press Enter to continue...")
                    return False
                    
        except Exception as e:
            print(f"Error fetching models: {e}")
            input("Press Enter to continue...")
            return False

    async def _configure_api_keys(self):
        """Configure API keys for different providers"""
        while True:
            self.clear_screen()
            print("=" * self.width)
            print("API KEY CONFIGURATION".center(self.width))
            print("=" * self.width)
            
            print("Current API Key Status:")
            print(f"  OpenAI: {'✓ Set' if OPENAI_API_KEY else '✗ Not Set'}")
            print(f"  Anthropic: {'✓ Set' if ANTHROPIC_API_KEY else '✗ Not Set'}")
            
            # Show custom providers
            for provider_name, config in CUSTOM_PROVIDERS.items():
                display_name = config.get("display_name", provider_name)
                api_key_set = bool(config.get("api_key"))
                print(f"  {display_name}: {'✓ Set' if api_key_set else '✗ Not Set'}")
            
            print("\nConfiguration Options:")
            print("1. Set OpenAI API Key")
            print("2. Set Anthropic API Key") 
            print("3. Configure Custom API Provider")
            print("4. Set Ollama Base URL")
            print("5. Test API Connections")
            print("0. Back to Settings")
            
            try:
                choice = input("\n> ").strip()
                
                if choice == "1":
                    await self._set_openai_key()
                elif choice == "2":
                    await self._set_anthropic_key()
                elif choice == "3":
                    await self._configure_custom_provider()
                elif choice == "4":
                    await self._set_ollama_url()
                elif choice == "5":
                    await self._test_api_connections()
                elif choice == "0" or choice == "":
                    break
                    
            except (ValueError, KeyboardInterrupt):
                break

    async def _set_openai_key(self):
        """Set OpenAI API key"""
        global OPENAI_API_KEY
        
        self.clear_screen()
        print("=" * self.width)
        print("OPENAI API KEY".center(self.width))
        print("=" * self.width)
        
        current_key = OPENAI_API_KEY
        if current_key:
            masked = current_key[:8] + "..." + current_key[-4:] if len(current_key) > 12 else "***"
            print(f"Current key: {masked}")
        else:
            print("No API key currently set")
        
        print("\nEnter new API key (or press Enter to skip):")
        new_key = input("> ").strip()
        
        if new_key:
            # Update environment and config
            import os
            os.environ["OPENAI_API_KEY"] = new_key
            CONFIG["openai_api_key"] = new_key
            
            # Update global variable
            OPENAI_API_KEY = new_key
            
            print("✓ OpenAI API key updated!")
        else:
            print("No changes made.")
        
        input("Press Enter to continue...")

    async def _set_anthropic_key(self):
        """Set Anthropic API key"""
        global ANTHROPIC_API_KEY
        
        self.clear_screen()
        print("=" * self.width)
        print("ANTHROPIC API KEY".center(self.width))
        print("=" * self.width)
        
        current_key = ANTHROPIC_API_KEY
        if current_key:
            masked = current_key[:8] + "..." + current_key[-4:] if len(current_key) > 12 else "***"
            print(f"Current key: {masked}")
        else:
            print("No API key currently set")
        
        print("\nEnter new API key (or press Enter to skip):")
        new_key = input("> ").strip()
        
        if new_key:
            # Update environment and config
            import os
            os.environ["ANTHROPIC_API_KEY"] = new_key
            CONFIG["anthropic_api_key"] = new_key
            
            # Update global variable  
            ANTHROPIC_API_KEY = new_key
            
            print("✓ Anthropic API key updated!")
        else:
            print("No changes made.")
        
        input("Press Enter to continue...")

    async def _configure_custom_provider(self):
        """Configure custom API provider"""
        self.clear_screen()
        print("=" * self.width)
        print("CUSTOM API PROVIDER".center(self.width))
        print("=" * self.width)
        
        # Get current custom provider info
        custom_config = CUSTOM_PROVIDERS.get("openai-compatible", {})
        current_url = custom_config.get("base_url", "")
        current_key = custom_config.get("api_key", "")
        current_name = custom_config.get("display_name", "Custom API")
        
        print("Current Configuration:")
        print(f"  Name: {current_name}")
        print(f"  URL: {current_url}")
        print(f"  API Key: {'Set' if current_key else 'Not Set'}")
        print()
        
        # Configure display name
        print("Display Name (or press Enter to keep current):")
        new_name = input(f"> [{current_name}] ").strip() or current_name
        
        # Configure base URL
        print("Base URL (or press Enter to keep current):")
        new_url = input(f"> [{current_url}] ").strip() or current_url
        
        # Configure API key
        print("API Key (or press Enter to keep current):")
        new_key = input("> ").strip() or current_key
        
        if new_url and new_key:
            # Update custom provider config
            CUSTOM_PROVIDERS["openai-compatible"] = {
                "base_url": new_url,
                "api_key": new_key,
                "type": "openai_compatible", 
                "display_name": new_name
            }
            
            # Save to config
            CONFIG["custom_api_enabled"] = True
            CONFIG["custom_api_base_url"] = new_url
            CONFIG["custom_api_key"] = new_key
            CONFIG["custom_api_display_name"] = new_name
            
            # Update environment variables
            import os
            os.environ["CUSTOM_API_BASE_URL"] = new_url
            os.environ["CUSTOM_API_KEY"] = new_key
            
            print("✓ Custom API provider configured!")
        else:
            print("❌ Both URL and API key are required.")
        
        input("Press Enter to continue...")

    async def _set_ollama_url(self):
        """Set Ollama base URL"""
        global OLLAMA_BASE_URL
        
        self.clear_screen()
        print("=" * self.width)
        print("OLLAMA BASE URL".center(self.width))
        print("=" * self.width)
        
        current_url = OLLAMA_BASE_URL
        print(f"Current URL: {current_url}")
        
        print("\nEnter new URL (or press Enter to keep current):")
        new_url = input(f"> [{current_url}] ").strip() or current_url
        
        if new_url != current_url:
            # Update config
            CONFIG["ollama_base_url"] = new_url
            
            # Update environment variable
            import os
            os.environ["OLLAMA_BASE_URL"] = new_url
            
            # Update global variable
            OLLAMA_BASE_URL = new_url
            
            print("✓ Ollama URL updated!")
        else:
            print("No changes made.")
        
        input("Press Enter to continue...")

    async def _test_api_connections(self):
        """Test connections to all configured APIs"""
        self.clear_screen()
        print("=" * self.width)
        print("API CONNECTION TESTS".center(self.width))
        print("=" * self.width)
        
        # Test OpenAI
        if OPENAI_API_KEY:
            print("Testing OpenAI...")
            try:
                from .api.openai import OpenAIClient
                client = await OpenAIClient.create()
                models = await client.list_models()
                print(f"✓ OpenAI: Connected ({len(models)} models)")
            except Exception as e:
                print(f"❌ OpenAI: Failed - {str(e)[:50]}")
        else:
            print("⚠ OpenAI: No API key set")
        
        # Test Anthropic
        if ANTHROPIC_API_KEY:
            print("Testing Anthropic...")
            try:
                from .api.anthropic import AnthropicClient
                client = await AnthropicClient.create()
                models = await client.list_models()
                print(f"✓ Anthropic: Connected ({len(models)} models)")
            except Exception as e:
                print(f"❌ Anthropic: Failed - {str(e)[:50]}")
        else:
            print("⚠ Anthropic: No API key set")
        
        # Test custom providers
        for provider_name, config in CUSTOM_PROVIDERS.items():
            if config.get("api_key"):
                display_name = config.get("display_name", provider_name)
                print(f"Testing {display_name}...")
                try:
                    from .api.custom_openai import CustomOpenAIClient
                    client = await CustomOpenAIClient.create(provider_name)
                    models = await client.list_models()
                    print(f"✓ {display_name}: Connected ({len(models)} models)")
                except Exception as e:
                    print(f"❌ {display_name}: Failed - {str(e)[:50]}")
            else:
                display_name = config.get("display_name", provider_name)
                print(f"⚠ {display_name}: No API key set")
        
        # Test Ollama
        print("Testing Ollama...")
        try:
            import requests
            response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                print(f"✓ Ollama: Connected ({len(models)} models)")
            else:
                print(f"❌ Ollama: HTTP {response.status_code}")
        except Exception as e:
            print(f"❌ Ollama: Failed - {str(e)[:50]}")
        
        input("\nPress Enter to continue...")
    
    async def _show_advanced_settings(self):
        """Show advanced settings configuration panel"""
        while True:
            self.clear_screen()
            print("=" * self.width)
            print("ADVANCED SETTINGS".center(self.width))
            print("=" * self.width)
            
            # Display current advanced settings
            print("Current Advanced Settings:")
            print(f"  Code Highlighting: {'On' if CONFIG.get('highlight_code', True) else 'Off'}")
            print(f"  Dynamic Titles: {'On' if CONFIG.get('generate_dynamic_titles', True) else 'Off'}")
            print(f"  Model Preloading: {'On' if CONFIG.get('ollama_model_preload', True) else 'Off'}")
            print(f"  Ollama URL: {CONFIG.get('ollama_base_url', 'http://localhost:11434')}")
            print(f"  Inactive Timeout: {CONFIG.get('ollama_inactive_timeout_minutes', 30)} minutes")
            print()
            
            print("What would you like to configure?")
            print("1. Provider Settings")
            print("2. UI Settings")
            print("3. Performance Settings")
            print("4. Ollama Settings")
            print("0. Back to Settings")
            
            try:
                choice = input("\n> ").strip()
                
                if choice == "1":
                    await self._configure_provider_settings()
                elif choice == "2":
                    await self._configure_ui_settings()
                elif choice == "3":
                    await self._configure_performance_settings()
                elif choice == "4":
                    await self._configure_ollama_settings()
                elif choice == "0" or choice == "":
                    break
                    
            except (ValueError, KeyboardInterrupt):
                break
    
    async def _configure_provider_settings(self):
        """Configure provider-specific settings"""
        self.clear_screen()
        print("=" * self.width)
        print("PROVIDER SETTINGS".center(self.width))
        print("=" * self.width)
        
        print("Current Provider Settings:")
        print(f"  OpenAI API Key: {'Set' if CONFIG.get('openai_api_key') else 'Not Set'}")
        print(f"  Anthropic API Key: {'Set' if CONFIG.get('anthropic_api_key') else 'Not Set'}")
        print(f"  Custom API: {'Enabled' if CONFIG.get('custom_api_enabled', True) else 'Disabled'}")
        print(f"  Custom API URL: {CONFIG.get('custom_api_base_url', 'https://api.example.com/v1')}")
        print(f"  Custom API Key: {'Set' if CONFIG.get('custom_api_key') else 'Not Set'}")
        print(f"  Ollama Base URL: {CONFIG.get('ollama_base_url', 'http://localhost:11434')}")
        print()
        
        print("Options:")
        print("1. Set OpenAI API Key")
        print("2. Set Anthropic API Key")
        print("3. Configure Custom API")
        print("4. Set Ollama Base URL")
        print("5. Test Custom API Connection")
        print("6. Clear API Keys")
        print("0. Back")
        
        choice = input("\n> ").strip()
        
        if choice == "1":
            key = input("Enter OpenAI API Key (or press Enter to skip): ").strip()
            if key:
                CONFIG["openai_api_key"] = key
                print("OpenAI API Key updated!")
                
        elif choice == "2":
            key = input("Enter Anthropic API Key (or press Enter to skip): ").strip()
            if key:
                CONFIG["anthropic_api_key"] = key
                print("Anthropic API Key updated!")
                
        elif choice == "3":
            await self._configure_custom_api()
            return  # Return early to avoid the continue prompt
                
        elif choice == "4":
            url = input(f"Enter Ollama Base URL (current: {CONFIG.get('ollama_base_url', 'http://localhost:11434')}): ").strip()
            if url:
                CONFIG["ollama_base_url"] = url
                print("Ollama Base URL updated!")
                
        elif choice == "5":
            await self._test_custom_api_connection()
            return  # Return early to avoid the continue prompt
                
        elif choice == "6":
            confirm = input("Clear all API keys? (y/N): ").strip().lower()
            if confirm == 'y':
                CONFIG.pop("openai_api_key", None)
                CONFIG.pop("anthropic_api_key", None)
                CONFIG.pop("custom_api_key", None)
                print("API keys cleared!")
        
        if choice in ["1", "2", "4", "6"]:
            input("\nPress Enter to continue...")
    
    async def _configure_custom_api(self):
        """Configure Custom API settings"""
        while True:
            self.clear_screen()
            print("=" * self.width)
            print("CUSTOM API CONFIGURATION".center(self.width))
            print("=" * self.width)
            
            current_enabled = CONFIG.get("custom_api_enabled", True)
            current_url = CONFIG.get("custom_api_base_url", "https://api.example.com/v1")
            current_key = CONFIG.get("custom_api_key")
            current_name = CONFIG.get("custom_api_display_name", "Custom API")
            
            print("Current Custom API Settings:")
            print(f"  Status: {'Enabled' if current_enabled else 'Disabled'}")
            print(f"  Display Name: {current_name}")
            print(f"  Base URL: {current_url}")
            print(f"  API Key: {'Set (' + current_key[:10] + '...)' if current_key else 'Not Set'}")
            print()
            
            print("Options:")
            print("1. Enable/Disable Custom API")
            print("2. Set Display Name")
            print("3. Set Base URL")
            print("4. Set API Key")
            print("5. Test Connection")
            print("6. Reset to Defaults")
            print("0. Back")
            
            choice = input("\n> ").strip()
            
            if choice == "1":
                new_status = not current_enabled
                CONFIG["custom_api_enabled"] = new_status
                status_text = "enabled" if new_status else "disabled"
                print(f"Custom API {status_text}!")
                input("Press Enter to continue...")
                
            elif choice == "2":
                name = input(f"Enter display name (current: {current_name}): ").strip()
                if name:
                    CONFIG["custom_api_display_name"] = name
                    print("Display name updated!")
                    input("Press Enter to continue...")
                    
            elif choice == "3":
                print("Enter the base URL for your Custom API endpoint.")
                print("Example: https://api.example.com/v1")
                url = input(f"Base URL (current: {current_url}): ").strip()
                if url:
                    if not url.endswith('/'):
                        url = url.rstrip('/') + ''  # Ensure proper URL format
                    CONFIG["custom_api_base_url"] = url
                    print("Base URL updated!")
                    input("Press Enter to continue...")
                    
            elif choice == "4":
                print("Enter your Custom API key.")
                key = input(f"API Key (current: {current_key[:10]}...): ").strip()
                if key:
                    CONFIG["custom_api_key"] = key
                    print("API key updated!")
                    input("Press Enter to continue...")
                    
            elif choice == "5":
                await self._test_custom_api_connection()
                
            elif choice == "6":
                confirm = input("Reset to default settings? (y/N): ").strip().lower()
                if confirm == 'y':
                    CONFIG["custom_api_enabled"] = True
                    CONFIG["custom_api_base_url"] = "https://api.example.com/v1"
                    CONFIG["custom_api_key"] = ""
                    CONFIG["custom_api_display_name"] = "Custom API"
                    print("Settings reset to defaults!")
                    input("Press Enter to continue...")
                    
            elif choice == "0" or choice == "":
                break
                
            # Save settings after each change
            save_config(CONFIG)
    
    async def _test_custom_api_connection(self):
        """Test connection to the Custom API"""
        self.clear_screen()
        print("=" * self.width)
        print("TESTING CUSTOM API CONNECTION".center(self.width))
        print("=" * self.width)
        
        if not CONFIG.get("custom_api_enabled", True):
            print("❌ Custom API is disabled. Enable it first.")
            input("\nPress Enter to continue...")
            return
        
        base_url = CONFIG.get("custom_api_base_url", "https://api.example.com/v1")
        api_key = CONFIG.get("custom_api_key", "")
        
        if not base_url or not api_key:
            print("❌ Custom API URL or key not configured.")
            input("\nPress Enter to continue...")
            return
        
        print(f"Testing connection to: {base_url}")
        print("Please wait...")
        
        try:
            # Update environment variables temporarily for the test
            import os
            old_url = os.environ.get("CUSTOM_API_BASE_URL")
            old_key = os.environ.get("CUSTOM_API_KEY")
            
            os.environ["CUSTOM_API_BASE_URL"] = base_url
            os.environ["CUSTOM_API_KEY"] = api_key
            
            # Update CUSTOM_PROVIDERS for the test
            from .config import CUSTOM_PROVIDERS
            old_provider = CUSTOM_PROVIDERS.get("openai-compatible", {}).copy()
            CUSTOM_PROVIDERS["openai-compatible"] = {
                "base_url": base_url,
                "api_key": api_key,
                "type": "openai_compatible",
                "display_name": CONFIG.get("custom_api_display_name", "Custom API")
            }
            
            # Test the connection
            from .api.custom_openai import CustomOpenAIClient
            client = await CustomOpenAIClient.create("openai-compatible")
            models = await client.list_models()
            
            # Restore old values
            if old_url is not None:
                os.environ["CUSTOM_API_BASE_URL"] = old_url
            else:
                os.environ.pop("CUSTOM_API_BASE_URL", None)
                
            if old_key is not None:
                os.environ["CUSTOM_API_KEY"] = old_key
            else:
                os.environ.pop("CUSTOM_API_KEY", None)
                
            CUSTOM_PROVIDERS["openai-compatible"] = old_provider
            
            print(f"✅ Connection successful!")
            print(f"Found {len(models)} available models:")
            for i, model in enumerate(models[:5]):
                print(f"  {i+1}. {model['name']} ({model['id']})")
            if len(models) > 5:
                print(f"  ... and {len(models) - 5} more models")
                
        except Exception as e:
            print(f"❌ Connection failed: {str(e)}")
            print("\nPlease check:")
            print("• Base URL is correct and accessible")
            print("• API key is valid")
            print("• Network connection is working")
            
        input("\nPress Enter to continue...")
    
    async def _configure_ui_settings(self):
        """Configure UI and display settings"""
        self.clear_screen()
        print("=" * self.width)
        print("UI SETTINGS".center(self.width))
        print("=" * self.width)
        
        print("Current UI Settings:")
        print(f"  Code Highlighting: {'On' if CONFIG.get('highlight_code', True) else 'Off'}")
        print(f"  Emoji Indicators: {'On' if CONFIG.get('use_emoji_indicators', True) else 'Off'}")
        print(f"  Word Wrapping: {'On' if CONFIG.get('word_wrap', True) else 'Off'}")
        print()
        
        print("Options:")
        print("1. Toggle Code Highlighting")
        print("2. Toggle Emoji Indicators")
        print("3. Toggle Word Wrapping")
        print("0. Back")
        
        choice = input("\n> ").strip()
        
        if choice == "1":
            current = CONFIG.get('highlight_code', True)
            CONFIG['highlight_code'] = not current
            print(f"Code highlighting {'enabled' if not current else 'disabled'}!")
            
        elif choice == "2":
            current = CONFIG.get('use_emoji_indicators', True)
            CONFIG['use_emoji_indicators'] = not current
            print(f"Emoji indicators {'enabled' if not current else 'disabled'}!")
            
        elif choice == "3":
            current = CONFIG.get('word_wrap', True)
            CONFIG['word_wrap'] = not current
            print(f"Word wrapping {'enabled' if not current else 'disabled'}!")
        
        if choice in ["1", "2", "3"]:
            input("\nPress Enter to continue...")
    
    async def _configure_performance_settings(self):
        """Configure performance and optimization settings"""
        self.clear_screen()
        print("=" * self.width)
        print("PERFORMANCE SETTINGS".center(self.width))
        print("=" * self.width)
        
        print("Current Performance Settings:")
        print(f"  Dynamic Title Generation: {'On' if CONFIG.get('generate_dynamic_titles', True) else 'Off'}")
        print(f"  Model Preloading: {'On' if CONFIG.get('ollama_model_preload', True) else 'Off'}")
        print(f"  History Limit: {CONFIG.get('history_limit', 100)} conversations")
        print(f"  Message Limit: {CONFIG.get('message_limit', 50)} per conversation")
        print()
        
        print("Options:")
        print("1. Toggle Dynamic Title Generation")
        print("2. Toggle Model Preloading")
        print("3. Set History Limit")
        print("4. Set Message Limit")
        print("0. Back")
        
        choice = input("\n> ").strip()
        
        if choice == "1":
            current = CONFIG.get('generate_dynamic_titles', True)
            CONFIG['generate_dynamic_titles'] = not current
            print(f"Dynamic title generation {'enabled' if not current else 'disabled'}!")
            
        elif choice == "2":
            current = CONFIG.get('ollama_model_preload', True)
            CONFIG['ollama_model_preload'] = not current
            print(f"Model preloading {'enabled' if not current else 'disabled'}!")
            
        elif choice == "3":
            try:
                limit = int(input(f"Enter history limit (current: {CONFIG.get('history_limit', 100)}): "))
                if limit > 0:
                    CONFIG['history_limit'] = limit
                    print(f"History limit set to {limit}!")
            except ValueError:
                print("Invalid number!")
                
        elif choice == "4":
            try:
                limit = int(input(f"Enter message limit (current: {CONFIG.get('message_limit', 50)}): "))
                if limit > 0:
                    CONFIG['message_limit'] = limit
                    print(f"Message limit set to {limit}!")
            except ValueError:
                print("Invalid number!")
        
        if choice in ["1", "2", "3", "4"]:
            # Save config after any performance setting change
            save_config(CONFIG)
            input("\nPress Enter to continue...")
    
    async def _configure_ollama_settings(self):
        """Configure Ollama-specific settings"""
        self.clear_screen()
        print("=" * self.width)
        print("OLLAMA SETTINGS".center(self.width))
        print("=" * self.width)
        
        print("Current Ollama Settings:")
        print(f"  Base URL: {CONFIG.get('ollama_base_url', 'http://localhost:11434')}")
        print(f"  Inactive Timeout: {CONFIG.get('ollama_inactive_timeout_minutes', 30)} minutes")
        print(f"  Auto Start: {'On' if CONFIG.get('ollama_auto_start', True) else 'Off'}")
        print(f"  Model Cleanup: {'On' if CONFIG.get('ollama_cleanup_models', True) else 'Off'}")
        print()
        
        print("Options:")
        print("1. Set Base URL")
        print("2. Set Inactive Timeout")
        print("3. Toggle Auto Start")
        print("4. Toggle Model Cleanup")
        print("5. Test Connection")
        print("0. Back")
        
        choice = input("\n> ").strip()
        
        if choice == "1":
            url = input(f"Enter Ollama Base URL (current: {CONFIG.get('ollama_base_url', 'http://localhost:11434')}): ").strip()
            if url:
                CONFIG['ollama_base_url'] = url
                print("Ollama Base URL updated!")
                
        elif choice == "2":
            try:
                timeout = int(input(f"Enter inactive timeout in minutes (current: {CONFIG.get('ollama_inactive_timeout_minutes', 30)}): "))
                if timeout > 0:
                    CONFIG['ollama_inactive_timeout_minutes'] = timeout
                    print(f"Inactive timeout set to {timeout} minutes!")
            except ValueError:
                print("Invalid number!")
                
        elif choice == "3":
            current = CONFIG.get('ollama_auto_start', True)
            CONFIG['ollama_auto_start'] = not current
            print(f"Ollama auto start {'enabled' if not current else 'disabled'}!")
            
        elif choice == "4":
            current = CONFIG.get('ollama_cleanup_models', True)
            CONFIG['ollama_cleanup_models'] = not current
            print(f"Model cleanup {'enabled' if not current else 'disabled'}!")
            
        elif choice == "5":
            print("Testing Ollama connection...")
            try:
                from .api.ollama import OllamaClient
                client = await OllamaClient.create()
                models = await client.get_available_models()
                print(f"✓ Connection successful! Found {len(models)} local models.")
            except Exception as e:
                print(f"✗ Connection failed: {str(e)}")
        
        if choice in ["1", "2", "3", "4"]:
            # Save config after any Ollama setting change
            save_config(CONFIG)
            
        if choice in ["1", "2", "3", "4", "5"]:
            input("\nPress Enter to continue...")
    
    async def show_model_browser(self):
        """Show Ollama model browser for managing local and available models"""
        while True:
            # Check if we should exit to chat
            if self._exit_to_chat:
                self._exit_to_chat = False  # Reset flag
                break
            self.soft_clear()
            print("=" * self.width)
            print("OLLAMA MODEL BROWSER".center(self.width))
            print("=" * self.width)
            
            print("What would you like to do?")
            print("1. View Local Models")
            print("2. Browse Available Models")
            print("3. Search Models")
            print("4. Switch Current Model")
            print("0. Back to Chat")
            
            try:
                choice = input("\n> ").strip()
                
                if choice == "1":
                    await self._list_local_models()
                elif choice == "2":
                    await self._list_available_models()
                    # Check if user chose to start chat after download
                    if self._exit_to_chat:
                        break
                elif choice == "3":
                    await self._search_models()
                    # Check if user chose to start chat after download
                    if self._exit_to_chat:
                        break
                elif choice == "4":
                    await self._switch_model()
                elif choice == "0" or choice == "":
                    break
                    
            except (ValueError, KeyboardInterrupt):
                break
    
    async def _list_local_models(self):
        """List locally installed Ollama models"""
        self.soft_clear()
        print("=" * self.width)
        print("LOCAL OLLAMA MODELS".center(self.width))
        print("=" * self.width)
        
        try:
            # Get Ollama client with output suppression
            with self._suppress_output():
                from .api.ollama import OllamaClient
                client = await OllamaClient.create()
                
                # Get local models
                local_models = await client.get_available_models()
            
            if not local_models:
                print("No local models found.")
                print("Use option 2 to browse and download models from the registry.")
            else:
                print(f"Found {len(local_models)} local models:\n")
                
                for i, model in enumerate(local_models):
                    model_id = model.get("id", "unknown")
                    marker = "►" if model_id == self.selected_model else " "
                    print(f"{marker} {i+1:2d}. {model_id}")
                
                print("\nOptions:")
                print("d) Delete a model")
                print("i) Show model details")
                print("s) Switch to a model")
                print("Enter) Back to model browser")
                
                sub_choice = input("\n> ").strip().lower()
                
                if sub_choice == "d":
                    await self._delete_model_menu(local_models)
                elif sub_choice == "i":
                    await self._show_model_details_menu(local_models)
                elif sub_choice == "s":
                    await self._switch_model_menu(local_models)
                    
        except Exception as e:
            print(f"Error connecting to Ollama: {str(e)}")
            print("Make sure Ollama is running and accessible.")
            
        input("\nPress Enter to continue...")
    
    async def _list_available_models(self):
        """List available models for download from Ollama registry"""
        self.soft_clear()
        print("=" * self.width)
        print("AVAILABLE OLLAMA MODELS".center(self.width))
        print("=" * self.width)
        
        try:
            # Get Ollama client with output suppression
            with self._suppress_output():
                from .api.ollama import OllamaClient
                client = await OllamaClient.create()
            
            print("Loading available models... (this may take a moment)")
            with self._suppress_output():
                available_models = await client.list_available_models_from_registry("")
            
            if not available_models:
                print("No models found in registry.")
            else:
                # Group by model family for better organization
                families = {}
                for model in available_models:
                    family = model.get("model_family", "Other")
                    if family not in families:
                        families[family] = []
                    families[family].append(model)
                
                # Display by family
                model_index = 1
                model_map = {}
                
                for family, models in sorted(families.items()):
                    print(f"\n{family} Models:")
                    print("-" * 40)
                    
                    for model in models[:5]:  # Show first 5 per family
                        name = model.get("name", "unknown")
                        description = model.get("description", "")
                        size = model.get("parameter_size", "Unknown size")
                        variants = model.get("variants", [])
                        
                        # Show model with variants if available
                        if variants:
                            variants_str = ", ".join(str(v) for v in variants[:3])
                            if len(variants) > 3:
                                variants_str += f", +{len(variants)-3} more"
                            print(f"{model_index:2d}. {name} - Variants: {variants_str}")
                        else:
                            print(f"{model_index:2d}. {name} ({size})")
                            
                        if description:
                            print(f"    {description[:60]}...")
                        
                        model_map[str(model_index)] = model
                        model_index += 1
                    
                    if len(models) > 5:
                        print(f"    ... and {len(models) - 5} more {family} models")
                
                print(f"\nShowing top models by family (total: {len(available_models)})")
                print("\nOptions:")
                print("Enter model number to view variants and download")
                print("s) Search for specific models")
                print("Enter) Back to model browser")
                
                choice = input("\n> ").strip()
                
                if choice in model_map:
                    # Use the new unified flow for browsing too
                    selected_model = model_map[choice]
                    await self._show_unified_model_variants([selected_model], client, selected_model.get("name", "unknown"))
                    # Check if user chose to start chat after download
                    if self._exit_to_chat:
                        return
                elif choice.lower() == "s":
                    await self._search_models()
                    
        except Exception as e:
            print(f"Error fetching available models: {str(e)}")
            
        input("\nPress Enter to continue...")
    
    async def _search_models(self):
        """Search for models with automatic variant fetching and unified selection"""
        self.clear_screen()
        print("=" * self.width)
        print("SEARCH OLLAMA MODELS".center(self.width))
        print("=" * self.width)
        
        query = input("Enter search term (name, family, or description): ").strip()
        
        if not query:
            return
            
        try:
            # Get Ollama client with output suppression
            with self._suppress_output():
                from .api.ollama import OllamaClient
                client = await OllamaClient.create()
            
            print(f"\nSearching for '{query}'...")
            with self._suppress_output():
                all_models = await client.list_available_models_from_registry("")
            
            # Filter models
            matching_models = []
            query_lower = query.lower()
            
            for model in all_models:
                # Check name, description, and model family
                name_match = query_lower in model.get("name", "").lower()
                desc_match = query_lower in model.get("description", "").lower()
                family_match = query_lower in model.get("model_family", "").lower()
                
                # Also check variants if available
                variants_match = False
                if "variants" in model and model["variants"]:
                    variants_text = " ".join([str(v).lower() for v in model["variants"]])
                    if query_lower in variants_text:
                        variants_match = True
                
                if name_match or desc_match or family_match or variants_match:
                    matching_models.append(model)
            
            if not matching_models:
                print(f"No models found matching '{query}'")
            else:
                print(f"\nFound {len(matching_models)} models matching '{query}'. Fetching variants...")
                
                # Get detailed variants for each matching model
                await self._show_unified_model_variants(matching_models[:10], client, query)  # Limit to top 10 matches
                # Check if user chose to start chat after download
                if self._exit_to_chat:
                    return
                    
        except Exception as e:
            print(f"Error searching models: {str(e)}")
            
        input("\nPress Enter to continue...")
    
    def _extract_size_from_tag(self, tag):
        """Extract size from model tag like '2b', '7b', '27b', etc."""
        import re
        
        # Look for patterns like 2b, 7b, 27b, 70b, etc.
        size_pattern = re.compile(r'(\d+(?:\.\d+)?)\s*([bBmMgG])', re.IGNORECASE)
        match = size_pattern.search(tag)
        
        if match:
            number = match.group(1)
            unit = match.group(2).upper()
            return f"{number}{unit}"
        
        # Handle special cases
        if 'instruct' in tag.lower():
            return "Unknown"
        if 'code' in tag.lower():
            return "Unknown"
        if 'vision' in tag.lower():
            return "Unknown"
        
        # If we can't parse it, return the tag itself
        return tag if tag != "latest" else "Unknown"
    
    async def _show_unified_model_variants(self, matching_models, client, query):
        """Show all model variants in a unified, numbered list for easy selection"""
        print("\n" + "="*60)
        print(f"AVAILABLE MODELS FOR '{query.upper()}'")
        print("="*60)
        
        all_variants = []
        variant_map = {}
        
        # Progress indicator
        print(f"\nFetching variants for {len(matching_models)} models...")
        
        for i, model in enumerate(matching_models, 1):
            model_name = model.get("name", "unknown")
            print(f"[{i}/{len(matching_models)}] Getting variants for {model_name}...")
            
            try:
                # Get detailed variants using the scraping method
                with self._suppress_output():
                    detailed_model = await client.get_model_with_variants(model_name)
                
                variants = detailed_model.get("detailed_variants", [])
                
                if variants:
                    # Add each variant to our unified list
                    for variant in variants:
                        tag = variant.get("tag", "latest")
                        size = variant.get("size", "Unknown")
                        pulls = variant.get("pulls", "")
                        updated = variant.get("updated", "")
                        
                        # Create full model name
                        full_name = f"{model_name}:{tag}" if tag != "latest" else model_name
                        
                        # Try to extract size from tag if size is Unknown
                        if size == "Unknown" and tag != "latest":
                            size = self._extract_size_from_tag(tag)
                        
                        all_variants.append({
                            "model_name": model_name,
                            "tag": tag,
                            "size": size,
                            "pulls": pulls,
                            "updated": updated,
                            "full_name": full_name,
                            "description": model.get("description", ""),
                            "family": model.get("model_family", "Unknown")
                        })
                else:
                    # Add base model if no variants found
                    # For models that already have tags in their names, extract the size
                    base_size = model.get("parameter_size", "Unknown")
                    if base_size == "Unknown" and ":" in model_name:
                        tag_part = model_name.split(":")[-1]
                        base_size = self._extract_size_from_tag(tag_part)
                    
                    all_variants.append({
                        "model_name": model_name,
                        "tag": "latest",
                        "size": base_size,
                        "pulls": "",
                        "updated": "",
                        "full_name": model_name,
                        "description": model.get("description", ""),
                        "family": model.get("model_family", "Unknown")
                    })
                    
            except Exception as e:
                print(f"    Warning: Could not get variants for {model_name}: {str(e)}")
                # Add base model as fallback
                fallback_size = model.get("parameter_size", "Unknown")
                if fallback_size == "Unknown" and ":" in model_name:
                    tag_part = model_name.split(":")[-1]
                    fallback_size = self._extract_size_from_tag(tag_part)
                
                all_variants.append({
                    "model_name": model_name,
                    "tag": "latest",
                    "size": fallback_size,
                    "pulls": "",
                    "updated": "",
                    "full_name": model_name,
                    "description": model.get("description", ""),
                    "family": model.get("model_family", "Unknown")
                })
        
        # Display unified list
        self.clear_screen()
        print("=" * self.width)
        print(f"AVAILABLE MODELS FOR '{query.upper()}' ({len(all_variants)} variants)".center(self.width))
        print("=" * self.width)
        
        if not all_variants:
            print("No model variants found.")
            return
        
        # Sort by model name, then by tag preference (latest first, then by size)
        def sort_key(variant):
            model_name = variant["model_name"]
            tag = variant["tag"]
            # Prioritize latest, then sort by size if possible
            if tag == "latest":
                return (model_name, "0_latest")
            return (model_name, tag)
        
        all_variants.sort(key=sort_key)
        
        # Display variants with numbers
        for i, variant in enumerate(all_variants, 1):
            full_name = variant["full_name"]
            size = variant["size"]
            family = variant["family"]
            description = variant["description"]
            
            # Format the display line
            print(f"{i:2d}. {full_name:<25} ({size:<10}) - {family}")
            if description and len(description) > 10:
                print(f"    {description[:65]}...")
            
            variant_map[str(i)] = variant
        
        print("\n" + "="*60)
        print(f"Found {len(all_variants)} downloadable models")
        print("\nOptions:")
        print("Enter number to download that model")
        print("Enter) Back to search")
        
        choice = input("\n> ").strip()
        
        if choice in variant_map:
            selected_variant = variant_map[choice]
            await self._download_selected_variant(selected_variant)
            # Check if user chose to start chat after download
            if self._exit_to_chat:
                return
    
    async def _download_selected_variant(self, variant):
        """Download a selected model variant with confirmation"""
        full_name = variant["full_name"]
        size = variant["size"]
        
        print(f"\n" + "="*50)
        print(f"DOWNLOAD: {full_name}")
        print(f"Size: {size}")
        print(f"Family: {variant.get('family', 'Unknown')}")
        if variant.get("description"):
            print(f"Description: {variant['description']}")
        print("="*50)
        
        print(f"\nThis will download {full_name} to your local Ollama installation.")
        print("Depending on the model size and your connection, this may take several minutes.")
        print("\nPress Ctrl+C at any time to cancel the download.")
        
        # Flush output to ensure the prompt is visible
        sys.stdout.flush()
        
        # Show the prompt and ensure it's visible
        print(f"\nDownload {full_name}? (y/N): ", end='', flush=True)
        confirm = input().strip().lower()
        
        if confirm in ['y', 'yes']:
            try:
                # Get Ollama client
                with self._suppress_output():
                    from .api.ollama import OllamaClient
                    client = await OllamaClient.create()
                
                print(f"\nStarting download of {full_name}...")
                print("Progress will be shown below:")
                print("-" * 60)
                
                # Track download progress with better visual indicators
                last_status = ""
                progress_bar_width = 40
                has_shown_progress = False
                
                try:
                    async for progress in client.pull_model(full_name):
                        has_shown_progress = True
                        
                        if "status" in progress:
                            status = progress["status"]
                            
                            # Handle different progress message formats
                            if "completed" in progress and "total" in progress:
                                completed = progress["completed"]
                                total = progress["total"]
                                percentage = (completed / total) * 100 if total > 0 else 0
                                
                                # Create progress bar
                                filled_width = int(progress_bar_width * percentage / 100)
                                bar = "█" * filled_width + "░" * (progress_bar_width - filled_width)
                                
                                # Format bytes nicely
                                if total > 1024 * 1024 * 1024:  # GB
                                    completed_gb = completed / (1024 * 1024 * 1024)
                                    total_gb = total / (1024 * 1024 * 1024)
                                    size_str = f"{completed_gb:.1f}GB/{total_gb:.1f}GB"
                                else:  # MB
                                    completed_mb = completed / (1024 * 1024)
                                    total_mb = total / (1024 * 1024)
                                    size_str = f"{completed_mb:.1f}MB/{total_mb:.1f}MB"
                                
                                # Extract the layer ID from status if present  
                                if "pulling" in status and len(status.split()) > 1:
                                    layer_id = status.split()[-1][:12]  # First 12 chars of layer hash
                                    display_status = f"pulling {layer_id}"
                                else:
                                    display_status = status
                                
                                print(f"\r📦 {display_status}: [{bar}] {percentage:.1f}% ({size_str})", end="", flush=True)
                            else:
                                # For status messages without progress (like "pulling manifest")
                                if status != last_status:
                                    if last_status and "pulling" in last_status:  # Add newline after progress bars
                                        print()
                                    print(f"📦 {status}...", end="", flush=True)
                                    last_status = status
                                else:
                                    print(".", end="", flush=True)  # Show activity dots
                
                except Exception as stream_error:
                    print(f"\nProgress stream error: {stream_error}")
                    if not has_shown_progress:
                        print("Download may still be proceeding in background...")
                
                print(f"\n\n✅ Successfully downloaded {full_name}!")
                print("The model is now available for use in your chats.")
                
                # Show post-download options
                await self._show_post_download_options(full_name)
                return
                
            except KeyboardInterrupt:
                print("\n\n❌ Download cancelled by user.")
            except Exception as e:
                print(f"\n\n❌ Error downloading {full_name}: {str(e)}")
                print("This might be due to network issues, insufficient disk space, or Ollama service problems.")
        else:
            print("Download cancelled.")
        
        input("\nPress Enter to continue...")
    
    async def _show_post_download_options(self, model_id: str) -> None:
        """Show options after successful model download"""
        while True:
            print("\n" + "=" * self.width)
            print("WHAT WOULD YOU LIKE TO DO NEXT?".center(self.width))
            print("=" * self.width)
            print()
            print("1. 🚀 Start chat with model")
            print("2. 🔍 Return to search results")
            print("3. 🔎 Return to search")
            print("4. 📋 Return to model menu")
            print()
            
            choice = input("\n> ").strip()
            
            if choice == "1":
                # Start chat with the downloaded model
                await self._start_chat_with_model(model_id)
                # Exit all the way back to main chat by setting a flag
                self._exit_to_chat = True
                return
            elif choice == "2":
                # Return to search results - just return to continue the search flow
                return
            elif choice == "3":
                # Return to search input - clear current search and go back
                self.search_query = ""
                await self._search_models()
                return
            elif choice == "4":
                # Return to main model browser menu - this will exit the current flow
                return
            else:
                print("\n❌ Invalid choice. Please enter 1, 2, 3, or 4.")
                input("Press Enter to continue...")
    
    async def _start_chat_with_model(self, model_id: str) -> None:
        """Start a chat with the downloaded model and update config"""
        try:
            # Update the configuration to use this model
            from app.config import load_config, save_config
            config = load_config()
            config["default_model"] = model_id
            save_config(config)
            
            # Also update the current selected model in the UI
            from app.utils import resolve_model_id
            self.selected_model = resolve_model_id(model_id)
            
            print(f"\n✅ Configuration updated to use {model_id} as default model.")
            print("🚀 Returning to chat...")
            
        except Exception as e:
            print(f"\n❌ Error updating configuration: {str(e)}")
            input("Press Enter to continue...")
    
    async def _show_model_details(self, model_info):
        """Show detailed model information including all available variants"""
        model_name = model_info.get("name", "unknown")
        
        self.clear_screen()
        print("=" * self.width)
        print(f"MODEL DETAILS: {model_name.upper()}".center(self.width))
        print("=" * self.width)
        
        print(f"Name: {model_name}")
        print(f"Family: {model_info.get('model_family', 'Unknown')}")
        print(f"Description: {model_info.get('description', 'No description available')}")
        print()
        
        print("Loading detailed variant information...")
        
        try:
            # Get detailed model information with variants
            with self._suppress_output():
                from .api.ollama import OllamaClient
                client = await OllamaClient.create()
                detailed_model = await client.get_model_with_variants(model_name)
            
            variants = detailed_model.get("detailed_variants", [])
            
            if variants:
                print(f"\nAvailable variants for {model_name}:")
                print("-" * 60)
                print(f"{'Tag':<20} {'Size':<15} {'Pulls':<10} {'Updated'}")
                print("-" * 60)
                
                variant_map = {}
                for i, variant in enumerate(variants, 1):
                    tag = variant.get("tag", "unknown")
                    size = variant.get("size", "Unknown")
                    pulls = variant.get("pulls", "")
                    updated = variant.get("updated", "")
                    
                    # Format pulls nicely
                    pulls_str = f"{pulls:,}" if pulls else ""
                    
                    print(f"{i:2d}. {tag:<17} {size:<15} {pulls_str:<10} {updated}")
                    variant_map[str(i)] = variant
                
                print("-" * 60)
                print(f"\nFound {len(variants)} variants")
                print("\nOptions:")
                print("Enter variant number to download")
                print("d) Download base model")
                print("Enter) Back to search")
                
                choice = input("\n> ").strip()
                
                if choice in variant_map:
                    selected_variant = variant_map[choice]
                    full_name = selected_variant.get("full_name", f"{model_name}:{selected_variant.get('tag', 'latest')}")
                    await self._download_specific_model(full_name, selected_variant.get("size", "Unknown"))
                elif choice.lower() == "d":
                    await self._download_specific_model(model_name, model_info.get("parameter_size", "Unknown"))
            else:
                print(f"\nNo detailed variants found for {model_name}")
                print("This might be due to network issues or the model page format has changed.")
                print("\nOptions:")
                print("d) Download base model anyway")
                print("Enter) Back to search")
                
                choice = input("\n> ").strip()
                
                if choice.lower() == "d":
                    await self._download_specific_model(model_name, model_info.get("parameter_size", "Unknown"))
                    
        except Exception as e:
            print(f"Error getting detailed model info: {str(e)}")
            print("\nOptions:")
            print("d) Download base model anyway")
            print("Enter) Back to search")
            
            choice = input("\n> ").strip()
            
            if choice.lower() == "d":
                await self._download_specific_model(model_name, model_info.get("parameter_size", "Unknown"))
    
    async def _download_specific_model(self, model_name, size_info):
        """Download a specific model variant"""
        print(f"\nDownloading {model_name} ({size_info})...")
        print("This may take several minutes depending on model size and connection.")
        print("Press Ctrl+C to cancel.\n")
        
        confirm = input(f"Download {model_name}? (y/N): ").strip().lower()
        if confirm != 'y':
            return
            
        try:
            # Get Ollama client with output suppression
            with self._suppress_output():
                from .api.ollama import OllamaClient
                client = await OllamaClient.create()
            
            # Use the pull functionality
            print(f"Pulling {model_name}...")
            print("This will show progress as the model downloads.\n")
            
            # Pull the model (this will show download progress)
            await client.pull_model(model_name)
            
            print(f"\n✓ Successfully downloaded {model_name}!")
            print("The model is now available for use.")
            
        except KeyboardInterrupt:
            print("\nDownload cancelled by user.")
        except Exception as e:
            print(f"\nError downloading model: {str(e)}")
            print("This might be due to network issues or insufficient disk space.")
        
        input("\nPress Enter to continue...")
    
    async def _download_model(self, model_info):
        """Download a model with progress indication"""
        model_name = model_info.get("name", "unknown")
        size_info = model_info.get("parameter_size", "Unknown size")
        
        print(f"\nDownloading {model_name} ({size_info})...")
        print("This may take several minutes depending on model size and connection.")
        print("Press Ctrl+C to cancel.\n")
        
        confirm = input(f"Download {model_name}? (y/N): ").strip().lower()
        if confirm != 'y':
            return
            
        try:
            # Get Ollama client with output suppression
            with self._suppress_output():
                from .api.ollama import OllamaClient
                client = await OllamaClient.create()
            
            # Track download progress
            last_status = ""
            
            async for progress in client.pull_model(model_name):
                status = progress.get("status", "")
                
                if status != last_status:
                    print(f"Status: {status}")
                    last_status = status
                
                # Show progress if available
                if "total" in progress and "completed" in progress:
                    total = progress["total"]
                    completed = progress["completed"]
                    percent = (completed / total) * 100 if total > 0 else 0
                    print(f"Progress: {percent:.1f}% ({completed:,}/{total:,} bytes)")
                
                # Check if download is complete
                if status == "success" or "success" in status.lower():
                    print(f"\n✓ {model_name} downloaded successfully!")
                    break
                    
        except KeyboardInterrupt:
            print("\nDownload cancelled by user.")
        except Exception as e:
            print(f"\nError downloading model: {str(e)}")
    
    async def _delete_model_menu(self, local_models):
        """Show model deletion menu"""
        print("\nSelect model to delete:")
        for i, model in enumerate(local_models):
            print(f"{i+1:2d}. {model.get('id', 'unknown')}")
            
        choice = input("\nEnter model number (or press Enter to cancel): ").strip()
        
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(local_models):
                model_id = local_models[idx].get("id", "unknown")
                
                print(f"\nWARNING: This will permanently delete {model_id}")
                confirm = input("Type 'DELETE' to confirm: ").strip()
                
                if confirm == "DELETE":
                    try:
                        with self._suppress_output():
                            from .api.ollama import OllamaClient
                            client = await OllamaClient.create()
                            await client.delete_model(model_id)
                        print(f"✓ {model_id} deleted successfully!")
                    except Exception as e:
                        print(f"Error deleting model: {str(e)}")
                else:
                    print("Deletion cancelled.")
    
    async def _show_model_details_menu(self, local_models):
        """Show detailed information about a model"""
        print("\nSelect model for details:")
        for i, model in enumerate(local_models):
            print(f"{i+1:2d}. {model.get('id', 'unknown')}")
            
        choice = input("\nEnter model number (or press Enter to cancel): ").strip()
        
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(local_models):
                model_id = local_models[idx].get("id", "unknown")
                await self._show_local_model_details(model_id)
    
    async def _show_local_model_details(self, model_id):
        """Show detailed information about a specific locally installed model"""
        try:
            from .api.ollama import OllamaClient
            client = await OllamaClient.create()
            details = await client.get_model_details(model_id)
            
            self.clear_screen()
            print("=" * self.width)
            print(f"MODEL DETAILS: {model_id}".center(self.width))
            print("=" * self.width)
            
            if "error" in details:
                print(f"Error getting details: {details['error']}")
            else:
                print(f"Name: {details.get('name', model_id)}")
                
                # Handle web-scraped data format
                if details.get("source") == "web_scraping":
                    if details.get("description"):
                        print(f"Description: {details['description']}")
                    
                    if details.get("downloads"):
                        print(f"Downloads: {details['downloads']}")
                    
                    if details.get("last_updated"):
                        print(f"Last Updated: {details['last_updated']}")
                    
                    if details.get("variants"):
                        print(f"\nAvailable Variants:")
                        print("-" * 40)
                        for variant in details['variants']:
                            print(f"  {variant['name']} - {variant['size']}")
                    
                    if details.get("url"):
                        print(f"\nMore info: {details['url']}")
                
                # Handle API response format
                else:
                    if details.get("size"):
                        size_gb = details["size"] / (1024**3)
                        print(f"Size: {size_gb:.1f} GB")
                    
                    if details.get("modified_at"):
                        print(f"Modified: {details['modified_at']}")
                    
                    if details.get("parameters"):
                        print(f"\nParameters: {details['parameters']}")
                    
                    if details.get("modelfile"):
                        print(f"\nModelfile (first 500 chars):")
                        print("-" * 40)
                    print(details["modelfile"][:500])
                    if len(details["modelfile"]) > 500:
                        print("...")
                
        except Exception as e:
            print(f"Error getting model details: {str(e)}")
            
        input("\nPress Enter to continue...")
    
    async def _switch_model_menu(self, local_models):
        """Switch to a different local model"""
        print("\nSelect model to switch to:")
        for i, model in enumerate(local_models):
            model_id = model.get("id", "unknown")
            marker = "►" if model_id == self.selected_model else " "
            print(f"{marker} {i+1:2d}. {model_id}")
            
        choice = input("\nEnter model number (or press Enter to cancel): ").strip()
        
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(local_models):
                old_model = self.selected_model
                self.selected_model = local_models[idx].get("id", "unknown")
                # Save the selection to config immediately
                CONFIG["default_model"] = self.selected_model
                save_config(CONFIG)
                update_last_used_model(self.selected_model)
                print(f"\n✓ Switched from {old_model} to {self.selected_model}")
                print("Settings saved successfully!")
    
    async def _switch_model(self):
        """Switch current model (combines local and available models)"""
        try:
            from .api.ollama import OllamaClient
            client = await OllamaClient.create()
            local_models = await client.get_available_models()
            await self._switch_model_menu(local_models)
        except Exception as e:
            print(f"Error getting local models: {str(e)}")
            
        input("\nPress Enter to continue...")
    
    
    async def run(self):
        """Enhanced main application loop with welcome experience"""
        # Create initial conversation
        await self.create_new_conversation()
        
        # Show welcome screen first
        self.draw_screen("", "Type your message to begin your AI conversation", show_welcome=True)
        
        # Brief pause after welcome before starting input loop
        await asyncio.sleep(0.5)
        
        while self.running:
            try:
                # Check for resize before getting input
                if self._resize_flag:
                    self._resize_flag = False
                    self._update_terminal_size()
                    self.draw_screen("")
                
                user_input = self.get_input("Type your message")
                
                if not user_input:
                    continue
                
                # Handle special command tokens from enhanced input
                if user_input == "##QUIT##":
                    self.running = False
                    break
                elif user_input == "##NEW##":
                    await self.create_new_conversation()
                    continue
                elif user_input == "##HISTORY##":
                    self.show_history()
                    continue
                elif user_input == "##SETTINGS##":
                    await self.show_settings()
                    continue
                elif user_input == "##MODELS##":
                    await self.show_model_browser()
                    # If user chose to start chat with new model, force screen redraw and input focus
                    if self._exit_to_chat:
                        self._exit_to_chat = False  # Reset flag
                        # Force a full screen redraw to show the new model and get ready for input
                        self.draw_screen("", f"Ready to chat with {self.selected_model}", force_redraw=True)
                    continue
                
                # Handle slash commands
                if user_input.lower().startswith('/'):
                    if user_input.lower() == '/settings':
                        await self.show_settings()
                        continue
                    elif user_input.lower() == '/models':
                        await self._select_model()
                        continue
                    elif user_input.lower() == '/history':
                        self.show_history()
                        continue
                    elif user_input.lower() == '/help':
                        self._show_help()
                        continue
                    elif user_input.lower() in ['/quit', '/exit']:
                        self.running = False
                        break
                    elif user_input.lower() == '/new':
                        await self.create_new_conversation()
                        continue
                    else:
                        print(f"Unknown command: {user_input}")
                        print("Available commands: /settings, /models, /history, /help, /new, /quit")
                        input("Press Enter to continue...")
                        continue

                # Handle legacy single-letter commands for backward compatibility
                if user_input.lower() == 'q':
                    self.running = False
                    break
                elif user_input.lower() == 'n':
                    await self.create_new_conversation()
                    continue
                elif user_input.lower() == 'h':
                    self.show_history()
                    continue
                elif user_input.lower() == 's':
                    await self.show_settings()
                    continue
                elif user_input.lower() == 'm':
                    await self.show_model_browser()
                    # If user chose to start chat with new model, force screen redraw and input focus
                    if self._exit_to_chat:
                        self._exit_to_chat = False  # Reset flag
                        # Force a full screen redraw to show the new model and get ready for input
                        self.draw_screen("", f"Ready to chat with {self.selected_model}", force_redraw=True)
                    continue
                
                # Generate response
                await self.generate_response(user_input)
                
            except KeyboardInterrupt:
                if self.generating:
                    self.generating = False
                    # Clean up incomplete assistant message if it exists
                    if self.messages and self.messages[-1].role == "assistant" and not self.messages[-1].content.strip():
                        self.messages.pop()
                    self.draw_screen("", "Generation cancelled - press Enter to continue")
                    input()  # Wait for user acknowledgment
                else:
                    self.running = False
                    break
            except Exception as e:
                print(f"\nError: {e}")
                input("Press Enter to continue...")

def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown"""
    def signal_handler(_signum, _frame):
        print("\n\nShutting down gracefully...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

# Main async function for this interface module
async def run_console_interface(args=None):
    """Run the console interface with optional args"""
    import argparse
    
    if args is None:
        parser = argparse.ArgumentParser(description="Chat Console - Pure Terminal Version")
        parser.add_argument("--model", help="Initial model to use")
        parser.add_argument("--style", help="Response style")
        parser.add_argument("message", nargs="?", help="Initial message to send")
        
        args = parser.parse_args()
    
    # Setup signal handling
    setup_signal_handlers()
    
    # Create console UI
    console = ConsoleUI()
    
    if args.model:
        console.selected_model = resolve_model_id(args.model)
    if args.style:
        console.selected_style = args.style
    
    # If a message was provided, send it directly for testing
    if hasattr(args, 'message') and args.message:
        await console.create_new_conversation()
        print(f"Sending message: {args.message}")
        await console.generate_response(args.message)
        print("Response generated!")
    else:
        # Run the application normally
        await console.run()
    
    print("\nGoodbye!")

def main():
    """Main entry point for the console interface"""
    import threading
    
    try:
        # Check if there's already a running event loop
        try:
            loop = asyncio.get_running_loop()
            # If we get here, there's already a loop running
            
            def run_in_thread():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    new_loop.run_until_complete(run_console_interface())
                finally:
                    new_loop.close()
            
            thread = threading.Thread(target=run_in_thread)
            thread.start()
            thread.join()
            
        except RuntimeError:
            # No running loop, we can use asyncio.run
            asyncio.run(run_console_interface())
            
    except KeyboardInterrupt:
        print("\nGoodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()