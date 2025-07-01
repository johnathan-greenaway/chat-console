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
from .config import CONFIG, save_config
from .utils import resolve_model_id, generate_conversation_title
from .console_utils import console_streaming_response, apply_style_prefix
from .api.base import BaseModelClient

class ConsoleUI:
    """Pure console UI following Rams design principles with Gemini-inspired enhancements"""
    
    def __init__(self):
        self.width = min(shutil.get_terminal_size().columns, 120)
        self.height = shutil.get_terminal_size().lines
        self.db = ChatDatabase()
        self.current_conversation: Optional[Conversation] = None
        self.messages: List[Message] = []
        self.selected_model = resolve_model_id(CONFIG["default_model"])
        self.selected_style = CONFIG["default_style"]
        self.running = True
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
        
        # Suppress verbose logging for console mode
        self._setup_console_logging()
    
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
    
    def _setup_console_logging(self):
        """Setup logging to minimize disruption to console UI"""
        # Set root logger to CRITICAL to suppress everything except critical errors
        logging.getLogger().setLevel(logging.CRITICAL)
        
        # Clear any existing handlers first
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        
        # Add only NullHandler to suppress all output
        logging.root.addHandler(logging.NullHandler())
        
        # Aggressively suppress all known loggers
        noisy_loggers = [
            'app', 'app.api', 'app.api.base', 'app.api.ollama', 
            'app.utils', 'app.console_utils', 'aiohttp', 'urllib3', 
            'httpx', 'asyncio', 'root', 'INFO', 'DEBUG', 'WARNING',
            'httpcore', 'httpx._client', 'hpack', 'h11'
        ]
        
        for logger_name in noisy_loggers:
            logger = logging.getLogger(logger_name)
            logger.setLevel(logging.CRITICAL)
            logger.handlers = []
            logger.addHandler(logging.NullHandler())
            logger.propagate = False
        
        # Redirect stdout/stderr for subprocess calls (if any)
        self._dev_null = open(os.devnull, 'w')
        
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
        """Clear the terminal screen"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
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
            
            ascii_art = [
                "    ███████╗██╗  ██╗ █████╗ ████████╗      ██████╗ ██████╗ ███╗   ██╗███████╗ ██████╗ ██╗     ███████╗",
                "    ██╔════╝██║  ██║██╔══██╗╚══██╔══╝     ██╔════╝██╔═══██╗████╗  ██║██╔════╝██╔═══██╗██║     ██╔════╝",
                "    ██║     ███████║███████║   ██║        ██║     ██║   ██║██╔██╗ ██║███████╗██║   ██║██║     █████╗  ",
                "    ██║     ██╔══██║██╔══██║   ██║        ██║     ██║   ██║██║╚██╗██║╚════██║██║   ██║██║     ██╔══╝  ",
                "    ╚██████╗██║  ██║██║  ██║   ██║        ╚██████╗╚██████╔╝██║ ╚████║███████║╚██████╔╝███████╗███████╗",
                "     ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝         ╚═════╝ ╚═════╝ ╚═╝  ╚═══╝╚══════╝ ╚═════╝ ╚══════╝╚══════╝"
            ]
            
            # Scale ASCII art for terminal width
            if self.width < 100:
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
        model_info = f" {self.theme['primary']}Model: {self.selected_model}{self.theme['reset']} "
        
        # Add scroll indicator if in scroll mode
        if self.scroll_mode or self.scroll_offset > 0:
            scroll_info = f" {self.theme['warning']}[SCROLL MODE]{self.theme['reset']} "
        else:
            scroll_info = ""
        
        # Calculate spacing (account for color codes)
        clean_title = f" Chat Console v{__version__} "
        clean_model = f" Model: {self.selected_model} "
        clean_scroll = " [SCROLL MODE] " if (self.scroll_mode or self.scroll_offset > 0) else ""
        used_space = len(clean_title) + len(clean_model) + len(clean_scroll)
        remaining = self.width - used_space - 2
        spacing = chars['horizontal'] * max(0, remaining)
        
        header_line = chars['top_left'] + title + spacing + scroll_info + model_info + chars['top_right']
        lines.append(header_line)
        
        # Conversation title with color
        conv_title = self.current_conversation.title if self.current_conversation else "New Conversation"
        colored_title = f" {self.theme['secondary']}{conv_title}{self.theme['reset']} "
        title_line = chars['vertical'] + colored_title.ljust(self.width - 2 + len(self.theme['secondary']) + len(self.theme['reset'])) + chars['vertical']
        lines.append(title_line)
        
        # Separator
        lines.append(self.draw_border_line(self.width, 'middle'))
        
        return lines
    
    def draw_footer(self) -> List[str]:
        """Draw the enhanced footer with colorized controls"""
        chars = self.get_border_chars()
        
        # Show different controls based on mode
        if self.scroll_mode or self.scroll_offset > 0:
            # Scroll mode controls
            controls = (
                f"{self.theme['muted']}[{self.theme['accent']}j/k{self.theme['muted']}] Line ↓/↑  "
                f"[{self.theme['accent']}Ctrl+U/D{self.theme['muted']}] Page ↑/↓  "
                f"[{self.theme['accent']}Ctrl+G{self.theme['muted']}] Top  "
                f"[{self.theme['accent']}Ctrl+E{self.theme['muted']}] End  "
                f"[{self.theme['accent']}Esc{self.theme['muted']}] Exit{self.theme['reset']}"
            )
            clean_controls = "[j/k] Line ↓/↑  [Ctrl+U/D] Page ↑/↓  [Ctrl+G] Top  [Ctrl+E] End  [Esc] Exit"
        else:
            # Normal controls
            controls = (
                f"{self.theme['muted']}[{self.theme['accent']}Tab{self.theme['muted']}] Menu  "
                f"[{self.theme['accent']}Ctrl+B{self.theme['muted']}] Scroll  "
                f"[{self.theme['accent']}q{self.theme['muted']}] Quit  "
                f"[{self.theme['accent']}n{self.theme['muted']}] New  "
                f"[{self.theme['accent']}h{self.theme['muted']}] History  "
                f"[{self.theme['accent']}s{self.theme['muted']}] Settings{self.theme['reset']}"
            )
            clean_controls = "[Tab] Menu  [Ctrl+B] Scroll  [q] Quit  [n] New  [h] History  [s] Settings"
        
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
        
        # Calculate available width for content
        content_width = self.width - 12  # Account for borders, timestamp, and role
        
        # Apply code highlighting if enabled
        highlighted_content = self._detect_and_highlight_code(message.content)
        
        # Add streaming cursor if actively streaming
        if streaming and message.content:
            highlighted_content += f"{self.theme['accent']}▎{self.theme['reset']}"
        
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
                
                formatted_line = (chars['vertical'] + prefix + 
                                colored_line.ljust(content_width + len(colored_line) - len(line)) + 
                                chars['vertical'])
            else:
                # Continuation lines with proper indentation and color
                prefix = "        "  # Align with content
                role_color = self.theme['primary'] if message.role == "user" else self.theme['text']
                colored_line = f"{role_color}{line}{self.theme['reset']}"
                formatted_line = (chars['vertical'] + prefix + 
                                colored_line.ljust(content_width + len(colored_line) - len(line)) + 
                                chars['vertical'])
            formatted_lines.append(formatted_line)
        
        # Add empty line for spacing
        empty_line = chars['vertical'] + " " * (self.width - 2) + chars['vertical']
        formatted_lines.append(empty_line)
        
        return formatted_lines
    
    def draw_messages(self) -> List[str]:
        """Draw all messages in the conversation with enhanced styling"""
        lines = []
        chars = self.get_border_chars()
        
        if not self.messages:
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
                f"{self.theme['muted']}• Use {self.theme['accent']}Up/Down arrows{self.theme['muted']} to navigate history{self.theme['reset']}"
            ]
            
            for tip in tips:
                clean_tip = tip.replace(self.theme['muted'], '').replace(self.theme['accent'], '').replace(self.theme['reset'], '')
                color_padding = len(tip) - len(clean_tip)
                tip_line = chars['vertical'] + f" {tip}".ljust(self.width - 2 + color_padding) + chars['vertical']
                lines.append(tip_line)
            
            lines.extend([empty_line] * 2)
        else:
            # Calculate visible message range based on scroll offset
            total_messages = len(self.messages)
            
            # First, let's count total lines needed for all messages
            message_line_counts = []
            for msg in self.messages:
                # Estimate lines per message (formatted message returns list of lines)
                formatted_lines = self.format_message(msg, streaming=False)
                message_line_counts.append(len(formatted_lines))
            
            # Simplified calculation - show a fixed window of messages
            if self.scroll_offset == 0:
                # Normal view - show most recent messages
                end_idx = total_messages
                # Show as many messages as fit, but at least 3-5 messages
                messages_to_show = min(self.messages_per_page, 5)
                start_idx = max(0, total_messages - messages_to_show)
            else:
                # Scrolled view - offset is number of messages from bottom
                end_idx = total_messages - self.scroll_offset
                # Ensure we show a reasonable window
                messages_to_show = min(self.messages_per_page, 5)
                start_idx = max(0, end_idx - messages_to_show)
                end_idx = max(start_idx + 1, end_idx)  # Ensure at least one message
            
            # Display messages with enhanced formatting
            visible_messages = self.messages[start_idx:end_idx]
            for i, message in enumerate(visible_messages):
                is_streaming = (self.scroll_offset == 0 and 
                              i == len(visible_messages) - 1 and
                              message == self.messages[-1] and 
                              message.role == "assistant" and 
                              self.generating)
                lines.extend(self.format_message(message, streaming=is_streaming))
            
            # Add scroll indicators if needed
            if self.scroll_mode or self.scroll_offset > 0:
                chars = self.get_border_chars()
                empty_line = chars['vertical'] + " " * (self.width - 2) + chars['vertical']
                
                
                # Top indicator
                if start_idx > 0:
                    more_above = f"{self.theme['accent']}↑ {start_idx} more messages above ↑{self.theme['reset']}"
                    clean_above = f"↑ {start_idx} more messages above ↑"
                    color_padding = len(more_above) - len(clean_above)
                    above_line = chars['vertical'] + more_above.center(self.width - 2 + color_padding) + chars['vertical']
                    lines.insert(0, above_line)
                    lines.insert(1, empty_line)
                
                # Bottom indicator  
                if end_idx < total_messages:
                    more_below = f"{self.theme['accent']}↓ {total_messages - end_idx} more messages below ↓{self.theme['reset']}"
                    clean_below = f"↓ {total_messages - end_idx} more messages below ↓"
                    color_padding = len(more_below) - len(clean_below)
                    below_line = chars['vertical'] + more_below.center(self.width - 2 + color_padding) + chars['vertical']
                    lines.append(empty_line)
                    lines.append(below_line)
        
        return lines
    
    def draw_input_area(self, current_input: str = "", prompt: str = "Type your message") -> List[str]:
        """Draw the enhanced input area with multi-line support and dynamic indicators"""
        chars = self.get_border_chars()
        lines = []
        
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
    
    def draw_screen(self, current_input: str = "", input_prompt: str = "Type your message", show_welcome: bool = False):
        """Draw the complete enhanced screen with welcome message and better layout"""
        self.clear_screen()
        
        # Show welcome message on first run
        if show_welcome:
            welcome_lines = self.draw_ascii_welcome()
            for line in welcome_lines:
                print(line)
            print("\n" * 2)
            time.sleep(2.5)  # Pause to let user see welcome screen properly
        
        # Calculate layout
        header_lines = self.draw_header()
        footer_lines = self.draw_footer()
        input_lines = self.draw_input_area(current_input, input_prompt)
        
        # Calculate available space for messages
        used_lines = len(header_lines) + len(footer_lines) + len(input_lines)
        available_lines = self.height - used_lines - 2
        
        # Update messages_per_page based on available space
        # Account for scroll indicators (2 lines each when active)
        indicator_lines = 4 if (self.scroll_mode or self.scroll_offset > 0) else 0
        self.messages_per_page = max(1, (available_lines - indicator_lines) // 3)  # Assuming ~3 lines per message
        
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
        
        # Draw input area
        for line in input_lines:
            print(line)
        
        # Draw footer
        for line in footer_lines:
            print(line)
        
        # Position cursor for better user experience
        cursor_offset = len(current_input) + 4
        if self.multi_line_input:
            cursor_offset = len(current_input) + 4  # Adjust for multi-line
        
        print("\033[A" * (len(footer_lines) + len(input_lines) - 1), end="")
        print(f"\033[{cursor_offset}C", end="")
        sys.stdout.flush()
    
    def get_input(self, prompt: str = "Type your message") -> str:
        """Enhanced input with multi-line support, history navigation, and improved UX"""
        current_input = ""
        show_welcome = not hasattr(self, '_welcome_shown')
        
        while True:
            # Only redraw screen if not currently generating to avoid interference
            if not self.generating:
                self.draw_screen(current_input, prompt, show_welcome)
                show_welcome = False  # Only show once
            
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
                        except:
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
                        # If empty, switch to menu mode
                        self.input_mode = "menu"
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
                # Force immediate redraw
                self.draw_screen(current_input, prompt)
                continue
            
            elif char == '\x15':  # Ctrl+U - Page up
                # First ensure we have enough messages to scroll
                if len(self.messages) > 1:  # Need at least 2 messages to scroll
                    # Page up means show older messages (increase offset)
                    page_size = max(1, self.messages_per_page // 2)  # Half page for smoother scrolling
                    max_offset = len(self.messages) - 1
                    self.scroll_offset = min(self.scroll_offset + page_size, max_offset)
                    self.scroll_mode = True
                    # Force immediate redraw
                    self.draw_screen(current_input, prompt)
                continue
            
            elif char == '\x04':  # Ctrl+D - Page down (when not in multi-line mode)
                if not self.multi_line_input and self.scroll_offset > 0:
                    self.scroll_offset = max(0, self.scroll_offset - self.messages_per_page)
                    if self.scroll_offset == 0:
                        self.scroll_mode = False
                    # Force immediate redraw
                    self.draw_screen(current_input, prompt)
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
                    # Force immediate redraw
                    self.draw_screen(current_input, prompt)
                continue
            
            elif char == '\x05':  # Ctrl+E - Go to end (bottom)
                self.scroll_offset = 0
                self.scroll_mode = False
                # Force immediate redraw
                self.draw_screen(current_input, prompt)
                continue
            
            # Mode-specific handling
            if self.input_mode == "text":
                # Check if we're in scroll mode for vim-style navigation
                if self.scroll_mode:
                    if char.lower() == 'j':  # Down one line
                        if self.scroll_offset > 0:
                            self.scroll_offset = max(0, self.scroll_offset - 1)
                            self.draw_screen(current_input, prompt)
                        continue
                    elif char.lower() == 'k':  # Up one line
                        if len(self.messages) > 1:
                            max_offset = len(self.messages) - 1
                            self.scroll_offset = min(self.scroll_offset + 1, max_offset)
                            self.draw_screen(current_input, prompt)
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
            from .config import OPENAI_API_KEY, ANTHROPIC_API_KEY
            
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
    
    def _update_streaming_display(self, content: str):
        """Update display with real-time streaming content and context-aware status"""
        if not self.generating:
            return
            
        # Rate limit updates to avoid flickering, but allow faster updates for better streaming effect
        current_time = time.time()
        if hasattr(self, '_last_display_update'):
            if current_time - self._last_display_update < 0.02:  # Max 50 updates per second for very smooth streaming
                return
        self._last_display_update = current_time
        
        # Clear screen and redraw with current content
        self.clear_screen()
        
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
        
        # Draw the full screen with current state
        self._draw_streaming_screen(streaming_status)
        
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
            except:
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
    
    async def show_settings(self):
        """Show enhanced settings menu with style selection and persistence"""
        while True:
            self.clear_screen()
            print("=" * self.width)
            print("SETTINGS".center(self.width))
            print("=" * self.width)
            
            print(f"Current Model: {CONFIG['available_models'][self.selected_model]['display_name']}")
            print(f"Current Style: {CONFIG['user_styles'][self.selected_style]['name']}")
            print()
            print("What would you like to change?")
            print("1. Model")
            print("2. Response Style")
            print("3. Advanced Settings")
            print("4. Save Settings")
            print("0. Back to Chat")
            
            try:
                choice = input("\n> ").strip()
                
                if choice == "1":
                    # Model selection
                    self._select_model()
                elif choice == "2":
                    # Style selection
                    self._select_style()
                elif choice == "3":
                    # Advanced settings
                    await self._show_advanced_settings()
                elif choice == "4":
                    # Save settings
                    self._save_settings()
                elif choice == "0" or choice == "":
                    break
                    
            except (ValueError, KeyboardInterrupt):
                break
    
    def _select_model(self):
        """Model selection submenu"""
        self.clear_screen()
        print("=" * self.width)
        print("MODEL SELECTION".center(self.width))
        print("=" * self.width)
        
        models = list(CONFIG["available_models"].keys())
        for i, model in enumerate(models):
            marker = "►" if model == self.selected_model else " "
            display_name = CONFIG["available_models"][model]["display_name"]
            provider = CONFIG["available_models"][model]["provider"]
            print(f"{marker} {i+1:2d}. {display_name} ({provider})")
        
        print("\nEnter model number to select (or press Enter to cancel):")
        
        try:
            choice = input("> ").strip()
            if choice and choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(models):
                    old_model = self.selected_model
                    self.selected_model = models[idx]
                    print(f"Model changed from {old_model} to {self.selected_model}")
                    input("Press Enter to continue...")
        except (ValueError, KeyboardInterrupt):
            pass
    
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
            print(f"  Model Preloading: {'On' if CONFIG.get('preload_models', True) else 'Off'}")
            print(f"  Ollama URL: {CONFIG.get('ollama_base_url', 'http://localhost:11434')}")
            print(f"  Inactive Timeout: {CONFIG.get('ollama_inactive_timeout', 30)} minutes")
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
        print(f"  Ollama Base URL: {CONFIG.get('ollama_base_url', 'http://localhost:11434')}")
        print()
        
        print("Options:")
        print("1. Set OpenAI API Key")
        print("2. Set Anthropic API Key")
        print("3. Set Ollama Base URL")
        print("4. Clear API Keys")
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
            url = input(f"Enter Ollama Base URL (current: {CONFIG.get('ollama_base_url', 'http://localhost:11434')}): ").strip()
            if url:
                CONFIG["ollama_base_url"] = url
                print("Ollama Base URL updated!")
                
        elif choice == "4":
            confirm = input("Clear all API keys? (y/N): ").strip().lower()
            if confirm == 'y':
                CONFIG.pop("openai_api_key", None)
                CONFIG.pop("anthropic_api_key", None)
                print("API keys cleared!")
        
        if choice in ["1", "2", "3", "4"]:
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
        print(f"  Model Preloading: {'On' if CONFIG.get('preload_models', True) else 'Off'}")
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
            current = CONFIG.get('preload_models', True)
            CONFIG['preload_models'] = not current
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
            input("\nPress Enter to continue...")
    
    async def _configure_ollama_settings(self):
        """Configure Ollama-specific settings"""
        self.clear_screen()
        print("=" * self.width)
        print("OLLAMA SETTINGS".center(self.width))
        print("=" * self.width)
        
        print("Current Ollama Settings:")
        print(f"  Base URL: {CONFIG.get('ollama_base_url', 'http://localhost:11434')}")
        print(f"  Inactive Timeout: {CONFIG.get('ollama_inactive_timeout', 30)} minutes")
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
                timeout = int(input(f"Enter inactive timeout in minutes (current: {CONFIG.get('ollama_inactive_timeout', 30)}): "))
                if timeout > 0:
                    CONFIG['ollama_inactive_timeout'] = timeout
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
        
        if choice in ["1", "2", "3", "4", "5"]:
            input("\nPress Enter to continue...")
    
    async def show_model_browser(self):
        """Show Ollama model browser for managing local and available models"""
        while True:
            self.clear_screen()
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
                elif choice == "3":
                    await self._search_models()
                elif choice == "4":
                    await self._switch_model()
                elif choice == "0" or choice == "":
                    break
                    
            except (ValueError, KeyboardInterrupt):
                break
    
    async def _list_local_models(self):
        """List locally installed Ollama models"""
        self.clear_screen()
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
        self.clear_screen()
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
                        
                        print(f"{model_index:2d}. {name} ({size})")
                        if description:
                            print(f"    {description[:60]}...")
                        
                        model_map[str(model_index)] = model
                        model_index += 1
                    
                    if len(models) > 5:
                        print(f"    ... and {len(models) - 5} more {family} models")
                
                print(f"\nShowing top models by family (total: {len(available_models)})")
                print("\nOptions:")
                print("Enter model number to download")
                print("s) Search for specific models")
                print("Enter) Back to model browser")
                
                choice = input("\n> ").strip()
                
                if choice in model_map:
                    await self._download_model(model_map[choice])
                elif choice.lower() == "s":
                    await self._search_models()
                    
        except Exception as e:
            print(f"Error fetching available models: {str(e)}")
            
        input("\nPress Enter to continue...")
    
    async def _search_models(self):
        """Search for models by name or description"""
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
                if (query_lower in model.get("name", "").lower() or
                    query_lower in model.get("description", "").lower() or
                    query_lower in model.get("model_family", "").lower()):
                    matching_models.append(model)
            
            if not matching_models:
                print(f"No models found matching '{query}'")
            else:
                print(f"\nFound {len(matching_models)} models matching '{query}':\n")
                
                model_map = {}
                for i, model in enumerate(matching_models[:20]):  # Show first 20 matches
                    name = model.get("name", "unknown")
                    description = model.get("description", "")
                    size = model.get("parameter_size", "Unknown size")
                    family = model.get("model_family", "Unknown")
                    
                    print(f"{i+1:2d}. {name} ({family}, {size})")
                    if description:
                        print(f"    {description[:70]}...")
                    print()
                    
                    model_map[str(i+1)] = model
                
                if len(matching_models) > 20:
                    print(f"... and {len(matching_models) - 20} more matches")
                
                print("\nEnter model number to download (or press Enter to continue):")
                choice = input("> ").strip()
                
                if choice in model_map:
                    await self._download_model(model_map[choice])
                    
        except Exception as e:
            print(f"Error searching models: {str(e)}")
            
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
                await self._show_model_details(model_id)
    
    async def _show_model_details(self, model_id):
        """Show detailed information about a specific model"""
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
                print(f"Name: {model_id}")
                
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
                print(f"\n✓ Switched from {old_model} to {self.selected_model}")
    
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